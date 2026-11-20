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


def http_error(status):
    return HttpError(httplib2.Response({'status': str(status), 'reason': str(status)}), b'{}')


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
            return dict(self.entries[fileId], id=fileId)

        return self.request(execute)

    def get_media(self, fileId):
        def execute():
            if fileId not in self.entries:
                raise http_error(404)
            return self.entries[fileId]['data']

        return self.request(execute)

    def list(self, q, **kwargs):
        def execute():
            batch = re.search(r"key='certificateBatch' and value='([^']+)'", q)
            results = []
            for file_id, file in self.entries.items():
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
            if media_body is not None:
                mime = media_body.mimetype()
                metadata['mimeType'] = mime
                metadata['data'] = media_body.getbytes(0, media_body.size())
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


def test_ambiguous_upload_response_is_reconciled(drive):
    batch = generator.reserve_web_batch(object())
    drive.lose_upload_response = True
    result = web_generate(batch, RECORDS[:1])
    assert (result['success'], result['failed']) == (1, 0)
    assert web_generate(batch, RECORDS[:1]) == result
    assert len(drive.pdf_creates) == 1


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
