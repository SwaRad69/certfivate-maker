import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

from httplib2 import Response
from googleapiclient.errors import HttpError
import pytest

from web import app as web


CLIENT_ID = 'fixture-client'
CLIENT_SECRET = 'fixture-server-only-value'


def fixture_credentials(expiry):
    return web.Credentials(
        token='fixture-access-token',
        refresh_token='fixture-refresh-token',
        token_uri='https://oauth2.googleapis.com/token',
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        expiry=expiry,
    )


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def test_oauth_callback_keeps_the_application_secret_out_of_the_cookie(monkeypatch):
    config = {'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET}
    flow = SimpleNamespace(
        client_config=config, fetch_token=Mock(),
        credentials=fixture_credentials(utc_now() + timedelta(hours=1)),
    )
    drive = Mock()
    drive.about.return_value.get.return_value.execute.return_value = {
        'user': {'emailAddress': 'fixture@example.test', 'displayName': 'Fixture'},
    }
    monkeypatch.setattr(web, 'get_flow', lambda: flow)
    monkeypatch.setattr('googleapiclient.discovery.build', lambda *args, **kwargs: drive)
    client = web.app.test_client()
    with client.session_transaction() as session:
        session['oauth_state'] = 'fixture-state'

    response = client.get('/auth/callback?state=fixture-state&code=fixture-code')
    assert response.status_code == 302
    cookie = client.get_cookie(web.app.config['SESSION_COOKIE_NAME'])
    payload = web.app.session_interface.get_signing_serializer(web.app).loads(cookie.value)
    assert 'client_secret' not in json.loads(payload['credentials'])
    assert client.get('/api/auth-token').get_json() == {'token': 'fixture-access-token'}


def test_refresh_replaces_legacy_cookie_secret_with_server_configuration(monkeypatch):
    config = {'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET}
    monkeypatch.setattr(web, 'get_flow', lambda: SimpleNamespace(client_config=config))

    def refresh(credentials, request):
        assert credentials.client_secret == CLIENT_SECRET
        credentials.token = 'fixture-refreshed-token'
        credentials.expiry = utc_now() + timedelta(hours=1)

    monkeypatch.setattr(web.Credentials, 'refresh', refresh)
    client = web.app.test_client()
    old = json.loads(fixture_credentials(utc_now() - timedelta(hours=1)).to_json())
    old['client_secret'] = 'fixture-legacy-value'
    with client.session_transaction() as session:
        session['credentials'] = json.dumps(old)

    assert client.get('/api/auth-token').get_json() == {'token': 'fixture-refreshed-token'}
    with client.session_transaction() as session:
        assert 'client_secret' not in json.loads(session['credentials'])


@pytest.fixture
def authenticated_client(monkeypatch):
    monkeypatch.setattr(
        web, '_session_credentials', lambda: SimpleNamespace(expired=False),
    )
    client = web.app.test_client()
    with client.session_transaction() as session:
        session['credentials'] = {'token': 'mock-token'}
    return client


def test_drive_template_listing_uses_shared_drives_and_pagination(authenticated_client, monkeypatch):
    drive = Mock()
    list_files = drive.files.return_value.list
    list_files.return_value.execute.return_value = {
        'files': [{'id': 'template', 'name': 'Certificate'}], 'nextPageToken': 'next',
    }
    monkeypatch.setattr('googleapiclient.discovery.build', lambda *args, **kwargs: drive)

    response = authenticated_client.get('/api/drive/templates?page_token=previous')
    assert response.status_code == 200
    assert response.get_json() == {
        'files': [{'id': 'template', 'name': 'Certificate'}], 'next_page_token': 'next',
    }
    options = list_files.call_args.kwargs
    assert options['supportsAllDrives'] is options['includeItemsFromAllDrives'] is True
    assert options['pageToken'] == 'previous'
    assert options['q'] == "trashed = false and (mimeType = 'application/vnd.google-apps.presentation')"


def test_drive_recipient_listing_keeps_sheets_and_csv_files(authenticated_client, monkeypatch):
    drive = Mock()
    list_files = drive.files.return_value.list
    sheet = {'id': 'sheet', 'name': 'Recipients', 'mimeType': 'application/vnd.google-apps.spreadsheet'}
    csv = {'id': 'csv', 'name': 'Recipients.CSV', 'mimeType': 'application/vnd.ms-excel'}
    excel = {'id': 'excel', 'name': 'Recipients.xls', 'mimeType': 'application/vnd.ms-excel'}
    list_files.return_value.execute.return_value = {'files': [sheet, csv, excel], 'nextPageToken': 'next'}
    monkeypatch.setattr('googleapiclient.discovery.build', lambda *args, **kwargs: drive)

    response = authenticated_client.get('/api/drive/recipient-files')
    assert response.status_code == 200
    assert response.get_json() == {'files': [sheet, csv], 'next_page_token': 'next'}


@pytest.mark.parametrize('access, error_text', [
    ('missing', 'share the file'),
    ('copy blocked', 'allow copying'),
])
def test_template_access_error_is_returned_before_generation(authenticated_client, monkeypatch, access, error_text):
    drive, slides = Mock(), Mock()
    execute = drive.files.return_value.get.return_value.execute
    if access == 'missing':
        execute.side_effect = HttpError(Response({'status': '404', 'reason': 'Not Found'}), b'{}')
    else:
        execute.return_value = {'capabilities': {'canCopy': False}}
    monkeypatch.setattr(
        'googleapiclient.discovery.build',
        lambda name, version, **kwargs: drive if name == 'drive' else slides,
    )

    template_id = 'a' * 27
    response = authenticated_client.post('/api/template/placeholders', json={
        'template_id': f'https://docs.google.com/presentation/u/0/d/{template_id}/edit',
    })
    assert response.status_code == 400
    assert error_text in response.get_json()['error']
    assert drive.files.return_value.get.call_args.kwargs['fileId'] == template_id
    slides.presentations.assert_not_called()
