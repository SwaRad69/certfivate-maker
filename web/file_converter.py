"""
File converter utility - converts various spreadsheet/data formats to CSV.
Supports: CSV, XLSX, XLS, ODS, TSV, JSON, and more.
"""

import io
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def detect_file_format(filename):
    """
    Detect file format from filename extension.
    Returns the file extension (lowercase, without dot).
    """
    ext = Path(filename).suffix.lower().lstrip('.')
    return ext if ext else None


def convert_to_csv(file_bytes, filename):
    """
    Convert any supported file format to CSV format.
    
    Args:
        file_bytes: Raw file bytes from upload
        filename: Original filename for format detection
    
    Returns:
        str: CSV content as string
        
    Raises:
        ValueError: If file format not supported or conversion fails
    """
    file_format = detect_file_format(filename)
    
    if not file_format:
        raise ValueError("Could not determine file format from filename")
    
    # Route to appropriate converter
    converters = {
        'csv': _convert_csv,
        'txt': _convert_csv,  # Plain text (tab/comma separated)
        'tsv': _convert_tsv,  # Tab-separated values
        'xlsx': _convert_excel,
        'xls': _convert_excel,
        'ods': _convert_ods,  # OpenDocument Spreadsheet
        'json': _convert_json,
        'jsonl': _convert_jsonl,  # JSON Lines
    }
    
    converter = converters.get(file_format)
    if not converter:
        raise ValueError(f"Unsupported file format: .{file_format}")
    
    try:
        csv_content = converter(file_bytes)
        logger.info(f"Successfully converted {filename} ({file_format}) to CSV")
        return csv_content
    except Exception as e:
        logger.error(f"Error converting {filename}: {e}")
        raise ValueError(f"Failed to convert {filename}: {str(e)}")


def _convert_csv(file_bytes):
    """Handle plain CSV files."""
    try:
        return file_bytes.decode('utf-8')
    except UnicodeDecodeError:
        # Try different encodings
        for encoding in ['latin-1', 'cp1252', 'iso-8859-1']:
            try:
                return file_bytes.decode(encoding)
            except:
                continue
        raise ValueError("Could not decode CSV file - unsupported encoding")


def _convert_tsv(file_bytes):
    """Convert TSV (Tab-Separated Values) to CSV."""
    try:
        tsv_content = file_bytes.decode('utf-8')
    except UnicodeDecodeError:
        tsv_content = file_bytes.decode('latin-1')
    
    import csv
    from io import StringIO
    
    # Read TSV and write as CSV
    reader = csv.reader(StringIO(tsv_content), delimiter='\t')
    output = StringIO()
    writer = csv.writer(output)
    writer.writerows(reader)
    return output.getvalue()


def _convert_excel(file_bytes):
    """Convert XLSX/XLS files to CSV using pandas."""
    try:
        import pandas as pd
    except ImportError:
        raise ImportError("pandas is required for Excel file conversion")
    
    bytes_io = io.BytesIO(file_bytes)
    
    try:
        # Try reading as Excel
        df = pd.read_excel(bytes_io, sheet_name=0)  # First sheet
    except Exception as e:
        raise ValueError(f"Failed to read Excel file: {e}")
    
    # Handle empty dataframe
    if df.empty:
        raise ValueError("Excel file is empty or has no data")
    
    # Convert to CSV
    output = io.StringIO()
    df.to_csv(output, index=False)
    return output.getvalue()


def _convert_ods(file_bytes):
    """Convert ODS (OpenDocument Spreadsheet) to CSV."""
    try:
        import odf.opendocument as opendocument
        import odf.table as table
        from odf.text import P
    except ImportError:
        raise ImportError("odfpy is required for ODS file conversion. Install with: pip install odfpy")
    
    bytes_io = io.BytesIO(file_bytes)
    
    try:
        doc = opendocument.load(bytes_io)
        tables = doc.spreadsheet.getElementsByType(table.Table)
        
        if not tables:
            raise ValueError("No tables found in ODS file")
        
        # Get first table
        spreadsheet = tables[0]
        rows = spreadsheet.getElementsByType(table.TableRow)
        
        if not rows:
            raise ValueError("Table has no rows")
        
        # Extract data
        data = []
        for row in rows:
            cells = row.getElementsByType(table.TableCell)
            row_data = []
            for cell in cells:
                # Get cell content
                paragraphs = cell.getElementsByType(P)
                if paragraphs:
                    # Extract text from paragraph
                    cell_text = ""
                    for para in paragraphs:
                        # Get all text nodes
                        for node in para.childNodes:
                            if hasattr(node, 'data'):
                                cell_text += node.data
                    row_data.append(cell_text)
                else:
                    row_data.append("")
            if any(row_data):  # Skip empty rows
                data.append(row_data)
        
        # Convert to CSV
        import csv
        from io import StringIO
        output = StringIO()
        writer = csv.writer(output)
        writer.writerows(data)
        return output.getvalue()
        
    except Exception as e:
        raise ValueError(f"Failed to read ODS file: {e}")


def _convert_json(file_bytes):
    """Convert JSON (array of objects) to CSV."""
    try:
        content = file_bytes.decode('utf-8')
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}")
    
    if not isinstance(data, list):
        raise ValueError("JSON must be an array of objects")
    
    if not data:
        raise ValueError("JSON array is empty")
    
    # All items should be dicts
    if not all(isinstance(item, dict) for item in data):
        raise ValueError("JSON array must contain only objects (dicts)")
    
    import csv
    from io import StringIO
    
    # Get all keys from all objects
    all_keys = set()
    for item in data:
        all_keys.update(item.keys())
    
    fieldnames = sorted(list(all_keys))
    
    # Write CSV
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(data)
    
    return output.getvalue()


def _convert_jsonl(file_bytes):
    """Convert JSONL (JSON Lines - one JSON object per line) to CSV."""
    try:
        content = file_bytes.decode('utf-8')
    except UnicodeDecodeError:
        content = file_bytes.decode('latin-1')
    
    import csv
    from io import StringIO
    
    lines = content.strip().split('\n')
    data = []
    
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
            if not isinstance(obj, dict):
                raise ValueError(f"Line {i+1} is not a JSON object")
            data.append(obj)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON on line {i+1}: {e}")
    
    if not data:
        raise ValueError("No valid JSON objects found")
    
    # Get all keys
    all_keys = set()
    for item in data:
        all_keys.update(item.keys())
    
    fieldnames = sorted(list(all_keys))
    
    # Write CSV
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(data)
    
    return output.getvalue()


# Supported file formats
SUPPORTED_FORMATS = {
    'csv': 'CSV (Comma-Separated Values)',
    'txt': 'Text (Comma/Tab-Separated)',
    'tsv': 'TSV (Tab-Separated Values)',
    'xlsx': 'Excel Spreadsheet (Modern)',
    'xls': 'Excel Spreadsheet (Legacy)',
    'ods': 'OpenDocument Spreadsheet',
    'json': 'JSON (Array of Objects)',
    'jsonl': 'JSON Lines (JSONL)',
}


def get_supported_formats():
    """Get dictionary of supported formats."""
    return SUPPORTED_FORMATS
