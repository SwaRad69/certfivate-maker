# Bulk Certificate Generator

Generate bulk personalized certificates from a Canva-designed template in Google Slides using a CSV file. This tool automates creating individual PDFs with dynamic placeholders replaced by participant data.

## 🚀 Try It Live

**[👉 Open Certificate Generator](https://certfivate-maker.onrender.com)** — No installation needed, just sign in with Google!

---

## 📚 Documentation

Full guides available in the [`readme/`](readme/) folder:

- [Getting Started](readme/QUICK_START.md) — Quick setup and first run
- [Setup Guide](readme/SETUP_GUIDE.md) — Detailed Google Cloud configuration  
- [Template Design](readme/TEMPLATE_DESIGN_GUIDE.md) — How to design your certificate template
- [Web App Guide](readme/WEB_APP_COMPLETE.md) — Using the web interface
- [Deployment Guide](readme/WEB_DEPLOYMENT_GUIDE.md) — Deploy to production (Render)

## Features

✅ **Canva → Google Slides Workflow** — Design in Canva, export to Google Slides  
✅ **Dynamic Placeholders** — Auto-detects `{{Placeholder}}` patterns  
✅ **CSV-Driven** — Read participant data, generate one PDF per row  
✅ **Bulk Export** — Generate 100–500+ certificates reliably  
✅ **Web Interface** — User-friendly dashboard with Google OAuth  
✅ **Google Drive Integration** — Save directly to your Drive  

## Quick Start

1. **Deploy Your Own** (free on Render):
   
   [![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

2. **Run Locally**:
   ```bash
   pip install -r requirements.txt
   cd web
   python app.py
   ```

## License

MIT License - Feel free to use and modify!
# Bulk Certificate Generator

Generate bulk personalized certificates from a Canva-designed template in Google Slides using a CSV file. This tool automates the process of creating individual PDFs with dynamic placeholders replaced by participant data.

## Features

✅ **Canva → Google Slides Workflow** — Design in Canva, export to Google Slides, add dynamic placeholders  
✅ **Dynamic Placeholder Detection** — Auto-detects `{{Placeholder}}` patterns in your slide  
✅ **CSV-Driven Generation** — Read participant data from CSV, generate one PDF per row  
✅ **Resume on Failure** — Checkpoint system lets you resume if generation is interrupted  
✅ **Bulk Export** — Generate 100–500+ certificates reliably in one run  
✅ **Comprehensive Logging** — Full logs to file + console, detailed error messages  

## Prerequisites

- **Google Cloud Project** with Google Drive & Slides APIs enabled
- **Service Account** with credentials (`credentials.json`)
- **Google Slides Template** with dynamic placeholders
- **Python 3.8+**
- **CSV file** with participant data

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
| `--csv` | ✓ | Path to CSV file | `participants.csv` |
| `--template` | ✓ | Google Slides template ID | `1abc2def3ghi4jkl5mno6pqr` |
| `--output` | | Output folder (default: `./certificates`) | `./my-certs` |
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

Create a CSV file with headers matching your placeholders. **At minimum, include a `Name` column** (used as the PDF filename).

### Example CSV (`participants.csv`)

```csv
Name,Email,Date,Event
John Doe,john@example.com,2024-04-13,Spring Conference
Jane Smith,jane@example.com,2024-04-13,Spring Conference
Bob Johnson,bob@example.com,2024-04-13,Spring Conference
```

**Rules:**
- First row is header row
- Column names must match placeholder names (case-sensitive)
- Use `Name` column for PDF filenames
- Extra CSV columns not in the slide are safely ignored
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
2. Field names are case-sensitive and must match CSV column headers
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
4. **Important:** Placeholders MUST be created in Google Slides, not Canva

### Step 4: Get Template ID
1. Open your template presentation in Google Slides
2. Copy the ID from the URL:
   ```
   https://docs.google.com/presentation/d/{TEMPLATE_ID}/edit
   ```

### Step 5: Prepare CSV
1. Create a CSV with columns matching your placeholders
2. Include at least a `Name` column for PDF filenames

### Step 6: Generate Certificates
```bash
python main.py --csv participants.csv --template {TEMPLATE_ID} --output ./certificates
```

### Step 7: Download PDFs
- All PDFs saved to `./certificates/` (or specified `--output` folder)
- Each file named: `{Name}.pdf`

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
   - Check spelling and case match CSV columns exactly
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

## Performance

- **Speed:** ~10–30 seconds per certificate (depends on Google Drive latency)
- **Batch Examples:**
  - 10 certificates: ~3–5 minutes
  - 50 certificates: ~10–20 minutes
  - 100 certificates: ~20–50 minutes
  - 500 certificates: ~2–3 hours

To speed up:
- Ensure stable internet connection
- Run during off-peak hours (lower API load)
- Use `--cleanup` to auto-delete temp slides (saves cleanup time later)

## API Limits & Rate Limiting

Google APIs have rate limits:
- **Drive API:** 10,000 requests/day (usually not hit)
- **Slides API:** Similar limits per quota unit

If you hit limits:
- Wait 1–2 hours before retrying
- Resume your batch with the same command
- Consider breaking large batches into smaller runs

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
- ✅ `credentials.json` is in `.gitignore` (not committed to Git)
- ✅ Service account = no personal account tokens
- ✅ Scopes limited to Drive + Slides APIs

**File Permissions:**
- Share template with service account email (read-only is sufficient)
- Output folder must be writable by your user
- Temp slides created in same folder as template

**Data Privacy:**
- CSV data stays local (not uploaded anywhere)
- Only template + replacements sent to Google
- PDFs downloaded to your output folder

## Version & Support

- **Python:** 3.8+
- **Dependencies:** See `requirements.txt`
- **Last Updated:** 2024-04-13

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
