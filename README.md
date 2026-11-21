# Bulk Certificate Generator

Generate one personalized PDF per recipient from a PowerPoint file or a Google Slides template.

## Web app

1. Set up Google sign-in and run the app locally. Follow the [web quick start](readme/WEB_QUICK_START.md).
2. On the dashboard, choose recipient data from Google Drive or upload a file from your computer.
3. Under **Certificate template**, choose **Upload from computer (.ppt or .pptx)** or **Google Slides**.
4. Set the output folder and click **Generate Certificates**. Use **Test (First N)** to check a sample.
5. Click **Open output folder** in the results to find your PDFs in Google Drive.

Type placeholders such as `{{Name}}` in editable text boxes on the certificate slide. The app matches column names without regard to case. When there is no `Name` column, it uses `Participant Name` for `{{Name}}` and for default PDF filenames.

## Command line

The CLI uses a Google Slides template ID and service-account credentials. It exports PDFs to a local folder.

```bash
python main.py --csv participants.csv --template YOUR_TEMPLATE_ID --output ./certificates
```

See the [CLI reference](readme/README.md) for setup, options, and recovery.

## Documentation

- [Web quick start](readme/WEB_QUICK_START.md)
- [Web app guide](readme/WEB_APP_COMPLETE.md)
- [Template design and troubleshooting](readme/TEMPLATE_DESIGN_GUIDE.md)
- [Recipient file formats](readme/FILE_CONVERTER_GUIDE.md)
- [Documentation index](readme/INDEX.md)

## License

MIT License - Feel free to use and modify!
