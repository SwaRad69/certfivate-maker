# Project Structure

This document explains each file and folder in the certificate generator project.

---

## File Overview

### Core Python Modules

| File | Purpose | Key Functions |
|------|---------|---|
| **main.py** | CLI entry point | `main()` — parses arguments and invokes generation |
| **generator.py** | Core business logic | `generate_certificates()`, `authenticate_google()`, `replace_text_in_slide()`, `export_slide_to_pdf()` |
| **config.py** | Configuration & constants | API scopes, placeholder regex, default paths |
| **utils.py** | Utilities & helpers | `CheckpointManager`, `setup_logging()`, `safe_filename()` |

### Documentation

| File | Audience | Content |
|------|----------|---------|
| **README.md** | Users | Complete usage guide, troubleshooting, features |
| **QUICK_START.md** | New users | 10-minute setup & first run |
| **SETUP_GUIDE.md** | Setup only | Step-by-step Google Cloud project creation |
| **TEMPLATE_DESIGN_GUIDE.md** | Template designers | Canva → Google Slides workflow |
| **PROJECT_STRUCTURE.md** | Developers | This file — explains code organization |

### Configuration & Examples

| File | Purpose |
|------|---------|
| **requirements.txt** | Python package dependencies |
| **sample_participants.csv** | Example CSV for testing |
| **.gitignore** | Excludes credentials, outputs, Python cache |
| **credentials.json.example** | Template for service account credentials structure |

### Generated During Runtime

| File | Created | Purpose |
|------|---------|---------|
| **certificate_generator.log** | `--output` folder | Full log of generation run |
| **.certificate_checkpoint.json** | `--output` folder | Resume state for interrupted runs |
| **\*.pdf** | `--output` folder | Generated certificate PDFs |

---

## Directory Structure

```
certificate-maker/               # Project root
│
├── Core Code
│   ├── main.py                 # Entry point - run this
│   ├── generator.py            # All core logic
│   ├── config.py               # Constants & configuration
│   └── utils.py                # Helpers & checkpoint manager
│
├── Documentation
│   ├── README.md               # ← Start here for usage
│   ├── QUICK_START.md          # ← Fast setup (10 min)
│   ├── SETUP_GUIDE.md          # Google Cloud setup
│   ├── TEMPLATE_DESIGN_GUIDE.md # Canva workflow
│   └── PROJECT_STRUCTURE.md    # This file
│
├── Configuration
│   ├── requirements.txt        # pip install this
│   ├── .gitignore             # Git exclusions
│   └── credentials.json.example # Config template
│
├── Examples & Testing
│   └── sample_participants.csv # Test data
│
└── Runtime Output (created when you run)
    └── certificates/           # Default output folder
        ├── John Doe.pdf
        ├── Jane Smith.pdf
        ├── certificate_generator.log
        └── .certificate_checkpoint.json
```

---

## Module Details

### main.py

**Purpose:** CLI interface — accepts user arguments and runs the generator

**Key Components:**
- `main()` — Entry point with argparse setup
- Argument parser with all available flags
- Input validation (file exists checks)
- Logging setup
- Summary report printing
- Exit codes for scripting

**Called by:** `python main.py --csv ... --template ...`

**Calls:** `generator.generate_certificates()`, `utils.setup_logging()`

---

### generator.py

**Purpose:** All certificate generation logic and Google API interactions

**Key Functions:**

1. **`authenticate_google(credentials_path)`**
   - Loads service account credentials
   - Builds Slides and Drive API clients
   - Returns: `(slides_service, drive_service)`

2. **`detect_placeholders_in_slide(slides_service, presentation_id)`**
   - Parses all text elements in slide
   - Extracts `{{Placeholder}}` patterns using regex
   - Returns: `Set[str]` of placeholder names

3. **`read_csv(file_path)`**
   - Loads CSV with pandas
   - Converts to list of dicts
   - Returns: `List[Dict]` with one dict per row

4. **`validate_csv_placeholders(csv_rows, detected_placeholders)`**
   - Checks CSV columns match slide placeholders
   - Returns: `(bool, List[str])` — is_valid, error_list

5. **`duplicate_slide_template(drive_service, template_id, row_index)`**
   - Creates a copy of template on Google Drive
   - Names with timestamp to avoid conflicts
   - Returns: new presentation ID

6. **`replace_text_in_slide(slides_service, presentation_id, replacements)`**
   - Uses Slides API batchUpdate to find & replace
   - Replaces all `{{Placeholder}}` with values from dict
   - Returns: `bool` — success/failure

7. **`export_slide_to_pdf(drive_service, presentation_id, output_folder, filename)`**
   - Uses Drive API export to convert to PDF
   - Saves to file with safe filename
   - Returns: `bool` — success/failure

8. **`generate_certificates(csv_path, template_id, output_folder, ...)`** ⭐
   - **Main orchestration function**
   - Loads CSV, detects placeholders, validates
   - Loops through rows with checkpoint resume
   - Calls duplicate, replace, export for each
   - Returns: `Dict` with summary stats

---

### config.py

**Purpose:** All configuration in one place

**Contents:**

- **SCOPES** — Google API permissions needed
- **PLACEHOLDER_PATTERN** — Regex matching `{{FieldName}}`
- **Default paths** — credentials, output folder
- **API versions** — Slides v1, Drive v3
- **Retry config** — MAX_RETRIES, backoff seconds
- **MIME types** — PDF, Slides
- **Logging format** — timestamp, level, message

**Usage:** `import config` and use `config.SOME_CONSTANT`

---

### utils.py

**Purpose:** Shared utilities and the checkpoint system

**Key Components:**

1. **`CheckpointManager` class**
   - Saves/loads progress to JSON file
   - Methods: `load()`, `save()`, `is_complete()`, `mark_complete()`
   - Stores: completed row indices, temp slide IDs
   - Location: `{output_folder}/.certificate_checkpoint.json`

2. **`setup_logging(output_folder, verbose)`**
   - Configures logging to file + console
   - File log: DEBUG level, includes everything
   - Console: INFO (or DEBUG if `--verbose`)
   - Log file: `{output_folder}/certificate_generator.log`

3. **`safe_filename(filename)`**
   - Removes invalid filename characters
   - Returns safe filename for PDF output

4. **`ensure_output_folder(output_folder)`**
   - Creates output folder if needed
   - Tests write permissions
   - Returns absolute path to folder

---

## Control Flow

```
main.py (CLI entry)
    ↓
parse arguments
    ↓
setup_logging()
    ↓
generate_certificates() ← Main orchestration
    ├── authenticate_google()
    ├── read_csv()
    ├── detect_placeholders_in_slide()
    ├── validate_csv_placeholders()
    ├── FOR EACH ROW:
    │   ├── duplicate_slide_template()
    │   ├── replace_text_in_slide()
    │   ├── export_slide_to_pdf()
    │   └── checkpoint.mark_complete()
    └── cleanup_temp_slides() [if --cleanup]
    ↓
print summary & exit
```

---

## Performance Notes

- **Per-certificate time:** 10–30 seconds (mostly Google Drive latency)
- **Bottleneck:** Drive API export step
- **Optimization:** Run with stable internet, off-peak hours
- **Debugging:** Use `--verbose` flag to see step-by-step progress

---

## Questions?

- **Usage?** → Check README.md
- **Setup?** → Check SETUP_GUIDE.md
- **Canva workflow?** → Check TEMPLATE_DESIGN_GUIDE.md
