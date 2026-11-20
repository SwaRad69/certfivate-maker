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
        replaceChildren() {
            this.children = [];
            if (this.id === 'recoveryBatchSelect') this.value = '';
        },
        appendChild(child) {
            this.children.push(child);
            if (this.id === 'recoveryBatchSelect' && this.children.length === 1) this.value = child.value;
        },
        dispatch(type, detail = {}) {
            const event = { preventDefault() {}, ...detail };
            return Promise.all((listeners.get(type) || []).map(handler => handler.call(this, event)));
        },
        focus() {},
    };
}

function dashboard({ generate, storage = new Map() } = {}) {
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
            return { ok: true, json: async () => ({ status: 'completed' }) };
        },
        FormData,
        Blob,
        URL,
        AbortController,
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
    await view.submit();
    assert.match(view.element('errorMessage').textContent, /Connection lost/);
    assert.equal(view.element('batchRecovery').hidden, false);
    const saved = JSON.parse(view.storage.get(savedBatchKey));
    assert.equal(saved.id, 'batch-1');
    assert.equal(saved.testCount, null);
    assert.equal(typeof saved.startedAt, 'number');
    view.element('outputFolder').value = 'Changed after POST';
    await view.element('resumeBatchBtn').dispatch('click');
    assert.equal(view.postCalls().length, 2);
    const retry = view.postCalls()[1].options.body;
    assert.equal(retry.get('batch_id'), 'batch-1');
    assert.equal(retry.get('retry_failed'), 'true');
    assert.equal(retry.get('csv_file').name, 'input.csv');
    assert.equal(retry.get('output_folder'), 'Awards Archive');
    assert.equal(view.calls.filter(call => call.url.endsWith('/new')).length, 1);

    const reloaded = dashboard({ storage: view.storage });
    assert.equal(reloaded.element('batchRecovery').hidden, false);
    await reloaded.element('checkBatchBtn').dispatch('click');
    assert.deepEqual(reloaded.calls.map(call => call.url), ['/api/generation-batches/batch-1']);
    assert.equal(reloaded.results[0][0].status, 'completed');
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
