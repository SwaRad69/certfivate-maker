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

# Placeholder pattern: {{FieldName}}
PLACEHOLDER_PATTERN = re.compile(r'\{\{([^}]+)\}\}')

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
