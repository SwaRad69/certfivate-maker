"""
Flask web application for Certificate Generator with OAuth2 authentication.
Users sign in with their Google account and generate certificates to their Drive.
"""

import os
import json
import logging
import re
from functools import wraps
from datetime import datetime
from pathlib import Path
from io import BytesIO

# Allow OAuth over HTTP for local development only
# Set to '1' if FLASK_ENV is 'development' or not set (default to local dev)
if os.environ.get('FLASK_ENV') in ('development', None) or os.environ.get('FLASK_ENV') != 'production':
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

from flask import Flask, g, render_template, redirect, url_for, request, session, jsonify, send_file
from itsdangerous import BadSignature, URLSafeSerializer
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request as GoogleRequest
from googleapiclient.errors import HttpError
import google.auth

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from generator import (
    PowerPointTemplate,
    generate_certificates_oauth2,
    read_web_template,
    recover_web_batch,
    reserve_web_batch,
)
from web.file_converter import (
    get_supported_formats,
    parse_rows,
    read_input_records,
    records_to_csv,
)
import config

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(
    __name__,
    template_folder='templates',
    static_folder='static'
)

# Configuration
FLASK_ENV = os.environ.get('FLASK_ENV', 'development')
if FLASK_ENV == 'production':
    app.secret_key = os.environ.get('FLASK_SECRET_KEY')
    if not app.secret_key:
        raise ValueError('FLASK_SECRET_KEY environment variable is required in production')
else:
    app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')

# Google OAuth2 configuration
GOOGLE_OAUTH_CLIENT_SECRETS = os.environ.get('GOOGLE_OAUTH_SECRETS', 'client_secrets.json')
GOOGLE_OAUTH_SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/presentations',
    'https://www.googleapis.com/auth/spreadsheets.readonly',
]

# Session configuration
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 hour


def get_flow():
    """Create and return OAuth2 flow."""
    return Flow.from_client_secrets_file(
        GOOGLE_OAUTH_CLIENT_SECRETS,
        scopes=GOOGLE_OAUTH_SCOPES,
        redirect_uri=url_for('oauth_callback', _external=True)
    )


def _save_session_credentials(creds):
    session['credentials'] = creds.to_json(strip=['client_secret'])


def _session_credentials():
    if 'google_credentials' in g:
        return g.google_credentials

    info = session['credentials']
    if isinstance(info, str):
        info = json.loads(info)
    if not isinstance(info, dict):
        raise ValueError('Invalid OAuth session credentials')
    if 'client_secret' in info:
        info = {key: value for key, value in info.items() if key != 'client_secret'}
        session['credentials'] = info
    if info.get('client_id'):
        client = get_flow().client_config
        if client.get('client_id') != info['client_id']:
            raise ValueError('The OAuth client for this session has changed')
        info = dict(info, client_secret=client['client_secret'])
    g.google_credentials = Credentials.from_authorized_user_info(info, GOOGLE_OAUTH_SCOPES)
    return g.google_credentials


def login_required(f):
    """Decorator to require user authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'credentials' not in session:
            return _login_response()
        
        # Refresh credentials if needed
        creds_data = session.get('credentials')
        if creds_data:
            try:
                creds = _session_credentials()
                
                # Check if credentials need refresh
                if creds.expired and creds.refresh_token:
                    creds.refresh(GoogleRequest())
                    _save_session_credentials(creds)
            except RefreshError as error:
                if error.retryable:
                    return jsonify({'error': 'Google sign-in is temporarily unavailable. Try again.'}), 503
                session.clear()
                return _login_response()
            except ValueError:
                session.clear()
                return _login_response()
        
        return f(*args, **kwargs)
    
    return decorated_function


def _login_response():
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Sign in to the certificate maker again and retry.'}), 401
    return redirect(url_for('login'))


@app.route('/')
def index():
    """Landing page - shown to unauthenticated users."""
    if 'credentials' in session:
        return redirect(url_for('dashboard'))
    
    # YouTube embed code
    youtube_embed = '<iframe width="100%" height="400" src="https://www.youtube.com/embed/gqEz11eXf_A?si=a2FCw2tbD4Gqgamu" title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" referrerpolicy="strict-origin-when-cross-origin" allowfullscreen style="border-radius: 10px;"></iframe>'
    
    return render_template('landing.html', youtube_embed=youtube_embed)


@app.route('/login')
def login():
    """Initiate Google OAuth2 login."""
    flow = get_flow()
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'  # Force consent screen to get refresh token
    )
    session['oauth_state'] = state
    # Store code_verifier to recover in callback (for PKCE)
    session['oauth_code_verifier'] = flow.code_verifier
    return redirect(authorization_url)


@app.route('/auth/callback')
def oauth_callback():
    """Handle OAuth2 callback from Google."""
    # Verify state for security
    state = request.args.get('state')
    if not state or state != session.get('oauth_state'):
        logger.error("OAuth state mismatch")
        return jsonify({'error': 'Invalid state parameter'}), 400
    
    # Get authorization code
    code = request.args.get('code')
    if not code:
        error = request.args.get('error', 'unknown')
        logger.error(f"OAuth error: {error}")
        return jsonify({'error': f'OAuth error: {error}'}), 400
    
    try:
        # Recreate flow and restore code_verifier for PKCE
        flow = get_flow()
        flow.code_verifier = session.get('oauth_code_verifier')
        
        # Use the full authorization response URL
        flow.fetch_token(authorization_response=request.url)
        creds = flow.credentials
        
        # Store credentials in session
        _save_session_credentials(creds)
        session.permanent = True
        
        # Get user info
        from googleapiclient.discovery import build
        drive_service = build('drive', 'v3', credentials=creds)
        about = drive_service.about().get(fields='user').execute()
        session['user_email'] = about['user']['emailAddress']
        session['user_name'] = about['user'].get('displayName', 'User')
        
        logger.info(f"User logged in: {session['user_email']}")
        
        return redirect(url_for('dashboard'))
    
    except Exception as e:
        logger.error(f"Error during OAuth callback: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/dashboard')
@login_required
def dashboard():
    """Main dashboard after login."""
    return render_template('dashboard.html', user_email=session.get('user_email'))


@app.route('/api/supported-formats')
@login_required
def api_supported_formats():
    """Get list of supported file formats."""
    formats = get_supported_formats()
    return jsonify({
        'formats': formats,
        'supported_extensions': list(formats.keys())
    })


@app.route('/api/upload/columns', methods=['POST'])
@login_required
def api_upload_columns():
    """Return the column names used by generation for an uploaded file."""
    uploaded_file = request.files.get('csv_file')
    if not uploaded_file or not uploaded_file.filename:
        return jsonify({'error': 'Choose a data file to upload.'}), 400
    try:
        headers, _ = read_input_records(uploaded_file.read(), uploaded_file.filename)
    except ValueError as error:
        return jsonify({'error': str(error)}), 400
    return jsonify({'headers': headers})


@app.route('/api/drive/file/<file_id>/csv', methods=['GET'])
@login_required
def api_drive_file_to_csv(file_id):
    """Download a file from Google Drive and convert to CSV."""
    try:
        # Get user credentials
        creds = _session_credentials()
        
        # Refresh credentials if needed
        if creds.expired and creds.refresh_token:
            creds.refresh(GoogleRequest())
            _save_session_credentials(creds)
        
        # Get Drive API service
        from googleapiclient.discovery import build
        drive_service = build('drive', 'v3', credentials=creds)
        
        logger.info(f"Downloading file {file_id} from Drive")
        
        # Get file metadata
        file_info = drive_service.files().get(
            fileId=file_id,
            fields='id,name,mimeType,trashed',
            supportsAllDrives=True,
        ).execute()
        
        if file_info.get('trashed'):
            return jsonify({'error': 'This file has been deleted'}), 410
        
        filename = file_info.get('name', 'file')
        mime_type = file_info.get('mimeType', '')
        
        logger.info(f"File info: {filename}, MIME type: {mime_type}")
        
        # Download file content
        request = drive_service.files().get_media(fileId=file_id, supportsAllDrives=True)
        file_bytes = request.execute()
        
        # Use the same headers and records that generation reads.
        try:
            headers, records = read_input_records(file_bytes, filename)
        except ValueError as e:
            return jsonify({'error': str(e)}), 400
        
        logger.info(f"Successfully converted {filename} to CSV ({len(records)} data rows)")
        
        return jsonify({
            'csv_content': records_to_csv(headers, records),
            'filename': filename,
            'headers': headers,
            'rows': [list(record.values()) for record in records[:5]],
            'rows_count': len(records),
            'mime_type': mime_type
        }), 200
        
    except Exception as e:
        error_str = str(e)
        logger.error(f"Error downloading file {file_id}: {error_str}")
        
        if '404' in error_str or 'not found' in error_str.lower():
            return jsonify({'error': 'File not found. It may have been deleted.'}), 404
        elif '403' in error_str or 'permission' in error_str.lower():
            return jsonify({'error': 'You do not have permission to access this file'}), 403
        else:
            return jsonify({'error': f'Failed to download file: {error_str}'}), 500


def _extract_template_id(value):
    if isinstance(value, str):
        value = value.strip()
        match = re.fullmatch(
            r'https://docs\.google\.com/presentation/(?:u/[0-9]+/)?d/'
            r'([A-Za-z0-9_-]+)(?:[/?#]\S*)?',
            value,
        )
        template_id = match[1] if match else value
        if re.fullmatch(r'[A-Za-z0-9_-]{20,}', template_id):
            return template_id
    raise ValueError('Select a Google Slides template or paste its link or file ID.')


@app.route('/api/drive/templates')
@login_required
def api_drive_templates():
    """List one page of Google Slides presentations for the template chooser."""
    return _list_drive_files(
        f"mimeType = '{config.SLIDES_MIME_TYPE}'",
        'Could not list presentations in Google Drive. Try again or paste a Slides link.',
    )


@app.route('/api/drive/recipient-files')
@login_required
def api_drive_recipient_files():
    """List one page of Google Sheets and CSV files for the recipient chooser."""
    return _list_drive_files(
        "mimeType = 'application/vnd.google-apps.spreadsheet' or mimeType = 'text/csv' "
        "or mimeType = 'application/csv' or mimeType = 'application/vnd.ms-excel'",
        'Could not list recipient files in Google Drive. Try again or upload a file.',
        csv_only_for_excel=True,
    )


def _list_drive_files(file_filter, failure_message, *, csv_only_for_excel=False):
    from googleapiclient.discovery import build

    try:
        drive = build('drive', config.DRIVE_API_VERSION, credentials=_session_credentials())
        result = drive.files().list(
            q=f'trashed = false and ({file_filter})',
            spaces='drive',
            corpora='user',
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
            orderBy='modifiedTime desc',
            fields='nextPageToken,files(id,name,mimeType)',
            pageSize=100,
            pageToken=request.args.get('page_token'),
        ).execute()
        files = result.get('files', [])
        if csv_only_for_excel:
            files = [
                file for file in files
                if file['mimeType'] != 'application/vnd.ms-excel' or file['name'].lower().endswith('.csv')
            ]
        return jsonify({'files': files, 'next_page_token': result.get('nextPageToken')})
    except HttpError as error:
        logger.warning('Unable to list Drive files: %s', error)
        if error.resp.status == 401:
            return _login_response()
        return jsonify({'error': failure_message}), 502


@app.route('/api/template/placeholders', methods=['POST'])
@login_required
def get_template_placeholders():
    """Read the template and return available certificate filename fields."""
    from googleapiclient.discovery import build

    try:
        data = request.get_json(silent=True)
        template_id = _extract_template_id(data.get('template_id') if isinstance(data, dict) else None)
        creds = _session_credentials()
        drive = build('drive', config.DRIVE_API_VERSION, credentials=creds)
        slides = build('slides', config.SLIDES_API_VERSION, credentials=creds)
        _, placeholders = read_web_template(drive, slides, template_id)
        return jsonify({
            'success': True,
            'placeholders': sorted(placeholders),
            'message': 'Select which field to use for certificate filenames',
        })
    except ValueError as error:
        return jsonify({'error': str(error)}), 400
    except Exception:
        logger.exception('Unable to read Google Slides template')
        return jsonify({'error': 'Could not read the Google Slides template. Try again.'}), 502


def generation_response(summary, input_rows=None, output_folder=None):
    """Return a generation outcome and its row/PDF counts."""
    summary = dict(summary)
    successful = summary.get('successful_rows', summary.get('success', 0))
    failed = summary.get('failed_rows', summary.get('failed', 0))
    attempted = summary.get('attempted_rows', successful + failed)
    created = summary.get('created_pdfs', successful)
    pending = summary.get('pending_rows', 0)
    selected = summary.get('total', attempted + pending)
    errors = summary.get('errors', [])
    summary.update(
        total=selected,
        success=successful,
        failed=failed,
        skipped=summary.get('skipped', 0),
        errors=errors,
        input_rows=summary.get('input_rows', selected) if input_rows is None else input_rows,
        attempted_rows=attempted,
        successful_rows=successful,
        failed_rows=failed,
        created_pdfs=created,
        pending_rows=pending,
    )

    if summary.get('validation_failed'):
        status, code = 'invalid_request', 400
        message = errors[0] if errors else 'The generation request is invalid.'
    elif pending:
        status, code = 'pending', 202
        if summary.get('interrupted'):
            message = f'{created} PDFs saved. Resume Batch to continue with the {pending} remaining rows.'
        else:
            message = f'{created} PDFs saved. {pending} rows are still pending.'
    elif not created:
        status, code = 'failed', 500
        message = 'Generation failed. No PDFs were created.'
    elif failed or successful < selected:
        status, code = 'partial', 200
        message = f'{created} PDFs saved. Some certificates could not be generated.'
    else:
        status, code = 'completed', 200
        message = f'Generated {created} certificates successfully.'

    destination_error = summary.get('destination_error')
    if destination_error:
        message = destination_error
    result = {'success': status == 'completed', 'status': status, 'message': message, 'summary': summary}
    if code >= 400:
        result['error'] = destination_error or (errors[0] if errors else message)
    if summary.get('batch_id'):
        result['batch_id'] = summary['batch_id']
    if output_folder is not None:
        result['output_folder'] = output_folder
    return jsonify(result), code


def invalid_generation_response(message, input_rows=0):
    return generation_response({'validation_failed': True, 'errors': [message]}, input_rows=input_rows)


def _batch_signer():
    return URLSafeSerializer(
        app.secret_key, salt=f"certificate-generation:{session.get('user_email', '')}"
    )


@app.route('/api/generation-batches/new')
@login_required
def api_reserve_generation_batch():
    """Reserve a retry key before the client starts the generation request."""
    try:
        batch_id = reserve_web_batch(_session_credentials())
        response = jsonify({'batch_id': _batch_signer().dumps(batch_id)})
        response.headers['Cache-Control'] = 'no-store'
        return response
    except Exception:
        logger.exception("Could not reserve a generation batch")
        return jsonify({'error': 'Could not reserve a generation batch in Google Drive.'}), 502


@app.route('/api/generation-batches/<token>')
@login_required
def api_recover_generation_batch(token):
    """Recover a result using the same signed key after an interrupted request."""
    try:
        batch_id = _batch_signer().loads(token)
    except BadSignature:
        return invalid_generation_response('Invalid generation batch ID.')
    try:
        summary = recover_web_batch(_session_credentials(), batch_id)
        if summary is None:
            return jsonify({'error': 'This generation batch has not started.'}), 404
        summary['batch_id'] = token
        response, status = generation_response(summary, output_folder=summary['output_folder'])
        response.headers['Cache-Control'] = 'no-store'
        return response, status
    except Exception:
        logger.exception("Could not recover the generation batch")
        return jsonify({'error': 'Could not recover generation results from Google Drive.'}), 502


@app.route('/api/generate', methods=['POST'])
@login_required
def api_generate():
    """Generate certificates from recipient data and a Slides or PowerPoint template."""
    try:
        # Get credentials from session
        creds_data = session.get('credentials')
        if not creds_data:
            return jsonify({'error': 'Not authenticated'}), 401
        
        creds = _session_credentials()
        
        # Refresh if needed
        if creds.expired and creds.refresh_token:
            creds.refresh(GoogleRequest())
            _save_session_credentials(creds)
        
        output_folder = request.form.get('output_folder', '').strip() or 'Certificate Generator'
        filename_field = request.form.get('filename_field') or 'Name'
        batch_token = request.form.get('batch_id', '').strip()
        batch_id = None
        if batch_token:
            try:
                batch_id = _batch_signer().loads(batch_token)
            except BadSignature:
                return invalid_generation_response('Invalid generation batch ID.')

        slides_input = request.form.get('template_id', '').strip()
        template_files = [file for file in request.files.getlist('template_file') if file.filename]
        use_powerpoint = bool(template_files) or request.form.get('template_source') == 'powerpoint'
        if len(template_files) > 1 or (slides_input and use_powerpoint):
            return invalid_generation_response('Choose one template: a Google Slides presentation or one PowerPoint file.')
        template_id = None
        powerpoint_template = None
        try:
            if template_files:
                file = template_files[0]
                powerpoint_template = PowerPointTemplate.from_upload(file.filename, file.stream)
            elif use_powerpoint:
                if not batch_id:
                    raise ValueError('Choose a .pptx or .ppt template to upload.')
            else:
                template_id = _extract_template_id(slides_input)
        except ValueError as error:
            return invalid_generation_response(str(error))

        uploads = [file for file in request.files.getlist('csv_file') if file.filename]
        has_sheets = bool(
            request.form.get('sheets_id')
            or request.form.get('sheets_url')
            or request.form.get('sheet_name')
        )
        if len(uploads) + has_sheets != 1:
            return invalid_generation_response('Provide exactly one data source: an uploaded or Drive file, or a Google Sheets tab')

        if uploads:
            uploaded_file = uploads[0]
            try:
                _, records = read_input_records(uploaded_file.read(), uploaded_file.filename)
            except ValueError as e:
                supported = ', '.join(get_supported_formats())
                return invalid_generation_response(f'{e}. Supported formats: {supported}')
        else:
            try:
                sheet_id, sheet_name = _sheet_selection(request.form)
            except ValueError as e:
                return invalid_generation_response(str(e))
            try:
                _, records = _read_sheet_records(creds, sheet_id, sheet_name)
            except Exception as e:
                logger.exception("Error reading Google Sheets")
                return generation_response({'errors': [f'Failed to read Google Sheets: {e}']})

        input_rows = len(records)
        if not input_rows:
            return invalid_generation_response('The selected source has no data rows')

        if request.form.get('test_mode', '').lower() == 'true':
            try:
                test_count = int(request.form.get('test_count', 10))
            except ValueError:
                test_count = 0
            if test_count < 1:
                return invalid_generation_response('First N must be a positive whole number', input_rows=input_rows)
            records = records[:test_count]
            output_folder = f"{output_folder} (TEST)"
            logger.info("Test mode enabled: limiting to %d certificates", test_count)

        try:
            # Generate certificates with user's credentials
            logger.info(f"Starting certificate generation for {session.get('user_email', 'unknown')}")
            logger.info("  Template: %s", template_id or 'PowerPoint upload')
            logger.info(f"  Output folder: {output_folder}")
            
            summary = generate_certificates_oauth2(
                csv_content=None,
                template_id=template_id,
                output_folder=output_folder,
                user_credentials=creds,
                filename_field=filename_field,
                group_by_column=request.form.get('group_by_column', ''),
                records=records,
                input_rows=input_rows,
                batch_id=batch_id,
                retry_failed=request.form.get('retry_failed') == 'true',
                powerpoint_template=powerpoint_template,
            )
            if batch_token:
                summary['batch_id'] = batch_token
            
            logger.info("Generation request finished with %s PDFs and %s failed rows",
                        summary.get('created_pdfs', summary.get('success', 0)), summary.get('failed', 0))
            
            return generation_response(summary, input_rows=input_rows, output_folder=output_folder)
        
        except ValueError as e:
            # Validation errors
            logger.warning(f"Validation error: {e}")
            return invalid_generation_response(str(e), input_rows=input_rows)
        
        except Exception as e:
            # Other errors
            logger.error(f"Generation error: {e}", exc_info=True)
            return generation_response({'errors': [str(e)], 'batch_id': batch_token}, input_rows=input_rows)
    
    except Exception as e:
        logger.error(f"API error: {e}", exc_info=True)
        return generation_response({'errors': ['Internal server error']})


@app.route('/logout')
def logout():
    """Logout user and clear session."""
    session.clear()
    logger.info("User logged out")
    return redirect(url_for('index'))


@app.route('/help')
def help():
    """Help page with instructions."""
    return render_template('help.html')


@app.route('/api/user')
@login_required
def api_user():
    """Get current user info."""
    return jsonify({
        'email': session.get('user_email'),
        'name': session.get('user_name')
    })


@app.route('/api/auth-token')
@login_required
def api_auth_token():
    """Get OAuth access token for Google Picker API."""
    creds_data = session.get('credentials')
    if creds_data:
        creds = _session_credentials()
        return jsonify({'token': creds.token})
    
    return jsonify({'error': 'No credentials found'}), 401


# Helper function to extract sheet ID from URL
def extract_sheet_id(url):
    """Extract Google Sheets ID from URL."""
    match = re.search(r'/spreadsheets/d/([a-zA-Z0-9_-]+)(?=[/?#]|$)', url)
    if match:
        return match.group(1)
    return None


# Helper function to get Sheets API service
def get_sheets_service(credentials):
    """Get Google Sheets API service."""
    from googleapiclient.discovery import build
    return build('sheets', 'v4', credentials=credentials)


def _sheet_selection(fields):
    """Resolve the spreadsheet ID and exact tab title from a request."""
    sheet_id = fields.get('sheets_id') or ''
    url = fields.get('sheets_url') or ''
    sheet_name = fields.get('sheet_name')
    if not all(isinstance(value, str) for value in (sheet_id, url, sheet_name)):
        raise ValueError('Select a Google Sheets spreadsheet and tab')
    sheet_id, url = sheet_id.strip(), url.strip()
    if not sheet_name:
        raise ValueError('Select a Google Sheets tab')

    if sheet_id and not re.fullmatch(r'[a-zA-Z0-9_-]+', sheet_id):
        raise ValueError('Invalid Google Sheets ID')
    if url:
        url_id = extract_sheet_id(url)
        if not url_id or (sheet_id and sheet_id != url_id):
            raise ValueError('Invalid or conflicting Google Sheets URL')
        sheet_id = url_id
    if not sheet_id:
        raise ValueError('Select a Google Sheets spreadsheet')
    return sheet_id, sheet_name


def _read_sheet_records(credentials, sheet_id, sheet_name):
    """Read a whole Sheets tab using the displayed values in its cells."""
    escaped_title = sheet_name.replace("'", "''")
    sheets_service = get_sheets_service(credentials)
    result = sheets_service.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range=f"'{escaped_title}'",
        valueRenderOption='FORMATTED_VALUE',
    ).execute()
    return parse_rows(result.get('values', []))


@app.route('/api/drive/sheets', methods=['GET'])
@login_required
def api_drive_sheets():
    """List all Google Sheets in user's Drive."""
    try:
        # Get user credentials
        creds = _session_credentials()
        
        # Get Drive API service
        from googleapiclient.discovery import build
        drive_service = build('drive', 'v3', credentials=creds)
        
        # Query for Google Sheets (mimeType = spreadsheet)
        query = "mimeType='application/vnd.google-apps.spreadsheet' and trashed=false"
        results = drive_service.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name, modifiedTime)',
            pageSize=50,
            orderBy='modifiedTime desc'
        ).execute()
        
        files = results.get('files', [])
        
        return jsonify({
            'sheets': files,
            'count': len(files)
        }), 200
    
    except Exception as e:
        logger.error(f"Error listing Drive sheets: {e}")
        return jsonify({'error': f'Failed to list sheets: {str(e)}'}), 500


@app.route('/api/drive/sheets/<sheet_id>/names', methods=['GET'])
@login_required
def api_drive_sheet_names(sheet_id):
    """Get sheet names (tabs) from a Google Sheet."""
    try:
        # Validate sheet_id format (should be alphanumeric and dashes)
        if not sheet_id or len(sheet_id) < 20:
            return jsonify({'error': 'Invalid spreadsheet ID format'}), 400
        
        # Get user credentials
        creds = _session_credentials()
        
        # Refresh credentials if needed
        if creds.expired and creds.refresh_token:
            creds.refresh(GoogleRequest())
            _save_session_credentials(creds)
        
        # Get Drive API service to check file type
        from googleapiclient.discovery import build
        drive_service = build('drive', 'v3', credentials=creds)
        sheets_service = build('sheets', 'v4', credentials=creds)
        
        logger.info(f"Fetching sheet names for ID: {sheet_id}")
        
        # First, check if file exists and get its MIME type
        try:
            file_info = drive_service.files().get(
                fileId=sheet_id,
                fields='id,name,mimeType,trashed',
                supportsAllDrives=True,
            ).execute()
            
            logger.info(f"File info: {file_info}")
            
            if file_info.get('trashed'):
                return jsonify({'error': 'This spreadsheet has been deleted'}), 410
            
            mime_type = file_info.get('mimeType', '')
            if 'spreadsheet' not in mime_type:
                return jsonify({'error': f'This file is not a Google Sheet (type: {mime_type}). Please select a Google Sheets document.'}), 400
                
        except Exception as e:
            logger.error(f"Error checking file info: {e}")
            return jsonify({'error': 'Could not access this file. It may have been deleted or you do not have permission.'}), 403
        
        # Get spreadsheet metadata with explicit fields
        spreadsheet = sheets_service.spreadsheets().get(
            spreadsheetId=sheet_id,
            fields='sheets/properties'
        ).execute()
        
        sheets = spreadsheet.get('sheets', [])
        
        if not sheets:
            return jsonify({'error': 'Spreadsheet has no sheets'}), 400
        
        sheet_names = [s['properties']['title'] for s in sheets]
        logger.info(f"Found {len(sheets)} sheets: {sheet_names}")
        
        return jsonify({
            'sheets': sheets,
            'sheet_names': sheet_names
        }), 200
    
    except Exception as e:
        error_str = str(e)
        logger.error(f"Error getting sheet names for {sheet_id}: {error_str}")
        
        # Provide user-friendly error messages
        if '400' in error_str or 'invalid' in error_str.lower():
            return jsonify({'error': 'Invalid spreadsheet ID or the file cannot be accessed. Please try selecting a different Google Sheet.'}), 400
        elif '403' in error_str or 'permission' in error_str.lower():
            return jsonify({'error': 'You do not have permission to access this spreadsheet'}), 403
        else:
            return jsonify({'error': f'Failed to load sheet: {error_str}'}), 500
@login_required
def api_sheets_list():
    """List all sheets in a Google Sheets workbook."""
    try:
        data = request.get_json()
        sheets_url = data.get('sheets_url', '').strip()
        
        if not sheets_url:
            return jsonify({'error': 'No URL provided'}), 400
        
        # Extract sheet ID
        sheet_id = extract_sheet_id(sheets_url)
        if not sheet_id:
            return jsonify({'error': 'Invalid Google Sheets URL'}), 400
        
        # Get user credentials
        creds = _session_credentials()
        
        # Get sheets from workbook
        sheets_service = get_sheets_service(creds)
        spreadsheet = sheets_service.spreadsheets().get(spreadsheetId=sheet_id).execute()
        
        sheets = spreadsheet.get('sheets', [])
        
        return jsonify({'sheets': sheets}), 200
    
    except Exception as e:
        logger.error(f"Error listing sheets: {e}")
        return jsonify({'error': f'Failed to load sheets: {str(e)}'}), 500


def _sheet_records_from_request(data):
    sheet_id, sheet_name = _sheet_selection(data)
    creds = _session_credentials()
    return _read_sheet_records(creds, sheet_id, sheet_name)


@app.route('/api/sheets/preview', methods=['POST'])
@login_required
def api_sheets_preview():
    """Get preview data from a Google Sheets tab."""
    try:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({'error': 'Select a Google Sheets spreadsheet and tab'}), 400
        try:
            rows_to_show = int(data.get('rows', 5))
        except (TypeError, ValueError):
            rows_to_show = 0
        if rows_to_show < 1:
            return jsonify({'error': 'Preview row count must be a positive whole number'}), 400

        headers, records = _sheet_records_from_request(data)
        if not headers:
            return jsonify({'error': 'No data found in sheet'}), 400
        return jsonify({
            'headers': headers,
            'rows': [list(record.values()) for record in records[:rows_to_show]],
            'total_rows': len(records),
        }), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.exception("Error previewing sheet")
        return jsonify({'error': f'Failed to preview sheet: {e}'}), 500


@app.route('/api/sheets/data', methods=['POST'])
@login_required
def api_sheets_data():
    """Get all data from a Google Sheets tab in CSV format."""
    try:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({'error': 'Select a Google Sheets spreadsheet and tab'}), 400

        headers, records = _sheet_records_from_request(data)
        if not records:
            return jsonify({'error': 'Sheet has no data'}), 400
        return jsonify({
            'csv_content': records_to_csv(headers, records),
            'rows': len(records),
        }), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.exception("Error getting sheet data")
        return jsonify({'error': f'Failed to get sheet data: {e}'}), 500


@app.route('/api/template/debug', methods=['POST'])
@login_required
def api_template_debug():
    """Debug endpoint: Show what placeholders are detected in a template."""
    try:
        data = request.get_json()
        template_id = data.get('template_id', '').strip()
        
        if not template_id:
            return jsonify({'error': 'No template ID provided'}), 400
        
        # Get user credentials
        creds = _session_credentials()
        
        # Get Slides API service
        from googleapiclient.discovery import build
        slides_service = build('slides', 'v1', credentials=creds)
        
        # Get presentation
        presentation = slides_service.presentations().get(
            presentationId=template_id
        ).execute()
        
        # Extract all text from slides
        all_text = []
        placeholders_found = []
        
        for slide_num, slide in enumerate(presentation.get('slides', []), 1):
            for element in slide.get('pageElements', []):
                # Check textBox
                if 'textBox' in element:
                    for text_elem in element['textBox'].get('textElements', []):
                        text = text_elem.get('textRun', {}).get('content', '')
                        all_text.append(('textBox', text))
                        # Find placeholders
                        import re
                        matches = re.findall(r'\{\{([^}]+)\}\}', text)
                        for match in matches:
                            placeholders_found.append(match)
                
                # Check shape
                if 'shape' in element:
                    for text_elem in element['shape'].get('textElements', []):
                        text = text_elem.get('textRun', {}).get('content', '')
                        all_text.append(('shape', text))
                        # Find placeholders
                        import re
                        matches = re.findall(r'\{\{([^}]+)\}\}', text)
                        for match in matches:
                            placeholders_found.append(match)
        
        return jsonify({
            'template_id': template_id,
            'slides_count': len(presentation.get('slides', [])),
            'placeholders_found': list(set(placeholders_found)),  # Unique
            'all_text_excerpts': all_text[:20],  # First 20 text elements
            'total_text_elements': len(all_text)
        }), 200
    
    except Exception as e:
        logger.error(f"Error debugging template: {e}")
        return jsonify({'error': f'Failed to debug template: {str(e)}'}), 500


@app.errorhandler(404)
def not_found(e):
    """Handle 404 errors."""
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(e):
    """Handle 500 errors."""
    logger.error(f"Server error: {e}")
    return render_template('500.html'), 500


if __name__ == '__main__':
    # Development
    app.run(
        debug=os.environ.get('FLASK_ENV') == 'development',
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 5000))
    )
