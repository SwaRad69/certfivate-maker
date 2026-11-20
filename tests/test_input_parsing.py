import io
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from web.file_converter import parse_csv, parse_rows, read_input_records, records_to_csv


FIXTURES = Path(__file__).with_name('fixtures')
INPUT_FILENAMES = ['input_records.csv', 'input_records.xlsx', 'input_records.xls']
EXPECTED_RECORDS = [
    {
        'Name': 'Zoë స్వర',
        'Identifier': '00123',
        'Blank': '',
        'Message': 'One, two\nthree',
        'Padded Number': '00042',
        'General Number': '42',
    },
    {
        'Name': '李',
        'Identifier': '00007',
        'Blank': '',
        'Message': 'NA',
        'Padded Number': '00001',
        'General Number': '7',
    },
]
SPREADSHEET_ID = 'mock-spreadsheet-id'
SPREADSHEET_URL = f'https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit'
TEMPLATE_ID = 'mock-template-abcdefghijklmno'


def fixture_records(filename):
    """Use the embedded line ending present in the checked-out CSV fixture."""
    records = [row.copy() for row in EXPECTED_RECORDS]
    if filename.endswith('.csv') and b'two\r\nthree' in (FIXTURES / filename).read_bytes():
        records[0]['Message'] = 'One, two\r\nthree'
    return records


@pytest.mark.parametrize('filename', INPUT_FILENAMES)
def test_read_first_worksheet_or_csv_with_original_values(filename):
    path = FIXTURES / filename
    headers, records = read_input_records(path.read_bytes(), path.name)
    expected = fixture_records(filename)
    assert headers == list(expected[0])
    assert records == expected
    assert parse_csv(records_to_csv(headers, records)) == (headers, records)


@pytest.mark.parametrize('filename', ['excel_display.xlsx', 'excel_display.xls'])
def test_excel_common_display_formats(filename):
    path = FIXTURES / filename
    _, records = read_input_records(path.read_bytes(), filename)
    assert records == [{
        'Identifier': '0012', 'Date': '20/11/2026', 'Percent': '35%', 'Currency': '$2.50',
        'Time': '3:04 PM', 'Grouped': '1,034.50', 'General': '12',
    }]


def test_quoted_carriage_return_and_literal_missing_markers():
    headers, records = parse_csv('Identifier,Note,Marker\r\n\r\n0001,"line 1\r\nline 2",nan\r\n0002,,\r\n')
    assert headers == ['Identifier', 'Note', 'Marker']
    assert records == [
        {'Identifier': '0001', 'Note': 'line 1\r\nline 2', 'Marker': 'nan'},
        {'Identifier': '0002', 'Note': '', 'Marker': ''},
    ]


def test_missing_columns_and_short_rows_have_the_same_width():
    headers, records = parse_rows([
        ['Name', 'name', 'Name.1', '', 'Identifier'],
        ['Ada', 'A', 'B', '', '0010', 'Extra'],
        [],
        ['Lee'],
    ])
    assert headers == ['Name', 'name.2', 'Name.1', 'Unnamed: 3', 'Identifier', 'Unnamed: 5']
    assert list(records[0].values()) == ['Ada', 'A', 'B', '', '0010', 'Extra']
    assert list(records[1].values()) == ['Lee', '', '', '', '', '']


@pytest.mark.parametrize(
    ('filename', 'content'),
    [
        ('data.tsv', 'Name\tID\nZoë\t00123\n'),
        ('data.txt', 'Name\tID\nZoë\t00123\n'),
        ('data.json', '[{"Name":"Zoë","ID":"00123"}]'),
        ('data.jsonl', '{"Name":"Zoë","ID":"00123"}\n'),
    ],
)
def test_existing_non_excel_formats(filename, content):
    _, records = read_input_records(content.encode(), filename)
    assert records == [{'Name': 'Zoë', 'ID': '00123'}]


@pytest.fixture
def generation_app(monkeypatch):
    from web import app as web_app

    credentials = MagicMock(expired=False)
    monkeypatch.setattr(web_app.Credentials, 'from_authorized_user_info', lambda *args: credentials)
    generate = MagicMock(side_effect=lambda **kwargs: {
        'total': len(kwargs['records']),
        'input_rows': kwargs['input_rows'],
        'attempted_rows': len(kwargs['records']),
        'success': len(kwargs['records']),
        'failed': 0,
        'skipped': 0,
        'errors': [],
    })
    monkeypatch.setattr(web_app, 'generate_certificates_oauth2', generate)
    with web_app.app.test_client() as client:
        with client.session_transaction() as session:
            session['credentials'] = {'token': 'mock'}
            session['user_email'] = 'test@example.invalid'
        yield client, web_app, generate


@pytest.mark.parametrize('filename', INPUT_FILENAMES)
def test_upload_first_n_slices_parsed_records(generation_app, filename):
    client, _, generate = generation_app
    response = client.post('/api/generate', data={
        'csv_file': (io.BytesIO((FIXTURES / filename).read_bytes()), filename),
        'template_id': TEMPLATE_ID,
        'output_folder': 'Award PDFs',
        'filename_field': 'Identifier',
        'test_mode': 'true',
        'test_count': '1',
    })
    assert response.status_code == 200, response.get_json()
    arguments = generate.call_args.kwargs
    assert arguments['records'] == fixture_records(filename)[:1]
    assert arguments['input_rows'] == 2
    assert arguments['filename_field'] == 'Identifier'
    assert arguments['output_folder'] == 'Award PDFs (TEST)'
    assert arguments['template_id'] == TEMPLATE_ID


def test_ambiguous_or_empty_sources_do_not_generate(generation_app):
    client, _, generate = generation_app
    ambiguous = client.post('/api/generate', data={
        'template_id': TEMPLATE_ID,
        'csv_file': (io.BytesIO(b'Name\nAda\n'), 'data.csv'),
        'sheets_id': SPREADSHEET_ID,
        'sheet_name': 'Tab',
    })
    empty = client.post('/api/generate', data={
        'template_id': TEMPLATE_ID,
        'csv_file': (io.BytesIO(b'Name\n'), 'data.csv'),
    })
    assert ambiguous.status_code == 400
    assert empty.status_code == 400
    generate.assert_not_called()


def test_drive_csv_preview_and_generation_use_the_same_records(generation_app, monkeypatch):
    client, _, generate = generation_app
    service = MagicMock()
    files = service.files.return_value
    files.get.return_value.execute.return_value = {
        'name': 'input_records.csv', 'mimeType': 'text/csv',
    }
    files.get_media.return_value.execute.return_value = (FIXTURES / 'input_records.csv').read_bytes()
    monkeypatch.setattr('googleapiclient.discovery.build', lambda *args, **kwargs: service)

    response = client.get('/api/drive/file/mock-file/csv')
    assert response.status_code == 200, response.get_json()
    preview = response.get_json()
    expected = fixture_records('input_records.csv')
    assert preview['rows_count'] == len(expected)
    assert preview['headers'] == list(expected[0])
    assert preview['rows'] == [list(row.values()) for row in expected]

    response = client.post('/api/generate', data={
        'template_id': TEMPLATE_ID,
        'csv_file': (io.BytesIO(preview['csv_content'].encode()), preview['filename']),
    })
    assert response.status_code == 200, response.get_json()
    assert generate.call_args.kwargs['records'] == expected


def test_sheets_preview_data_and_generation_read_selected_tab_beyond_z(generation_app, monkeypatch):
    client, web_app, generate = generation_app
    sheet_name = " Team's A1 "
    headers = ['Name', *(f'Column {n}' for n in range(2, 27)), 'Code AA', 'Code AB']
    values = [headers, ['李', *([''] * 25), '00123', 'AB'], [], ['Zoë']]
    service = MagicMock()
    request_values = service.spreadsheets.return_value.values.return_value.get
    request_values.return_value.execute.return_value = {'values': values}
    monkeypatch.setattr(web_app, 'get_sheets_service', lambda _credentials: service)

    preview_response = client.post('/api/sheets/preview', json={
        'sheets_id': SPREADSHEET_ID, 'sheet_name': sheet_name, 'rows': 2,
    })
    csv_response = client.post('/api/sheets/data', json={
        'sheets_url': SPREADSHEET_URL, 'sheet_name': sheet_name,
    })
    generate_response = client.post('/api/generate', data={
        'sheets_id': SPREADSHEET_ID, 'sheet_name': sheet_name, 'template_id': TEMPLATE_ID,
    })
    for response in (preview_response, csv_response, generate_response):
        assert response.status_code == 200, response.get_json()
    preview = preview_response.get_json()
    assert preview['total_rows'] == 2
    assert preview['headers'] == headers
    assert preview['rows'][0][-2:] == ['00123', 'AB']
    assert preview['rows'][1][-2:] == ['', '']

    selected = generate.call_args.kwargs['records']
    assert selected == [dict(zip(headers, row)) for row in preview['rows']]
    assert parse_csv(csv_response.get_json()['csv_content']) == (headers, selected)
    for call in request_values.call_args_list:
        assert call.kwargs == {
            'spreadsheetId': SPREADSHEET_ID,
            'range': "' Team''s A1 '",
            'valueRenderOption': 'FORMATTED_VALUE',
        }


@pytest.mark.parametrize('filename', INPUT_FILENAMES)
def test_cli_reader_shares_the_record_parser(filename):
    from generator import read_csv

    assert read_csv(FIXTURES / filename) == fixture_records(filename)
