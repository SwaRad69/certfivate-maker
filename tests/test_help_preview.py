"""Render Jinja templates and exercise the dashboard with intercepted Google requests."""

from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape


WEB = Path(__file__).resolve().parents[1] / "web"
SHEET_A = "spreadsheet_alpha_12345"
SHEET_B = "spreadsheet_beta_123456"
DRIVE_CSV = "csv-file-id"
TEMPLATE_A = "template_alpha_12345678"
TEMPLATE_B = "template_beta_123456789"
TAG = '<img src=x onerror="window.previewExecuted = true">'
CSV_ROW = [TAG, "00123", "Hello,\nworld", ""]


@pytest.fixture
def template_env():
    env = Environment(
        loader=FileSystemLoader(WEB / "templates"),
        autoescape=select_autoescape(("html",)),
        undefined=StrictUndefined,
    )
    env.globals.update(
        session={"user_email": "fixture@example.test"},
        url_for=lambda name, filename=None: f"/static/{filename}" if filename else f"/{name}",
        get_flashed_messages=lambda **_: [],
    )
    return env


def test_all_templates_compile(template_env):
    for name in template_env.list_templates():
        template_env.get_template(name)


@pytest.mark.parametrize(
    "name,markers",
    [
        ("help.html", ["Placeholder", "Name", "Email", "Date", "Any Custom Field", "email"]),
        ("dashboard.html", ["Placeholder"]),
        ("login.html", ["Placeholder"]),
        ("landing.html", ["name", "achievement"]),
    ],
)
def test_certificate_examples_render_as_literal_text(template_env, name, markers):
    rendered = template_env.get_template(name).render(youtube_embed=None)
    for marker in markers:
        assert "{{" + marker + "}}" in rendered


@pytest.fixture(scope="module")
def browser():
    playwright = pytest.importorskip("playwright.sync_api")
    with playwright.sync_playwright() as engine:
        browser = engine.chromium.launch()
        yield browser
        browser.close()


class Dashboard:
    def __init__(self, page, template_env):
        self.page = page
        self.held = {}
        self.delayed = set()
        self.empty = set()
        self.previews = []
        self.templates = []
        self.template_errors = {}
        self.generation_posts = 0
        self.generation_payloads = []
        page.route("https://apis.google.com/**", lambda route: route.abort())
        page.route("http://certificate.test/**", lambda route: self.route(route, template_env))

    def open(self):
        self.page.goto("http://certificate.test/dashboard")

    def route(self, route, template_env):
        request = route.request
        path = request.url.removeprefix("http://certificate.test")
        if path == "/dashboard":
            page = template_env.get_template("dashboard.html").render()
            route.fulfill(content_type="text/html; charset=utf-8", body=page)
        elif path.startswith("/static/"):
            route.fulfill(path=WEB / path.lstrip("/"))
        elif path == "/api/user":
            route.fulfill(json={"email": "fixture@example.test"})
        elif path == "/api/drive/recipient-files":
            route.fulfill(json={"files": [
                {"id": SHEET_A, "name": "Test workbook", "mimeType": "application/vnd.google-apps.spreadsheet"},
                {"id": SHEET_B, "name": "Other workbook", "mimeType": "application/vnd.google-apps.spreadsheet"},
                {"id": DRIVE_CSV, "name": "recipients.CSV", "mimeType": "text/csv"},
            ]})
        elif path == "/api/drive/templates":
            route.fulfill(json={
                "files": [{"id": TEMPLATE_A, "name": TAG}],
                "next_page_token": "next+/=",
            })
        elif path == "/api/drive/templates?page_token=next%2B%2F%3D":
            route.fulfill(json={"files": [{"id": TEMPLATE_B, "name": "Second template"}]})
        elif path.endswith("/names"):
            sheet_id = path.split("/")[-2]
            tabs = ["First Tab", "O'Brien!2026"] if sheet_id == SHEET_A else ["Other Workbook"]
            self.reply(route, ("names", sheet_id), {
                "sheets": [{"properties": {"title": tab}} for tab in tabs],
            })
        elif path == "/api/sheets/preview":
            payload = request.post_data_json
            self.previews.append(payload)
            title = payload["sheet_name"]
            rows = [] if title in self.empty else [[title]]
            self.reply(route, ("preview", title), {
                "headers": [TAG],
                "rows": rows,
                "total_rows": len(rows),
            })
        elif path == f"/api/drive/file/{DRIVE_CSV}/csv":
            empty = DRIVE_CSV in self.empty
            self.reply(route, ("csv", DRIVE_CSV), {
                "csv_content": 'Name,Code,Note,Blank\r\n' if empty else 'Name,Code,Note,Blank\r\n<Value>,00123,"Hello,\nworld",\r\n',
                "headers": ["Name", "Code", "Note", "Blank"],
                "rows": [] if empty else [CSV_ROW],
                "rows_count": int(not empty),
            })
        elif path == "/api/template/placeholders":
            template_id = request.post_data_json["template_id"]
            self.templates.append(template_id)
            if template_id in self.template_errors:
                route.fulfill(status=400, json={"error": self.template_errors[template_id]})
            else:
                self.reply(route, ("template", template_id), {
                    "placeholders": ["Name", TAG] if template_id == TEMPLATE_A else ["Recipient"],
                })
        elif path == "/api/generation-batches/new":
            route.fulfill(json={"batch_id": "test-batch"})
        elif path == "/api/generate":
            self.generation_posts += 1
            self.generation_payloads.append(request.post_data_buffer)
            route.fulfill(json={"status": "completed"})
        else:
            route.abort()

    def reply(self, route, key, payload):
        if key in self.delayed:
            self.delayed.remove(key)
            self.held[key] = (route, payload)
        else:
            route.fulfill(json=payload)

    def release(self, key, status=200):
        route, payload = self.held.pop(key)
        route.fulfill(json=payload, status=status)
        self.page.wait_for_load_state("networkidle")

    def choose_recipients(self, file_id):
        self.page.locator("#recipientBrowse").click()
        self.page.locator("#recipientOptions").select_option(file_id)

    def pick_sheet(self, sheet_id=SHEET_A):
        self.choose_recipients(sheet_id)

    def pick_csv(self):
        self.choose_recipients(DRIVE_CSV)


@pytest.fixture
def dashboard(browser, template_env):
    page = browser.new_page()
    try:
        dashboard = Dashboard(page, template_env)
        dashboard.open()
        yield dashboard
    finally:
        page.close()


def test_drive_selection_and_preview_agree_on_workbook_and_exact_tab(dashboard):
    from playwright.sync_api import expect

    page = dashboard.page
    dashboard.pick_sheet()
    expect(page.locator("#previewBody")).to_have_text("First Tab")
    page.locator("#sheetSelect").select_option("O'Brien!2026")
    expect(page.locator("#previewBody")).to_have_text("O'Brien!2026")
    assert dashboard.previews == [
        {"sheets_id": SHEET_A, "sheet_name": "First Tab", "rows": 5},
        {"sheets_id": SHEET_A, "sheet_name": "O'Brien!2026", "rows": 5},
    ]
    assert page.locator("#selectedSheetId").input_value() == SHEET_A


def test_switching_sheet_csv_sheet_keeps_selector_and_preserves_cell_text(dashboard):
    from playwright.sync_api import expect

    page = dashboard.page
    dashboard.pick_sheet()
    expect(page.locator("#previewBody")).to_have_text("First Tab")
    page.evaluate("window.originalSheetSelect = document.getElementById('sheetSelect')")
    assert page.locator("#previewHead th").text_content() == TAG

    dashboard.pick_csv()
    expect(page.locator("#previewBody td")).to_have_count(4)
    assert page.locator("#previewBody td").all_text_contents() == CSV_ROW
    expect(page.locator("#sheetTabsGroup")).to_be_hidden()
    assert page.locator("#selectedSheetId").input_value() == "csv:" + DRIVE_CSV
    assert not page.locator("#previewContainer img").count()
    assert page.evaluate("window.previewExecuted") is None

    page.locator('[data-tab="csv"]').click()
    expect(page.locator("#previewContainer")).to_be_hidden()
    page.locator('[data-tab="sheets"]').click()
    expect(page.locator("#previewContainer")).to_be_visible()

    dashboard.pick_sheet(SHEET_B)
    expect(page.locator("#previewBody")).to_have_text("Other Workbook")
    expect(page.locator("#sheetTabsGroup")).to_be_visible()
    assert page.locator("#sheetSelect").input_value() == "Other Workbook"
    assert page.evaluate("window.originalSheetSelect === document.getElementById('sheetSelect')")


def test_empty_or_loading_drive_selection_cannot_submit(dashboard):
    from playwright.sync_api import expect

    page = dashboard.page
    page.locator("#templateId").fill(TEMPLATE_A)
    dashboard.empty.update(["First Tab", DRIVE_CSV])
    dashboard.delayed.add(("preview", "First Tab"))
    dashboard.pick_sheet()
    page.wait_for_function("document.getElementById('driveDataStatus').textContent.includes('Loading sheet preview')")
    page.locator("#generateBtn").click()
    expect(page.locator("#errorMessage")).to_contain_text("Wait for the sheet preview")
    assert dashboard.generation_posts == 0

    dashboard.release(("preview", "First Tab"))
    expect(page.locator("#driveDataStatus")).to_contain_text("no data rows")
    page.locator("#generateBtn").click()
    assert dashboard.generation_posts == 0

    dashboard.pick_csv()
    expect(page.locator("#driveDataStatus")).to_contain_text("no data rows")
    page.locator("#generateBtn").click()
    expect(page.locator("#errorMessage")).to_contain_text("Drive CSV is empty")
    assert dashboard.generation_posts == 0

    dashboard.empty.clear()
    dashboard.pick_sheet()
    expect(page.locator("#previewBody")).to_have_text("First Tab")
    page.locator("#generateBtn").click()
    expect(page.locator("#successResult h3")).to_have_text("Generation complete")
    assert dashboard.generation_posts == 1


def test_browser_generate_and_first_n_each_post_once(dashboard):
    from playwright.sync_api import expect

    page = dashboard.page
    page.locator("#templateId").fill(TEMPLATE_A)
    page.locator('[data-tab="csv"]').click()
    page.locator("#csvFile").set_input_files({
        "name": "records.csv", "mimeType": "text/csv", "buffer": b"Name\nAda\n",
    })
    page.locator("#generateBtn").click()
    expect(page.locator("#successResult h3")).to_have_text("Generation complete")
    assert dashboard.generation_posts == 1
    assert b'name="test_count"' not in dashboard.generation_payloads[0]

    page.locator("#testBtn").click()
    page.locator("#testCount").fill("3")
    assert dashboard.generation_posts == 1
    page.locator("#startTestBtn").click()
    expect(page.locator("#testCountGroup")).to_be_hidden()
    assert dashboard.generation_posts == 2
    assert b'name="test_count"\r\n\r\n3\r\n' in dashboard.generation_payloads[1]


def test_browser_can_upload_a_powerpoint_template_with_drive_recipients(dashboard):
    from playwright.sync_api import expect

    page = dashboard.page
    dashboard.pick_csv()
    expect(page.locator('#previewBody td')).to_have_count(4)
    expect(page.locator('#slidesTemplateSource')).to_be_checked()
    page.get_by_label('Upload from computer (.ppt or .pptx)', exact=True).check()
    expect(page.locator('#templateId')).to_be_hidden()
    page.locator('#templateFile').set_input_files({
        'name': 'Awards.ppt', 'mimeType': 'application/vnd.ms-powerpoint', 'buffer': b'Mock PowerPoint content',
    })
    page.locator('#filenameField').select_option('Code')
    page.locator('#generateBtn').click()
    expect(page.locator('#successResult h3')).to_have_text('Generation complete')
    payload, = dashboard.generation_payloads
    assert b'name="template_file"; filename="Awards.ppt"' in payload
    assert b'name="template_id"' not in payload
    assert b'name="filename_field"\r\n\r\nCode\r\n' in payload

    page.get_by_label('Google Slides', exact=True).check()
    expect(page.locator('#templateFile')).to_be_hidden()
    page.locator('#templateId').fill(TEMPLATE_A)
    with page.expect_response('**/api/generate'):
        page.locator('#generateBtn').click()
    expect(page.locator('#successResult h3')).to_have_text('Generation complete')
    assert len(dashboard.generation_payloads) == 2
    assert b'name="template_id"' in dashboard.generation_payloads[1]
    assert b'name="template_file"' not in dashboard.generation_payloads[1]


@pytest.mark.parametrize(
    "key",
    [("names", SHEET_A), ("preview", "First Tab"), ("csv", DRIVE_CSV)],
)
def test_prior_source_response_cannot_replace_current_preview(dashboard, key):
    from playwright.sync_api import expect

    dashboard.delayed.add(key)
    pending_url = {
        "names": f"**/drive/sheets/{SHEET_A}/names",
        "preview": "**/sheets/preview",
        "csv": f"**/drive/file/{DRIVE_CSV}/csv",
    }
    with dashboard.page.expect_request(pending_url[key[0]]):
        if key[0] == "csv":
            dashboard.pick_csv()
        else:
            dashboard.pick_sheet()
    dashboard.pick_sheet(SHEET_B)
    expect(dashboard.page.locator("#previewBody")).to_have_text("Other Workbook")
    dashboard.release(key)
    expect(dashboard.page.locator("#previewBody")).to_have_text("Other Workbook")
    assert dashboard.page.locator("#sheetSelect").input_value() == "Other Workbook"


def test_closing_recipient_chooser_keeps_selection(dashboard):
    from playwright.sync_api import expect

    page = dashboard.page
    dashboard.pick_sheet()
    expect(page.locator("#previewBody")).to_have_text("First Tab")
    page.locator("#recipientBrowse").click()
    expect(page.locator("#recipientOptions")).to_be_visible()
    page.locator("#recipientBrowse").click()
    expect(page.locator("#recipientOptions")).to_be_hidden()
    expect(page.locator("#previewBody")).to_have_text("First Tab")
    assert page.locator("#selectedSheetId").input_value() == SHEET_A



def test_prior_tab_response_cannot_replace_newer_tab_or_show_stale_error(dashboard):
    from playwright.sync_api import expect

    page = dashboard.page
    key = ("preview", "First Tab")
    dashboard.delayed.add(key)
    dashboard.pick_sheet()
    expect(page.locator("#sheetSelect")).to_be_visible()
    page.locator("#sheetSelect").select_option("O'Brien!2026")
    expect(page.locator("#previewBody")).to_have_text("O'Brien!2026")
    dashboard.release(key, status=500)
    expect(page.locator("#previewBody")).to_have_text("O'Brien!2026")
    expect(page.locator("#driveDataStatus")).to_be_empty()


def test_pasted_slide_link_and_drive_selection_show_safe_literal_filename_options(dashboard):
    from playwright.sync_api import expect

    page = dashboard.page
    page.locator("#templateId").fill(f"https://docs.google.com/presentation/d/{TEMPLATE_A}/edit#slide=id.1")
    expect(page.locator("#filenameField")).to_have_value("Name")
    assert dashboard.templates == [TEMPLATE_A]
    assert page.locator("#filenameField option").all_text_contents() == ["Default filename field", "Name", TAG]
    assert page.locator("#filenameField img").count() == 0
    page.locator("#filenameField").select_option(TAG)

    page.locator("#templateBrowse").click()
    page.locator("#templateOptions").select_option(TEMPLATE_A)
    expect(page.locator("#selectedTemplateName")).to_have_text(TAG)
    expect(page.locator("#filenameField")).to_have_value(TAG)
    assert page.locator("#selectedTemplateName img").count() == 0
    assert page.locator("#templateId").input_value() == TEMPLATE_A


def test_template_chooser_loads_more_and_reports_access_error(dashboard):
    from playwright.sync_api import expect

    page = dashboard.page
    error = "Could not open this presentation. Check its sharing permissions."
    dashboard.template_errors[TEMPLATE_B] = error
    page.locator("#templateId").fill(TEMPLATE_A)
    expect(page.locator("#filenameField")).to_have_value("Name")
    page.locator("#templateBrowse").click()
    page.locator("#templateMore").click()
    page.locator("#templateOptions").select_option(TEMPLATE_B)
    expect(page.locator("#templateStatus")).to_have_text(error)
    expect(page.locator("#filenameField")).to_be_hidden()


def test_template_lookup_from_old_selection_cannot_replace_current_options(dashboard):
    from playwright.sync_api import expect

    page = dashboard.page
    old = ("template", TEMPLATE_A)
    dashboard.delayed.add(old)
    with page.expect_request("**/template/placeholders"):
        page.locator("#templateId").fill(TEMPLATE_A)
    page.locator("#templateId").fill(TEMPLATE_B)
    expect(page.locator("#filenameField")).to_have_value("Recipient")
    dashboard.release(old)
    expect(page.locator("#filenameField")).to_have_value("Recipient")
    assert dashboard.templates == [TEMPLATE_A, TEMPLATE_B]
