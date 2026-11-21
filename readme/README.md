# Certificate Generator CLI Reference

Generate personalized PDFs in a local folder from a native Google Slides template and a recipient file. To upload a PowerPoint template or save PDFs to Google Drive, use the [web app](WEB_QUICK_START.md).

## Features

- Detects editable `{{Placeholder}}` fields in the Google Slides template.
- Reads recipient data from local files and generates one PDF per row.
- Uses a checkpoint to resume interrupted runs.
- Writes logs to the console and the output folder.

## Prerequisites

- **Google Cloud Project** with Google Drive & Slides APIs enabled
- **Service Account** with credentials (`credentials.json`)
- **Google Slides Template** with dynamic placeholders
- **Python 3.11**
- A supported [recipient file](FILE_CONVERTER_GUIDE.md)

See [SETUP_GUIDE.md](SETUP_GUIDE.md) for detailed setup instructions.

## Installation

1. **Clone/download the project:**
   ```bash
   cd certificate-maker
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Place credentials:**
   - Download `credentials.json` from Google Cloud Console (see SETUP_GUIDE.md)
   - Place in project root directory (same folder as `main.py`)

## Usage

### Basic Command

```bash
python main.py --csv participants.csv --template TEMPLATE_ID --output ./certificates
```

### Arguments

| Argument | Required | Description | Example |
|----------|----------|-------------|---------|
| `--csv` | ✓ | Path to a supported recipient file | `participants.xlsx` |
| `--template` | ✓ | Google Slides template ID | `1abc2def3ghi4jkl5mno6pqr` |
| `--output` | | Output folder (default: `./certificates`) | `./my-certs` |
| `--group-by-column` | | Put PDFs in subfolders by column value. Blank values stay in the main output folder. | `Team` |
| `--creds` | | Credentials path (default: `./credentials.json`) | `./my-creds.json` |
| `--cleanup` | | Delete temp slides after success | *(flag)* |
| `--verbose` | | Enable debug logging | *(flag)* |
| `--clear-checkpoint` | | Regenerate all (skips resume) | *(flag)* |

### Examples

**Generate with default settings:**
```bash
python main.py --csv data.csv --template 1abc2def3ghi4jkl5mno6pqr
```

**Generate and cleanup temporary slides:**
```bash
python main.py --csv data.csv --template 1abc2def3ghi4jkl5mno6pqr --cleanup
```

**Resume interrupted generation:**
```bash
# Just run the same command again; checkpoint will skip already-generated files
python main.py --csv data.csv --template 1abc2def3ghi4jkl5mno6pqr --output ./certificates
```

**Regenerate all (clear checkpoint):**
```bash
python main.py --csv data.csv --template 1abc2def3ghi4jkl5mno6pqr --clear-checkpoint
```

**Verbose debugging:**
```bash
python main.py --csv data.csv --template 1abc2def3ghi4jkl5mno6pqr --verbose
```

## CSV Format

Create a CSV or another supported recipient file with headers matching your placeholders. Filenames use `Name` first and `Participant Name` when the `Name` column is absent.

### Example CSV (`participants.csv`)

```csv
Name,Email,Date,Event
John Doe,john@example.com,2024-04-13,Spring Conference
Jane Smith,jane@example.com,2024-04-13,Spring Conference
Bob Johnson,bob@example.com,2024-04-13,Spring Conference
```

**Rules:**
- First row is header row
- Match column and placeholder names without regard to case. `{{Name}}` falls back to `Participant Name` when `Name` is absent.
- Extra recipient columns can be used for grouping.
- Missing columns will cause an error (see validation)

## Placeholder Syntax

In your Google Slides template, create text boxes with placeholder syntax:

```
{{Name}}
{{Email}}
{{Date}}
{{Event}}
```

**Key Rules:**
1. Placeholders use double curly braces: `{{FieldName}}`
2. Field names match recipient column headers without regard to case
3. Placeholders can be anywhere in the slide (text boxes, shapes, tables)
4. Each placeholder is replaced independently

### Example Slide Text

```
Certificate of Completion

This certifies that

    {{Name}}

has successfully completed the

    {{Event}}

on {{Date}}

Email: {{Email}}
```

## Workflow

### Step 1: Design in Canva
1. Design your certificate in Canva
2. Export as **PPTX** (preferred) or PNG

### Step 2: Upload to Google Slides
1. Upload the PPTX/PNG to Google Drive
2. Open in Google Slides (auto-conversion from PPTX; PNG requires manual layout)

### Step 3: Add Placeholders
1. Click on each text element that needs dynamic content
2. Replace text with `{{FieldName}}`
3. Use column names from your CSV as field names
4. Verify that each placeholder is editable in the native Google Slides template.

### Step 4: Get Template ID
1. Open your template presentation in Google Slides
2. Copy the ID from the URL:
   ```
   https://docs.google.com/presentation/d/{TEMPLATE_ID}/edit
   ```

### Step 5: Prepare CSV
1. Create a CSV with columns matching your placeholders
2. Use `Name` or `Participant Name` for recipient-based filenames.

### Step 6: Generate Certificates
```bash
python main.py --csv participants.csv --template {TEMPLATE_ID} --output ./certificates
```

### Step 7: Download PDFs
- All PDFs saved to `./certificates/` (or specified `--output` folder)
- The app uses a generated filename when neither name column is available.

## Output

### Generated Files

```
certificates/
├── certificate_generator.log       # Full log of the run
├── .certificate_checkpoint.json    # Resume checkpoint (auto-managed)
├── John Doe.pdf                    # Generated certificate
├── Jane Smith.pdf
└── Bob Johnson.pdf
```

### Log File

The log file (`certificate_generator.log`) contains:
- Timestamp and level (INFO, DEBUG, ERROR, WARNING)
- Detailed messages for each step
- Error messages with row numbers
- Summary at the end

View recent logs:
```bash
tail -20 certificates/certificate_generator.log
```

## Resume & Checkpoints

The system automatically saves progress in `.certificate_checkpoint.json`:

- **Automatic:** After each successful certificate, progress is saved
- **Resume:** Run the same command again; already-generated files are skipped
- **Clear:** Use `--clear-checkpoint` flag to regenerate all files

### Example Resume Workflow

```bash
# Start generation (fails after 50 of 100)
python main.py --csv data.csv --template ID --output ./certs
# OUTPUT: 50 success, 50 failed

# Fix the issue and resume (skips the 50 completed)
python main.py --csv data.csv --template ID --output ./certs
# OUTPUT: 50 skipped, 50 success (total 100 complete)
```

## Troubleshooting

### Common Issues

**1. "Credentials file not found"**
   - Place `credentials.json` in the project root
   - Or use: `--creds /path/to/credentials.json`
   - See [SETUP_GUIDE.md](SETUP_GUIDE.md) for how to get credentials

**2. "Missing CSV columns for placeholders"**
   - Your CSV is missing a column that's in the slide
   - Add the missing column to your CSV
   - Example: Slide has `{{Email}}` but CSV doesn't have an Email column

**3. "CSV file not found"**
   - Use absolute path: `python main.py --csv /full/path/data.csv --template ID`
   - Or ensure file is in current directory

**4. "Invalid template ID"**
   - Copy the full ID from the URL (contains ~26 characters)
   - Ensure the template is shared with your service account email
   - Check that it's a Google Slides presentation (not Docs or Sheets)

**5. "Permission denied on Google Drive"**
   - Share the template with the service account email (see SETUP_GUIDE.md)
   - Ensure service account has Drive access

**6. "No placeholders detected in template"**
   - Verify placeholders use correct syntax: `{{FieldName}}`
   - Check that each placeholder spelling matches a recipient column.
   - Run with `--verbose` to see detected placeholders

**7. Script was interrupted, how do I resume?**
   - Run the exact same command again
   - The checkpoint will skip already-generated files
   - Only failed/pending rows will be retried

**8. I want to start fresh (regenerate all)"**
   ```bash
   python main.py --csv data.csv --template ID --clear-checkpoint
   ```

### Debug Mode

Enable detailed logging with `--verbose`:

```bash
python main.py --csv data.csv --template ID --verbose
```

This outputs DEBUG-level messages to console + file, helpful for troubleshooting.

### View Logs

```bash
# Real-time (last 50 lines)
tail -50 certificates/certificate_generator.log

# Follow live updates (like 'tail -f')
Get-Content certificates/certificate_generator.log -Wait  # Windows PowerShell
tail -f certificates/certificate_generator.log              # Linux/Mac
```

## Runtime and Google API limits

Runtime depends on the number of recipients, template complexity, and Google API response times. If Google rate-limits the run, retry with the same command after the limit clears so the checkpoint skips completed rows.

## Features Details

### Checkpoint & Resume

The system uses a JSON checkpoint file to track progress:

```json
{
  "completed_rows": [0, 1, 2, ...],
  "temp_slide_ids": {"0": "file_id_123", ...},
  "last_saved": "2024-04-13T15:30:00.000000"
}
```

- **Automatic saving:** After every successful certificate
- **Auto-skip:** Already-completed rows are skipped on resume
- **Cleanup tracking:** Temp file IDs saved for optional cleanup

### Temp Slide Management

The system creates temporary copies of your template:
- Renamed as: `TemplateTitle_cert_{row_index}_{timestamp}`
- Auto-tracked in checkpoint
- Optional cleanup with `--cleanup` flag (deletes from Drive)

**Why keep temps?** You can inspect/download them before cleanup; checkpoint lets you delete them later.

## Security & Best Practices

**Credentials Security:**
- `credentials.json` is in `.gitignore` (not committed to Git)
- Service account = no personal account tokens
- Scopes limited to Drive + Slides APIs

**File Permissions:**
- Give the service account permission to read and copy the template and to create files in its Drive folder.
- Output folder must be writable by your user
- Temp slides created in same folder as template

The CLI reads the recipient file locally and sends replacement values to the Google Slides API. It downloads the exported PDFs to the local output folder.

## Version & Support

- **Python:** 3.11
- **Dependencies:** See `requirements.txt`

## License

This project is provided as-is for personal or organizational use.

## Contributing

To report issues or suggest improvements:
1. Check existing logs and the [Troubleshooting](#troubleshooting) section
2. Include:
   - Error message from logs
   - CSV sample (without sensitive data)
   - Command used
   - System info (Python version, OS)

---

**Ready to get started?** See [SETUP_GUIDE.md](SETUP_GUIDE.md) for step-by-step Google Cloud setup.
