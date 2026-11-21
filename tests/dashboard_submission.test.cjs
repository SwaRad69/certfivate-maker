const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');
const vm = require('node:vm');

const root = path.join(__dirname, '..');
const script = fs.readFileSync(path.join(root, 'web/static/main.js'), 'utf8');
const template = fs.readFileSync(path.join(root, 'web/templates/dashboard.html'), 'utf8');
const templateId = 'A_valid_slides_template_id_123';
const spreadsheetId = 'A_valid_spreadsheet_id_1234567';
const savedBatchKey = 'certificate-generator.batch.batch-1';

function mockElement(id) {
    const listeners = new Map();
    const classes = new Set();
    const heading = {};
    return {
        id,
        style: {},
        value: '',
        dataset: {},
        children: [],
        disabled: false,
        hidden: false,
        classList: {
            add: name => classes.add(name),
            contains: name => classes.has(name),
            remove: name => classes.delete(name),
            toggle(name, force) {
                if (force) classes.add(name);
                else classes.delete(name);
                return force;
            },
        },
        addEventListener(type, listener) {
            const handlers = listeners.get(type) || [];
            handlers.push(listener);
            listeners.set(type, handlers);
        },
        getAttribute() {
            return this.tabName;
        },
        querySelector: selector => selector === 'h3' ? heading : null,
        replaceChildren(...children) {
            this.children = children;
            if (this.id === 'recoveryBatchSelect') this.value = '';
        },
        appendChild(child) {
            this.children.push(child);
            if (this.id === 'recoveryBatchSelect' && this.children.length === 1) this.value = child.value;
        },
        insertRow() {
            const row = mockElement('row');
            this.appendChild(row);
            return row;
        },
        dispatch(type, detail = {}) {
            const event = { preventDefault() {}, ...detail };
            return Promise.all((listeners.get(type) || []).map(handler => handler.call(this, event)));
        },
        focus() {},
    };
}

function dashboard({ generate, request, storage = new Map() } = {}) {
    const elements = Object.fromEntries([...template.matchAll(/\bid="([^"]+)"/g)]
        .map(match => [match[1], mockElement(match[1])]));
    const element = id => elements[id] || null;
    elements.filenameField = mockElement('filenameField');
    elements.filenameField.value = 'Participant ID';
    elements.templateId.value = templateId;
    elements.outputFolder.value = 'Awards Archive';
    elements.testCount.min = '1';
    elements.testCount.max = '1000';
    elements.testCount.value = '10';
    elements.csvFile.accept = '.csv,.txt,.tsv,.xlsx,.xls,.ods,.json,.jsonl';
    elements.csvFile.files = [];
    elements.templateFile.files = [];
    elements['sheets-tab'].classList.add('active');
    const tabs = ['sheets', 'csv'].map(tabName => Object.assign(
        mockElement(tabName), { tabName, dataset: { tab: tabName } }
    ));
    const fileLabel = mockElement('fileLabel');
    const calls = [];
    const results = [];
    let currentBatch = 0;
    const context = vm.createContext({
        console: { log() {}, error() {}, warn() {} },
        document: {
            addEventListener() {},
            getElementById: element,
            createElement: tag => mockElement(tag),
            querySelector(selector) {
                if (selector === '.file-input-text') return fileLabel;
                return tabs.find(tab => selector === `[data-tab="${tab.tabName}"]`);
            },
            querySelectorAll(selector) {
                return selector === '.tab-btn' ? tabs : [elements['sheets-tab'], elements['csv-tab']];
            },
        },
        fetch: async (url, options) => {
            calls.push({ url, options });
            if (url === '/api/generation-batches/new') {
                return { ok: true, json: async () => ({ batch_id: `batch-${++currentBatch}` }) };
            }
            if (url === '/api/generate' && generate) return generate(options.body);
            const response = request?.(url, options);
            if (response) return response;
            return { ok: true, json: async () => ({ status: 'completed' }) };
        },
        FormData,
        Blob,
        URL,
        AbortController,
        setTimeout,
        clearTimeout,
        localStorage: {
            get length() { return storage.size; },
            key: index => [...storage.keys()][index] ?? null,
            getItem: key => storage.get(key) ?? null,
            setItem: (key, value) => storage.set(key, value),
            removeItem: key => storage.delete(key),
        },
    });
    vm.runInContext(script, context);
    context.renderGenerationResult = (...args) => results.push(args);
    vm.runInContext('setupEventListeners()', context);

    return {
        calls,
        results,
        element,
        storage,
        tab: tabName => tabs.find(tab => tab.tabName === tabName).dispatch('click'),
        local(name = 'input.csv', data = 'Name\nAda') {
            elements.csvFile.files = [new File([data], name)];
        },
        sheet(tabName = ' Participants ') {
            elements.selectedSheetId.value = spreadsheetId;
            elements.sheetSelect.value = tabName;
            vm.runInContext('selectedSheetReady = true;', context);
        },
        drive(value) {
            elements.selectedSheetId.value = 'csv:drive-file';
            context.mockCsvContent = value;
            vm.runInContext('csvFromDriveContent = mockCsvContent;', context);
        },
        driveHeaders(headers) {
            context.mockHeaders = headers;
            vm.runInContext('displayPreview(mockHeaders, [], 2);', context);
        },
        postCalls() {
            return calls.filter(call => call.url === '/api/generate');
        },
        submit(id = 'generateBtn') {
            return element('generateForm').dispatch('submit', { submitter: element(id) });
        },
    };
}

test('dashboard only attaches one submit handler and exposes two submit actions', () => {
    assert.doesNotMatch(template, /addEventListener\(['"](?:submit|change)['"]/);
    assert.match(template, /type="submit" id="generateBtn"/);
    assert.match(template, /type="submit" id="startTestBtn"/);
    assert.equal([...script.matchAll(/addEventListener\('submit'/g)].length, 1);
});

test('local upload posts once with template, output folder and filename field', async () => {
    const view = dashboard();
    view.local('input.xlsx');
    await view.tab('csv');
    await view.submit();
    assert.equal(view.postCalls().length, 1);
    const { body, method } = view.postCalls()[0].options;
    assert.equal(method, 'POST');
    assert.equal(body.get('csv_file').name, 'input.xlsx');
    assert.equal(body.get('template_id'), templateId);
    assert.equal(body.get('output_folder'), 'Awards Archive');
    assert.equal(body.get('filename_field'), 'Participant ID');
    assert.equal(body.get('batch_id'), 'batch-1');
    assert.equal(body.has('sheets_id'), false);
    assert.equal(body.has('sheet_name'), false);
    assert.equal(body.has('test_mode'), false);
});

test('Drive CSV posts once as one CSV upload without stale local file or sheet tab', async () => {
    const view = dashboard();
    view.local();
    view.sheet();
    view.drive('Name\nAda');
    await view.submit();
    assert.equal(view.postCalls().length, 1);
    const body = view.postCalls()[0].options.body;
    assert.equal(body.getAll('csv_file').length, 1);
    assert.equal(body.get('csv_file').name, 'data.csv');
    assert.equal(await body.get('csv_file').text(), 'Name\nAda');
    assert.equal(body.has('sheets_id'), false);
    assert.equal(body.has('sheet_name'), false);
});

test('grouping loads upload columns and resets when switching to a different source', async () => {
    assert.match(template, /<label for="groupByColumn"[^>]*>Group certificates by column \(optional\)<\/label>/);
    const view = dashboard({
        request(url, options) {
            if (url === '/api/upload/columns') {
                assert.equal(options.body.get('csv_file').name, 'input.xlsx');
                return { ok: true, json: async () => ({ headers: ['Name', 'Team'] }) };
            }
        },
    });
    view.sheet();
    view.driveHeaders(['Name', 'Department']);
    const group = view.element('groupByColumn');
    assert.deepEqual(group.children.map(option => option.value), ['', 'Name', 'Department']);
    assert.equal(group.children[0].textContent, 'No grouping');
    group.value = 'Department';
    await view.tab('csv');
    assert.equal(group.value, '');
    assert.equal(group.disabled, true);
    assert.equal(group.children[0].textContent, 'Upload a file or select a sheet to see columns');
    view.local('input.xlsx');
    await view.element('csvFile').dispatch('change');
    assert.deepEqual(group.children.map(option => option.value), ['', 'Name', 'Team']);
    assert.equal(group.disabled, false);
    group.value = 'Team';
    await view.submit('startTestBtn');
    assert.equal(view.postCalls()[0].options.body.get('group_by_column'), 'Team');
    assert.equal(view.postCalls()[0].options.body.get('test_mode'), 'true');
    await view.tab('sheets');
    assert.deepEqual(group.children.map(option => option.value), ['', 'Name', 'Department']);
    assert.equal(group.value, '');
    await view.submit();
    assert.equal(view.postCalls()[1].options.body.has('group_by_column'), false);
});

test('Google Sheets posts once with the exact selected tab and no local file', async () => {
    const view = dashboard();
    view.local();
    view.sheet();
    await view.submit();
    assert.equal(view.postCalls().length, 1);
    const body = view.postCalls()[0].options.body;
    assert.equal(body.get('sheets_id'), spreadsheetId);
    assert.equal(body.get('sheet_name'), ' Participants ');
    assert.equal(body.has('csv_file'), false);
});

test('First N posts once with source and settings, while opening it sends no request', async () => {
    const view = dashboard();
    view.local('input.csv');
    view.sheet();
    await view.tab('csv');
    await view.element('testBtn').dispatch('click');
    assert.equal(view.calls.length, 0);
    view.element('testCount').value = '3';
    await view.submit('startTestBtn');
    assert.equal(view.postCalls().length, 1);
    const body = view.postCalls()[0].options.body;
    assert.equal(body.get('test_mode'), 'true');
    assert.equal(body.get('test_count'), '3');
    assert.equal(body.get('template_id'), templateId);
    assert.equal(body.get('output_folder'), 'Awards Archive');
    assert.equal(body.get('filename_field'), 'Participant ID');
    assert.equal(body.get('csv_file').name, 'input.csv');
    assert.equal(body.has('sheets_id'), false);
    assert.equal(view.results[0][1], 'Awards Archive (TEST)');
});

test('invalid active source blocks HTTP requests even with a valid inactive source', async () => {
    const view = dashboard();
    view.sheet();
    await view.tab('csv');
    await view.submit();
    assert.match(view.element('errorMessage').textContent, /Choose a data file/);
    view.local('input.csv', '');
    await view.submit();
    assert.match(view.element('errorMessage').textContent, /empty/);
    view.local('input.exe');
    await view.submit();
    assert.match(view.element('errorMessage').textContent, /supported data file formats/);
    view.local();
    await view.tab('sheets');
    view.sheet('');
    await view.submit();
    assert.match(view.element('errorMessage').textContent, /Select a tab/);
    view.drive(null);
    await view.submit();
    assert.match(view.element('errorMessage').textContent, /empty or still loading/);
    assert.equal(view.calls.length, 0);
});

test('invalid First N stays local and does not prevent a later full generation', async () => {
    const view = dashboard();
    view.sheet();
    view.element('testCount').value = '0';
    await view.submit('startTestBtn');
    view.element('testCount').value = '1.5';
    await view.submit('startTestBtn');
    view.element('testCount').value = '1001';
    await view.submit('startTestBtn');
    assert.equal(view.calls.length, 0);
    assert.match(view.element('errorMessage').textContent, /whole number/);
    await view.submit();
    assert.equal(view.postCalls().length, 1);
    assert.equal(view.postCalls()[0].options.body.has('test_count'), false);
});

test('rapid Generate and First N actions share one in-flight request', async () => {
    let respond;
    let signalPosted;
    const response = new Promise(resolve => { respond = resolve; });
    const posted = new Promise(resolve => { signalPosted = resolve; });
    const view = dashboard({
        generate: () => {
            signalPosted();
            return response;
        },
    });
    view.sheet();
    const first = view.submit();
    const firstN = view.submit('startTestBtn');
    await posted;
    const full = view.submit();
    assert.equal(view.element('generateBtn').disabled, true);
    respond({ json: async () => ({ status: 'completed' }) });
    await Promise.all([first, firstN, full]);
    assert.deepEqual(view.calls.map(call => call.url), ['/api/generation-batches/new', '/api/generate']);
    assert.equal(view.element('generateBtn').disabled, false);
});

test('source switches submit the current selection and preserve inactive selections', async () => {
    const view = dashboard();
    view.local();
    view.sheet();
    await view.tab('csv');
    await view.submit();
    await view.tab('sheets');
    await view.submit();
    const [local, sheets] = view.postCalls().map(call => call.options.body);
    assert.equal(local.get('csv_file').name, 'input.csv');
    assert.equal(local.has('sheets_id'), false);
    assert.equal(sheets.get('sheets_id'), spreadsheetId);
    assert.equal(sheets.has('csv_file'), false);
    assert.notEqual(local.get('batch_id'), sheets.get('batch_id'));
});

test('one Generate click continues across work windows with the same batch and settings', async () => {
    const remaining = [3, 1, 0];
    const view = dashboard({
        generate: async () => {
            const pending = remaining.shift();
            const summary = { pending_rows: pending, created_pdfs: 4 - pending };
            return {
                status: pending ? 202 : 200,
                json: async () => ({ status: pending ? 'pending' : 'completed', summary }),
            };
        },
    });
    view.local();
    await view.tab('csv');
    await view.submit();

    assert.deepEqual(view.calls.map(call => call.url), [
        '/api/generation-batches/new', '/api/generate', '/api/generate', '/api/generate',
    ]);
    const bodies = view.postCalls().map(call => call.options.body);
    assert.ok(bodies.every(body => body === bodies[0]));
    assert.equal(bodies[0].get('batch_id'), 'batch-1');
    assert.equal(bodies[0].has('retry_failed'), false);
    assert.match(view.element('progressText').textContent, /3 saved, 1 remaining/);
    assert.equal(view.results.at(-1)[0].status, 'completed');
    assert.equal(view.storage.has(savedBatchKey), false);
});

test('PowerPoint submits the local template once and keeps its filename choice after reload', async () => {
    let attempts = 0;
    const view = dashboard({
        generate: async () => {
            const summary = { pending_rows: 3, created_pdfs: 0, interrupted: ++attempts === 2 };
            return { status: 202, json: async () => ({ status: 'pending', summary }) };
        },
    });
    view.drive('Name,Code\nAda,A1');
    view.driveHeaders(['Name', 'Code']);
    view.element('powerpointTemplateSource').checked = true;
    await view.element('powerpointTemplateSource').dispatch('change');
    assert.equal(view.element('slidesTemplateFields').hidden, true);
    assert.equal(view.element('powerpointTemplateFields').hidden, false);
    assert.deepEqual(view.element('filenameField').children.map(option => option.value), ['', 'Name', 'Code']);
    view.element('filenameField').value = 'Code';
    view.element('templateFile').files = [new File(['PowerPoint content'], 'Awards.pptx')];
    await view.submit();

    const [first, continued] = view.postCalls().map(call => call.options.body);
    assert.equal(first.get('template_file').name, 'Awards.pptx');
    assert.equal(first.get('template_source'), 'powerpoint');
    assert.equal(first.has('template_id'), false);
    assert.equal(continued.get('batch_id'), first.get('batch_id'));
    assert.equal(continued.has('template_file'), false);

    const reloaded = dashboard({ storage: view.storage });
    reloaded.drive('Name,Code\nAda,A1');
    await reloaded.element('resumeBatchBtn').dispatch('click');
    const resumed = reloaded.postCalls()[0].options.body;
    assert.equal(resumed.get('template_source'), 'powerpoint');
    assert.equal(resumed.get('filename_field'), 'Code');
    assert.equal(resumed.has('template_file'), false);
    assert.equal(resumed.has('template_id'), false);
    assert.equal(resumed.get('retry_failed'), 'true');
});

test('a Drive interruption stays recoverable with either server response format', async () => {
    for (const interruption of [
        { interrupted: true },
        { errors: ['Generation paused after a Drive error. Check batch status or resume.'] },
    ]) {
        const view = dashboard({
            generate: async () => ({
                status: 202,
                json: async () => ({ status: 'pending', summary: { pending_rows: 3, ...interruption } }),
            }),
        });
        view.local();
        await view.tab('csv');
        await view.submit();
        assert.equal(view.postCalls().length, 1);
        assert.equal(view.storage.has(savedBatchKey), true);
    }
});

test('unchanged pending counts stop automatic continuation and preserve the batch', async () => {
    const view = dashboard({
        generate: async () => ({
            status: 202,
            json: async () => ({ status: 'pending', summary: { pending_rows: 3, created_pdfs: 0 } }),
        }),
    });
    view.local();
    await view.tab('csv');
    await view.submit();
    assert.equal(view.postCalls().length, 3);
    assert.match(view.results.at(-1)[0].message, /no new rows were processed/);
    assert.equal(view.storage.has(savedBatchKey), true);
});

test('interruption keeps a token, resumes the original submission, and checks status after reload', async () => {
    let attempts = 0;
    const view = dashboard({
        generate: async () => {
            if (++attempts === 1) throw new Error('Connection lost');
            return { ok: true, status: 202, json: async () => ({ status: 'pending' }) };
        },
    });
    view.local();
    await view.tab('csv');
    view.element('groupByColumn').value = 'Team';
    await view.submit();
    assert.match(view.element('errorMessage').textContent, /Connection lost/);
    assert.equal(view.element('batchRecovery').hidden, false);
    const saved = JSON.parse(view.storage.get(savedBatchKey));
    assert.equal(saved.id, 'batch-1');
    assert.equal(saved.testCount, null);
    assert.equal(saved.groupByColumn, 'Team');
    assert.equal(typeof saved.startedAt, 'number');
    view.element('outputFolder').value = 'Changed after POST';
    await view.element('resumeBatchBtn').dispatch('click');
    assert.equal(view.postCalls().length, 2);
    const retry = view.postCalls()[1].options.body;
    assert.equal(retry.get('batch_id'), 'batch-1');
    assert.equal(retry.get('retry_failed'), 'true');
    assert.equal(retry.get('csv_file').name, 'input.csv');
    assert.equal(retry.get('output_folder'), 'Awards Archive');
    assert.equal(retry.get('group_by_column'), 'Team');
    assert.equal(view.calls.filter(call => call.url.endsWith('/new')).length, 1);

    const reloaded = dashboard({
        storage: view.storage,
        generate: async () => ({ json: async () => ({ status: 'pending' }) }),
    });
    assert.equal(reloaded.element('batchRecovery').hidden, false);
    reloaded.local();
    await reloaded.tab('csv');
    await reloaded.element('resumeBatchBtn').dispatch('click');
    assert.equal(reloaded.postCalls()[0].options.body.get('group_by_column'), 'Team');
    await reloaded.element('checkBatchBtn').dispatch('click');
    assert.deepEqual(reloaded.calls.map(call => call.url), ['/api/generate', '/api/generation-batches/batch-1']);
    assert.equal(reloaded.results.at(-1)[0].status, 'completed');
    assert.equal(reloaded.element('batchRecovery').hidden, true);
    assert.equal(reloaded.storage.has(savedBatchKey), false);
});

test('each interrupted batch remains selectable after invalid submissions and reload', async () => {
    const statuses = ['pending', 'pending', 'invalid_request'];
    const view = dashboard({
        generate: async () => ({ json: async () => ({ status: statuses.shift() }) }),
    });
    await view.tab('csv');
    view.local();
    await view.submit();
    await view.submit();
    await view.submit();
    assert.equal(view.storage.size, 2);

    const reloaded = dashboard({ storage: view.storage });
    const select = reloaded.element('recoveryBatchSelect');
    assert.deepEqual(new Set(select.children.map(option => option.value)), new Set(['batch-1', 'batch-2']));
    select.value = 'batch-1';
    await reloaded.element('checkBatchBtn').dispatch('click');
    assert.equal(reloaded.calls[0].url, '/api/generation-batches/batch-1');
    assert.deepEqual(select.children.map(option => option.value), ['batch-2']);
});
