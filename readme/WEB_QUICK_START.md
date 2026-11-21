# Web App Quick Start

Run the dashboard locally to generate PDFs in your Google Drive. You can upload a PowerPoint template directly or use an existing Google Slides presentation.

## Set up Google sign-in

1. Use Python 3.11 and a Google Cloud project with the Drive API, Slides API, and Sheets API enabled.
2. Configure the OAuth consent screen and create an OAuth client of type **Web application**. Add your Google account as a test user if the app's audience requires it. See [Google OAuth setup](https://developers.google.com/identity/protocols/oauth2/web-server).
3. Add `http://localhost:5000/auth/callback` as an authorized redirect URI. Open the app at `http://localhost:5000` so the callback uses the same host and port.
4. Download the client JSON and save it as `web/client_secrets.json`. Keep this file out of version control.

## Start the app

Run from the repository root. For PowerShell on Windows, use:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Set-Location web
..\.venv\Scripts\python.exe app.py
```

For macOS or Linux, use:

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cd web
../.venv/bin/python app.py
```

Open [http://localhost:5000](http://localhost:5000) and click **Sign In with Google**. Run the install commands once per environment. To reload the updated app, stop the server with Ctrl+C and run the final command again from `web/`.

The default OAuth client path is relative to the working directory. Set `GOOGLE_OAUTH_SECRETS` in the process environment to use another path. See [environment setup](ENVIRONMENT_SETUP.md) for other settings.

## Generate a test certificate

1. Under **Recipient data**, use **Google Drive** to choose a Google Sheet or CSV, or **CSV Upload** to upload a supported local file. If you pick a Google Sheet, select the tab with your recipients. For example, you can upload this CSV.

   ```csv
   Participant Name,Event
   Ada Example,Quantum Week
   ```

2. Type `{{Name}}` in an editable text box on the certificate slide. In the example above, the app gets the value from `Participant Name`.
3. Under **Certificate template**, choose **Upload from computer (.ppt or .pptx)** and pick your file. For a Google Slides template, choose **Google Slides**, then select a presentation from Drive or paste a Slides link or ID.
4. Set **Output Folder (in Drive)**. Select **Test (First N)**, enter `1`, then click **Start Test**.
5. Click **Open output folder** in the results and check the PDF in the folder ending in `(TEST)`. Click **Generate Certificates** to run all rows once the sample looks right.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| The app cannot find the OAuth client JSON | Confirm that `client_secrets.json` is in `web/` and launch the app from that directory. |
| Google reports a redirect URI mismatch | Check that the registered URI exactly matches the browser host, port, and `/auth/callback` path. |
| PowerPoint conversion reports missing editable text | Type the listed placeholders into regular text boxes on the certificate slide in PowerPoint and upload the file again. |
| The app reports missing data columns | Match the column names to the missing placeholders. `{{Name}}` looks for `Name` first, then `Participant Name`. |
| Generation pauses or Drive rejects the upload | Open **Recover a generation batch** and use **Check Batch Status**. See [batch recovery](WEB_APP_COMPLETE.md#recover-an-interrupted-batch) for the next step. |

See the [web app guide](WEB_APP_COMPLETE.md) for grouping, output folders, and recovery.
