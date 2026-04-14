# File Converter Feature

## Overview

The Certificate Generator now includes a built-in universal file converter that automatically converts various data formats to CSV before processing. This eliminates the need to manually prepare your files in a specific format.

## Supported File Formats

| Format | Extension(s) | Description |
|--------|-------------|-------------|
| **CSV** | `.csv` | Comma-Separated Values (standard format) |
| **TSV** | `.tsv` | Tab-Separated Values |
| **Excel (Modern)** | `.xlsx` | Microsoft Excel spreadsheets (2007+) |
| **Excel (Legacy)** | `.xls` | Microsoft Excel spreadsheets (97-2003) |
| **OpenDocument** | `.ods` | OpenDocument Spreadsheets (LibreOffice/OpenOffice) |
| **JSON** | `.json` | Array of objects: `[{"name": "John", "email": "..."}]` |
| **JSON Lines** | `.jsonl` | One JSON object per line |
| **Plain Text** | `.txt` | Tab or comma-separated text files |

## How It Works

1. **Upload any supported file** in the "Data File" section of the dashboard
2. **Automatic conversion** - The file is instantly converted to CSV format
3. **Processing** - The converted CSV is used to generate certificates
4. **No manual preparation needed** - Works with files from any source!

## Format Details

### CSV & TSV
- Standard spreadsheet formats
- TSV is automatically detected by file extension
- Supports various character encodings

### Excel Files (XLS/XLSX)
- Reads the first sheet by default
- Empty cells are preserved
- Works with files from modern Excel and legacy versions

### OpenDocument (ODS)
- Fully compatible with LibreOffice and OpenOffice
- Extracts data from the first table
- Requires `odfpy` package (auto-installed)

### JSON Format
Expected format - array of objects:
```json
[
  {"name": "John Doe", "email": "john@example.com", "achievement": "Excellence"},
  {"name": "Jane Smith", "email": "jane@example.com", "achievement": "Merit"},
  {"name": "Bob Johnson", "email": "bob@example.com", "achievement": "Distinction"}
]
```

### JSON Lines Format
One JSON object per line:
```jsonl
{"name": "John Doe", "email": "john@example.com", "achievement": "Excellence"}
{"name": "Jane Smith", "email": "jane@example.com", "achievement": "Merit"}
{"name": "Bob Johnson", "email": "bob@example.com", "achievement": "Distinction"}
```

## Requirements

### Python Packages

Standard requirements (included in `requirements.txt`):
- `pandas` - For Excel (XLSX/XLS) conversion
- `odfpy` - For OpenDocument (ODS) conversion

Install with:
```bash
pip install pandas odfpy
```

## Best Practices

1. **Column Names** - Ensure your data has column headers that match your template placeholders
2. **Encoding** - Use UTF-8 encoding when saving files for best compatibility
3. **Data Validation** - Check that your data is complete before uploading
4. **Template Matching** - Verify column names match your Google Slides template variables

## Error Handling

If conversion fails:
- Check that the file isn't corrupted
- Verify the file has the correct extension
- Ensure the file contains valid data
- Check error message for specific issues

For JSON files, ensure:
- File is valid JSON syntax
- Array contains only objects (not mixed types)
- Objects have consistent (but not necessarily identical) keys

## Examples

### Converting From Excel
1. Have your data in any Excel format (XLS/XLSX)
2. Click "Choose data file" and select your Excel file
3. System automatically converts to CSV
4. Upload and generate!

### Converting From OpenDocument
1. Export or open your LibreOffice/OpenOffice spreadsheet
2. Save as `.ods` if not already
3. Upload directly - no conversion needed on your end
4. System handles the rest!

### Converting From JSON
1. Export your data as JSON (many tools support this)
2. Format as array of objects
3. Upload the `.json` file
4. Auto-converted to CSV for processing
