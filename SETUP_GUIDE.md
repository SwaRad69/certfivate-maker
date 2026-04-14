# Setup Guide: Google Cloud Project & Service Account

This guide walks you through setting up a Google Cloud Project and obtaining the service account credentials needed to run the certificate generator.

## Overview

To use the certificate generator, you need:
1. A Google Cloud Project
2. Google Drive & Slides APIs enabled
3. A Service Account with JSON credentials
4. Proper permissions shared with the service account

**Estimated setup time:** 10–15 minutes

---

## Step 1: Create a Google Cloud Project

### 1.1 Go to Google Cloud Console

1. Open [Google Cloud Console](https://console.cloud.google.com/)
2. Sign in with your Google account
3. If prompted, accept the terms of service

### 1.2 Create a New Project

1. Click the **Project dropdown** at the top (shows project name)
2. Click **NEW PROJECT**
3. Fill in project details:
   - **Project name:** e.g., "Certificate Maker" or "Cert Generator"
   - **Organization:** Leave blank (or select if you have one)
4. Click **CREATE**
5. Wait for the project to be created (may take a moment)

### 1.3 Select Your Project

- Once created, click the **Project dropdown** again
- Select your new project from the list
- Confirm the project name appears at the top

---

## Step 2: Enable Required APIs

### 2.1 Enable Google Drive API

1. In Google Cloud Console, go to **APIs & Services** → **Library**
2. Search for **"Google Drive API"**
3. Click the **Google Drive API** result
4. Click **ENABLE**
5. Wait for it to say "API enabled"

### 2.2 Enable Google Slides API

1. Go back to **APIs & Services** → **Library**
2. Search for **"Google Slides API"**
3. Click the **Google Slides API** result
4. Click **ENABLE**
5. Confirm it's enabled

✅ You should now have both APIs enabled. You can verify:
- Go to **APIs & Services** → **Enabled APIs & services**
- You should see "Google Drive API" and "Google Slides API" in the list

---

## Step 3: Create a Service Account

### 3.1 Go to Service Accounts Page

1. In Google Cloud Console, go to **APIs & Services** → **Credentials**
2. Click **CREATE CREDENTIALS** button
3. Select **Service Account**

### 3.2 Fill Service Account Details

**Step 1: Service Account Details**
- **Service account name:** e.g., "certificate-generator"
- **Service account ID:** Auto-generated based on name (usually OK to leave as-is)
- **Description (optional):** e.g., "Service account for bulk certificate generation"
- Click **CREATE AND CONTINUE**

**Step 2: Grant This Service Account Access to Project (Optional)**
- You can skip this step (not needed for Drive/Slides)
- Click **CONTINUE**

**Step 3: Grant Users Access to Service Account (Optional)**
- Skip this step
- Click **DONE**

### 3.3 Verify Service Account Created

You should see a new service account in the **Service Accounts** list.

---

## Step 4: Create and Download Credentials JSON

### 4.1 Go to Service Account Details

1. In **APIs & Services** → **Credentials**
2. Under **Service Accounts**, click on your newly created service account name
3. You're now on the service account's details page

### 4.2 Create a Key

1. Click the **KEYS** tab at the top
2. Click **ADD KEY** → **Create new key**
3. Select **JSON** as the key type
4. Click **CREATE**

A JSON file will automatically download to your computer. This is your `credentials.json` file.

### 4.3 Save Credentials File

1. **Important:** Save this file safely. You'll need it to run the generator.
2. Place the downloaded file in your project root directory:
   ```
   certificate-maker/
   ├── credentials.json     ← Place file here
   ├── main.py
   ├── generator.py
   └── ...
   ```

3. **Do NOT commit to Git** (it's in `.gitignore`)
4. **Do NOT share** with others

### 4.4 Verify File Contents

Open `credentials.json` in a text editor. It should contain:
```json
{
  "type": "service_account",
  "project_id": "your-project-id",
  "private_key_id": "...",
  "private_key": "-----BEGIN PRIVATE KEY-----\n...",
  "client_email": "certificate-generator@...",
  "client_id": "...",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  ...
}
```

✅ You now have the credentials file needed to run the generator!

---

## Step 5: Share Your Template with Service Account

### 5.1 Get Service Account Email

1. Open your downloaded `credentials.json`
2. Find the `"client_email"` field
3. Copy this email address
   - Example: `certificate-gen@your-project-123.iam.gserviceaccount.com`

### 5.2 Share Template in Google Slides

1. Open your Google Slides template
2. Click **Share** button (top right)
3. Paste the service account email in the "Add people and groups" field
4. Select **Editor** access (allows reading slides + creating copies)
5. Click **Share**
6. (Optional) Check "Notify people" — service account won't receive email

### 5.3 Share Output Folder (Optional)

If you want to organize certificates in a Google Drive folder:

1. Create a folder in Google Drive (or use existing)
2. Share the folder with the service account email (same as above)
3. Grant **Editor** access
4. In the certificate generator, you can then specify this folder path

---

## Step 6: Test Your Setup

### 6.1 Verify Credentials File

Run a quick test to ensure credentials are valid:

```bash
python -c "
from google.oauth2.service_account import Credentials
import json

with open('credentials.json') as f:
    creds_data = json.load(f)
    print(f'Service Account: {creds_data[\"client_email\"]}')
    print(f'Project ID: {creds_data[\"project_id\"]}')
    print('✓ Credentials file is valid!')
"
```

### 6.2 Test API Access

If the above works, you're ready to use the generator!

---

## Troubleshooting Setup

### Problem: "Unable to parse credentials"

**Solution:**
- Ensure `credentials.json` is properly formatted JSON
- Open in a text editor to check for missing/extra characters
- Re-download from Google Cloud Console

### Problem: "Credentials file not found"

**Solution:**
- Ensure file is named exactly `credentials.json`
- Place in the same folder as `main.py`
- Use full path: `python main.py --creds /full/path/credentials.json ...`

### Problem: "Permission denied" when accessing template

**Solution:**
1. Verify you've shared the template with the service account email
2. Check that access level is **Editor** (not Viewer)
3. Wait a few seconds after sharing (sometimes takes a moment to sync)
4. In Google Slides, refresh the page to ensure permissions are updated

### Problem: "API not enabled" error

**Solution:**
1. Go to Google Cloud Console → **APIs & Services** → **Enabled APIs & services**
2. Verify both "Google Drive API" and "Google Slides API" are listed
3. If not, enable them (see Step 2)

### Problem: "Invalid service account" during generation

**Solution:**
1. Verify `credentials.json` contains all required fields
2. Check the `private_key` field is not empty
3. Re-download credentials from Google Cloud Console

---

## Security Checklist

- ✅ `credentials.json` is in `.gitignore` (not committed)
- ✅ Service account email shared with template (readonly if possible)
- ✅ Service account scopes limited to Drive + Slides APIs
- ✅ Key is stored locally, not shared online
- ✅ JSON file permissions are readable only by you

---

## Next Steps

Once setup is complete:

1. Design your certificate in Canva
2. Export as PPTX and upload to Google Drive
3. Open in Google Slides and add `{{Placeholder}}` text
4. Get your template ID from the URL
5. Create a CSV file with participant data
6. Run the generator:
   ```bash
   python main.py --csv participants.csv --template YOUR_TEMPLATE_ID
   ```

See [README.md](README.md) for usage examples and more information.

---

## Advanced: Service Account Credentials Rotation

If you need to rotate credentials (for security):

1. In Google Cloud Console → Service Account → Keys
2. Click the three dots next to the current key
3. Select **Delete**
4. Create a new key (same steps as Step 4)

Old credentials will stop working immediately.

---

## Reference: Google Cloud Project Costs

- **Good news:** This setup is **100% free** under Google's free tier
- Google Drive API: 10,000 requests/day (free)
- Google Slides API: Similar limits (free)
- No credit card required for free tier
- You only pay if you exceed free limits significantly

For typical certificate generation (100s of certs), you won't exceed free limits.

---

**All set?** You can now run the certificate generator. See [README.md](README.md) for usage.
