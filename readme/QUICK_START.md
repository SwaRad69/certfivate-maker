# Quick Start Guide

Get your certificate generator running in 10 minutes.

---

## Prerequisites Checklist

Before starting, ensure you have:

- [ ] Google Cloud Project created
- [ ] Google Drive & Slides APIs enabled
- [ ] Service Account created with credentials
- [ ] `credentials.json` file downloaded
- [ ] Template shared with service account email
- [ ] Python 3.8+ installed
- [ ] CSV file with participant data

**Not done?** Follow [SETUP_GUIDE.md](SETUP_GUIDE.md) first (takes ~15 min).

---

## Installation

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Place Credentials

Put your `credentials.json` in the project root (same folder as `main.py`):

```
certificate-maker/
├── credentials.json    ← Place file here
├── main.py
├── generator.py
└── ...
```

### 3. Verify Setup

```bash
python -c "import google.auth; print('✓ Setup complete')"
```

---

## Generate Certificates (3 Steps)

### Step 1: Prepare Your CSV

Create a `participants.csv` file:

```csv
Name,Email,Date,Event
John Doe,john@example.com,April 13 2024,Spring Conference
Jane Smith,jane@example.com,April 13 2024,Spring Conference
```

**Rules:**
- First row is header (column names)
- Column names must match placeholders in slide
- One row per certificate

See `sample_participants.csv` for example.

### Step 2: Get Your Template ID

1. Open your Google Slides template
2. Look at the URL:
   ```
   https://docs.google.com/presentation/d/1abc2def3ghi4jkl5mno/edit
                                        ^^^^^^^^^^^^^^^^^^^^^^
                                        COPY THIS (Template ID)
   ```

### Step 3: Run the Generator

```bash
python main.py --csv participants.csv --template 1abc2def3ghi4jkl5mno6pqr --output ./certs
```

**Done!** PDFs appear in `./certs/` folder, one per participant.

---

## Output

Check your output folder:

```
certs/
├── John Doe.pdf          ← Certificate with John's data
├── Jane Smith.pdf        ← Certificate with Jane's data
├── certificate_generator.log
└── .certificate_checkpoint.json
```

Open any PDF to verify it looks correct!

---

## Troubleshooting Quick Fixes

| Problem | Fix |
|---------|-----|
| "Credentials not found" | Put `credentials.json` in project root |
| "Template not found" | Check template ID is correct (26+ chars) |
| "CSV not found" | Use full path: `python main.py --csv /path/to/file.csv ...` |
| "{{Placeholder}} still in PDF" | Add missing column to CSV |
| "Permission denied" | Share template with service account in Google Drive |

More help? See README.md or SETUP_GUIDE.md.

---

## Common Commands

```bash
# Basic run
python main.py --csv data.csv --template ID --output ./certs

# Show debug info
python main.py --csv data.csv --template ID --verbose

# Resume after interruption (auto-skips completed)
python main.py --csv data.csv --template ID --output ./certs

# Regenerate all
python main.py --csv data.csv --template ID --clear-checkpoint

# Delete temp slides after success
python main.py --csv data.csv --template ID --cleanup
```

---

## Next Steps

**Done with one batch?** Run again with different CSV  
**Need help?** Check [README.md](README.md) for detailed docs  
**Advanced setup?** See [SETUP_GUIDE.md](SETUP_GUIDE.md)  
**Design questions?** Read [TEMPLATE_DESIGN_GUIDE.md](TEMPLATE_DESIGN_GUIDE.md)  

---

**Happy certificating!**
