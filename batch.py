"""Drive-backed recovery state for web certificate generation."""

import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from io import BytesIO

from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload

from config import PDF_MIME_TYPE, SLIDES_MIME_TYPE


FOLDER_MIME_TYPE = 'application/vnd.google-apps.folder'


def can_add_drive_children(folder):
    return folder.get('capabilities', {}).get('canAddChildren') is True


def drive_parent_denied(error):
    return isinstance(error, HttpError) and error.resp.status == 403 and any(
        detail.get('reason') == 'insufficientParentPermissions'
        for detail in (error.error_details or ()) if isinstance(detail, dict)
    )


class DriveDestinationError(RuntimeError):
    def __init__(self, folder_name):
        super().__init__(f'Google Drive cannot save files to "{folder_name}".')


def content_digest(value):
    data = json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(data).hexdigest()


def drive_query_value(value):
    return value.replace('\\', '\\\\').replace("'", "\\'")


def reserve_drive_ids(files, count):
    ids = []
    while count:
        size = min(count, 1000)
        page = files.generateIds(count=size, space='drive').execute()['ids']
        if len(page) != size:
            raise RuntimeError("Google Drive did not reserve all requested file IDs.")
        ids.extend(page)
        count -= size
    return ids


def drive_not_found(error):
    return isinstance(error, HttpError) and error.resp.status == 404


def _drive_conflict(error):
    return isinstance(error, HttpError) and error.resp.status == 409


class DriveBatch:
    """Immutable manifest with fixed PDF IDs and durable per-row outcomes."""

    def __init__(self, files, batch_id):
        self.files = files
        self.batch_id = batch_id
        self.manifest = None
        self.successes = set()
        self.failures = {}

    def load(self):
        try:
            payload = self.files.get_media(fileId=self.batch_id).execute()
        except HttpError as error:
            if drive_not_found(error):
                return None
            raise
        self.manifest = json.loads(payload)
        if self.manifest['schema'] != 1:
            raise ValueError("This generation batch uses an unsupported format.")
        return self.manifest

    def create(
        self, *, identity, input_rows, rows, snapshot_id, template_metadata, placeholders,
        folder_id, folder_name, group_folders=None, powerpoint_identity=None,
    ):
        group_folders = group_folders or {}
        new_folders = sum(existing_id is None for existing_id in group_folders.values())
        file_ids = reserve_drive_ids(self.files, rows * 2 + (not folder_id) + new_folders)
        folder_ids = iter(file_ids[rows * 2:])
        manifest = {
            'schema': 1,
            'identity': identity,
            'input_rows': input_rows,
            'template': template_metadata,
            'snapshot_id': snapshot_id,
            'placeholders': sorted(placeholders),
            'folder_id': folder_id or next(folder_ids),
            'output_folder': folder_name,
            'create_folder': not folder_id,
            'pdf_ids': file_ids[:rows],
            'failure_ids': file_ids[rows:rows * 2],
        }
        if group_folders:
            manifest['group_folders'] = {
                name: {'id': existing_id or next(folder_ids), 'create': existing_id is None}
                for name, existing_id in group_folders.items()
            }
        if powerpoint_identity:
            manifest['powerpoint_template'] = powerpoint_identity
        media = MediaIoBaseUpload(
            BytesIO(json.dumps(manifest).encode('utf-8')), mimetype='application/json'
        )
        try:
            self.files.create(
                body={
                    'id': self.batch_id,
                    'name': 'Certificate generation batch.json',
                    'parents': ['root'],
                },
                media_body=media,
                fields='id',
            ).execute()
        except HttpError as error:
            if not _drive_conflict(error):
                raise
            # A request retried after losing the create response uses the first manifest.
            manifest = self.load()
            if manifest is None:
                raise
        self.manifest = manifest
        return manifest

    def ensure_output_folder(self):
        return self._ensure_folder(
            self.manifest['folder_id'], self.manifest['output_folder'],
            create=self.manifest['create_folder'],
        )

    def ensure_group_folder(self, name):
        folder = self.manifest['group_folders'][name]
        return self._ensure_folder(
            folder['id'], name, create=folder['create'], parent_id=self.manifest['folder_id'],
        )

    def _ensure_folder(self, folder_id, name, *, create, parent_id='root'):
        fields = 'mimeType,trashed,capabilities(canAddChildren)'
        folder = self._get_file(folder_id, fields)
        if folder is None and create:
            body = {
                'id': folder_id,
                'name': name,
                'mimeType': FOLDER_MIME_TYPE,
                'parents': [parent_id],
            }
            try:
                self.files.create(body=body, fields='id', supportsAllDrives=True).execute()
            except HttpError as error:
                if drive_parent_denied(error):
                    raise DriveDestinationError(name) from error
                if not _drive_conflict(error):
                    raise
                folder = self._get_file(folder_id, fields)
            else:
                return folder_id
        if (not folder or folder.get('trashed') or folder.get('mimeType') != FOLDER_MIME_TYPE
                or not can_add_drive_children(folder)):
            raise DriveDestinationError(name)
        return folder_id

    def properties(self, row_index):
        return {'certificateBatch': self.batch_id, 'certificateRow': str(row_index)}

    def _list_files(self, clause):
        query = (
            "trashed=false and appProperties has { key='certificateBatch' "
            f"and value='{drive_query_value(self.batch_id)}' }} and ({clause})"
        )
        page_token = None
        while True:
            result = self.files.list(
                q=query,
                spaces='drive',
                fields='nextPageToken,files(id,mimeType,description,appProperties)',
                pageSize=1000,
                pageToken=page_token,
            ).execute()
            yield from result.get('files', [])
            page_token = result.get('nextPageToken')
            if not page_token:
                break

    def refresh_outcomes(self):
        pdfs = {file_id: index for index, file_id in enumerate(self.manifest['pdf_ids'])}
        failures = {file_id: index for index, file_id in enumerate(self.manifest['failure_ids'])}
        for file in self._list_files(f"mimeType='{PDF_MIME_TYPE}' or mimeType='text/plain'"):
            file_id = file['id']
            if file_id in pdfs:
                self.successes.add(pdfs[file_id])
            elif file_id in failures:
                self.failures[failures[file_id]] = file.get('description') or 'Generation failed.'

    def _get_file(self, file_id, fields):
        try:
            return self.files.get(fileId=file_id, fields=fields, supportsAllDrives=True).execute()
        except HttpError as error:
            if not drive_not_found(error):
                raise
            return None

    def pdf_exists(self, row_index):
        file = self._get_file(self.manifest['pdf_ids'][row_index], 'id,trashed')
        if file and not file.get('trashed'):
            self.successes.add(row_index)
            return True
        return False

    def existing_failure(self, row_index):
        """Check the receipt ID if Drive's list index has yet to report it."""
        file = self._get_file(self.manifest['failure_ids'][row_index], 'description,trashed')
        if file and not file.get('trashed'):
            self.failures[row_index] = file.get('description') or 'Generation failed.'
        return row_index in self.failures

    def record_failure(self, row_index, message):
        file_id = self.manifest['failure_ids'][row_index]
        body = {
            'id': file_id,
            'name': 'Certificate generation failure.txt',
            'mimeType': 'text/plain',
            'parents': ['root'],
            'appProperties': self.properties(row_index),
            'description': message,
        }
        try:
            self.files.create(body=body, fields='id').execute()
        except HttpError as error:
            if not _drive_conflict(error):
                raise
            self.files.update(
                fileId=file_id, body={'description': message}, fields='id'
            ).execute()
        self.failures[row_index] = message

    def clean_abandoned_slides(self, *, completed=False):
        clause = f"mimeType='{SLIDES_MIME_TYPE}'"
        if not completed:
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
            clause += f" and createdTime < '{cutoff.isoformat()}'"
        cleaned = True
        for file in self._list_files(clause):
            if file['id'] != self.manifest['snapshot_id']:
                cleaned = delete_temp_slide(self.files, file['id']) and cleaned
        return cleaned

    def summary(self):
        total = len(self.manifest['pdf_ids'])
        failed = self.failures.keys() - self.successes
        attempted = len(self.successes) + len(failed)
        return {
            'input_rows': self.manifest['input_rows'],
            'total': total,
            'attempted_rows': attempted,
            'success': len(self.successes),
            'created_pdfs': len(self.successes),
            'failed': len(failed),
            'skipped': 0,
            'pending_rows': total - attempted,
            'errors': [self.failures[index] for index in sorted(failed)],
            'output_folder': self.manifest['output_folder'],
            'output_folder_id': self.manifest['folder_id'],
        }


def delete_temp_slide(files, slide_id):
    for attempt in range(2):
        try:
            files.delete(fileId=slide_id).execute()
            return True
        except Exception as error:
            if drive_not_found(error):
                return True
            transient = isinstance(error, OSError) or (
                isinstance(error, HttpError) and error.resp.status in (408, 429, 500, 502, 503, 504)
            )
            if attempt or not transient:
                logging.warning("Failed to delete temporary slide %s: %s", slide_id, error)
                return False
