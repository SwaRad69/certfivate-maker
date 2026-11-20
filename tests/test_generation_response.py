from io import BytesIO
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'web'))

import app as web_app_module

app = web_app_module.app
generation_response = web_app_module.generation_response
invalid_generation_response = web_app_module.invalid_generation_response


@pytest.mark.parametrize('summary, http_code, status, counts', [
    (
        {'total': 3, 'failed': 3, 'errors': ['Row 0: PDF export failed']},
        500, 'failed', (5, 3, 0, 3, 0),
    ),
    (
        {'total': 3, 'success': 2, 'failed': 1, 'errors': ['Row 1: PDF upload failed']},
        200, 'partial', (5, 3, 2, 1, 2),
    ),
    (
        {'total': 3, 'success': 3},
        200, 'completed', (5, 3, 3, 0, 3),
    ),
    (
        {'total': 3, 'success': 1, 'pending_rows': 2, 'batch_id': 'known-batch'},
        202, 'pending', (5, 1, 1, 0, 1),
    ),
])
def test_generation_response_counts_and_outcome(summary, http_code, status, counts):
    with app.app_context():
        response, code = generation_response(summary, input_rows=5, output_folder='Picked folder')
    body = response.get_json()
    assert code == http_code
    assert body['status'] == status
    assert body['success'] is (status == 'completed')
    assert body['output_folder'] == 'Picked folder'
    assert tuple(body['summary'][key] for key in (
        'input_rows', 'attempted_rows', 'successful_rows', 'failed_rows', 'created_pdfs'
    )) == counts
    assert body['summary']['errors'] == summary.get('errors', [])
    if status == 'failed':
        assert body['error'] == summary['errors'][0]
    if status == 'pending':
        assert body['batch_id'] == summary['batch_id']


def test_invalid_request_carries_error_with_no_attempted_rows():
    with app.app_context():
        response, code = invalid_generation_response('Select one source', input_rows=2)
    body = response.get_json()
    assert code == 400
    assert body['status'] == 'invalid_request'
    assert not body['success']
    assert body['error'] == 'Select one source'
    assert body['summary']['input_rows'] == 2
    assert body['summary']['attempted_rows'] == body['summary']['failed_rows'] == 0


@pytest.mark.parametrize('successful, status, http_code', [
    (0, 'failed', 500), (1, 'partial', 200), (2, 'completed', 200)
])
def test_generate_route_reports_mocked_generation_outcome(monkeypatch, successful, status, http_code):
    monkeypatch.setattr(
        web_app_module.Credentials, 'from_authorized_user_info',
        lambda *_: SimpleNamespace(expired=False, refresh_token=None),
    )
    response = {
        'total': 2, 'success': successful, 'failed': 2 - successful,
        'errors': ['Row 1: PDF export failed'] if successful < 2 else [],
    }
    template_id = 'a' * 27

    def generate(**settings):
        assert settings['template_id'] == template_id
        return response

    monkeypatch.setattr(web_app_module, 'generate_certificates_oauth2', generate)
    client = app.test_client()
    with client.session_transaction() as session:
        session['credentials'] = {'token': 'mock-token'}
    result = client.post('/api/generate', data={
        'template_id': f'https://docs.google.com/presentation/d/{template_id}/edit?usp=sharing',
        'output_folder': 'Picked folder',
        'csv_file': (BytesIO(b'Name\nAda\nGrace\n'), 'data.csv'),
    })
    assert result.status_code == http_code
    body = result.get_json()
    assert body['status'] == status
    assert body['summary']['input_rows'] == body['summary']['attempted_rows'] == 2
    assert body['summary']['created_pdfs'] == successful


def test_uploaded_grouping_uses_parsed_columns_and_first_n_settings(monkeypatch):
    monkeypatch.setattr(
        web_app_module.Credentials, 'from_authorized_user_info',
        lambda *_: SimpleNamespace(expired=False),
    )
    client = app.test_client()
    with client.session_transaction() as session:
        session['credentials'] = {'token': 'mock-token'}
    sample = b'Name,Team\nAda,Orbit\nGrace,Nova\n'
    columns = client.post('/api/upload/columns', data={'csv_file': (BytesIO(sample), 'data.csv')})
    assert columns.get_json() == {'headers': ['Name', 'Team']}

    form = {
        'template_id': 'a' * 27,
        'output_folder': 'Hackathon',
        'group_by_column': 'Missing',
        'test_mode': 'true',
        'test_count': '1',
    }
    result = client.post('/api/generate', data={**form, 'csv_file': (BytesIO(sample), 'data.csv')})
    assert result.status_code == 400
    assert 'Grouping column "Missing"' in result.get_json()['error']

    def generate(**settings):
        assert settings['records'] == [{'Name': 'Ada', 'Team': 'Orbit'}]
        assert settings['group_by_column'] == 'Team'
        assert settings['output_folder'] == 'Hackathon (TEST)'
        return {'total': 1, 'success': 1}

    monkeypatch.setattr(web_app_module, 'generate_certificates_oauth2', generate)
    form['group_by_column'] = 'Team'
    result = client.post('/api/generate', data={**form, 'csv_file': (BytesIO(sample), 'data.csv')})
    assert result.status_code == 200
    assert result.get_json()['output_folder'] == 'Hackathon (TEST)'
