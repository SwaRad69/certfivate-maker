import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

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
