"""Exercise web recovery and CLI output with local files and mocked Google APIs."""

import json
import re
from types import SimpleNamespace

import httplib2
import pytest
from googleapiclient.errors import HttpError

import generator
from config import CHECKPOINT_FILENAME, PDF_MIME_TYPE, SLIDES_MIME_TYPE


FOLDER_MIME_TYPE = 'application/vnd.google-apps.folder'
PDF_BYTES = b'%PDF-1.4\nmock certificate\n'
RECORDS = [{'Name': 'Ada'}, {'Name': 'Tariq'}]


def http_error(status, reason=None):
    payload = {'error': {'message': reason, 'errors': [{'reason': reason}]}} if reason else {}
    return HttpError(
        httplib2.Response({'status': str(status), 'reason': str(status)}),
        json.dumps(payload).encode(),
    )


class Drive:
    """In-memory Drive files service with real predefined-ID conflict behavior."""

    def __init__(self):
        self.entries = {
            'template': {'name': 'Template', 'parents': ['template-folder'], 'version': '1'},
            'alternate': {'name': 'Other template', 'parents': [], 'version': '1'},
        }
        self.template_reads = 0
        self.counter = 0
        self.copies = []
        self.deleted = []
        self.pdf_creates = []
        self.imported_templates = []
        self.bad_export = False
        self.fail_upload = False
        self.interrupt_upload = False
        self.lose_upload_response = False

    @staticmethod
    def request(callback):
        return SimpleNamespace(execute=callback)

    def files(self):
        return self

    def generateIds(self, count, **kwargs):
        def execute():
            start = self.counter
            self.counter += count
            return {'ids': [f'file-{i}' for i in range(start, self.counter)]}

        return self.request(execute)

    def get(self, fileId, **kwargs):
        def execute():
            if fileId in ('template', 'alternate') and kwargs.get('fields') != 'version':
                self.template_reads += 1
            if fileId not in self.entries:
                raise http_error(404)
            metadata = dict(self.entries[fileId], id=fileId)
            metadata.pop('data', None)
            return metadata

        return self.request(execute)

    def get_media(self, fileId, **kwargs):
        def execute():
            if fileId not in self.entries:
                raise http_error(404)
            return self.entries[fileId]['data']

        return self.request(execute)

    def list(self, q, **kwargs):
        def execute():
            batch = re.search(r"key='certificateBatch' and value='([^']+)'", q)
            name = re.search(r"name='((?:\\.|[^'])*)'", q)
            parent = re.search(r"'([^']+)' in parents", q)
            results = []
            for file_id, file in self.entries.items():
                if file.get('trashed'):
                    continue
                if batch:
                    if file.get('appProperties', {}).get('certificateBatch') != batch[1]:
                        continue
                    if 'createdTime' in q:
                        if not file.get('abandoned'):
                            continue
                    elif SLIDES_MIME_TYPE in q:
                        if file.get('mimeType') != SLIDES_MIME_TYPE:
                            continue
                    elif file.get('mimeType') not in (PDF_MIME_TYPE, 'text/plain'):
                        continue
                elif file.get('mimeType') != FOLDER_MIME_TYPE:
                    continue
                if name and file['name'] != re.sub(r"\\(.)", r"\1", name[1]):
                    continue
                if parent and parent[1] not in file.get('parents', ['root']):
                    continue
                results.append(dict(file, id=file_id))
            return {'files': results}

        return self.request(execute)

    def create(self, body, media_body=None, **kwargs):
        def execute():
            file_id = body.get('id')
            if not file_id:
                file_id = self.generateIds(count=1).execute()['ids'][0]
            if file_id in self.entries:
                raise http_error(409)
            metadata = dict(body)
            if metadata.get('mimeType') == FOLDER_MIME_TYPE:
                metadata['capabilities'] = {'canAddChildren': True}
            if media_body is not None:
                mime = media_body.mimetype()
                metadata.setdefault('mimeType', mime)
                metadata['data'] = media_body.getbytes(0, media_body.size())
                if metadata['mimeType'] == SLIDES_MIME_TYPE:
                    self.imported_templates.append((file_id, mime, metadata['data']))
                    metadata['version'] = '1'
                if mime == PDF_MIME_TYPE:
                    if self.fail_upload:
                        raise IOError("upload unavailable")
                    if self.interrupt_upload:
                        self.interrupt_upload = False
                        raise KeyboardInterrupt()
                    self.pdf_creates.append(file_id)
                    if self.lose_upload_response:
                        self.lose_upload_response = False
                        self.entries[file_id] = metadata
                        raise TimeoutError("response lost after commit")
            self.entries[file_id] = metadata
            return {'id': file_id}

        return self.request(execute)

    def update(self, fileId, body, **kwargs):
        def execute():
            self.entries[fileId].update(body)
            return {'id': fileId}

        return self.request(execute)

    def copy(self, fileId, body, **kwargs):
        def execute():
            new_id = self.generateIds(count=1).execute()['ids'][0]
            self.entries[new_id] = dict(body, mimeType=SLIDES_MIME_TYPE)
            self.copies.append(new_id)
            return {'id': new_id}

        return self.request(execute)

    def delete(self, fileId):
        def execute():
            if fileId not in self.entries:
                raise http_error(404)
            del self.entries[fileId]
            self.deleted.append(fileId)

        return self.request(execute)

    def export_media(self, fileId, mimeType):
        def execute():
            if self.bad_export:
                raise IOError("export unavailable")
            assert fileId in self.entries
            return PDF_BYTES

        return self.request(execute)


@pytest.fixture
def drive(monkeypatch):
    service = Drive()
    slides = object()
    monkeypatch.setattr(
        generator, 'build',
        lambda name, version, credentials: service if name == 'drive' else slides,
    )
    monkeypatch.setattr(generator, 'authenticate_google', lambda _: (slides, service))
    monkeypatch.setattr(generator, 'detect_placeholders_in_slide', lambda *args: {'name'})
    monkeypatch.setattr(generator, 'replace_text_in_slide', lambda *args, **kwargs: True)
    return service


def web_generate(batch, records=RECORDS, **kwargs):
    return generator.generate_certificates_oauth2(
        None, 'template', "Director's Certificates", object(),
        records=records, input_rows=5, batch_id=batch, **kwargs,
    )


def test_resume_after_interruption_preserves_existing_pdfs_and_does_not_duplicate(drive, monkeypatch):
    batch = generator.reserve_web_batch(object())

    def replace_and_interrupt(_, slide, replacements, **kwargs):
        if replacements == {'name': 'Tariq'}:
            drive.interrupt_upload = True
        return True

    monkeypatch.setattr(generator, 'replace_text_in_slide', replace_and_interrupt)
    with pytest.raises(KeyboardInterrupt):
        web_generate(batch)

    first_pdf = drive.pdf_creates[0]
    interrupted = generator.recover_web_batch(object(), batch)
    assert interrupted['input_rows'] == 5
    assert interrupted['success'] == interrupted['attempted_rows'] == 1
    assert interrupted['pending_rows'] == 1
    assert set(drive.copies[1:]) == set(drive.deleted)

    monkeypatch.setattr(generator, 'replace_text_in_slide', lambda *args, **kwargs: True)
    completed = web_generate(batch)
    assert completed['success'] == 2
    assert completed['failed'] == completed['pending_rows'] == 0
    assert drive.entries[first_pdf]['data'] == PDF_BYTES
    assert web_generate(batch) == completed
    assert generator.recover_web_batch(object(), batch) == completed
    assert len(drive.pdf_creates) == 2


def test_grouped_drive_batch_reuses_subfolders_after_interruption_and_in_a_new_batch(drive, monkeypatch):
    records = [
        {'Name': 'Ada', 'Team': ' Orbit '},
        {'Name': 'Tariq', 'Team': 'Orbit'},
        {'Name': 'Grace', 'Team': 'Nova'},
        {'Name': 'Lina', 'Team': '   '},
    ]
    drive.entries['unrelated'] = {'name': 'Orbit', 'mimeType': FOLDER_MIME_TYPE, 'parents': ['other']}
    batch = generator.reserve_web_batch(object())

    def interrupt_second_row(_, slide, replacements, **kwargs):
        drive.interrupt_upload = replacements == {'name': 'Tariq'}
        return True

    with monkeypatch.context() as patch:
        patch.setattr(generator, 'replace_text_in_slide', interrupt_second_row)
        with pytest.raises(KeyboardInterrupt):
            web_generate(batch, records, group_by_column='Team')

    with pytest.raises(ValueError, match='differ from the original'):
        web_generate(batch, records)
    assert web_generate(batch, records, group_by_column='Team')['success'] == 4
    assert web_generate(generator.reserve_web_batch(object()), records, group_by_column='Team')['success'] == 4

    folders = [(file_id, file) for file_id, file in drive.entries.items()
               if file.get('mimeType') == FOLDER_MIME_TYPE and file_id != 'unrelated']
    assert sorted(file['name'] for _, file in folders) == ["Director's Certificates", 'Nova', 'Orbit']
    by_name = {file['name']: file_id for file_id, file in folders}
    root_id = by_name["Director's Certificates"]
    assert all(file['parents'] == [root_id] for file_id, file in folders if file_id != root_id)
    destinations = {'Ada.pdf': 'Orbit', 'Tariq.pdf': 'Orbit', 'Grace.pdf': 'Nova',
                    'Lina.pdf': "Director's Certificates"}
    assert len(drive.pdf_creates) == 8
    for file_id in drive.pdf_creates:
        pdf = drive.entries[file_id]
        assert pdf['parents'] == [by_name[destinations[pdf['name']]]]


@pytest.mark.parametrize('resumable', [False, True])
def test_new_batches_skip_read_only_and_nested_folders_with_the_same_name(drive, resumable):
    name = "Director's Certificates"
    drive.entries['read-only'] = {
        'name': name, 'mimeType': FOLDER_MIME_TYPE, 'parents': ['root'],
        'capabilities': {'canAddChildren': False},
    }
    drive.entries['nested'] = {
        'name': name, 'mimeType': FOLDER_MIME_TYPE, 'parents': ['another-folder'],
        'capabilities': {'canAddChildren': True},
    }
    first = web_generate(generator.reserve_web_batch(object()) if resumable else None)
    assert first['created_pdfs'] == 2
    folder_id = first['output_folder_id']
    assert folder_id not in ('read-only', 'nested')
    assert drive.entries[folder_id]['parents'] == ['root']

    second = web_generate(generator.reserve_web_batch(object()) if resumable else None)
    assert second['created_pdfs'] == 2
    assert second['output_folder_id'] == folder_id
    assert all(drive.entries[pdf]['parents'] == [folder_id] for pdf in drive.pdf_creates)


def test_grouped_batch_replaces_read_only_group_destination(drive):
    initial = web_generate(generator.reserve_web_batch(object()))
    folder_id = initial['output_folder_id']
    drive.entries['read-only-group'] = {
        'name': 'Orbit', 'mimeType': FOLDER_MIME_TYPE, 'parents': [folder_id],
        'capabilities': {'canAddChildren': False},
    }
    result = web_generate(
        generator.reserve_web_batch(object()), [{'Name': 'Grace', 'Team': 'Orbit'}],
        group_by_column='Team',
    )
    assert result['created_pdfs'] == 1
    group_id, = drive.entries[drive.pdf_creates[-1]]['parents']
    assert group_id != 'read-only-group'
    assert drive.entries[group_id]['name'] == 'Orbit'
    assert drive.entries[group_id]['parents'] == [folder_id]


def test_existing_batch_stops_on_unwritable_pinned_folder(drive):
    folder_id = 'legacy-destination'
    drive.entries[folder_id] = {
        'name': "Director's Certificates", 'mimeType': FOLDER_MIME_TYPE, 'parents': ['root'],
        'capabilities': {'canAddChildren': True},
    }
    batch_id = generator.reserve_web_batch(object())
    web_generate(batch_id, work_seconds=0)
    batch = generator.DriveBatch(drive, batch_id)
    batch.load()
    batch.record_failure(0, 'Row 1: old PDF upload error')
    drive.entries[folder_id]['capabilities']['canAddChildren'] = False

    result = web_generate(batch_id, retry_failed=True)
    assert result['interrupted'] is True
    assert 'Start a new batch' in result['destination_error']
    assert (result['created_pdfs'], result['failed'], result['pending_rows']) == (0, 1, 1)
    assert result['output_folder_id'] == folder_id
    assert drive.copies == [batch.manifest['snapshot_id']]
    assert not drive.pdf_creates


def test_parent_permission_rejection_during_upload_pauses_and_resumes(drive, monkeypatch):
    from io import BytesIO
    from web import app as web

    template_id = 'existing_template_for_fixtures'
    drive.entries[template_id] = drive.entries['template']
    monkeypatch.setattr(web.Credentials, 'from_authorized_user_info', lambda *a, **k: SimpleNamespace(expired=False))
    client = web.app.test_client()
    with client.session_transaction() as session:
        session['credentials'] = {'mock': 'credentials'}
        session['user_email'] = 'fixture@example.test'
    token = client.get('/api/generation-batches/new').get_json()['batch_id']

    def submit_batch(retry_failed='false'):
        return client.post('/api/generate', data={
            'csv_file': (BytesIO(b'Name\nAda\nTariq\nGrace\n'), 'input.csv'),
            'template_id': template_id, 'batch_id': token, 'retry_failed': retry_failed,
        })

    original_create = drive.create
    attempted_pdfs = []

    def deny_second_upload(body, media_body=None, **kwargs):
        if media_body and media_body.mimetype() == PDF_MIME_TYPE:
            attempted_pdfs.append(body['id'])
            if len(attempted_pdfs) == 2:
                def forbidden():
                    raise http_error(403, 'insufficientParentPermissions')
                return drive.request(forbidden)
        return original_create(body, media_body=media_body, **kwargs)

    monkeypatch.setattr(drive, 'create', deny_second_upload)
    response = submit_batch()
    assert response.status_code == 202
    body = response.get_json()
    assert body['status'] == 'pending'
    assert 'Restore write access and use Resume Batch' in body['message']
    result = body['summary']
    assert result['interrupted'] is True
    assert (result['created_pdfs'], result['failed'], result['pending_rows']) == (1, 0, 2)
    assert len(attempted_pdfs) == 2
    assert set(drive.copies[1:]) == set(drive.deleted)

    response = submit_batch(retry_failed='true')
    assert response.status_code == 200
    finished = response.get_json()['summary']
    assert finished['created_pdfs'] == 3
    assert finished['output_folder_id'] == result['output_folder_id']
    assert attempted_pdfs[1] == attempted_pdfs[2]
    assert len(drive.pdf_creates) == len(set(drive.pdf_creates)) == 3


@pytest.mark.parametrize('extension, mime_type, filename_field, filenames', [
    ('pptx', 'application/vnd.openxmlformats-officedocument.presentationml.presentation', '', ['Ada.pdf', 'Tariq.pdf']),
    ('PPT', 'application/vnd.ms-powerpoint', 'Code', ['A1.pdf', 'T2.pdf']),
])
def test_powerpoint_batch_imports_once_and_resumes_without_the_upload(
    drive, monkeypatch, extension, mime_type, filename_field, filenames,
):
    from io import BytesIO
    from web import app as web

    monkeypatch.setattr(web.Credentials, 'from_authorized_user_info', lambda *a, **k: SimpleNamespace(expired=False))
    client = web.app.test_client()
    with client.session_transaction() as session:
        session['credentials'] = {'mock': 'credentials'}
    token = client.get('/api/generation-batches/new').get_json()['batch_id']
    original_generate = web.generate_certificates_oauth2
    substitutions = []

    def replace(_slides, _slide_id, replacements, **_kwargs):
        substitutions.append(replacements)
        return True

    monkeypatch.setattr(generator, 'replace_text_in_slide', replace)

    def submit(template_data=None):
        data = {
            'batch_id': token, 'template_source': 'powerpoint', 'filename_field': filename_field,
            'csv_file': (BytesIO(b'Participant Name,Code\nAda,A1\nTariq,T2\n'), 'input.csv'),
        }
        if template_data is not None:
            data['template_file'] = (BytesIO(template_data), f'Certificate.{extension}')
        return client.post('/api/generate', data=data)

    with monkeypatch.context() as patch:
        patch.setattr(web, 'generate_certificates_oauth2', lambda **kwargs: original_generate(work_seconds=0, **kwargs))
        first = submit(b'PowerPoint content used by the Drive stub')
    assert first.status_code == 202
    assert first.get_json()['summary']['pending_rows'] == 2
    (snapshot_id, source_mime, data), = drive.imported_templates
    assert source_mime == mime_type
    assert data == b'PowerPoint content used by the Drive stub'
    assert drive.entries[snapshot_id]['mimeType'] == SLIDES_MIME_TYPE
    assert not drive.copies

    changed = submit(b'A different PowerPoint template')
    assert changed.status_code == 400
    assert 'differ from the original batch' in changed.get_json()['error']

    finished = submit()
    assert finished.status_code == 200
    assert finished.get_json()['summary']['created_pdfs'] == 2
    assert len(drive.imported_templates) == 1
    assert snapshot_id in drive.deleted
    assert [drive.entries[pdf]['name'] for pdf in drive.pdf_creates] == filenames
    assert substitutions == [{'name': 'Ada'}, {'name': 'Tariq'}]


def test_exact_name_column_takes_priority_over_participant_name(drive, monkeypatch):
    substitutions = []

    def replace(_slides, _slide_id, replacements, **_kwargs):
        substitutions.append(replacements)
        return True

    monkeypatch.setattr(generator, 'replace_text_in_slide', replace)
    result = web_generate(None, [{'Name': 'Ada', 'Participant Name': 'Different Name'}])
    assert result['created_pdfs'] == 1
    assert drive.entries[drive.pdf_creates[0]]['name'] == 'Ada.pdf'
    assert substitutions == [{'name': 'Ada'}]


@pytest.mark.parametrize('part, converted_fields, message', [
    ('slides/slide1.xml', {'code'}, r'did not preserve \{\{name\}\}'),
    ('slideMasters/slideMaster1.xml', set(), 'Slide Master or a layout'),
])
def test_powerpoint_reports_missing_placeholders_and_cleans_up(drive, monkeypatch, part, converted_fields, message):
    from io import BytesIO
    from zipfile import ZipFile

    source = BytesIO()
    with ZipFile(source, 'w') as archive:
        archive.writestr(f'ppt/{part}', (
            f'<a:p xmlns:a="{generator.DRAWINGML[1:-1]}">'
            '<a:r><a:t>{{Na</a:t></a:r><a:r><a:t>me}}</a:t></a:r></a:p>'
        ))
    source.seek(0)
    monkeypatch.setattr(generator, 'detect_placeholders_in_slide', lambda *args: converted_fields)
    batch_id = generator.reserve_web_batch(object())
    template = generator.PowerPointTemplate.from_upload('Certificate.pptx', source)
    with pytest.raises(ValueError, match=message):
        generator.generate_certificates_oauth2(
            None, None, 'Certificates', object(), records=RECORDS, batch_id=batch_id, powerpoint_template=template,
        )
    (snapshot_id, _, _), = drive.imported_templates
    assert snapshot_id in drive.deleted
    assert batch_id not in drive.entries
    assert not drive.pdf_creates


def test_cli_grouped_pdfs_keep_separate_names_and_resume(drive, tmp_path):
    data = tmp_path / 'recipients.csv'
    data.write_text(
        'Name,Team\nAda,Orbit\nAda,Orbit\nAda,Nova\nAda,\nAda,A/B\nAda,A_B\n', encoding='utf-8',
    )
    output = tmp_path / 'output'
    args = (str(data), 'template', str(output))
    assert generator.generate_certificates(*args, group_by_column='Team')['success'] == 6
    files = {path.relative_to(output).as_posix() for path in output.rglob('*.pdf')}
    assert {'Ada.pdf', 'Orbit/Ada.pdf', 'Orbit/Ada_2.pdf', 'Nova/Ada.pdf', 'A_B/Ada.pdf'} < files
    assert len(files) == 6
    assert generator.generate_certificates(*args, group_by_column='Team')['skipped'] == 6
    assert generator.generate_certificates(*args)['success'] == 6


def test_ambiguous_upload_response_is_reconciled(drive):
    batch = generator.reserve_web_batch(object())
    drive.lose_upload_response = True
    result = web_generate(batch, RECORDS[:1])
    assert (result['success'], result['failed']) == (1, 0)
    assert web_generate(batch, RECORDS[:1]) == result
    assert len(drive.pdf_creates) == 1


def test_unwritten_failure_receipt_leaves_the_row_pending(drive, monkeypatch):
    create = drive.create

    def create_without_receipt(body, **kwargs):
        if body.get('mimeType') == 'text/plain':
            def unavailable():
                raise http_error(503)
            return drive.request(unavailable)
        return create(body, **kwargs)

    monkeypatch.setattr(drive, 'create', create_without_receipt)
    drive.fail_upload = True
    batch = generator.reserve_web_batch(object())
    result = web_generate(batch, RECORDS[:1])
    assert (result['created_pdfs'], result['failed'], result['pending_rows']) == (0, 0, 1)
    assert 'Generation paused' in result['errors'][0]
    assert generator.recover_web_batch(object(), batch)['pending_rows'] == 1

    drive.fail_upload = False
    assert web_generate(batch, RECORDS[:1], retry_failed=True)['created_pdfs'] == 1


@pytest.mark.parametrize('step', ['replace', 'export', 'upload'])
def test_temporary_slide_cleanup_and_durable_retry_after_failed_step(drive, monkeypatch, step):
    batch = generator.reserve_web_batch(object())
    drive.bad_export = step == 'export'
    drive.fail_upload = step == 'upload'
    if step == 'replace':
        def reject(*args, **kwargs):
            raise ValueError("unresolved {{name}}")
        monkeypatch.setattr(generator, 'replace_text_in_slide', reject)

    result = web_generate(batch, RECORDS[:1])
    assert (result['success'], result['failed'], result['pending_rows']) == (0, 1, 0)
    assert step in result['errors'][0].lower() or 'unresolved' in result['errors'][0]
    assert drive.copies[1:] == drive.deleted
    assert generator.recover_web_batch(object(), batch) == result
    assert web_generate(batch, RECORDS[:1]) == result
    assert len(drive.copies) == 2  # A saved snapshot and one attempted row.

    monkeypatch.setattr(generator, 'replace_text_in_slide', lambda *args, **kwargs: True)
    drive.bad_export = drive.fail_upload = False
    retried = web_generate(batch, RECORDS[:1], retry_failed=True)
    assert (retried['success'], retried['failed'], retried['pending_rows']) == (1, 0, 0)
    assert len(drive.pdf_creates) == 1


def test_intentional_new_batch_and_template_metadata_fetched_once(drive):
    original = generator.reserve_web_batch(object())
    assert web_generate(original)['success'] == 2
    assert drive.template_reads == 1
    new_batch = generator.reserve_web_batch(object())
    assert web_generate(new_batch)['success'] == 2
    assert drive.template_reads == 2
    assert len(set(drive.pdf_creates)) == 4
    assert set(drive.copies) == set(drive.deleted)


def test_bounded_request_recovers_without_changing_input_identity(drive):
    batch = generator.reserve_web_batch(object())
    pending = web_generate(batch, work_seconds=0)
    assert pending['pending_rows'] == 2
    assert pending['attempted_rows'] == 0
    with pytest.raises(ValueError, match='differ from the original'):
        web_generate(batch, [{'Name': 'Another recipient'}, RECORDS[1]])
    assert web_generate(batch)['success'] == 2


def test_cli_local_generation_resume_and_optional_cleanup(drive, tmp_path):
    data = tmp_path / 'recipients.csv'
    data.write_text('Name\nAda\nTariq\n', encoding='utf-8')
    output = tmp_path / 'output'
    initial = generator.generate_certificates(str(data), 'template', str(output))
    assert (initial['success'], initial['skipped']) == (2, 0)
    assert (output / 'Ada.pdf').read_bytes() == PDF_BYTES
    assert (output / 'Tariq.pdf').read_bytes() == PDF_BYTES
    assert drive.template_reads == 1
    assert not drive.deleted

    resumed = generator.generate_certificates(str(data), 'template', str(output), cleanup=True)
    assert (resumed['success'], resumed['skipped']) == (0, 2)
    assert drive.copies == drive.deleted


def test_cli_reused_folder_with_different_input_and_template(drive, tmp_path):
    original = tmp_path / 'original.csv'
    original.write_text('Name\nAda\n', encoding='utf-8')
    different = tmp_path / 'different.csv'
    different.write_text('Name\nTariq\n', encoding='utf-8')
    output = tmp_path / 'output'
    assert generator.generate_certificates(str(original), 'template', str(output))['success'] == 1
    assert generator.generate_certificates(str(different), 'template', str(output))['success'] == 1
    assert generator.generate_certificates(str(original), 'alternate', str(output))['success'] == 1
    assert generator.generate_certificates(str(original), 'template', str(output))['skipped'] == 1
    assert {path.name for path in output.glob('*.pdf')} == {'Ada.pdf', 'Tariq.pdf', 'Ada_2.pdf'}


def test_cli_legacy_checkpoint_never_skips_unrelated_row(drive, tmp_path):
    data = tmp_path / 'recipients.csv'
    data.write_text('Name\nAda\n', encoding='utf-8')
    (tmp_path / CHECKPOINT_FILENAME).write_text(
        '{"completed_rows":[0],"temp_slide_ids":{"0":"unknown-old-slide"}}', encoding='utf-8'
    )
    result = generator.generate_certificates(str(data), 'template', str(tmp_path), cleanup=True)
    assert (result['success'], result['skipped']) == (1, 0)
    assert json.loads((tmp_path / CHECKPOINT_FILENAME).read_text(encoding='utf-8'))['version'] == 2
    assert drive.deleted == drive.copies

def test_batch_tokens_are_signed_and_bound_to_account(monkeypatch, drive):
    from pathlib import Path

    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'web'))
    import app as web

    monkeypatch.setattr(
        web.Credentials, 'from_authorized_user_info',
        lambda *args, **kwargs: SimpleNamespace(expired=False),
    )
    # The integrated response renderer is supplied by the results workstream.
    if not hasattr(web, 'generation_response'):
        monkeypatch.setattr(
            web, 'generation_response',
            lambda summary, **kwargs: (web.jsonify({'summary': summary}), 200), raising=False,
        )

    client = web.app.test_client()
    with client.session_transaction() as session:
        session['credentials'] = {'mock': 'credentials'}
        session['user_email'] = 'first@example.test'

    reserved = client.get('/api/generation-batches/new')
    assert reserved.status_code == 200
    assert reserved.headers['Cache-Control'] == 'no-store'
    token = reserved.get_json()['batch_id']
    assert client.get(f'/api/generation-batches/{token}').status_code == 404
    with web.app.test_request_context():
        web.session['user_email'] = 'first@example.test'
        batch_id = web._batch_signer().loads(token)

    assert web_generate(batch_id)['success'] == 2
    recovered = client.get(f'/api/generation-batches/{token}')
    assert recovered.status_code == 200
    assert recovered.headers['Cache-Control'] == 'no-store'
    assert recovered.get_json()['summary']['created_pdfs'] == 2

    with client.session_transaction() as session:
        session['user_email'] = 'second@example.test'
    assert client.get(f'/api/generation-batches/{token}').status_code == 400


def test_abandoned_temporary_copy_is_removed_on_resume(drive):
    batch = generator.reserve_web_batch(object())
    web_generate(batch, work_seconds=0)
    drive.entries['orphan'] = {
        'mimeType': SLIDES_MIME_TYPE, 'abandoned': True, 'appProperties': {'certificateBatch': batch},
    }
    drive.entries['other-batch'] = {
        'mimeType': SLIDES_MIME_TYPE, 'abandoned': True,
        'appProperties': {'certificateBatch': 'unrelated-batch'},
    }
    assert web_generate(batch)['success'] == 2
    assert 'orphan' in drive.deleted
    assert 'other-batch' in drive.entries


def test_batch_uses_one_template_snapshot_after_source_changes(drive, monkeypatch):
    copy = drive.copy
    revisions = []

    def copy_with_revision(fileId, body, **kwargs):
        request = copy(fileId, body, **kwargs)

        def execute():
            result = request.execute()
            source = drive.entries[fileId]
            revision = source.get('copied_revision', source.get('version'))
            drive.entries[result['id']]['copied_revision'] = revision
            if 'certificateRow' in body['appProperties']:
                revisions.append(revision)
                drive.entries['template']['version'] = '2'
            return result

        return drive.request(execute)

    monkeypatch.setattr(drive, 'copy', copy_with_revision)
    batch = generator.reserve_web_batch(object())
    assert web_generate(batch)['success'] == 2
    assert revisions == ['1', '1']
    assert drive.template_reads == 1
    assert set(drive.copies) == set(drive.deleted)


def test_legacy_generation_rejects_changed_template_before_next_export(drive, monkeypatch):
    export = drive.export_media

    def export_and_edit(*args, **kwargs):
        def execute():
            pdf = export(*args, **kwargs).execute()
            drive.entries['template']['version'] = '2'
            return pdf
        return drive.request(execute)

    monkeypatch.setattr(drive, 'export_media', export_and_edit)
    summary = web_generate(None)
    assert (summary['success'], summary['failed']) == (1, 1)
    assert 'template changed' in summary['errors'][0].lower()
    assert len(drive.pdf_creates) == 1
    assert drive.copies == drive.deleted


def test_generation_route_reports_saved_rows_when_drive_preflight_is_unavailable(drive, monkeypatch):
    from io import BytesIO
    from web import app as web

    template_id = 'existing_template_for_fixtures'
    drive.entries[template_id] = drive.entries['template']
    monkeypatch.setattr(web.Credentials, 'from_authorized_user_info', lambda *a, **k: SimpleNamespace(expired=False))
    client = web.app.test_client()
    with client.session_transaction() as session:
        session['credentials'] = {'mock': 'credentials'}
        session['user_email'] = 'fixture@example.test'

    token = client.get('/api/generation-batches/new').get_json()['batch_id']
    original_get = drive.get

    def fail_second_row_lookup(fileId, **kwargs):
        if drive.pdf_creates and kwargs.get('fields') == 'id,trashed' and fileId not in drive.entries:
            def unavailable():
                raise http_error(503)
            return drive.request(unavailable)
        return original_get(fileId, **kwargs)

    monkeypatch.setattr(drive, 'get', fail_second_row_lookup)
    response = client.post('/api/generate', data={
        'csv_file': (BytesIO(b'Name\nAda\nTariq\n'), 'input.csv'),
        'template_id': template_id,
        'batch_id': token,
    })
    assert response.status_code == 202
    result = response.get_json()
    assert result['batch_id'] == token
    assert result['summary']['created_pdfs'] == result['summary']['pending_rows'] == 1
    assert result['summary']['interrupted'] is True
    assert 'Drive error' in result['summary']['errors'][0]
    status = client.get(f'/api/generation-batches/{token}').get_json()
    assert status['summary']['created_pdfs'] == status['summary']['pending_rows'] == 1


def test_cleanup_retries_and_completed_batch_can_finish_deferred_cleanup(drive, monkeypatch):
    delete = drive.delete
    attempts = {}
    fail_permanently = False

    def limited_delete(fileId):
        def execute():
            attempts[fileId] = attempts.get(fileId, 0) + 1
            if fail_permanently or attempts[fileId] == 1:
                raise http_error(503)
            return delete(fileId).execute()
        return drive.request(execute)

    monkeypatch.setattr(drive, 'delete', limited_delete)
    completed = generator.reserve_web_batch(object())
    assert not web_generate(completed).get('cleanup_pending')
    assert set(attempts.values()) == {2}

    fail_permanently = True
    deferred = generator.reserve_web_batch(object())
    summary = web_generate(deferred)
    assert summary['created_pdfs'] == 2 and summary['cleanup_pending']
    assert generator.recover_web_batch(object(), deferred)['cleanup_pending']
    fail_permanently = False
    recovered = generator.recover_web_batch(object(), deferred)
    assert not recovered.get('cleanup_pending')
    assert set(drive.copies) == set(drive.deleted)


def test_cli_reservations_protect_pdfs_from_other_interrupted_batches(tmp_path):
    from utils import CheckpointManager

    first = CheckpointManager(tmp_path, 'first')
    assert first.plan_output(0, 'Ada') == 'Ada.pdf'
    second = CheckpointManager(tmp_path, 'second')
    second_name = second.plan_output(0, 'Ada')
    assert second_name != 'Ada.pdf'
    (tmp_path / second_name).write_bytes(b'Second certificate')
    second.mark_complete(0)

    first = CheckpointManager(tmp_path, 'first')
    first_name = first.plan_output(0, 'Ada')
    assert first_name == 'Ada.pdf'
    (tmp_path / first_name).write_bytes(b'First certificate')
    first.mark_complete(0)
    assert CheckpointManager(tmp_path, 'first').is_complete(0)
    assert CheckpointManager(tmp_path, 'second').is_complete(0)
    assert (tmp_path / second_name).read_bytes() == b'Second certificate'


def test_cli_output_lock_releases_after_interruption(tmp_path):
    from utils import output_checkpoint_lock

    with pytest.raises(KeyboardInterrupt), output_checkpoint_lock(tmp_path):
        with pytest.raises(RuntimeError, match='Could not lock'):
            with output_checkpoint_lock(tmp_path):
                pytest.fail('The same folder was locked twice')
        raise KeyboardInterrupt()
    with output_checkpoint_lock(tmp_path):
        pass


@pytest.mark.parametrize('source', ['csv', 'xlsx', 'xls', 'drive-csv', 'sheets'])
def test_generation_routes_parse_replace_and_save_pdf_to_drive(monkeypatch, source):
    from copy import deepcopy
    from io import BytesIO
    from unittest.mock import MagicMock

    from test_input_parsing import FIXTURES, SPREADSHEET_ID, TEMPLATE_ID, fixture_records
    from test_placeholder_replacement import SlidesPresentation
    from web import app as web

    drive = Drive()
    drive.entries[TEMPLATE_ID] = {'name': 'Template', 'version': '1'}
    shape = ('certificate-content', None)
    presentations = {TEMPLATE_ID: SlidesPresentation({
        shape: ['{{Name}} / {{NA', 'ME}} / {{Identifier}} / {{Message}}\n'],
    })}
    slides = SimpleNamespace(presentations=lambda: SimpleNamespace(
        get=lambda presentationId: presentations[presentationId].get(),
        batchUpdate=lambda presentationId, body: presentations[presentationId].batchUpdate(body=body),
    ))
    sheets = MagicMock()
    sheet_get = sheets.spreadsheets.return_value.values.return_value.get
    sheet_title = 'Participants 2026'
    filename = f'input_records.{source}' if source in {'xls', 'xlsx'} else 'input_records.csv'
    expected = fixture_records(filename)
    headers = ['Name', *(f'Unused {i}' for i in range(25)), 'Identifier', 'Message']
    sheet_get.return_value.execute.return_value = {'values': [
        headers, *[[record.get(header, '') for header in headers] for record in expected],
    ]}

    def build(name, version, credentials):
        return {'drive': drive, 'slides': slides, 'sheets': sheets}[name]

    monkeypatch.setattr(generator, 'build', build)
    monkeypatch.setattr('googleapiclient.discovery.build', build)
    monkeypatch.setattr(web.Credentials, 'from_authorized_user_info', lambda *a, **k: SimpleNamespace(expired=False))
    copy, export = drive.copy, drive.export_media
    rendered = []

    def copy_presentation(fileId, **kwargs):
        def execute():
            result = copy(fileId, **kwargs).execute()
            presentations[result['id']] = SlidesPresentation(deepcopy(presentations[fileId].containers))
            return result
        return drive.request(execute)

    def export_presentation(fileId, **kwargs):
        def execute():
            rendered.append(''.join(presentations[fileId].containers[shape]))
            return export(fileId, **kwargs).execute()
        return drive.request(execute)

    monkeypatch.setattr(drive, 'copy', copy_presentation)
    monkeypatch.setattr(drive, 'export_media', export_presentation)

    client = web.app.test_client()
    with client.session_transaction() as session:
        session['user_email'] = 'fixture@example.test'
        session['credentials'] = {'mock': 'credentials'}

    token = client.get('/api/generation-batches/new').get_json()['batch_id']
    form = {
        'template_id': TEMPLATE_ID, 'output_folder': 'Recipient Awards',
        'filename_field': 'Identifier', 'batch_id': token,
    }
    data = (FIXTURES / filename).read_bytes()
    if source == 'drive-csv':
        drive.entries['source-file'] = {'name': filename, 'mimeType': 'text/csv', 'data': data}
        preview = client.get('/api/drive/file/source-file/csv').get_json()
        data = preview['csv_content'].encode()
        assert preview['rows'][0][1] == '00123'
    if source == 'sheets':
        form.update(sheets_id=SPREADSHEET_ID, sheet_name=sheet_title)
    else:
        form['csv_file'] = (BytesIO(data), filename)

    response = client.post('/api/generate', data=form)
    result = response.get_json()
    assert response.status_code == 200, result
    assert result['status'] == 'completed'
    assert result['summary']['created_pdfs'] == result['summary']['attempted_rows'] == 2
    assert result['output_folder'] == 'Recipient Awards'
    assert [drive.entries[file_id]['name'] for file_id in drive.pdf_creates] == ['00123.pdf', '00007.pdf']
    for certificate, values in zip(rendered, expected, strict=True):
        message = values['Message'].replace('\r\n', '\n')
        assert certificate == f"{values['Name']} / {values['Name']} / {values['Identifier']} / {message}\n"
    assert all(drive.entries[file_id]['data'] == PDF_BYTES for file_id in drive.pdf_creates)
    assert set(drive.copies) == set(drive.deleted)
    if source == 'sheets':
        assert sheet_get.call_args.kwargs['range'] == f"'{sheet_title}'"
