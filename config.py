"""
Configuration for the Certificate Generator.
Defines API scopes, constants, and patterns.
"""

import re

# Google API Scopes
SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/presentations',
]

# Office documents can insert invisible formatting marks into otherwise identical text.
PLACEHOLDER_FORMAT_MARKS = r'\u00ad\u061c\u200b-\u200f\u202a-\u202e\u2060\u2066-\u2069\ufeff'
PLACEHOLDER_FORMATTING = re.compile(f'[{PLACEHOLDER_FORMAT_MARKS}]')
_OPEN_BRACE = r'[{\uff5b]'
_CLOSE_BRACE = r'[}\uff5d]'
_OPTIONAL_MARKS = rf'[{PLACEHOLDER_FORMAT_MARKS}]*'
PLACEHOLDER_PATTERN = re.compile(
    _OPEN_BRACE + _OPTIONAL_MARKS + _OPEN_BRACE + r'([^}\uff5d]+)' + _CLOSE_BRACE + _OPTIONAL_MARKS + _CLOSE_BRACE
)

# Default paths
DEFAULT_OUTPUT_FOLDER = './certificates'
DEFAULT_CREDENTIALS_PATH = './credentials.json'
CHECKPOINT_FILENAME = '.certificate_checkpoint.json'

# API configuration
DRIVE_API_VERSION = 'v3'
SLIDES_API_VERSION = 'v1'

# Retry configuration
MAX_RETRIES = 3
INITIAL_BACKOFF_SECONDS = 1

# MIME types
PDF_MIME_TYPE = 'application/pdf'
SLIDES_MIME_TYPE = 'application/vnd.google-apps.presentation'

# Logging
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
LOG_FILENAME = 'certificate_generator.log'
