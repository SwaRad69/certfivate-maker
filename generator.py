"""
Core certificate generation logic.
Handles Google API interactions, template copying, text replacement, and PDF export.
"""

import logging
import tempfile
import time
from collections import Counter
from io import BytesIO
from typing import Dict, List, Tuple, Set
from pathlib import Path

from google.oauth2.service_account import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

import config
from batch import (
    DriveBatch,
    content_digest,
    delete_temp_slide,
    drive_query_value,
    reserve_drive_ids,
)
from utils import CheckpointManager, output_checkpoint_lock, safe_filename
from web.file_converter import detect_file_format, get_supported_formats, parse_csv, read_input_records


def authenticate_google(credentials_path: str) -> Tuple:
    """
    Authenticate with Google using service account credentials.
    
    Args:
        credentials_path: Path to service account credentials.json
        
    Returns:
        Tuple of (slides_service, drive_service)
        
    Raises:
        FileNotFoundError: If credentials file not found
        ValueError: If credentials are invalid
    """
    try:
        creds = Credentials.from_service_account_file(
            credentials_path,
            scopes=config.SCOPES
        )
        
        slides_service = build(
            'slides',
            config.SLIDES_API_VERSION,
            credentials=creds
        )
        drive_service = build(
            'drive',
            config.DRIVE_API_VERSION,
            credentials=creds
        )
        
        logging.info("Successfully authenticated with Google APIs")
        return (slides_service, drive_service)
        
    except FileNotFoundError:
        logging.error(f"Credentials file not found: {credentials_path}")
        raise
    except Exception as e:
        logging.error(f"Authentication failed: {e}")
        raise ValueError(f"Failed to authenticate: {e}") from e


def get_presentation_metadata(slides_service, presentation_id: str) -> Dict:
    """
    Retrieve metadata about a presentation.
    Includes title, slide count, and text element information.
    
    Args:
        slides_service: Google Slides API service
        presentation_id: ID of the presentation
        
    Returns:
        Dict with presentation metadata
        
    Raises:
        Exception: If API call fails
    """
    try:
        presentation = slides_service.presentations().get(
            presentationId=presentation_id
        ).execute()
        
        metadata = {
            'id': presentation_id,
            'title': presentation.get('title', 'Untitled'),
            'slide_count': len(presentation.get('slides', [])),
            'slides': presentation.get('slides', []),
        }
        
        logging.debug(f"Retrieved metadata for presentation: {metadata['title']}")
        return metadata
        
    except Exception as e:
        logging.error(f"Failed to get presentation metadata: {e}")
        raise


def _placeholder_name(match):
    return match.group(1).lower().strip("\"'")


def _slide_text_elements(page_elements):
    for element in page_elements:
        object_id = element.get('objectId')
        for kind in ('shape', 'textBox'):
            section = element.get(kind)
            if section is not None:
                yield (object_id, None), section

        for row_index, row in enumerate(element.get('table', {}).get('tableRows', [])):
            column_index = 0
            for cell in row.get('tableCells', []):
                location = cell.get('location', {})
                row_number = location.get('rowIndex', row_index)
                column_number = location.get('columnIndex', column_index)
                yield (object_id, (row_number, column_number)), cell
                column_index = column_number + cell.get('columnSpan', 1)

        yield from _slide_text_elements(element.get('elementGroup', {}).get('children', []))


def _presentation_text(presentation):
    for slide in presentation.get('slides', []):
        for location, section in _slide_text_elements(slide.get('pageElements', [])):
            text_elements = section.get('text', {}).get('textElements', []) or section.get('textElements', [])
            # Paragraph markers describe the runs and carry no additional text.
            text = ''.join(
                element.get('textRun', element.get('autoText', {})).get('content', '')
                for element in text_elements
            )
            yield location, text


def detect_placeholders_in_slide(slides_service, presentation_id: str, *, presentation=None) -> Set[str]:
    """Read placeholder names, joining text runs within each shape or table cell."""
    if presentation is None:
        presentation = get_presentation_metadata(slides_service, presentation_id)
    placeholders = {
        _placeholder_name(match)
        for _, text in _presentation_text(presentation)
        for match in config.PLACEHOLDER_PATTERN.finditer(text)
    }
    logging.info("Detected placeholders: %s", placeholders)
    return placeholders


def read_csv(file_path: str) -> List[Dict]:
    """
    Read certificate data as a list of text-valued records.
    
    Args:
        file_path: Path to a CSV file or other supported input
        
    Returns:
        List of dicts, one per row
        
    Raises:
        FileNotFoundError: If CSV file not found
        ValueError: If CSV is invalid or empty
    """
    try:
        path = Path(file_path)
        filename = path.name if detect_file_format(path.name) in get_supported_formats() else 'input.csv'
        headers, rows = read_input_records(path.read_bytes(), filename)
        if not rows:
            raise ValueError("Input file has no data rows")
        logging.info("Loaded %d rows and columns: %s", len(rows), headers)
        return rows
        
    except FileNotFoundError:
        logging.error(f"CSV file not found: {file_path}")
        raise
    except Exception as e:
        logging.error(f"Failed to read CSV: {e}")
        raise ValueError(f"Invalid CSV format: {e}") from e


def validate_csv_placeholders(csv_rows: List[Dict], detected_placeholders: Set[str]) -> Tuple[bool, List[str]]:
    """
    Validate that CSV columns match detected placeholders.
    Case-insensitive matching.
    
    Args:
        csv_rows: List of dicts from CSV
        detected_placeholders: Set of placeholder names from slide (lowercase)
        
    Returns:
        Tuple of (is_valid, list_of_issues)
    """
    if not csv_rows:
        return False, ["CSV is empty"]
    
    csv_columns = set(csv_rows[0].keys())
    # Normalize CSV column names to lowercase for comparison
    csv_columns_lower = {col.lower() for col in csv_columns}
    issues = []
    
    # Check for missing columns (case-insensitive)
    missing = detected_placeholders - csv_columns_lower
    if missing:
        issues.append(f"Missing CSV columns for placeholders: {missing}")
    
    # Warn about unused columns (case-insensitive)
    unused = csv_columns_lower - detected_placeholders
    if unused:
        logging.warning(f"CSV columns not used in slide: {unused}")
    
    is_valid = len(issues) == 0
    if is_valid:
        logging.info("CSV columns match all placeholders ✓")
    else:
        logging.warning(f"CSV validation issues: {issues}")
    
    return is_valid, issues


def duplicate_slide_template(
    drive_service, template_id: str, row_index: int, *, template_metadata=None, batch_properties=None
) -> str:
    """
    Create a copy of the template slide on Google Drive.
    
    Args:
        drive_service: Google Drive API service
        template_id: ID of the template presentation
        row_index: Row index for naming
        
    Returns:
        ID of the new presentation copy
        
    Raises:
        Exception: If API call fails
    """
    try:
        # Get original file metadata
        original = template_metadata
        if original is None:
            original = _template_drive_metadata(drive_service, template_id)
        
        # Create copy with unique name
        copy_name = f"{original['name']}_cert_{row_index}_{int(time.time())}"
        copy_metadata = {
            'name': copy_name,
            'parents': original.get('parents', []),
        }
        
        if batch_properties is not None:
            copy_metadata['parents'] = ['root']
            copy_metadata['appProperties'] = batch_properties

        copied_file = drive_service.files().copy(
            fileId=template_id,
            body=copy_metadata,
            supportsAllDrives=True,
            fields='id',
        ).execute()
        
        new_id = copied_file['id']
        logging.debug(f"Duplicated template to new presentation: {new_id}")
        
        return new_id
        
    except Exception as e:
        logging.error(f"Failed to duplicate template: {e}")
        raise


def _format_occurrences(occurrences):
    return ', '.join(f'{name} ({count})' for name, count in sorted(occurrences.items()))


def _manual_replacement_requests(text_by_location, values):
    for (object_id, cell), text in text_by_location.items():
        matches = list(config.PLACEHOLDER_PATTERN.finditer(text))
        if not matches:
            continue
        target = {'objectId': object_id}
        if cell is not None:
            target['cellLocation'] = {'rowIndex': cell[0], 'columnIndex': cell[1]}
        # Slides indexes UTF-16 code units. Editing right to left keeps the
        # ranges of earlier occurrences valid, including repeats in one shape.
        for match in reversed(matches):
            value = values[_placeholder_name(match)]
            start = len(text[:match.start()].encode('utf-16-le')) // 2
            end = start + len(match.group().encode('utf-16-le')) // 2
            yield {'deleteText': {**target, 'textRange': {
                'type': 'FIXED_RANGE', 'startIndex': start, 'endIndex': end,
            }}}
            if value:
                yield {'insertText': {**target, 'insertionIndex': start, 'text': value}}


def replace_text_in_slide(
    slides_service, presentation_id: str, replacements: Dict[str, str], *, raise_on_failure=False
) -> bool:
    """Apply and verify every original placeholder occurrence before PDF export."""
    try:
        _replace_and_verify(slides_service.presentations(), presentation_id, replacements)
        return True
    except Exception as error:
        logging.error("Failed to replace text in presentation %s: %s", presentation_id, error)
        if raise_on_failure:
            raise
        return False


def _replace_and_verify(presentations, presentation_id, replacements):
    def read_text():
        presentation = presentations.get(presentationId=presentation_id).execute()
        return dict(_presentation_text(presentation))

    def update(requests):
        return presentations.batchUpdate(
            presentationId=presentation_id, body={'requests': requests}
        ).execute()

    original = read_text()
    matches = [
        match for text in original.values() for match in config.PLACEHOLDER_PATTERN.finditer(text)
    ]
    if not matches:
        return

    values = {
        key.lower(): str(value).replace('\r\n', '\n').replace('\r', '\n')
        for key, value in replacements.items()
    }
    missing = Counter(_placeholder_name(match) for match in matches if _placeholder_name(match) not in values)
    if missing:
        raise ValueError(f"Missing replacement values for placeholders: {_format_occurrences(missing)}")

    expected = {
        location: config.PLACEHOLDER_PATTERN.sub(lambda match: values[_placeholder_name(match)], text)
        for location, text in original.items()
    }

    actual = original
    # Native find-and-replace preserves formatting when it finds the token.
    # Use positional updates when values include braces so they stay literal
    # and cannot become input to a subsequent native replacement.
    if not any('{' in value or '}' in value for value in values.values()):
        native = {}
        for match in matches:
            native.setdefault(match.group().lower(), match)
        response = update([
            {'replaceAllText': {
                'containsText': {'text': match.group(), 'matchCase': False},
                'replaceText': values[_placeholder_name(match)],
            }}
            for match in native.values()
        ])
        native_counts = {
            literal: reply.get('replaceAllText', {}).get('occurrencesChanged', 0)
            for literal, reply in zip(native, response.get('replies', []))
        }
        expected_counts = Counter(match.group().lower() for match in matches)
        logging.debug("Native placeholder counts in %s: %s of %s", presentation_id, native_counts, expected_counts)
        # Counts alone cannot establish that the right text was inserted or
        # that Slides found every occurrence spread across text runs.
        actual = read_text()

    remaining = {
        location: text for location, text in actual.items()
        if text != expected.get(location) and config.PLACEHOLDER_PATTERN.search(text)
    }
    if remaining:
        unknown = Counter(
            _placeholder_name(match)
            for text in remaining.values()
            for match in config.PLACEHOLDER_PATTERN.finditer(text)
            if _placeholder_name(match) not in values
        )
        if unknown:
            raise ValueError(f"Unresolved placeholders: {_format_occurrences(unknown)}")
        update(list(_manual_replacement_requests(remaining, values)))
        actual = read_text()

    # An empty shape or cell may omit the otherwise implicit final newline.
    differences = [
        location for location in actual.keys() | expected.keys()
        if (actual.get(location) or '\n') != (expected.get(location) or '\n')
    ]
    if differences:
        unresolved = Counter(
            _placeholder_name(match)
            for location in differences
            for match in config.PLACEHOLDER_PATTERN.finditer(actual.get(location, ''))
        )
        if unresolved:
            raise ValueError(f"Unresolved placeholders: {_format_occurrences(unresolved)}")
        raise ValueError("Slides text differs from the expected replacement. Check the template and values.")


def export_slide_to_pdf(drive_service, presentation_id: str, output_folder: str, filename: str) -> bool:
    """Export a presentation to a local PDF and publish it atomically."""
    pdf_path = Path(output_folder) / f"{safe_filename(filename)}.pdf"
    temp_path = None
    try:
        pdf_content = drive_service.files().export_media(
            fileId=presentation_id, mimeType=config.PDF_MIME_TYPE
        ).execute()
        if not pdf_content:
            raise RuntimeError("Drive returned an empty PDF.")
        with tempfile.NamedTemporaryFile(dir=output_folder, suffix='.tmp', delete=False) as temporary:
            temp_path = Path(temporary.name)
            temporary.write(pdf_content)
        temp_path.replace(pdf_path)
        logging.info("Exported PDF: %s", pdf_path)
        return True
    except Exception as error:
        logging.error("Failed to export PDF for %s: %s", presentation_id, error)
        return False
    finally:
        if temp_path:
            temp_path.unlink(missing_ok=True)


def cleanup_temp_slides(drive_service, temp_slide_ids):
    """Return the checkpoint keys of successfully cleaned-up Slides copies."""
    files = drive_service.files()
    deleted = [
        row_key for row_key, slide_id in temp_slide_ids.items()
        if delete_temp_slide(files, slide_id)
    ]
    logging.info("Cleanup complete: deleted %s temporary slides", len(deleted))
    return deleted


WEB_BATCH_WORK_SECONDS = 18


def _template_drive_metadata(drive_service, template_id):
    return drive_service.files().get(
        fileId=template_id, fields='name,parents,version', supportsAllDrives=True
    ).execute()


def _template_version(files, template_id):
    return files.get(fileId=template_id, fields='version', supportsAllDrives=True).execute().get('version')


def _drive_service(user_credentials):
    return build('drive', config.DRIVE_API_VERSION, credentials=user_credentials)


def reserve_web_batch(user_credentials):
    return reserve_drive_ids(_drive_service(user_credentials).files(), 1)[0]


def recover_web_batch(user_credentials, batch_id):
    batch = DriveBatch(_drive_service(user_credentials).files(), batch_id)
    if batch.load() is None:
        return None
    batch.refresh_outcomes()
    return _web_batch_result(batch, sweep=True)


def _web_batch_result(batch, *, sweep=False, cleanup_pending=False, interruption=None):
    summary = batch.summary()
    completed = summary['success'] == summary['total']
    if completed:
        cleanup_pending = not delete_temp_slide(batch.files, batch.manifest['snapshot_id']) or cleanup_pending
    if sweep:
        try:
            cleanup_pending = not batch.clean_abandoned_slides(completed=completed) or cleanup_pending
        except Exception:
            logging.exception("Could not sweep temporary slides for batch %s", batch.batch_id)
            cleanup_pending = True
    if cleanup_pending:
        summary['cleanup_pending'] = True
    if interruption:
        summary['errors'].append(interruption)
    return summary


def _snapshot_web_template(drive_service, template_id, metadata, batch_id):
    files = drive_service.files()
    snapshot_id = files.copy(
        fileId=template_id,
        body={
            'name': 'Certificate generation template snapshot',
            'parents': ['root'],
            'appProperties': {'certificateBatch': batch_id},
        },
        supportsAllDrives=True,
        fields='id',
    ).execute()['id']
    try:
        source_version = _template_version(files, template_id)
        if source_version != metadata.get('version'):
            raise ValueError("The template changed while the batch was starting. Start a new batch.")
    except Exception:
        delete_temp_slide(files, snapshot_id)
        raise
    return snapshot_id


def generate_certificates_oauth2(
    csv_content: str | None,
    template_id: str,
    output_folder: str,
    user_credentials,
    filename_field: str = 'Name',
    *,
    records: List[Dict] | None = None,
    input_rows: int | None = None,
    batch_id=None,
    retry_failed=False,
    work_seconds=WEB_BATCH_WORK_SECONDS,
) -> Dict:
    """Generate Drive PDFs, optionally resuming a durable, time-bounded batch."""
    if records is None:
        records = parse_csv(csv_content)[1]
    if not records:
        raise ValueError("The selected data source has no certificate records.")

    input_rows = len(records) if input_rows is None else input_rows
    identity = content_digest([template_id, output_folder, filename_field, input_rows, records])
    deadline = time.monotonic() + work_seconds if batch_id else float('inf')
    slides_service = build('slides', config.SLIDES_API_VERSION, credentials=user_credentials)
    drive_service = _drive_service(user_credentials)
    files = drive_service.files()
    batch = DriveBatch(files, batch_id) if batch_id else None
    manifest = batch.load() if batch else None
    template_metadata = None

    if manifest is None:
        template_metadata = _template_drive_metadata(drive_service, template_id)
        detected_placeholders = detect_placeholders_in_slide(slides_service, template_id)
        is_valid, issues = validate_csv_placeholders(records, detected_placeholders)
        if not is_valid:
            return {
                'input_rows': input_rows, 'total': len(records), 'attempted_rows': 0,
                'success': 0, 'failed': 0, 'skipped': 0, 'created_pdfs': 0,
                'validation_failed': True, 'errors': issues,
            }
        if batch:
            folder_id = _find_drive_folder(drive_service, output_folder)
            snapshot_id = _snapshot_web_template(drive_service, template_id, template_metadata, batch_id)
            manifest = batch.create(
                identity=identity, input_rows=input_rows, rows=len(records),
                snapshot_id=snapshot_id,
                template_metadata=template_metadata, placeholders=detected_placeholders,
                folder_id=folder_id,
                folder_name=output_folder,
            )
            if manifest['snapshot_id'] != snapshot_id:
                delete_temp_slide(files, snapshot_id)
        else:
            folder_id = _find_or_create_drive_folder(drive_service, output_folder)

    if batch and manifest['identity'] != identity:
        raise ValueError("The data, template, or output settings differ from the original batch.")

    cleanup_pending = False
    try:
        success = 0
        errors = []
        candidates = range(len(records))
        if batch:
            batch.refresh_outcomes()
            batch.clean_abandoned_slides()
            pending = [i for i in candidates if i not in batch.successes and i not in batch.failures]
            failed = sorted(batch.failures.keys() - batch.successes) if retry_failed else []
            candidates = pending + failed
            if not candidates:
                return _web_batch_result(batch, sweep=True)

            template_id = manifest['snapshot_id']
            template_metadata = manifest['template']
            detected_placeholders = set(manifest['placeholders'])
            folder_id = batch.ensure_output_folder()

        for row_idx in candidates:
            if time.monotonic() >= deadline:
                break

            row = records[row_idx]
            if batch and batch.pdf_exists(row_idx):
                continue
            if batch and not retry_failed and batch.existing_failure(row_idx):
                continue

            filename = next(
                (str(value) for key, value in row.items() if key.lower() == filename_field.lower()),
                '',
            ) or f'certificate_{row_idx}'
            replacements = {
                key.lower(): str(value)
                for key, value in row.items()
                if key.lower() in detected_placeholders
            }
            temp_slide_id = None
            try:
                temp_slide_id = duplicate_slide_template(
                    drive_service, template_id, row_idx, template_metadata=template_metadata,
                    batch_properties=batch.properties(row_idx) if batch else {},
                )
                if (batch is None and len(records) > 1
                        and _template_version(files, template_id) != template_metadata.get('version')):
                    raise RuntimeError("The Google Slides template changed during generation. Start a new batch.")
                if not replace_text_in_slide(
                    slides_service, temp_slide_id, replacements, raise_on_failure=True
                ):
                    raise RuntimeError("Text replacement failed.")
                if not export_slide_to_pdf_drive(
                    drive_service, temp_slide_id, filename, folder_id,
                    file_id=batch.manifest['pdf_ids'][row_idx] if batch else None,
                    app_properties=batch.properties(row_idx) if batch else None,
                    raise_on_failure=True,
                ):
                    raise RuntimeError("PDF export failed.")
                if batch:
                    batch.successes.add(row_idx)
                success += 1
            except Exception as error:
                message = f"Row {row_idx + 1}: {error}"[:2000]
                logging.error(message)
                if batch:
                    # An upload can succeed even when the response is lost.
                    if not batch.pdf_exists(row_idx):
                        batch.record_failure(row_idx, message)
                else:
                    errors.append(message)
            finally:
                if temp_slide_id and not delete_temp_slide(files, temp_slide_id):
                    cleanup_pending = True

        if batch:
            return _web_batch_result(batch, cleanup_pending=cleanup_pending)
        return {
            'input_rows': input_rows, 'total': len(records), 'attempted_rows': len(records),
            'success': success, 'failed': len(errors), 'skipped': 0,
            'created_pdfs': success, 'errors': errors,
        }
    except Exception as error:
        if batch is None:
            raise
        logging.exception("Generation was interrupted for batch %s", batch.batch_id)
        return _web_batch_result(
            batch, cleanup_pending=cleanup_pending,
            interruption=f"Generation paused after a Drive error. Check batch status or resume. {error}"[:2000],
        )



def _find_drive_folder(drive_service, folder_name):
    name = drive_query_value(folder_name)
    result = drive_service.files().list(
        q=f"name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
        spaces='drive',
        fields='files(id)',
        pageSize=10,
    ).execute()
    folders = result.get('files', [])
    return folders[0]['id'] if folders else None


def _find_or_create_drive_folder(drive_service, folder_name: str) -> str:
    folder_id = _find_drive_folder(drive_service, folder_name)
    if folder_id:
        return folder_id
    return drive_service.files().create(
        body={'name': folder_name, 'mimeType': 'application/vnd.google-apps.folder'},
        fields='id',
    ).execute()['id']


def export_slide_to_pdf_drive(
    drive_service,
    presentation_id: str,
    filename: str,
    output_folder_id: str,
    *,
    file_id=None,
    app_properties=None,
    raise_on_failure=False,
) -> bool:
    """Export Slides and upload a PDF using a fixed Drive ID when supplied."""
    files = drive_service.files()
    try:
        pdf_content = files.export_media(
            fileId=presentation_id, mimeType=config.PDF_MIME_TYPE
        ).execute()
        if not pdf_content:
            raise RuntimeError("Drive returned an empty PDF.")
    except Exception as error:
        if raise_on_failure:
            raise RuntimeError(f"PDF export failed: {error}") from error
        logging.error("PDF export failed: %s", error)
        return False

    file_metadata = {
        'name': f'{safe_filename(filename)}.pdf',
        'parents': [output_folder_id],
    }
    if file_id:
        file_metadata['id'] = file_id
        file_metadata['appProperties'] = app_properties

    try:
        media = MediaIoBaseUpload(BytesIO(pdf_content), mimetype=config.PDF_MIME_TYPE, resumable=True)
        file_obj = files.create(
            body=file_metadata, media_body=media, fields='id', supportsAllDrives=True
        ).execute()
        logging.info("Saved PDF to Drive: %s", file_obj['id'])
        return True
    except Exception as error:
        if raise_on_failure:
            raise RuntimeError(f"PDF upload failed: {error}") from error
        logging.error("PDF upload failed: %s", error)
        return False


def generate_certificates(
    csv_path: str,
    template_id: str,
    output_folder: str,
    credentials_path: str = config.DEFAULT_CREDENTIALS_PATH,
    cleanup: bool = False,
    clear_checkpoint: bool = False,
) -> Dict:
    """
    Main orchestration function to generate all certificates (CLI version).
    
    Args:
        csv_path: Path to CSV file with certificate data
        template_id: Google Slides template ID
        output_folder: Path to output folder
        credentials_path: Path to service account credentials
        cleanup: If True, delete temp slides after success
        
    Returns:
        Dict with summary: {total, success, failed, skipped, errors}
    """
    from utils import ensure_output_folder
    
    try:
        output_folder = ensure_output_folder(output_folder)
        with output_checkpoint_lock(output_folder):
            return _generate_local_certificates(csv_path, template_id, output_folder, credentials_path, cleanup, clear_checkpoint)

    except Exception as e:
        logging.error(f"Fatal error in generate_certificates: {e}")
        return {'total': 0, 'success': 0, 'failed': 0, 'skipped': 0, 'errors': [str(e)]}


def _generate_local_certificates(csv_path, template_id, output_folder, credentials_path, cleanup, clear_checkpoint):
    slides_service, drive_service = authenticate_google(credentials_path)

    # Load and validate CSV
    csv_rows = read_csv(csv_path)

    # Detect placeholders from template
    detected_placeholders = detect_placeholders_in_slide(slides_service, template_id)

    # Validate CSV vs placeholders
    is_valid, issues = validate_csv_placeholders(csv_rows, detected_placeholders)
    if not is_valid:
        logging.error(f"CSV validation failed: {issues}")
        return {'total': 0, 'success': 0, 'failed': len(csv_rows), 'skipped': 0, 'errors': issues}

    template_metadata = _template_drive_metadata(drive_service, template_id)
    checkpoint_identity = content_digest([
        str(Path(csv_path).resolve()), csv_rows, template_id, template_metadata.get('version'),
    ])
    checkpoint = CheckpointManager(output_folder, checkpoint_identity)
    if clear_checkpoint:
        checkpoint.clear()

    # Main loop
    summary = {
        'total': len(csv_rows),
        'success': 0,
        'failed': 0,
        'skipped': 0,
        'errors': [],
    }

    from tqdm import tqdm

    for row_idx, row in tqdm(enumerate(csv_rows), total=len(csv_rows), desc="Generating certificates"):
        # Skip if already completed
        if checkpoint.is_complete(row_idx):
            summary['skipped'] += 1
            logging.debug(f"Skipping row {row_idx}: already completed")
            continue

        temp_slide_id = None
        try:
            filename = safe_filename(str(row.get('Name', f'certificate_{row_idx}')), max_bytes=200)
            planned_output = checkpoint.plan_output(row_idx, filename)
            temp_slide_id = duplicate_slide_template(
                drive_service, template_id, row_idx, template_metadata=template_metadata
            )

            # Prepare replacements (convert all values to strings, case-insensitive matching)
            replacements = {}
            for k, v in row.items():
                if k.lower() in detected_placeholders:
                    replacements[k.lower()] = str(v)

            # Replace text
            if not replace_text_in_slide(slides_service, temp_slide_id, replacements):
                raise Exception("Text replacement failed")

            # Export to PDF
            if not export_slide_to_pdf(
                drive_service, temp_slide_id, output_folder, Path(planned_output).stem
            ):
                raise Exception("PDF export failed")

            # Mark complete
            checkpoint.mark_complete(row_idx, temp_slide_id)
            summary['success'] += 1

        except Exception as e:
            error_msg = f"Row {row_idx}: {str(e)}"
            logging.error(error_msg)
            summary['failed'] += 1
            summary['errors'].append(error_msg)
        finally:
            if cleanup and temp_slide_id and not checkpoint.is_complete(row_idx):
                delete_temp_slide(drive_service.files(), temp_slide_id)

    if cleanup and checkpoint.temp_slide_ids:
        for row_key in cleanup_temp_slides(drive_service, checkpoint.temp_slide_ids):
            del checkpoint.temp_slide_ids[row_key]
        checkpoint.save()

    # Log summary
    logging.info(
        f"Certificate generation complete: "
        f"{summary['success']} success, {summary['failed']} failed, {summary['skipped']} skipped"
    )

    return summary
