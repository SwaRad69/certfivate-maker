# Environment Setup Guide

The web app reads its settings from the process environment. The repository's [.env.example](../.env.example) lists the keys. If you keep local settings in a `.env` file, load them into the environment before running `python app.py`.

## Web app settings

| Variable | Purpose | Default |
| --- | --- | --- |
| `FLASK_ENV` | Set `development` for local debugging or `production` for deployment. | `development` |
| `FLASK_SECRET_KEY` | Signs the Flask session and generation batch tokens. Keep the key stable so sessions and recovery tokens stay usable across restarts. | Development fallback. Set a secret key in production. |
| `GOOGLE_OAUTH_SECRETS` | Path to the Google OAuth web client JSON. Relative paths resolve from the working directory. | `client_secrets.json` |
| `PORT` | Port used by `python app.py`. | `5000` |

To configure the OAuth client and start the server, follow the [web quick start](WEB_QUICK_START.md).

### Windows PowerShell

Set variables in the same shell that starts the app. With your virtual environment active, run these commands from `web/`.

```powershell
$env:FLASK_ENV = 'development'
$env:GOOGLE_OAUTH_SECRETS = 'client_secrets.json'
python app.py
```

### macOS and Linux

```bash
export FLASK_ENV=development
export GOOGLE_OAUTH_SECRETS=client_secrets.json
python app.py
```

## Production

Set `FLASK_ENV=production` and a stable `FLASK_SECRET_KEY`. The value of `GOOGLE_OAUTH_SECRETS` should be the filesystem path to the OAuth client JSON. Register the deployed application's HTTPS `/auth/callback` URL with the production OAuth client. Keep the client JSON, session secret, and service-account credentials out of version control.

Generate a random Flask secret with:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

See the [web deployment guide](WEB_DEPLOYMENT_GUIDE.md) for server setup.

## Command line

The CLI reads a service-account JSON file from the path supplied to `--creds`, which defaults to `./credentials.json`. See the [CLI setup guide](SETUP_GUIDE.md).
