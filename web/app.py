"""
Flask web application for Certificate Generator with OAuth2 authentication.
Users sign in with their Google account and generate certificates to their Drive.
"""

import os
import json
import logging
from functools import wraps
from datetime import datetime
from pathlib import Path
from io import BytesIO

from flask import Flask, render_template, redirect, url_for, request, session, jsonify, send_file
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request as GoogleRequest
import google.auth

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from generator import generate_certificates_oauth2
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


def login_required(f):
    """Decorator to require user authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'credentials' not in session:
            return redirect(url_for('login'))
        
        # Refresh credentials if needed
        creds_data = session.get('credentials')
        if creds_data:
            # Parse JSON string if needed
            if isinstance(creds_data, str):
                creds_data = json.loads(creds_data)
            
            creds = Credentials.from_authorized_user_info(creds_data, GOOGLE_OAUTH_SCOPES)
            
            # Check if credentials need refresh
            if creds.expired and creds.refresh_token:
                creds.refresh(GoogleRequest())
                session['credentials'] = creds.to_json()
        
        return f(*args, **kwargs)
    
    return decorated_function


@app.route('/')
def index():
    """Home page."""
    if 'credentials' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login')
def login():
    """Initiate Google OAuth2 login."""
    flow = get_flow()
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )
    session['oauth_state'] = state
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
        # Exchange code for credentials
        flow = get_flow()
        flow.fetch_token(code=code)
        creds = flow.credentials
        
        # Store credentials in session
        session['credentials'] = creds.to_json()
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


@app.route('/api/generate', methods=['POST'])
@login_required
def api_generate():
    """
    API endpoint to generate certificates.
    Processes either CSV file or Google Sheets URL with template ID.
    """
    try:
        # Get credentials from session
        creds_data = session.get('credentials')
        if not creds_data:
            return jsonify({'error': 'Not authenticated'}), 401
        
        if isinstance(creds_data, str):
            creds_data = json.loads(creds_data)
        
        creds = Credentials.from_authorized_user_info(creds_data, GOOGLE_OAUTH_SCOPES)
        
        # Refresh if needed
        if creds.expired and creds.refresh_token:
            creds.refresh(GoogleRequest())
            session['credentials'] = creds.to_json()
        
        # Get form data
        template_id = request.form.get('template_id', '').strip()
        output_folder = request.form.get('output_folder', 'Certificate Generator').strip()
        
        # Validate template ID
        if not template_id or len(template_id) < 20:
            return jsonify({'error': 'Invalid template ID. Must be 26+ characters.'}), 400
        
        # Determine data source: CSV file, Excel file, or Google Sheets
        csv_content = None
        
        if 'csv_file' in request.files and request.files['csv_file'].filename:
            # Method 1: CSV or Excel file upload
            uploaded_file = request.files['csv_file']
            filename = uploaded_file.filename.lower()
            
            # Handle Excel files
            if filename.endswith(('.xlsx', '.xls')):
                try:
                    import pandas as pd
                    from io import BytesIO
                    
                    # Read Excel file using pandas
                    excel_data = BytesIO(uploaded_file.read())
                    df = pd.read_excel(excel_data)
                    
                    # Convert to CSV format
                    csv_content = df.to_csv(index=False)
                    logger.info(f"Loaded Excel file with {len(df)} rows")
                    
                except Exception as e:
                    logger.error(f"Error reading Excel file: {e}")
                    return jsonify({'error': f'Failed to read Excel file: {str(e)}'}), 400
            
            # Handle CSV files
            elif filename.endswith('.csv'):
                try:
                    csv_content = uploaded_file.read().decode('utf-8')
                except Exception as e:
                    logger.error(f"Error reading CSV file: {e}")
                    return jsonify({'error': f'Failed to read CSV file: {str(e)}'}), 400
            
            else:
                return jsonify({'error': 'File must be CSV or Excel format (.csv, .xlsx, .xls)'}), 400
            
            
        elif request.form.get('sheets_id') or request.form.get('sheets_url'):
            # Method 2: Google Sheets (by ID or URL)
            sheets_id = request.form.get('sheets_id', '').strip()
            sheets_url = request.form.get('sheets_url', '').strip()
            sheet_name = request.form.get('sheet_name', '').strip()
            
            if not sheet_name:
                return jsonify({'error': 'Google Sheet name required'}), 400
            
            # Get sheet ID from either direct ID or URL
            if sheets_id:
                sheet_id = sheets_id
            elif sheets_url:
                sheet_id = extract_sheet_id(sheets_url)
                if not sheet_id:
                    return jsonify({'error': 'Invalid Google Sheets URL'}), 400
            else:
                return jsonify({'error': 'Must provide Google Sheets ID or URL'}), 400
            
            # Fetch data from Google Sheets
            try:
                sheets_service = get_sheets_service(creds)
                result = sheets_service.spreadsheets().values().get(
                    spreadsheetId=sheet_id,
                    range=f"'{sheet_name}'!A:Z"
                ).execute()
                
                values = result.get('values', [])
                if not values or len(values) < 2:
                    return jsonify({'error': 'Sheet has no data'}), 400
                
                # Convert to CSV format
                import csv
                from io import StringIO
                csv_buffer = StringIO()
                writer = csv.writer(csv_buffer)
                writer.writerows(values)
                csv_content = csv_buffer.getvalue()
                
            except Exception as e:
                logger.error(f"Error reading Google Sheets: {e}")
                return jsonify({'error': f'Failed to read Google Sheets: {str(e)}'}), 500
        
        else:
            return jsonify({'error': 'Must provide CSV file or Google Sheets URL'}), 400
        
        if not csv_content:
            return jsonify({'error': 'No data provided'}), 400
        
        try:
            # Generate certificates with user's credentials
            logger.info(f"Starting certificate generation for {session.get('user_email', 'unknown')}")
            logger.info(f"  Template ID: {template_id}")
            logger.info(f"  Output folder: {output_folder}")
            
            summary = generate_certificates_oauth2(
                csv_content=csv_content,
                template_id=template_id,
                output_folder=output_folder,
                user_credentials=creds
            )
            
            logger.info(f"Generation complete: {summary}")
            
            return jsonify({
                'success': True,
                'summary': summary,
                'message': f"Generated {summary['success']} certificates successfully!"
            }), 200
        
        except ValueError as e:
            # Validation errors
            logger.warning(f"Validation error: {e}")
            return jsonify({'error': str(e)}), 400
        
        except Exception as e:
            # Other errors
            logger.error(f"Generation error: {e}", exc_info=True)
            return jsonify({'error': f'Generation failed: {str(e)}'}), 500
    
    except Exception as e:
        logger.error(f"API error: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/logout')
def logout():
    """Logout user and clear session."""
    session.clear()
    logger.info("User logged out")
    return redirect(url_for('login'))


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
        # Parse JSON string if needed
        if isinstance(creds_data, str):
            creds_data = json.loads(creds_data)
        
        creds = Credentials.from_authorized_user_info(creds_data, GOOGLE_OAUTH_SCOPES)
        return jsonify({'token': creds.token})
    
    return jsonify({'error': 'No credentials found'}), 401


# Helper function to extract sheet ID from URL
def extract_sheet_id(url):
    """Extract Google Sheets ID from URL."""
    import re
    match = re.search(r'/spreadsheets/d/([a-zA-Z0-9-_]+)', url)
    if match:
        return match.group(1)
    return None


# Helper function to get Sheets API service
def get_sheets_service(credentials):
    """Get Google Sheets API service."""
    from googleapiclient.discovery import build
    return build('sheets', 'v4', credentials=credentials)


@app.route('/api/drive/sheets', methods=['GET'])
@login_required
def api_drive_sheets():
    """List all Google Sheets in user's Drive."""
    try:
        # Get user credentials
        creds_data = session.get('credentials')
        if isinstance(creds_data, str):
            creds_data = json.loads(creds_data)
        creds = Credentials.from_authorized_user_info(creds_data, GOOGLE_OAUTH_SCOPES)
        
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
        # Get user credentials
        creds_data = session.get('credentials')
        if isinstance(creds_data, str):
            creds_data = json.loads(creds_data)
        creds = Credentials.from_authorized_user_info(creds_data, GOOGLE_OAUTH_SCOPES)
        
        # Get Sheets API service
        from googleapiclient.discovery import build
        sheets_service = build('sheets', 'v4', credentials=creds)
        
        # Get spreadsheet metadata
        spreadsheet = sheets_service.spreadsheets().get(
            spreadsheetId=sheet_id
        ).execute()
        
        sheets = spreadsheet.get('sheets', [])
        sheet_names = [s['properties']['title'] for s in sheets]
        
        return jsonify({
            'sheets': sheets,
            'sheet_names': sheet_names
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting sheet names: {e}")
        return jsonify({'error': f'Failed to get sheet names: {str(e)}'}), 500
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
        creds_data = session.get('credentials')
        if isinstance(creds_data, str):
            creds_data = json.loads(creds_data)
        creds = Credentials.from_authorized_user_info(creds_data, GOOGLE_OAUTH_SCOPES)
        
        # Get sheets from workbook
        sheets_service = get_sheets_service(creds)
        spreadsheet = sheets_service.spreadsheets().get(spreadsheetId=sheet_id).execute()
        
        sheets = spreadsheet.get('sheets', [])
        
        return jsonify({'sheets': sheets}), 200
    
    except Exception as e:
        logger.error(f"Error listing sheets: {e}")
        return jsonify({'error': f'Failed to load sheets: {str(e)}'}), 500


@app.route('/api/sheets/preview', methods=['POST'])
@login_required
def api_sheets_preview():
    """Get preview data from a Google Sheet."""
    try:
        data = request.get_json()
        sheets_url = data.get('sheets_url', '').strip()
        sheet_name = data.get('sheet_name', '').strip()
        rows_to_show = int(data.get('rows', 5))
        
        if not sheets_url or not sheet_name:
            return jsonify({'error': 'Missing URL or sheet name'}), 400
        
        # Extract sheet ID
        sheet_id = extract_sheet_id(sheets_url)
        if not sheet_id:
            return jsonify({'error': 'Invalid Google Sheets URL'}), 400
        
        # Get user credentials
        creds_data = session.get('credentials')
        if isinstance(creds_data, str):
            creds_data = json.loads(creds_data)
        creds = Credentials.from_authorized_user_info(creds_data, GOOGLE_OAUTH_SCOPES)
        
        # Get data from sheet
        sheets_service = get_sheets_service(creds)
        result = sheets_service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"'{sheet_name}'!A:Z"
        ).execute()
        
        values = result.get('values', [])
        
        if not values:
            return jsonify({'error': 'No data found in sheet'}), 400
        
        # Extract headers and preview rows
        headers = values[0] if values else []
        preview_rows = values[1:rows_to_show+1] if len(values) > 1 else []
        total_rows = len(values) - 1  # Subtract header row
        
        # Pad rows to match header length
        for row in preview_rows:
            while len(row) < len(headers):
                row.append('')
        
        return jsonify({
            'headers': headers,
            'rows': preview_rows,
            'total_rows': total_rows
        }), 200
    
    except Exception as e:
        logger.error(f"Error previewing sheet: {e}")
        return jsonify({'error': f'Failed to preview sheet: {str(e)}'}), 500


@app.route('/api/sheets/data', methods=['POST'])
@login_required
def api_sheets_data():
    """Get all data from a Google Sheet as CSV format."""
    try:
        data = request.get_json()
        sheets_url = data.get('sheets_url', '').strip()
        sheet_name = data.get('sheet_name', '').strip()
        
        if not sheets_url or not sheet_name:
            return jsonify({'error': 'Missing URL or sheet name'}), 400
        
        # Extract sheet ID
        sheet_id = extract_sheet_id(sheets_url)
        if not sheet_id:
            return jsonify({'error': 'Invalid Google Sheets URL'}), 400
        
        # Get user credentials
        creds_data = session.get('credentials')
        if isinstance(creds_data, str):
            creds_data = json.loads(creds_data)
        creds = Credentials.from_authorized_user_info(creds_data, GOOGLE_OAUTH_SCOPES)
        
        # Get all data from sheet
        sheets_service = get_sheets_service(creds)
        result = sheets_service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"'{sheet_name}'!A:Z"
        ).execute()
        
        values = result.get('values', [])
        
        if not values or len(values) < 2:
            return jsonify({'error': 'Sheet has no data'}), 400
        
        # Convert to CSV format
        import csv
        from io import StringIO
        
        csv_buffer = StringIO()
        writer = csv.writer(csv_buffer)
        writer.writerows(values)
        csv_content = csv_buffer.getvalue()
        
        return jsonify({
            'csv_content': csv_content,
            'rows': len(values) - 1  # Subtract header
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting sheet data: {e}")
        return jsonify({'error': f'Failed to get sheet data: {str(e)}'}), 500


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
        creds_data = session.get('credentials')
        if isinstance(creds_data, str):
            creds_data = json.loads(creds_data)
        
        creds = Credentials.from_authorized_user_info(creds_data, GOOGLE_OAUTH_SCOPES)
        
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
