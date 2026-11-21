const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function makeNode() {
    return {
        textContent: '',
        className: '',
        children: [],
        style: {},
        appendChild(child) { this.children.push(child); },
        replaceChildren() { this.children = []; },
        querySelector() { return this.heading; },
    };
}

function loadResultRenderer() {
    const ids = [
        'resultContainer', 'successResult', 'successMessage', 'successDetails',
        'errorResult', 'errorMessage', 'errorDetails',
    ];
    const elements = Object.fromEntries(ids.map(id => [id, makeNode()]));
    elements.successResult.heading = makeNode();
    elements.errorResult.heading = makeNode();

    const source = fs.readFileSync(path.join(__dirname, '../web/static/main.js'), 'utf8');
    const context = vm.createContext({
        document: {
            addEventListener() {},
            getElementById(id) { return elements[id]; },
            createElement() { return makeNode(); },
        },
        window: {addEventListener() {}},
    });
    vm.runInContext(source, context);
    return {elements, render: context.renderGenerationResult};
}

test('partial result renders accurate counts, actual folder and literal error details', () => {
    const {elements, render} = loadResultRenderer();
    const detail = 'Row 1: <img src=x onerror=alert(1)>';
    render({
        status: 'partial',
        message: '2 PDFs saved. Some certificates could not be generated.',
        output_folder: '<partial folder>',
        summary: {
            input_rows: 10, attempted_rows: 3, successful_rows: 2, failed_rows: 1,
            created_pdfs: 2, errors: [detail], output_folder_id: 'actual-folder-id',
        },
    });
    assert.equal(elements.successResult.heading.textContent, 'Generation partially complete');
    assert.equal(elements.successResult.className, 'result result-partial');
    const [counts, folder] = elements.successDetails.children;
    assert.deepEqual(counts.children.map(item => item.textContent), [
        'Input rows: 10', 'Attempted rows: 3', 'Successful rows: 2', 'Failed rows: 1',
        'Created PDFs: 2', detail,
    ]);
    assert.equal(folder.textContent.trim(), 'Certificates saved to your Google Drive in "<partial folder>".');
    assert.equal(folder.children[0].href, 'https://drive.google.com/drive/folders/actual-folder-id');
});

test('zero PDFs display failure and no saved-folder message', () => {
    const {elements, render} = loadResultRenderer();
    render({
        status: 'failed', output_folder: 'Unused folder',
        summary: {created_pdfs: 0, failed_rows: 3, errors: ['Row 0: export failed']},
    });
    assert.equal(elements.errorResult.heading.textContent, 'Generation failed');
    assert.equal(elements.successResult.style.display, 'none');
    assert.equal(elements.errorDetails.children.length, 1);
    assert.ok(elements.errorDetails.children[0].children.some(el => el.textContent === 'Created PDFs: 0'));
});

test('a successful result replaces the pending state', () => {
    const {elements, render} = loadResultRenderer();
    render({status: 'pending', summary: {pending_rows: 2, created_pdfs: 1}});
    assert.equal(elements.successResult.heading.textContent, 'Generation pending');
    assert.equal(elements.successResult.className, 'result result-pending');
    assert.ok(elements.successDetails.children[0].children.some(el => el.textContent === 'Pending rows: 2'));

    render({status: 'completed', summary: {created_pdfs: 3, successful_rows: 3}});
    assert.equal(elements.successResult.heading.textContent, 'Generation complete');
    assert.equal(elements.successResult.className, 'result result-success');
    assert.ok(elements.successDetails.children[0].children.every(el => !el.textContent.startsWith('Pending rows')));
});
