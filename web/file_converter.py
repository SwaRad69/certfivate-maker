"""
File converter utility - converts various spreadsheet/data formats to CSV.
Supports: CSV, XLSX, XLS, ODS, TSV, JSON, and more.
"""

import csv
import io
import json
import logging
import re
from datetime import date, time
from decimal import Decimal, ROUND_HALF_UP, localcontext
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
        'txt': _convert_text,
        'tsv': _convert_tsv,  # Tab-separated values
        'xlsx': _convert_xlsx,
        'xlsm': _convert_xlsx,  # Excel Macro-Enabled Spreadsheet
        'xls': _convert_xls,
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


def parse_rows(rows):
    """Turn tabular values into headers and records with text-valued cells."""
    rows = iter(rows)
    raw_headers = next((row for row in rows if row), [])
    values = [[_cell_text(cell) for cell in row] for row in rows if row]
    width = max((len(row) for row in values), default=0)
    header_names = [_cell_text(cell) for cell in raw_headers]
    header_names.extend([''] * max(0, width - len(header_names)))

    # Keep every column addressable, including blanks and duplicate headings.
    headers = []
    original_names = {name.casefold() for name in header_names if name}
    used = set()
    for index, name in enumerate(header_names):
        base = name or f'Unnamed: {index}'
        candidate = base
        suffix = 1
        while candidate.casefold() in used or (
            candidate != name and candidate.casefold() in original_names
        ):
            candidate = f'{base}.{suffix}'
            suffix += 1
        headers.append(candidate)
        used.add(candidate.casefold())

    records = [
        dict(zip(headers, row + [''] * (len(headers) - len(row))))
        for row in values
    ]
    return headers, records


def parse_csv(content):
    """Read complete CSV records without numeric or missing-value inference."""
    try:
        return parse_rows(csv.reader(io.StringIO(content.removeprefix('\ufeff'), newline=''), strict=True))
    except csv.Error as exc:
        raise ValueError(f"Invalid CSV format: {exc}") from exc


def read_input_records(file_bytes, filename):
    """Read any supported upload format as headers and text-valued records."""
    return parse_csv(convert_to_csv(file_bytes, filename))


def records_to_csv(headers, records):
    """Serialize normalized records for callers using the CSV response fields."""
    def rows():
        yield headers
        for record in records:
            yield [record.get(header, '') for header in headers]

    return _rows_to_csv(rows())


def _rows_to_csv(rows):
    output = io.StringIO(newline='')
    csv.writer(output).writerows(rows)
    return output.getvalue()


def _cell_text(value):
    return '' if value is None else str(value)


def _convert_csv(file_bytes):
    """Decode UTF-8, UTF-16 with a BOM, or common legacy Windows text."""
    if file_bytes.startswith((b'\xff\xfe', b'\xfe\xff')):
        return file_bytes.decode('utf-16')
    for encoding in ('utf-8-sig', 'cp1252', 'latin-1'):
        try:
            return file_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue


def _convert_text(file_bytes):
    content = _convert_csv(file_bytes)
    try:
        dialect = csv.Sniffer().sniff(content[:4096], delimiters=',\t')
    except csv.Error:
        return content
    if dialect.delimiter == '\t':
        return _rows_to_csv(csv.reader(io.StringIO(content, newline=''), dialect))
    return content


def _convert_tsv(file_bytes):
    """Convert TSV (Tab-Separated Values) to CSV."""
    content = io.StringIO(_convert_csv(file_bytes), newline='')
    return _rows_to_csv(csv.reader(content, delimiter='\t', strict=True))


_EXCEL_NUMBER = re.compile(
    r'(?P<prefix>[$€£¥₹ ]*)(?P<whole>(?:#,##)?0+)(?:\.(?P<fraction>0*#*))?'
    r'(?P<suffix> *%| *[$€£¥₹])?'
)
_EXCEL_DATE_TOKEN = re.compile(
    r'AM/PM|y{4}|y{2}|m{1,4}|d{1,4}|h{1,2}|s{1,2}|"[^"]*"|\\.|[ /:.,-]+',
    re.IGNORECASE,
)


def _excel_number_text(value, number_format):
    parts = _EXCEL_NUMBER.fullmatch(number_format or '')
    if parts is None:
        return str(int(value)) if isinstance(value, int) or value.is_integer() else str(value)

    prefix = parts['prefix']
    whole = parts['whole']
    fraction = parts['fraction'] or ''
    suffix = parts['suffix'] or ''
    number = Decimal(str(value))
    if suffix.endswith('%'):
        number = number.scaleb(2)
    style = ',' if whole.startswith('#,##') else ''
    with localcontext() as context:
        context.rounding = ROUND_HALF_UP
        integral, _, decimals = format(abs(number), f'{style}.{len(fraction)}f').partition('.')
    integral = integral.zfill(whole.count('0'))
    decimals = decimals.rstrip('0').ljust(fraction.count('0'), '0')
    decimal_text = f'.{decimals}' if decimals else ''
    sign = '-' if number < 0 else ''
    return f'{sign}{prefix}{integral}{decimal_text}{suffix}'


def _excel_date_text(value, number_format):
    tokens = _EXCEL_DATE_TOKEN.findall(number_format or '')
    if not tokens or ''.join(tokens) != number_format:
        return str(value)
    fields = [token.lower() for token in tokens]
    hour = getattr(value, 'hour', 0)
    hour_display = (hour % 12 or 12) if 'am/pm' in fields else hour
    day = getattr(value, 'day', 1)
    month = getattr(value, 'month', 1)
    minute = getattr(value, 'minute', 0)
    second = getattr(value, 'second', 0)
    formats = {
        'yyyy': '%Y', 'yy': '%y', 'mmm': '%b', 'mmmm': '%B',
        'ddd': '%a', 'dddd': '%A', 'am/pm': '%p',
    }
    numbers = {'d': day, 'h': hour_display, 's': second}
    previous_field = ''
    result = []
    for index, field in enumerate(fields):
        token = tokens[index]
        if field in formats:
            result.append(value.strftime(formats[field]))
        elif field[0] in numbers:
            result.append(str(numbers[field[0]]).zfill(len(field)))
        elif field in ('m', 'mm'):
            following = fields[index + 1:]
            next_field = next((item for item in following if item.isalpha()), '')
            is_minute = previous_field in ('h', 'hh') or next_field in ('s', 'ss')
            result.append(str(minute if is_minute else month).zfill(len(field)))
        elif token.startswith(('"', '\\')):
            result.append(token.strip('"') if token.startswith('"') else token[1:])
        else:
            result.append(token)
        if field.isalpha():
            previous_field = field
    return ''.join(result)


def _excel_cell_text(value, number_format):
    """Use stored text and render common Excel number and date formats."""
    if isinstance(value, bool):
        return str(value).upper()
    if isinstance(value, (int, float)):
        return _excel_number_text(value, number_format)
    if isinstance(value, (date, time)):
        return _excel_date_text(value, number_format)
    return _cell_text(value)


def _excel_rows_to_csv(rows):
    # Excel workbooks can report trailing rows solely because they are styled.
    while rows and not any(rows[-1]):
        rows.pop()
    return _rows_to_csv(rows)


def _convert_xlsx(file_bytes):
    """Export the first worksheet using cached formula values when available."""
    from openpyxl import load_workbook

    workbook = load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    try:
        rows = [
            [_excel_cell_text(cell.value, cell.number_format) for cell in row]
            for row in workbook.worksheets[0].iter_rows()
        ]
    finally:
        workbook.close()
    return _excel_rows_to_csv(rows)


def _convert_xls(file_bytes):
    """Export the first worksheet of a legacy BIFF workbook."""
    import xlrd

    workbook = xlrd.open_workbook(file_contents=file_bytes, formatting_info=True)
    try:
        worksheet = workbook.sheet_by_index(0)
        rows = []
        for row_index in range(worksheet.nrows):
            row = []
            for cell in worksheet.row(row_index):
                value = cell.value
                if cell.ctype == xlrd.XL_CELL_DATE:
                    value = xlrd.xldate_as_datetime(value, workbook.datemode)
                elif cell.ctype == xlrd.XL_CELL_BOOLEAN:
                    value = bool(value)
                elif cell.ctype == xlrd.XL_CELL_ERROR:
                    value = xlrd.error_text_from_code.get(value, '')
                number_format = None
                if cell.xf_index is not None:
                    format_key = workbook.xf_list[cell.xf_index].format_key
                    formatting = workbook.format_map.get(format_key)
                    number_format = formatting.format_str if formatting else None
                row.append(_excel_cell_text(value, number_format))
            rows.append(row)
    finally:
        workbook.release_resources()
    return _excel_rows_to_csv(rows)


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
    'xlsm': 'Excel Macro-Enabled Spreadsheet (.xlsm)',
    'xls': 'Excel Spreadsheet (Legacy)',
    'ods': 'OpenDocument Spreadsheet',
    'json': 'JSON (Array of Objects)',
    'jsonl': 'JSON Lines (JSONL)',
}


def get_supported_formats():
    """Get dictionary of supported formats."""
    return SUPPORTED_FORMATS
