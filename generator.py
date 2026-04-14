"""
Core certificate generation logic.
Handles Google API interactions, template copying, text replacement, and PDF export.
"""

import logging
import time
from typing import Dict, List, Tuple, Set
from pathlib import Path

from google.oauth2.service_account import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
import pandas as pd
from io import BytesIO
import io

import config
from utils import CheckpointManager, safe_filename


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


def detect_placeholders_in_slide(slides_service, presentation_id: str) -> Set[str]:
    """
    Detect all {{Placeholder}} patterns in a presentation.
    Handles Canva-imported PPTX files where text may be split across
    multiple text runs (e.g., '{{', 'Name', '}}' as separate runs).
    
    Args:
        slides_service: Google Slides API service
        presentation_id: ID of the presentation
        
    Returns:
        Set of unique placeholder names (without curly braces)
        
    Example:
        Returns: {'Name', 'Email', 'Date'}
    """
    try:
        presentation = slides_service.presentations().get(
            presentationId=presentation_id
        ).execute()
        
        placeholders = set()
        
        def extract_from_text_elements(text_elements):
            """Concatenate all text runs then search for placeholders."""
            # First try individual runs
            for text_elem in text_elements:
                text = text_elem.get('textRun', {}).get('content', '')
                matches = config.PLACEHOLDER_PATTERN.findall(text)
                placeholders.update(matches)
            
            # Also concatenate all runs and search (handles split text)
            full_text = ''.join(
                elem.get('textRun', {}).get('content', '')
                for elem in text_elements
            )
            matches = config.PLACEHOLDER_PATTERN.findall(full_text)
            placeholders.update(matches)
        
        for slide in presentation.get('slides', []):
            for element in slide.get('pageElements', []):
                # Check shapes (includes text boxes in Slides API)
                if 'shape' in element:
                    text_elems = element['shape'].get('text', {}).get('textElements', [])
                    if not text_elems:
                        # Fallback: some older structures
                        text_elems = element['shape'].get('textElements', [])
                    extract_from_text_elements(text_elems)
                
                # Check textBox (rare, but possible)
                if 'textBox' in element:
                    text_elems = element['textBox'].get('text', {}).get('textElements', [])
                    if not text_elems:
                        text_elems = element['textBox'].get('textElements', [])
                    extract_from_text_elements(text_elems)
                
                # Check tables
                if 'table' in element:
                    table = element['table']
                    for row in table.get('tableRows', []):
                        for cell in row.get('tableCells', []):
                            text_elems = cell.get('text', {}).get('textElements', [])
                            if not text_elems:
                                text_elems = cell.get('textElements', [])
                            extract_from_text_elements(text_elems)
        
        # Normalize placeholders to lowercase for case-insensitive matching
        normalized_placeholders = {p.lower() for p in placeholders}
        logging.info(f"Detected placeholders: {normalized_placeholders}")
        return normalized_placeholders
        
    except Exception as e:
        logging.error(f"Failed to detect placeholders: {e}")
        raise


def read_csv(file_path: str) -> List[Dict]:
    """
    Read CSV file and return as list of dictionaries.
    
    Args:
        file_path: Path to CSV file
        
    Returns:
        List of dicts, one per row
        
    Raises:
        FileNotFoundError: If CSV file not found
        ValueError: If CSV is invalid or empty
    """
    try:
        df = pd.read_csv(file_path)
        
        if df.empty:
            raise ValueError("CSV file is empty")
        
        rows = df.to_dict(orient='records')
        logging.info(f"Loaded CSV with {len(rows)} rows and columns: {list(df.columns)}")
        
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


def duplicate_slide_template(drive_service, template_id: str, row_index: int) -> str:
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
        original = drive_service.files().get(
            fileId=template_id,
            fields='name, parents'
        ).execute()
        
        # Create copy with unique name
        copy_name = f"{original['name']}_cert_{row_index}_{int(time.time())}"
        copy_metadata = {
            'name': copy_name,
            'parents': original.get('parents', []),
        }
        
        copied_file = drive_service.files().copy(
            fileId=template_id,
            body=copy_metadata
        ).execute()
        
        new_id = copied_file['id']
        logging.debug(f"Duplicated template to new presentation: {new_id}")
        
        return new_id
        
    except Exception as e:
        logging.error(f"Failed to duplicate template: {e}")
        raise


def replace_text_in_slide(slides_service, presentation_id: str, replacements: Dict[str, str]) -> bool:
    """
    Replace all {{Placeholder}} with values from replacements dict.
    Handles Canva-imported templates where placeholder text may be split
    across multiple text runs (e.g., '{{', 'Name', '}}' as separate runs).
    
    Strategy:
      1. Try the standard findReplace API first.
      2. If findReplace reports 0 occurrences replaced, fall back to manual
         run-level text manipulation that handles split runs.
    
    Args:
        slides_service: Google Slides API service
        presentation_id: ID of presentation to update
        replacements: Dict mapping placeholder names to values
        
    Returns:
        True if successful, False otherwise
        
    Example:
        replacements = {'Name': 'John Doe', 'Email': 'john@example.com'}
    """
    import re

    if not replacements:
        logging.warning(f"No replacements to make for presentation {presentation_id}")
        return True

    try:
        # ── Step 1: Try standard findReplace first ──────────────────────
        requests = []
        for placeholder, value in replacements.items():
            find_text = f"{{{{{placeholder}}}}}"
            requests.append({
                'replaceAllText': {
                    'containsText': {
                        'text': find_text,
                        'matchCase': False,
                    },
                    'replaceText': str(value),
                }
            })

        body = {'requests': requests}
        response = slides_service.presentations().batchUpdate(
            presentationId=presentation_id,
            body=body
        ).execute()

        # Check how many occurrences were actually replaced
        total_replaced = 0
        for reply in response.get('replies', []):
            total_replaced += reply.get('replaceAllText', {}).get('occurrencesChanged', 0)

        if total_replaced > 0:
            logging.debug(
                f"findReplace replaced {total_replaced} occurrences in {presentation_id}"
            )
            return True

        logging.info(
            f"findReplace found 0 occurrences in {presentation_id} — "
            "falling back to manual run-level replacement"
        )

        # ── Step 2: Manual run-level replacement for split runs ─────────
        return _replace_text_manual(slides_service, presentation_id, replacements)

    except Exception as e:
        logging.error(f"Failed to replace text in presentation: {e}")
        return False


def _replace_text_manual(
    slides_service, presentation_id: str, replacements: Dict[str, str]
) -> bool:
    """
    Fallback replacement that handles placeholders split across multiple
    Google Slides text runs.

    Algorithm per text element (shape / textBox / table cell):
      1. Concatenate all runs into one string.
      2. Search for {{Placeholder}} patterns.
      3. For each match, map the character range back to the original runs,
         build deleteText + insertText requests with correct indices.
    """
    import re

    try:
        presentation = slides_service.presentations().get(
            presentationId=presentation_id
        ).execute()

        all_requests: list = []

        def _process_text_element(page_element_id: str, text_elements: list):
            """Process a single text element and collect replacement requests."""
            # Build a map: for each character position in the concatenated text,
            # record the cumulative start index of each run (in Slides coordinates).
            runs = []
            for te in text_elements:
                tr = te.get('textRun')
                if tr is None:
                    continue
                content = tr.get('content', '')
                start_index = te.get('startIndex', 0)
                end_index = te.get('endIndex', start_index + len(content))
                runs.append({
                    'content': content,
                    'startIndex': start_index,
                    'endIndex': end_index,
                })

            if not runs:
                return

            full_text = ''.join(r['content'] for r in runs)

            # Build char-position → slides-index mapping
            char_to_slides_index = []
            for run in runs:
                for i in range(len(run['content'])):
                    char_to_slides_index.append(run['startIndex'] + i)

            for placeholder, value in replacements.items():
                # Use case-insensitive regex to find placeholders
                pattern = r'\{\{' + re.escape(placeholder) + r'\}\}'
                matches = list(re.finditer(pattern, full_text, re.IGNORECASE))
                
                for match in matches:
                    idx = match.start()
                    match_len = match.end() - match.start()

                    # Map char range back to Slides startIndex / endIndex
                    slides_start = char_to_slides_index[idx]
                    slides_end_char = idx + match_len - 1
                    if slides_end_char < len(char_to_slides_index):
                        slides_end = char_to_slides_index[slides_end_char] + 1
                    else:
                        slides_end = runs[-1]['endIndex']

                    # Delete the placeholder characters, then insert value
                    all_requests.append({
                        'deleteText': {
                            'objectId': page_element_id,
                            'textRange': {
                                'type': 'FIXED_RANGE',
                                'startIndex': slides_start,
                                'endIndex': slides_end,
                            }
                        }
                    })
                    all_requests.append({
                        'insertText': {
                            'objectId': page_element_id,
                            'insertionIndex': slides_start,
                            'text': str(value),
                        }
                    })

                    # Only handle first occurrence per element to avoid
                    # index-shifting issues; re-read would be needed for
                    # multiple occurrences in the same element.
                    break

        # Walk every page element on every slide
        for slide in presentation.get('slides', []):
            for element in slide.get('pageElements', []):
                eid = element.get('objectId')

                if 'shape' in element:
                    text_elems = element['shape'].get('text', {}).get('textElements', [])
                    _process_text_element(eid, text_elems)

                elif 'textBox' in element:
                    text_elems = element['textBox'].get('text', {}).get('textElements', [])
                    _process_text_element(eid, text_elems)

                elif 'table' in element:
                    table = element['table']
                    for row in table.get('tableRows', []):
                        for cell in row.get('tableCells', []):
                            cell_text_elems = cell.get('text', {}).get('textElements', [])
                            # Table cells reference by objectId + cell location
                            _process_text_element(eid, cell_text_elems)

        if not all_requests:
            logging.warning(
                f"Manual replacement also found no placeholders in {presentation_id}"
            )
            return True

        # Execute all delete + insert requests in one batch
        slides_service.presentations().batchUpdate(
            presentationId=presentation_id,
            body={'requests': all_requests}
        ).execute()

        logging.info(
            f"Manual replacement made {len(all_requests)} operations in {presentation_id}"
        )
        return True

    except Exception as e:
        logging.error(f"Manual text replacement failed for {presentation_id}: {e}")
        return False


def export_slide_to_pdf(drive_service, presentation_id: str, output_folder: str, filename: str) -> bool:
    """
    Export a presentation as PDF and save to output folder.
    
    Args:
        drive_service: Google Drive API service
        presentation_id: ID of presentation to export
        output_folder: Path to output folder
        filename: Name for output file (without extension)
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Use Google Drive's native export to PDF
        export_url = (
            f"https://www.googleapis.com/drive/v3/files/{presentation_id}/export"
            f"?mimeType={config.PDF_MIME_TYPE}&key={''}"  # Key handled by service account auth
        )
        
        # Direct download via Drive API
        request = drive_service.files().export_media(
            fileId=presentation_id,
            mimeType=config.PDF_MIME_TYPE
        )
        
        file_io = BytesIO()
        downloader = MediaIoBaseDownload(file_io, request)
        
        done = False
        while not done:
            status, done = downloader.next_chunk()
        
        # Save to file
        safe_name = safe_filename(filename)
        pdf_path = Path(output_folder) / f"{safe_name}.pdf"
        
        with open(pdf_path, 'wb') as f:
            f.write(file_io.getvalue())
        
        logging.info(f"Exported PDF: {pdf_path}")
        return True
        
    except Exception as e:
        logging.error(f"Failed to export PDF for {presentation_id}: {e}")
        return False


def cleanup_temp_slides(drive_service, temp_slide_ids: Dict[int, str]) -> None:
    """
    Delete temporary slide copies from Google Drive.
    
    Args:
        drive_service: Google Drive API service
        temp_slide_ids: Dict of row_index -> slide_id
    """
    if not temp_slide_ids:
        return
    
    deleted_count = 0
    for row_idx, slide_id in temp_slide_ids.items():
        try:
            drive_service.files().delete(fileId=slide_id).execute()
            deleted_count += 1
            logging.debug(f"Deleted temp slide {slide_id}")
        except Exception as e:
            logging.warning(f"Failed to delete temp slide {slide_id}: {e}")
    
    logging.info(f"Cleanup complete: deleted {deleted_count} temporary slides")


def generate_certificates_oauth2(
    csv_content: str,
    template_id: str,
    output_folder: str,
    user_credentials,
    filename_field: str = 'Name'
) -> Dict:
    """
    Generate certificates using user's OAuth2 credentials.
    Certificates are saved to user's Google Drive in specified folder.
    
    Args:
        csv_content: CSV content as string (from file upload)
        template_id: Google Slides template ID
        output_folder: Drive folder name to save certificates
        user_credentials: OAuth2 credentials object from user
        filename_field: CSV column name to use for certificate filenames (default: 'Name')
        
    Returns:
        Dict with summary: {total, success, failed, skipped, errors}
    """
    import io
    
    try:
        # Build services with user's credentials
        slides_service = build(
            'slides',
            config.SLIDES_API_VERSION,
            credentials=user_credentials
        )
        drive_service = build(
            'drive',
            config.DRIVE_API_VERSION,
            credentials=user_credentials
        )
        
        logging.info("Authenticated with user's Google account")
        
        # Parse CSV from string
        csv_file = io.StringIO(csv_content)
        df = pd.read_csv(csv_file)
        
        if df.empty:
            raise ValueError("CSV is empty")
        
        csv_rows = df.to_dict(orient='records')
        logging.info(f"Loaded CSV with {len(csv_rows)} rows")
        
        # Detect placeholders from template
        detected_placeholders = detect_placeholders_in_slide(slides_service, template_id)
        
        # Validate CSV vs placeholders
        is_valid, issues = validate_csv_placeholders(csv_rows, detected_placeholders)
        if not is_valid:
            logging.error(f"CSV validation failed: {issues}")
            return {'total': 0, 'success': 0, 'failed': len(csv_rows), 'skipped': 0, 'errors': issues}
        
        # Find or create output folder in Drive
        folder_id = _find_or_create_drive_folder(drive_service, output_folder)
        
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
            try:
                # Get filename from specified column (case-insensitive)
                filename_value = None
                for key in row.keys():
                    if key.lower() == filename_field.lower():
                        filename_value = str(row[key])
                        break
                
                if filename_value is None:
                    filename_value = f'certificate_{row_idx}'
                
                filename = filename_value
                
                # Duplicate template
                temp_slide_id = duplicate_slide_template(drive_service, template_id, row_idx)
                
                # Prepare replacements
                replacements = {k: str(v) for k, v in row.items() if k in detected_placeholders}
                
                # Replace text
                if not replace_text_in_slide(slides_service, temp_slide_id, replacements):
                    raise Exception("Text replacement failed")
                
                # Export to PDF and save to folder
                if not export_slide_to_pdf_drive(drive_service, temp_slide_id, filename, folder_id):
                    raise Exception("PDF export failed")
                
                # Cleanup temp slide
                try:
                    drive_service.files().delete(fileId=temp_slide_id).execute()
                    logging.debug(f"Deleted temp slide {temp_slide_id}")
                except Exception as e:
                    logging.warning(f"Failed to delete temp slide: {e}")
                
                summary['success'] += 1
            
            except Exception as e:
                error_msg = f"Row {row_idx}: {str(e)}"
                logging.error(error_msg)
                summary['failed'] += 1
                summary['errors'].append(error_msg)
        
        logging.info(
            f"Certificate generation complete: "
            f"{summary['success']} success, {summary['failed']} failed"
        )
        
        return summary
    
    except Exception as e:
        logging.error(f"Fatal error in generate_certificates_oauth2: {e}")
        return {'total': 0, 'success': 0, 'failed': 0, 'skipped': 0, 'errors': [str(e)]}


def _find_or_create_drive_folder(drive_service, folder_name: str) -> str:
    """
    Find existing folder in Drive or create it.
    Returns folder ID.
    """
    try:
        # Search for folder
        query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        results = drive_service.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name)',
            pageSize=10
        ).execute()
        
        files = results.get('files', [])
        if files:
            logging.info(f"Found existing folder: {files[0]['id']}")
            return files[0]['id']
        
        # Create new folder
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        folder = drive_service.files().create(body=file_metadata, fields='id').execute()
        folder_id = folder.get('id')
        logging.info(f"Created new folder: {folder_id}")
        
        return folder_id
    
    except Exception as e:
        logging.error(f"Failed to manage Drive folder: {e}")
        raise


def export_slide_to_pdf_drive(
    drive_service,
    presentation_id: str,
    filename: str,
    output_folder_id: str
) -> bool:
    """
    Export slide to PDF and save directly to Drive folder.
    
    Args:
        drive_service: Google Drive API service
        presentation_id: ID of presentation to export
        filename: Name for output file
        output_folder_id: Google Drive folder ID where to save
        
    Returns:
        True if successful
    """
    try:
        # Export to PDF
        request = drive_service.files().export_media(
            fileId=presentation_id,
            mimeType=config.PDF_MIME_TYPE
        )
        
        file_io = BytesIO()
        downloader = MediaIoBaseDownload(file_io, request)
        
        done = False
        while not done:
            status, done = downloader.next_chunk()
        
        pdf_content = file_io.getvalue()
        
        # Upload to Drive folder
        safe_name = safe_filename(filename)
        file_metadata = {
            'name': f'{safe_name}.pdf',
            'parents': [output_folder_id]
        }
        
        media = MediaIoBaseUpload(
            io.BytesIO(pdf_content),
            mimetype=config.PDF_MIME_TYPE,
            resumable=True
        )
        
        file_obj = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        
        logging.info(f"Saved PDF to Drive: {file_obj['id']}")
        return True
    
    except Exception as e:
        logging.error(f"Failed to export PDF to Drive: {e}")
        return False


def generate_certificates(
    csv_path: str,
    template_id: str,
    output_folder: str,
    credentials_path: str = config.DEFAULT_CREDENTIALS_PATH,
    cleanup: bool = False
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
        # Setup
        output_folder = ensure_output_folder(output_folder)
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
        
        # Initialize checkpoint
        checkpoint = CheckpointManager(output_folder)
        
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
            
            try:
                # Get filename from first string column or use row index
                filename = str(row.get('Name', f'certificate_{row_idx}'))
                
                # Duplicate template
                temp_slide_id = duplicate_slide_template(drive_service, template_id, row_idx)
                
                # Prepare replacements (convert all values to strings, case-insensitive matching)
                replacements = {}
                for k, v in row.items():
                    if k.lower() in detected_placeholders:
                        replacements[k.lower()] = str(v)
                
                # Replace text
                if not replace_text_in_slide(slides_service, temp_slide_id, replacements):
                    raise Exception("Text replacement failed")
                
                # Export to PDF
                if not export_slide_to_pdf(drive_service, temp_slide_id, output_folder, filename):
                    raise Exception("PDF export failed")
                
                # Mark complete
                checkpoint.mark_complete(row_idx, temp_slide_id)
                summary['success'] += 1
                
            except Exception as e:
                error_msg = f"Row {row_idx}: {str(e)}"
                logging.error(error_msg)
                summary['failed'] += 1
                summary['errors'].append(error_msg)
        
        # Cleanup if requested
        if cleanup:
            cleanup_temp_slides(drive_service, checkpoint.temp_slide_ids)
        
        # Log summary
        logging.info(
            f"Certificate generation complete: "
            f"{summary['success']} success, {summary['failed']} failed, {summary['skipped']} skipped"
        )
        
        return summary
        
    except Exception as e:
        logging.error(f"Fatal error in generate_certificates: {e}")
        return {'total': 0, 'success': 0, 'failed': 0, 'skipped': 0, 'errors': [str(e)]}
