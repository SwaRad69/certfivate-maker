# Web App Guide

The dashboard signs in to Google, uses a PowerPoint or Google Slides template, and saves one PDF per recipient row to Google Drive. To run it locally, follow the [web quick start](WEB_QUICK_START.md).

## Choose the data and template

- **Google Drive** lists Google Sheets and CSV files. For a Google Sheet, select its tab and check the preview. Preview and generation use the displayed cell values from that tab.
- **CSV Upload** accepts CSV, TSV, TXT, XLSX, XLSM, XLS, ODS, JSON, and JSONL. An uploaded Excel workbook uses its first worksheet. See the [recipient file formats](FILE_CONVERTER_GUIDE.md).
- **Upload from computer (.ppt or .pptx)** accepts a local PowerPoint file. The app converts it to a temporary Google Slides presentation when the batch starts and reuses the converted copy as the template for that batch.
- **Google Slides** accepts a native presentation from the Drive chooser, a Slides link, or a file ID. The signed-in account needs permission to read and copy the presentation.

Type placeholders such as `{{Name}}` and `{{Event}}` in editable text boxes directly on the certificate slide. The app matches column and field names without regard to case. It looks for `Name` first and uses `Participant Name` when that column is absent. For custom fields, use the corresponding header, for example `{{Days Attended}}`. If a PowerPoint marker is missing from the converted slide, the app can report the missing field before exporting any PDFs. See the [template design guide](TEMPLATE_DESIGN_GUIDE.md).

## Name and organize PDFs

- **Certificate Filename Field** lets you choose a data field when the dashboard has loaded the available fields. The default is `Name`, with `Participant Name` as its fallback. A row without a filename value gets a generated filename.
- **Output Folder (in Drive)** defaults to `Certificate Generator`. A new batch uses a writable folder of that name at the top level of **My Drive**. The app creates one there if it finds no writable match.
- **Group certificates by column (optional)** creates or reuses subfolders named after the selected column's values. For example, selecting `Team` sends a recipient with `Orbit` to the `Orbit` subfolder. Blank values save to the main folder.
- **Test (First N)** followed by **Start Test** generates only the first N data rows and adds ` (TEST)` to the output folder name.
- **Generate Certificates** starts a full batch. Results show how many PDFs were actually saved. When PDFs are saved, **Open output folder** opens the exact Drive destination.

## Recover an interrupted batch

1. Under **Recover a generation batch**, select the batch and click **Check Batch Status** to see its saved, failed, and pending rows.
2. Click **Resume Batch** to continue pending work and retry failed rows. Use the original data and settings. After a reload, you may need to select the original data again. For PowerPoint, upload the original file again if the batch paused before conversion was saved.
3. If Drive blocks the destination after PDFs have been saved, restore write access and resume. If zero PDFs were saved and the original folder is blocked, start a new batch so the app can choose a writable destination.

## How batch generation works

The browser submits work in multiple requests as needed. A batch stores a template snapshot and recovery state in the signed-in user's Drive. The generator replaces and verifies the template text for each row, exports PDF bytes, and uploads them to the output folder. Reserved PDF IDs let it check whether a row was already saved after an interruption.

| Route | Purpose |
| --- | --- |
| `/login` and `/auth/callback` | Start and finish Google sign-in |
| `GET /api/drive/templates` | List Google Slides templates |
| `GET /api/drive/recipient-files` | List Google Sheets and CSV recipient files |
| `POST /api/template/placeholders` | Read editable placeholders from a Google Slides presentation |
| `GET /api/generation-batches/new` | Reserve a signed batch token |
| `POST /api/generate` | Validate inputs or run the next portion of a batch |
| `GET /api/generation-batches/<token>` | Retrieve saved progress |

The [CLI reference](README.md) covers service-account authentication and local PDF output.
