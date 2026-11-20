/* Certificate Generator Web App - JavaScript */

// Google Picker API key and credentials
let pickerApiLoaded = false;
let pickerAuthToken = null;
let csvFromDriveContent = null;  // Store CSV content when selected from Drive
let selectedSheetReady = false;
let driveSelectionVersion = 0;
let sheetPreviewVersion = 0;
let templateSelectionVersion = 0;
let templateLookupTimer;

// Initialize app
document.addEventListener('DOMContentLoaded', function() {
    if (!document.getElementById('generateForm')) return;

    setupEventListeners();
    loadUserInfo();
    initializeGooglePicker();
});

async function loadUserInfo() {
    try {
        const response = await fetch('/api/user');
        if (!response.ok) {
            window.location.href = '/login';
            return;
        }
        const data = await response.json();
        console.log('User info loaded:', data.email);
    } catch (error) {
        console.error('Error loading user info:', error);
    }
}

function initializeGooglePicker() {
    if (typeof gapi === 'undefined') return;

    gapi.load('picker', { 'callback': onPickerApiLoad });
    
    // Get OAuth token for Picker
    fetch('/api/auth-token')
        .then(res => res.json())
        .then(data => {
            pickerAuthToken = data.token;
            console.log('Auth token loaded for Picker');
        })
        .catch(err => console.error('Error getting auth token:', err));
}

function onPickerApiLoad() {
    pickerApiLoaded = true;
    console.log('Google Picker API loaded');
}

function setupEventListeners() {
    // Tab switching
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const tabName = this.getAttribute('data-tab');
            switchTab(tabName);
        });
    });

    // Open Google Picker button
    const openPickerButton = document.getElementById('openGooglePicker');
    if (openPickerButton) {
        openPickerButton.addEventListener('click', openGooglePicker);
    }
    
    // Open Slide Picker button
    const openSlidePickerButton = document.getElementById('openSlidePicker');
    if (openSlidePickerButton) {
        openSlidePickerButton.addEventListener('click', openSlidePicker);
    }

    // File input
    const fileInput = document.getElementById('csvFile');
    if (fileInput) {
        fileInput.addEventListener('change', function() {
            const filename = this.files[0]?.name || 'Choose data file';
            const textSpan = document.querySelector('.file-input-text');
            if (textSpan) {
                textSpan.textContent = filename;
            }
        });
    }

    const sheetSelect = document.getElementById('sheetSelect');
    sheetSelect.addEventListener('change', function() {
        const sheetId = document.getElementById('selectedSheetId').value;
        previewSheetData(sheetId, this.value);
    });

    const templateInput = document.getElementById('templateId');
    templateInput.addEventListener('input', function() {
        updateTemplateSelection(templateInput.value.trim());
    });

    setupGenerationSubmission();
}

function openGooglePicker() {
    if (!pickerApiLoaded || !pickerAuthToken) {
        setDriveDataStatus('Google Picker is unavailable. Please try again.');
        return;
    }

    const csvView = new google.picker.DocsView(google.picker.ViewId.DOCS)
        .setMimeTypes('text/csv,application/csv,application/vnd.ms-excel');
    const picker = new google.picker.PickerBuilder()
        .addView(google.picker.ViewId.SPREADSHEETS)
        .addView(csvView)
        .addView(new google.picker.DocsUploadView())
        .setOAuthToken(pickerAuthToken)
        .setCallback(handlePickerResponse)
        .build();
    
    picker.setVisible(true);
}

function openSlidePicker() {
    if (!pickerApiLoaded || !pickerAuthToken) {
        showError('Error', 'Google Picker is still loading. Please try again.');
        return;
    }
    
    // Create Picker for Google Presentations (Slides) only
    const picker = new google.picker.PickerBuilder()
        .addView(google.picker.ViewId.PRESENTATIONS)  // Google Slides/Presentations
        .setOAuthToken(pickerAuthToken)
        .setCallback(handleSlidePickerResponse)
        .build();
    
    picker.setVisible(true);
}

function handleSlidePickerResponse(data) {
    if (data[google.picker.Response.ACTION] !== google.picker.Action.PICKED) return;

    const doc = data[google.picker.Response.DOCUMENTS][0];
    if (doc.mimeType !== 'application/vnd.google-apps.presentation') {
        showError('Error', 'Please select a Google Slides presentation.');
        return;
    }

    document.getElementById('templateId').value = doc.id;
    updateTemplateSelection(doc.id, doc.name);
}

function updateTemplateSelection(templateId, templateName = '') {
    const version = ++templateSelectionVersion;
    const container = document.getElementById('filenamePlaceholderSelector');
    const filenameField = document.getElementById('filenameField');
    const selectedTemplateName = document.getElementById('selectedTemplateName');

    if (container.dataset.templateId !== templateId) {
        container.hidden = true;
        filenameField.options.length = 1;
        filenameField.value = '';
        container.dataset.templateId = templateId;
    }
    selectedTemplateName.textContent = templateName ? ('? ' + templateName) : 'Click to browse...';
    clearTimeout(templateLookupTimer);
    if (/^[a-zA-Z0-9_-]{20,}$/.test(templateId)) {
        templateLookupTimer = setTimeout(() => detectTemplatePlaceholders(templateId, version), 250);
    }
}

async function detectTemplatePlaceholders(templateId, version) {
    try {
        const response = await fetch('/api/template/placeholders', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ template_id: templateId })
        });
        if (!response.ok || version !== templateSelectionVersion) return;

        const data = await response.json();
        if (version !== templateSelectionVersion ||
            document.getElementById('templateId').value.trim() !== templateId) return;

        const container = document.getElementById('filenamePlaceholderSelector');
        const select = document.getElementById('filenameField');
        const previousValue = container.hidden ? data.placeholders?.[0] : select.value;
        select.options.length = 1;
        for (const placeholder of data.placeholders || []) {
            const option = document.createElement('option');
            option.value = placeholder;
            option.textContent = placeholder;
            select.appendChild(option);
        }
        select.value = previousValue ?? '';
        container.hidden = select.options.length === 1;
    } catch (error) {
        console.error('Error detecting placeholders:', error);
    }
}

function handlePickerResponse(data) {
    if (data[google.picker.Response.ACTION] !== google.picker.Action.PICKED) return;

    const doc = data[google.picker.Response.DOCUMENTS][0];
    const isCsv = doc.mimeType === 'text/csv' || doc.mimeType === 'application/csv' ||
        /[.]csv$/i.test(doc.name);
    const isSheet = doc.mimeType === 'application/vnd.google-apps.spreadsheet';
    const version = ++driveSelectionVersion;
    ++sheetPreviewVersion;
    selectedSheetReady = false;
    csvFromDriveContent = null;
    const selectedId = document.getElementById('selectedSheetId');
    const selectedName = document.getElementById('selectedSheetName');
    selectedId.value = '';
    selectedName.textContent = 'Click to browse...';
    document.getElementById('sheetSelect').replaceChildren();
    document.getElementById('sheetTabsGroup').style.display = 'none';
    clearDataPreview();
    switchTab('sheets');

    if (!isCsv && !isSheet) {
        setDriveDataStatus('Please select a Google Sheet or a CSV file.');
        return;
    }
    selectedId.value = isCsv ? ('csv:' + doc.id) : doc.id;
    selectedName.textContent = doc.name + (isCsv ? ' (CSV)' : '');

    if (isCsv) {
        return downloadAndUseCsvFile(doc.id, version);
    }
    return loadSheetTabs(doc.id, version);
}

function setDriveDataStatus(message) {
    document.getElementById('driveDataStatus').textContent = message;
}

function clearDataPreview() {
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
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.toggle('active', tab.id === tabName + '-tab');
    });
    document.querySelectorAll('.tab-btn').forEach(button => {
        button.classList.toggle('active', button.dataset.tab === tabName);
    });
}

function displayPreview(headers, rows, totalRows) {
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

function buildGenerationPayload(testCount) {
    const templateId = document.getElementById('templateId').value.trim();
    if (!templateId) throw new Error('Enter or select a Google Slides template.');
    if (!/^[A-Za-z0-9_-]{20,}$/.test(templateId)) {
        throw new Error('Enter a valid template ID from the Google Slides URL.');
    }

    const data = new FormData();
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

    data.append('template_id', templateId);
    const outputFolder = document.getElementById('outputFolder').value.trim() || 'Certificate Generator';
    data.append('output_folder', outputFolder);
    const filenameField = document.getElementById('filenameField')?.value;
    if (filenameField) data.append('filename_field', filenameField);

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
        const { id, testCount, startedAt } = batch;
        localStorage.setItem(batchStoragePrefix + id, JSON.stringify({ id, testCount, startedAt }));
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
        const data = batch?.data || buildGenerationPayload(testCount);
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
        if (resume) data.set('retry_failed', 'true');
        const savedBatch = { id: batchId, testCount, data, startedAt: batch?.startedAt ?? Date.now() };
        rememberBatch(savedBatch);
        const response = await fetch('/api/generate', { method: 'POST', body: data });
        const result = await response.json();
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
        created > 0 && folder ? folder : ''
    );
}

function renderResult(title, appearance, message, details, errors, folder) {
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
