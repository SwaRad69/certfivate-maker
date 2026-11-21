# File Converter Feature

## Overview

The dashboard reads recipient data from an uploaded file or from Google Drive. Use **CSV Upload** for a local recipient file and **Certificate template** for a PowerPoint or Google Slides template.

## Supported File Formats

| Format | Extension(s) | Description |
|--------|-------------|-------------|
| **CSV** | `.csv` | Comma-Separated Values (standard format) |
| **TSV** | `.tsv` | Tab-Separated Values |
| **Excel (Modern)** | `.xlsx` | Microsoft Excel spreadsheets (2007+) |
| **Excel (Macro-Enabled)** | `.xlsm` | Workbook data with cached formula values when available |
| **Excel (Legacy)** | `.xls` | Microsoft Excel spreadsheets (97-2003) |
| **OpenDocument** | `.ods` | OpenDocument Spreadsheets (LibreOffice/OpenOffice) |
| **JSON** | `.json` | Array of objects: `[{"name": "John", "email": "..."}]` |
| **JSON Lines** | `.jsonl` | One JSON object per line |
| **Plain Text** | `.txt` | Tab or comma-separated text files |

## How It Works

1. Open **CSV Upload** and click **Choose data file**.
2. Choose your local recipient file. The app reads its headers and rows and offers available columns for grouping.
3. Choose a certificate template and generate. **Test (First N)** uses the first N data rows.

## Format Details

### CSV & TSV
- Quoted cells retain commas and line breaks.
- Cells retain their text, including leading zeros, Unicode, and empty values.
- First N counts complete data records after the header, including records that span several lines.

### Excel Files (XLSX/XLSM/XLS)
- Uploads read the first worksheet.
- Text and empty cells are preserved. The reader renders common fixed-decimal, percentage, currency, date, time, and zero-padded formats such as `00000`.
- A numeric cell with General formatting contains no leading zeros. Store identifiers as text when the exact spelling matters.
- Excel formulas use their cached results when the workbook provides them. Locale-specific and complex custom formats can fall back to the underlying value. Use text when exact display formatting matters.

### Google Sheets

Preview and generation use the displayed values from the selected tab, including columns after Z.

Under **Google Drive**, you can also choose a CSV already saved in Drive.

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
- `openpyxl` for XLSX and XLSM workbooks
- `xlrd` for legacy XLS workbooks
- `odfpy` - For OpenDocument (ODS) conversion

Install with:
```bash
pip install openpyxl xlrd odfpy
```

## Best Practices

1. Use column headers that match your template placeholders without regard to case. `{{Name}}` uses `Name` first and falls back to `Participant Name` when `Name` is absent.
2. **Encoding** - Use UTF-8 encoding when saving files for best compatibility
3. **Data Validation** - Check that your data is complete before uploading
4. A column can supply PDF filenames or subfolder names even when it has no matching placeholder.

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
1. Save your data as `.xlsx`, `.xlsm`, or `.xls`.
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
