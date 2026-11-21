/* Certificate Generator Web App - JavaScript */

let csvFromDriveContent = null;  // Store CSV content when selected from Drive
let selectedSheetReady = false;
let driveSelectionVersion = 0;
let sheetPreviewVersion = 0;
let templateSelectionVersion = 0;
let templateLookupTimer;
let driveColumns = [];
let uploadColumns = [];

// Initialize app
document.addEventListener('DOMContentLoaded', function() {
    if (!document.getElementById('generateForm')) return;

    setupEventListeners();
    loadUserInfo();
});

async function loadUserInfo() {
    try {
        const response = await fetch('/api/user');
        if (!response.ok) {
            if (response.status === 401) window.location.href = '/login';
            return;
        }
        const data = await response.json();
        console.log('User info loaded:', data.email);
    } catch (error) {
        console.error('Error loading user info:', error);
    }
}

function setupEventListeners() {
    // Tab switching
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const tabName = this.getAttribute('data-tab');
            switchTab(tabName);
        });
    });

    setupDriveChooser('recipient', '/api/drive/recipient-files', 'Google Sheets or CSV files', 'Upload a file instead.', selectRecipientFile);
    setupDriveChooser('template', '/api/drive/templates', 'Google Slides presentations', 'Paste a Slides link instead.', file => {
        document.getElementById('templateId').value = file.id;
        return updateTemplateSelection(file.id, file.name);
    });

    // File input
    const fileInput = document.getElementById('csvFile');
    if (fileInput) {
        fileInput.addEventListener('change', function() {
            const file = this.files[0];
            const filename = file?.name || 'Choose data file';
            const textSpan = document.querySelector('.file-input-text');
            if (textSpan) {
                textSpan.textContent = filename;
            }
            return loadUploadColumns(fileInput, file);
        });
    }

    const sheetSelect = document.getElementById('sheetSelect');
    sheetSelect.addEventListener('change', function() {
        const sheetId = document.getElementById('selectedSheetId').value;
        previewSheetData(sheetId, this.value);
    });

    const templateInput = document.getElementById('templateId');
    templateInput.addEventListener('input', function() {
        updateTemplateSelection(templateInput.value);
    });
    const powerpointSource = document.getElementById('powerpointTemplateSource');
    powerpointSource.addEventListener('change', switchTemplateSource);
    document.getElementById('slidesTemplateSource').addEventListener('change', switchTemplateSource);
    if (powerpointSource.checked) switchTemplateSource();

    setupGenerationSubmission();
}

function setupDriveChooser(prefix, endpoint, fileType, fallback, onSelect) {
    const browse = document.getElementById(prefix + 'Browse');
    const panel = document.getElementById(prefix + 'List');
    const select = document.getElementById(prefix + 'Options');
    const more = document.getElementById(prefix + 'More');
    const status = document.getElementById(prefix + 'BrowseStatus');
    const files = new Map();
    let nextPage = '';

    function toggle(open) {
        panel.hidden = !open;
        browse.setAttribute('aria-expanded', String(open));
    }

    async function loadFiles(pageToken = '') {
        if (!pageToken) {
            files.clear();
            select.options.length = 1;
            more.hidden = true;
        }
        browse.disabled = more.disabled = select.disabled = true;
        status.textContent = 'Loading files from Google Drive…';
        const loadError = 'Could not load files from Google Drive. ' + fallback;
        try {
            const query = pageToken ? '?page_token=' + encodeURIComponent(pageToken) : '';
            const response = await fetch(endpoint + query, { cache: 'no-store' });
            const data = await response.json();
            if (!response.ok) {
                status.textContent = data.error || loadError;
                return;
            }
            for (const file of data.files) {
                if (files.has(file.id)) continue;
                files.set(file.id, file);
                const option = document.createElement('option');
                option.value = file.id;
                option.textContent = file.name;
                select.appendChild(option);
            }
            nextPage = data.next_page_token || '';
            more.hidden = !nextPage;
            status.textContent = files.size || nextPage ? '' : 'No ' + fileType + ' found. ' + fallback;
        } catch (error) {
            console.error('Could not list Drive files:', error);
            status.textContent = loadError;
        } finally {
            browse.disabled = more.disabled = select.disabled = false;
        }
    }

    browse.addEventListener('click', () => {
        toggle(panel.hidden);
        if (!panel.hidden) return loadFiles();
    });
    more.addEventListener('click', () => loadFiles(nextPage));
    select.addEventListener('change', () => {
        const file = files.get(select.value);
        if (!file) return;
        toggle(false);
        browse.focus();
        return onSelect(file);
    });
}

function extractTemplateId(input) {
    const value = input.trim();
    const link = value.match(/^https:\/\/docs\.google\.com\/presentation\/(?:u\/[0-9]+\/)?d\/([A-Za-z0-9_-]+)(?:[/?#]\S*)?$/);
    const id = link ? link[1] : value;
    return /^[A-Za-z0-9_-]{20,}$/.test(id) ? id : '';
}

function switchTemplateSource() {
    const usePowerPoint = document.getElementById('powerpointTemplateSource').checked;
    document.getElementById('slidesTemplateFields').hidden = usePowerPoint;
    document.getElementById('powerpointTemplateFields').hidden = !usePowerPoint;
    setFilenameFields([]);
    if (usePowerPoint) {
        updateTemplateSelection('');
        const useUpload = document.getElementById('csv-tab').classList.contains('active');
        updatePowerPointFilenameColumns(useUpload ? uploadColumns : driveColumns);
    } else {
        updateTemplateSelection(document.getElementById('templateId').value);
    }
}

function setFilenameFields(fields, selected = '') {
    const select = document.getElementById('filenameField');
    const defaultOption = document.createElement('option');
    defaultOption.value = '';
    defaultOption.textContent = 'Default filename field';
    select.replaceChildren(defaultOption);
    for (const field of fields) {
        const option = document.createElement('option');
        option.value = field;
        option.textContent = field;
        select.appendChild(option);
    }
    select.value = fields.includes(selected) ? selected : '';
    document.getElementById('filenamePlaceholderSelector').hidden = fields.length === 0;
}

function updateTemplateSelection(input, templateName = '') {
    const templateId = extractTemplateId(input);
    const version = ++templateSelectionVersion;
    const container = document.getElementById('filenamePlaceholderSelector');
    const selectedTemplateName = document.getElementById('selectedTemplateName');
    const status = document.getElementById('templateStatus');

    if (container.dataset.templateId !== templateId) {
        setFilenameFields([]);
        container.dataset.templateId = templateId;
    }
    selectedTemplateName.textContent = templateName;
    clearTimeout(templateLookupTimer);
    status.textContent = templateId ? 'Checking template…' : '';
    if (!templateId) return;
    if (templateName) return detectTemplatePlaceholders(templateId, version);
    templateLookupTimer = setTimeout(() => detectTemplatePlaceholders(templateId, version), 250);
}

async function detectTemplatePlaceholders(templateId, version) {
    const status = document.getElementById('templateStatus');
    const container = document.getElementById('filenamePlaceholderSelector');
    const select = document.getElementById('filenameField');
    try {
        const response = await fetch('/api/template/placeholders', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ template_id: templateId })
        });
        const data = await response.json();
        if (version !== templateSelectionVersion ||
            extractTemplateId(document.getElementById('templateId').value) !== templateId) return;

        if (!response.ok) {
            setFilenameFields([]);
            status.textContent = data.error || 'Could not read the Google Slides template. Try again.';
            return;
        }
        const previousValue = container.hidden ? data.placeholders?.[0] : select.value;
        setFilenameFields(data.placeholders || [], previousValue);
        status.textContent = data.placeholders?.length ? '' : 'This presentation has no certificate placeholders.';
    } catch (error) {
        console.error('Error detecting placeholders:', error);
        if (version === templateSelectionVersion) {
            setFilenameFields([]);
            status.textContent = 'Could not read the Google Slides template. Try again.';
        }
    }
}

function selectRecipientFile(file) {
    const isSheet = file.mimeType === 'application/vnd.google-apps.spreadsheet';
    const version = ++driveSelectionVersion;
    ++sheetPreviewVersion;
    selectedSheetReady = false;
    csvFromDriveContent = null;
    const selectedId = document.getElementById('selectedSheetId');
    const selectedName = document.getElementById('selectedSheetName');
    selectedId.value = isSheet ? file.id : ('csv:' + file.id);
    selectedName.textContent = file.name + (isSheet ? '' : ' (CSV)');
    document.getElementById('sheetSelect').replaceChildren();
    document.getElementById('sheetTabsGroup').style.display = 'none';
    clearDataPreview();
    switchTab('sheets');

    return isSheet ? loadSheetTabs(file.id, version) : downloadAndUseCsvFile(file.id, version);
}

function setDriveDataStatus(message) {
    document.getElementById('driveDataStatus').textContent = message;
}

function clearDataPreview() {
    driveColumns = [];
    if (document.getElementById('sheets-tab').classList.contains('active')) {
        updateGroupingColumns(driveColumns);
    }
    document.getElementById('previewContainer').style.display = 'none';
    document.getElementById('previewHead').replaceChildren();
    document.getElementById('previewBody').replaceChildren();
    document.getElementById('rowCount').textContent = '';
}

async function downloadAndUseCsvFile(fileId, version) {
    setDriveDataStatus('Loading CSV preview...');
    try {
        const response = await fetch('/api/drive/file/' + encodeURIComponent(fileId) + '/csv');
        const data = await response.json();
        if (version !== driveSelectionVersion) return;
        if (!response.ok) throw new Error(data.error || 'Could not load CSV data.');

        displayPreview(data.headers, data.rows, data.rows_count);
        if (data.rows_count > 0) {
            csvFromDriveContent = data.csv_content;
            setDriveDataStatus('');
        } else {
            setDriveDataStatus('This CSV has no data rows.');
        }
    } catch (error) {
        if (version === driveSelectionVersion) setDriveDataStatus(error.message);
    }
}

async function loadSheetTabs(sheetId, version) {
    setDriveDataStatus('Loading spreadsheet tabs...');
    try {
        const response = await fetch('/api/drive/sheets/' + encodeURIComponent(sheetId) + '/names');
        const data = await response.json();
        if (version !== driveSelectionVersion) return;
        if (!response.ok) throw new Error(data.error || 'Could not load spreadsheet tabs.');
        if (!data.sheets.length) throw new Error('Spreadsheet has no tabs.');

        const select = document.getElementById('sheetSelect');
        for (const sheet of data.sheets) {
            const option = document.createElement('option');
            option.value = sheet.properties.title;
            option.textContent = sheet.properties.title;
            select.appendChild(option);
        }
        select.selectedIndex = 0;
        document.getElementById('sheetTabsGroup').style.display = 'block';
        return previewSheetData(sheetId, select.value);
    } catch (error) {
        if (version === driveSelectionVersion) setDriveDataStatus(error.message);
    }
}

async function previewSheetData(sheetId, sheetName) {
    const version = ++sheetPreviewVersion;
    selectedSheetReady = false;
    clearDataPreview();
    setDriveDataStatus('');
    if (!sheetId || !sheetName) return;

    setDriveDataStatus('Loading sheet preview...');
    try {
        const response = await fetch('/api/sheets/preview', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sheets_id: sheetId, sheet_name: sheetName, rows: 5 })
        });
        const data = await response.json();
        if (version !== sheetPreviewVersion) return;
        if (!response.ok) throw new Error(data.error || 'Could not load sheet data.');

        displayPreview(data.headers, data.rows, data.total_rows);
        selectedSheetReady = data.total_rows > 0;
        setDriveDataStatus(selectedSheetReady ? '' : 'This tab has no data rows.');
    } catch (error) {
        if (version === sheetPreviewVersion) setDriveDataStatus(error.message);
    }
}

function switchTab(tabName) {
    const wasActive = document.getElementById(tabName + '-tab').classList.contains('active');
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.toggle('active', tab.id === tabName + '-tab');
    });
    document.querySelectorAll('.tab-btn').forEach(button => {
        button.classList.toggle('active', button.dataset.tab === tabName);
    });
    if (!wasActive) {
        updateGroupingColumns(tabName === 'csv' ? uploadColumns : driveColumns);
    }
    document.getElementById('uploadColumnStatus').hidden = tabName !== 'csv';
}

function displayPreview(headers, rows, totalRows) {
    driveColumns = totalRows > 0 ? headers : [];
    if (document.getElementById('sheets-tab').classList.contains('active')) {
        updateGroupingColumns(driveColumns);
    }
    const thead = document.getElementById('previewHead');
    const tbody = document.getElementById('previewBody');
    const headerRow = thead.insertRow();
    for (const header of headers) {
        const cell = document.createElement('th');
        cell.scope = 'col';
        cell.textContent = header ?? '';
        headerRow.appendChild(cell);
    }
    for (const row of rows) {
        const tableRow = tbody.insertRow();
        for (const value of row) {
            tableRow.insertCell().textContent = value ?? '';
        }
    }

    document.getElementById('rowCount').textContent = 'Showing ' + rows.length + ' of ' + totalRows + ' data rows';
    document.getElementById('previewContainer').style.display = 'block';
}

function updateGroupingColumns(headers) {
    const select = document.getElementById('groupByColumn');
    const defaultOption = document.createElement('option');
    defaultOption.value = '';
    defaultOption.textContent = headers.length ? 'No grouping' : 'Upload a file or select a sheet to see columns';
    select.replaceChildren(defaultOption);
    select.value = '';
    for (const header of headers) {
        const option = document.createElement('option');
        option.value = header;
        option.textContent = header;
        select.appendChild(option);
    }
    select.disabled = headers.length === 0;
    updatePowerPointFilenameColumns(headers);
}

function updatePowerPointFilenameColumns(headers) {
    if (!document.getElementById('powerpointTemplateSource').checked) return;
    setFilenameFields(headers, document.getElementById('filenameField').value);
}

async function loadUploadColumns(fileInput, file) {
    const isActive = () => document.getElementById('csv-tab').classList.contains('active');
    const status = document.getElementById('uploadColumnStatus');
    uploadColumns = [];
    if (isActive()) updateGroupingColumns(uploadColumns);
    status.textContent = file?.size ? 'Reading column names…' : '';
    if (!file?.size) return;

    const data = new FormData();
    data.append('csv_file', file);
    try {
        const response = await fetch('/api/upload/columns', { method: 'POST', body: data });
        const result = await response.json();
        if (fileInput.files[0] !== file) return;
        if (!response.ok) throw new Error(result.error);
        uploadColumns = result.headers;
        if (isActive()) updateGroupingColumns(uploadColumns);
        status.textContent = '';
    } catch (error) {
        if (fileInput.files[0] === file) {
            status.textContent = error.message || 'Could not read column names.';
        }
    }
}

const batchStoragePrefix = 'certificate-generator.batch.';
const pendingBatches = new Map();
let generationRequestActive = false;

function setupGenerationSubmission() {
    const form = document.getElementById('generateForm');
    if (!form) return;

    try {
        for (let index = 0; index < localStorage.length; index++) {
            const key = localStorage.key(index);
            if (key?.startsWith(batchStoragePrefix)) {
                const batch = JSON.parse(localStorage.getItem(key));
                if (batch?.id) pendingBatches.set(batch.id, batch);
            }
        }
    } catch {
        // The current page can still resume a batch if browser storage is unavailable.
    }
    updateBatchRecovery();

    form.addEventListener('submit', event => {
        event.preventDefault();
        return submitGeneration({ testMode: event.submitter?.id === 'startTestBtn' });
    });
    document.getElementById('testBtn').addEventListener('click', () => {
        document.getElementById('testCountGroup').style.display = 'block';
        document.getElementById('testCount').focus();
    });
    document.getElementById('cancelTestBtn').addEventListener('click', () => {
        document.getElementById('testCountGroup').style.display = 'none';
    });
    document.getElementById('resumeBatchBtn').addEventListener('click', () => submitGeneration({ resume: true }));
    document.getElementById('checkBatchBtn').addEventListener('click', checkBatchStatus);
}

function buildGenerationPayload(testCount, batch) {
    const data = new FormData();
    const usePowerPoint = batch ? batch.templateSource === 'powerpoint'
        : document.getElementById('powerpointTemplateSource').checked;
    if (usePowerPoint) {
        data.append('template_source', 'powerpoint');
        const file = document.getElementById('templateFile').files[0];
        if (file && !batch?.powerpointReady) {
            if (!/\.pptx?$/i.test(file.name)) throw new Error('Choose a .pptx or .ppt template.');
            if (!file.size) throw new Error('The selected PowerPoint template is empty.');
            data.append('template_file', file);
        } else if (!batch) {
            throw new Error('Choose a .pptx or .ppt template to upload.');
        }
    } else {
        const templateId = extractTemplateId(document.getElementById('templateId').value);
        if (!templateId) throw new Error('Select a Google Slides template or paste its link or file ID.');
        data.append('template_id', templateId);
    }

    if (document.getElementById('csv-tab').classList.contains('active')) {
        const fileInput = document.getElementById('csvFile');
        const file = fileInput.files[0];
        if (!file) throw new Error('Choose a data file to upload.');
        if (!file.size) throw new Error('The selected data file is empty.');
        if (!fileInput.accept.split(',').some(extension => file.name.toLowerCase().endsWith(extension))) {
            throw new Error('Choose one of the supported data file formats.');
        }
        data.append('csv_file', file);
    } else if (document.getElementById('sheets-tab').classList.contains('active')) {
        const driveId = document.getElementById('selectedSheetId').value;
        if (!driveId) throw new Error('Select a spreadsheet or CSV file from Google Drive.');

        if (driveId.startsWith('csv:')) {
            if (!csvFromDriveContent?.trim()) {
                throw new Error('The Drive CSV is empty or still loading. Wait for the preview or select another file.');
            }
            data.append('csv_file', new Blob([csvFromDriveContent], { type: 'text/csv' }), 'data.csv');
        } else {
            if (!selectedSheetReady) {
                throw new Error('Wait for the sheet preview and choose a tab with data rows.');
            }
            const sheetName = document.getElementById('sheetSelect').value;
            if (!sheetName) throw new Error('Select a tab from the spreadsheet.');
            data.append('sheets_id', driveId);
            data.append('sheet_name', sheetName);
        }
    } else {
        throw new Error('Select a data source.');
    }

    const outputFolder = document.getElementById('outputFolder').value.trim() || 'Certificate Generator';
    data.append('output_folder', outputFolder);
    const filenameField = batch?.filenameField ?? document.getElementById('filenameField').value;
    if (filenameField) data.append('filename_field', filenameField);
    const groupByColumn = document.getElementById('groupByColumn').value;
    if (groupByColumn) data.append('group_by_column', groupByColumn);

    if (testCount !== null) {
        const input = document.getElementById('testCount');
        if (!Number.isInteger(testCount) || testCount < Number(input.min) || testCount > Number(input.max)) {
            throw new Error(`Enter a whole number from ${input.min} to ${input.max} for First N.`);
        }
        data.append('test_mode', 'true');
        data.append('test_count', testCount);
    }
    return data;
}

function updateBatchRecovery(selectedId) {
    const select = document.getElementById('recoveryBatchSelect');
    const previous = selectedId || select.value;
    select.replaceChildren();
    for (const batch of [...pendingBatches.values()].sort((a, b) => b.startedAt - a.startedAt)) {
        const option = document.createElement('option');
        option.value = batch.id;
        const action = batch.testCount === null ? 'Generate' : `First ${batch.testCount}`;
        option.textContent = `${action} · ${new Date(batch.startedAt).toLocaleString()} · ${batch.id.slice(-6)}`;
        select.appendChild(option);
    }
    if (pendingBatches.has(previous)) select.value = previous;
    document.getElementById('batchRecovery').hidden = pendingBatches.size === 0;
}

function rememberBatch(batch) {
    pendingBatches.set(batch.id, batch);
    try {
        const { id, testCount, startedAt, groupByColumn, templateSource, filenameField, powerpointReady } = batch;
        localStorage.setItem(batchStoragePrefix + id, JSON.stringify({
            id, testCount, startedAt, groupByColumn, templateSource, filenameField, powerpointReady,
        }));
    } catch {
        // Keep the batch available for recovery on the current page.
    }
    updateBatchRecovery(batch.id);
}

function clearBatch(batch) {
    pendingBatches.delete(batch.id);
    try {
        localStorage.removeItem(batchStoragePrefix + batch.id);
    } catch {
        // The current page can still clear the batch.
    }
    updateBatchRecovery();
}

function selectedRecoveryBatch() {
    return pendingBatches.get(document.getElementById('recoveryBatchSelect').value);
}

async function runGenerationAction(message, request) {
    if (generationRequestActive) return;
    generationRequestActive = true;
    const buttons = ['generateBtn', 'testBtn', 'startTestBtn', 'resumeBatchBtn', 'checkBatchBtn']
        .map(id => document.getElementById(id));
    buttons.forEach(button => { button.disabled = true; });
    document.getElementById('resultContainer').style.display = 'none';
    showLoading(message);
    try {
        await request();
    } catch (error) {
        showError('Error', error.message || 'Request failed.');
    } finally {
        hideLoading();
        buttons.forEach(button => { button.disabled = false; });
        generationRequestActive = false;
    }
}

function submitGeneration({ testMode = false, resume = false } = {}) {
    const message = resume ? 'Resuming certificate generation...' : 'Generating certificates...';
    return runGenerationAction(message, async () => {
        const batch = resume ? selectedRecoveryBatch() : null;
        if (resume && !batch) return;
        const testCount = batch ? batch.testCount : testMode ? Number(document.getElementById('testCount').value) : null;
        const needsPowerPoint = batch?.templateSource === 'powerpoint' && !batch.powerpointReady &&
            !batch.data?.has('template_file');
        const data = (needsPowerPoint ? null : batch?.data) || buildGenerationPayload(testCount, batch);
        if (batch?.groupByColumn !== undefined) {
            if (batch.groupByColumn) data.set('group_by_column', batch.groupByColumn);
            else data.delete('group_by_column');
        }
        let batchId = batch?.id;
        if (!batchId) {
            const response = await fetch('/api/generation-batches/new', { cache: 'no-store' });
            const reservation = await response.json();
            if (!response.ok || !reservation.batch_id) {
                throw new Error(reservation.error || 'Could not start a generation batch.');
            }
            batchId = reservation.batch_id;
        }

        data.set('batch_id', batchId);
        const savedBatch = {
            id: batchId, testCount, data,
            startedAt: batch?.startedAt ?? Date.now(),
            groupByColumn: data.get('group_by_column') || '',
            templateSource: data.get('template_source') || 'slides',
            filenameField: data.get('filename_field') || '',
            powerpointReady: batch?.powerpointReady || false,
        };
        rememberBatch(savedBatch);
        let body = data;
        if (resume) {
            body = new FormData();
            data.forEach((value, key) => body.append(key, value));
            body.set('retry_failed', 'true');
        }

        let result;
        let previousPending = Infinity;
        let stalledRequests = 0;
        while (true) {
            let response;
            try {
                response = await fetch('/api/generate', { method: 'POST', body });
                result = await response.json();
            } catch (error) {
                throw new Error(`Generation paused. Use Check Batch Status or Resume Batch to recover it. ${error.message}`);
            }

            const summary = result.summary;
            if (savedBatch.templateSource === 'powerpoint' && !savedBatch.powerpointReady && summary &&
                ['pending', 'partial', 'completed'].includes(result.status)) {
                const continuation = new FormData();
                data.forEach((value, key) => {
                    if (key !== 'template_file') continuation.append(key, value);
                });
                savedBatch.data = continuation;
                savedBatch.powerpointReady = true;
                rememberBatch(savedBatch);
            }
            const pending = summary?.pending_rows;
            if (response.status !== 202 || result.status !== 'pending' || !(pending > 0)) break;
            // Older running servers report a Drive interruption only in the error details.
            if (summary.interrupted || summary.errors?.some(error => error.startsWith('Generation paused after a Drive error.'))) break;

            stalledRequests = pending < previousPending ? 0 : stalledRequests + 1;
            if (stalledRequests >= 2) {
                result.message = 'Generation paused because no new rows were processed. Use Resume Batch to try again.';
                break;
            }

            showLoading(`Generating certificates… ${summary.created_pdfs} saved, ${pending} remaining.`);
            previousPending = pending;
            body = savedBatch.data;
        }

        const outputFolder = data.get('output_folder') + (testCount === null ? '' : ' (TEST)');
        renderGenerationResult(result, outputFolder);

        if ((result.status === 'completed' && !result.summary?.cleanup_pending) ||
            (!resume && result.status === 'invalid_request')) {
            clearBatch(savedBatch);
        }
        if (result.status === 'completed' && testCount !== null) {
            document.getElementById('testCountGroup').style.display = 'none';
        }
    });
}

function checkBatchStatus() {
    return runGenerationAction('Checking generation status...', async () => {
        const batch = selectedRecoveryBatch();
        if (!batch) return;
        const response = await fetch(`/api/generation-batches/${encodeURIComponent(batch.id)}`, { cache: 'no-store' });
        if (response.status === 404) {
            throw new Error('The batch has no saved progress yet. Resume the batch to try again.');
        }
        const result = await response.json();
        renderGenerationResult(result);
        if (result.status === 'completed' && !result.summary?.cleanup_pending) clearBatch(batch);
    });
}

// Show loading state
function showLoading(message = 'Processing...') {
    const container = document.getElementById('progressContainer');
    if (container) {
        container.style.display = 'block';
        const text = document.getElementById('progressText');
        if (text) {
            text.textContent = message;
        }
    }
}

// Hide loading state
function hideLoading() {
    const container = document.getElementById('progressContainer');
    if (container) {
        container.style.display = 'none';
    }
}

// Show success message
function renderGenerationResult(result, outputFolder) {
    const summary = result.summary || {};
    const created = summary.created_pdfs ?? summary.success ?? 0;
    const failed = summary.failed_rows ?? summary.failed ?? 0;
    const successful = summary.successful_rows ?? summary.success ?? 0;
    const status = result.status || (created > 0 ? (failed ? 'partial' : 'completed') : 'failed');
    const presentations = {
        completed: ['Generation complete', 'success'],
        partial: ['Generation partially complete', 'partial'],
        pending: ['Generation pending', 'pending'],
        invalid_request: ['Invalid generation request', 'error'],
        failed: ['Generation failed', 'error'],
    };
    const [title, appearance] = presentations[status] || presentations.failed;
    const details = [];
    if (result.summary) {
        details.push(
            ['Input rows', summary.input_rows ?? summary.total ?? 0],
            ['Attempted rows', summary.attempted_rows ?? successful + failed],
            ['Successful rows', successful],
            ['Failed rows', failed],
            ['Created PDFs', created]
        );
        if (summary.pending_rows) {
            details.push(['Pending rows', summary.pending_rows]);
        }
        if (summary.cleanup_pending) {
            details.push(['Temporary Slides', 'Cleanup is pending. Check batch status again to retry.']);
        }
    }

    const folder = result.output_folder || outputFolder;
    const message = result.message || result.error || 'Failed to generate certificates.';
    const errors = (summary.errors || []).filter(error => error !== message);
    renderResult(
        title, appearance, message, details, errors,
        created > 0 && folder ? folder : '', summary.output_folder_id
    );
}

function renderResult(title, appearance, message, details, errors, folder, folderId) {
    const container = document.getElementById('resultContainer');
    if (!container) return;

    const isError = appearance === 'error';
    const active = document.getElementById(isError ? 'errorResult' : 'successResult');
    const inactive = document.getElementById(isError ? 'successResult' : 'errorResult');
    const messageElement = document.getElementById(isError ? 'errorMessage' : 'successMessage');
    const detailElement = document.getElementById(isError ? 'errorDetails' : 'successDetails');
    active.querySelector('h3').textContent = title;
    active.className = 'result result-' + appearance;
    messageElement.textContent = message;
    detailElement.replaceChildren();

    if (details.length || errors.length) {
        const list = document.createElement('ul');
        const rows = details.map(([label, value]) => label + ': ' + value).concat(errors);
        rows.forEach(row => {
            const item = document.createElement('li');
            item.textContent = row;
            list.appendChild(item);
        });
        detailElement.appendChild(list);
    }
    if (folder) {
        const path = document.createElement('p');
        path.textContent = 'Certificates saved to your Google Drive in "' + folder + '".';
        if (folderId) {
            const link = document.createElement('a');
            link.href = `https://drive.google.com/drive/folders/${encodeURIComponent(folderId)}`;
            link.target = '_blank';
            link.rel = 'noopener';
            link.textContent = 'Open output folder';
            path.textContent += ' ';
            path.appendChild(link);
        }
        detailElement.appendChild(path);
    }

    inactive.style.display = 'none';
    active.style.display = 'block';
    container.style.display = 'block';
}

function showError(title, message) {
    renderResult(title, 'error', message, [], [], '');
}

// Utility: Format file size
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

// Utility: Format duration
function formatDuration(seconds) {
    if (seconds < 60) return Math.round(seconds) + 's';
    const minutes = Math.floor(seconds / 60);
    const secs = Math.round(seconds % 60);
    return minutes + 'm ' + secs + 's';
}

// Copy to clipboard
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        alert('Copied to clipboard!');
    }).catch(() => {
        alert('Failed to copy');
    });
}

console.log('Certificate Generator Web App loaded');
