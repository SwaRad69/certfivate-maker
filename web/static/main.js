/* Certificate Generator Web App - JavaScript */

// Google Picker API key and credentials
let pickerApiLoaded = false;
let pickerAuthToken = null;
let csvFromDriveContent = null;  // Store CSV content when selected from Drive
let selectedSheetsLoaded = false;  // Track if sheet tabs have been loaded

// Initialize app
document.addEventListener('DOMContentLoaded', function() {
    // Load user info and initialize Picker
    loadUserInfo();
    
    // Load Google Picker API
    initializeGooglePicker();
    
    // Setup event listeners
    setupEventListeners();
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
    // Load Google APIs library and get auth token
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
            const filename = this.files[0]?.name || 'Choose CSV or Excel file';
            const textSpan = document.querySelector('.file-input-text');
            if (textSpan) {
                textSpan.textContent = filename;
            }
        });
    }

    // Sheet selector
    const sheetSelect = document.getElementById('sheetSelect');
    if (sheetSelect) {
        sheetSelect.addEventListener('change', function() {
            if (this.value) {
                const sheetId = document.getElementById('selectedSheetId').value;
                previewSheetData(sheetId, this.value);
            }
        });
    }

    // Form submission
    const generateForm = document.getElementById('generateForm');
    if (generateForm) {
        generateForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            // Get the actual data available, not just which tab looks active
            const sheetId = document.getElementById('selectedSheetId').value;
            const csvFile = document.getElementById('csvFile').files[0];
            const templateId = document.getElementById('templateId').value.trim();
            
            console.log('Form submission - Available data:', { 
                hasSheetId: !!sheetId, 
                hasCSVFile: !!csvFile, 
                hasTemplateId: !!templateId 
            });
            
            // Validate template ID first (required in all cases)
            if (!templateId) {
                showError('Error', 'Please enter or select a template');
                return;
            }
            if (templateId.length < 20) {
                showError('Error', 'Template ID appears to be invalid (too short)');
                return;
            }
            
            // Determine which data source to use
            // Priority: Google Sheet > CSV File > Error
            if (sheetId) {
                // User has selected a Google Sheet or Drive CSV
                console.log('Using Google Sheets/Drive source');
                
                // Check if it's a CSV file from Drive
                if (sheetId.startsWith('csv:')) {
                    // Submit CSV from Drive
                    console.log('Submitting CSV from Drive');
                    if (!csvFromDriveContent) {
                        showError('Error', 'CSV content not loaded. Please reselect the CSV file.');
                        return;
                    }
                    await submitFormWithDriveCSV(csvFromDriveContent, templateId);
                } else {
                    // Regular Google Sheet - ensure sheets are loaded
                    if (!selectedSheetsLoaded) {
                        showError('Error', 'Sheet tabs are still loading. Please wait a moment and try again.');
                        return;
                    }
                    
                    const sheetName = document.getElementById('sheetSelect').value;
                    console.log('Submitting Google Sheet:', { sheetId, sheetName });
                    
                    if (!sheetName) {
                        showError('Error', 'Please select a sheet tab from the dropdown that appeared after selecting your Google Sheet.');
                        return;
                    }
                    await submitFormWithSheetsId(sheetId, sheetName, templateId);
                }
            } else if (csvFile) {
                // User uploaded a CSV file directly
                console.log('Using uploaded CSV file');
                await submitFormWithCSV(csvFile, templateId);
            } else {
                // No data source selected
                showError('Error', 'Please either:\n1. Click "📊 Open Google Drive Picker" to select a Google Sheet or CSV file\n2. Click "Choose data file" to upload a CSV or Excel file');
                return;
            }
        });
    }
}

function openGooglePicker() {
    // Check if API is loaded
    if (!pickerApiLoaded) {
        showError('Error', 'Google Picker is still loading. Please try again.');
        return;
    }
    
    // Create Picker with both Spreadsheets and CSV support
    const picker = new google.picker.PickerBuilder()
        .addView(google.picker.ViewId.SPREADSHEETS)  // Google Sheets
        .addView(new google.picker.DocsUploadView())  // All files (for CSV)
        .setOAuthToken(pickerAuthToken)
        .setCallback(handlePickerResponse)
        .build();
    
    picker.setVisible(true);
}

function openSlidePicker() {
    // Check if API is loaded
    if (!pickerApiLoaded) {
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
    const action = data[google.picker.Response.ACTION];
    
    if (action === google.picker.Action.PICKED) {
        const doc = data[google.picker.Response.DOCUMENTS][0];
        const slideId = doc.id;
        const slideName = doc.name;
        const mimeType = doc.mimeType || 'unknown';
        
        console.log('Slide picker selection:', { id: slideId, name: slideName, mimeType: mimeType });
        
        // Validate it's a presentation
        if (!mimeType.includes('presentation')) {
            showError('Error', `Selected file is not a Google Slide (${mimeType}). Please select a Google Slides presentation.`);
            return;
        }
        
        // Set the template ID and display name
        document.getElementById('templateId').value = slideId;
        document.getElementById('selectedTemplateName').textContent = `✓ ${slideName}`;
        
        console.log('Template selected:', slideName);
    } else if (action === google.picker.Action.CANCEL) {
        console.log('Slide picker cancelled');
    }
}

function handlePickerResponse(data) {
    const action = data[google.picker.Response.ACTION];
    
    if (action === google.picker.Action.PICKED) {
        const doc = data[google.picker.Response.DOCUMENTS][0];
        const fileId = doc.id;
        const fileName = doc.name;
        const mimeType = doc.mimeType || 'unknown';
        
        console.log('Picker selection:', { id: fileId, name: fileName, mimeType: mimeType });
        
        // Ensure sheets tab is active
        switchTab('sheets');
        
        // Check if it's a CSV file
        if (mimeType === 'text/csv' || fileName.endsWith('.csv')) {
            // Handle CSV file - download and use directly
            downloadAndUseCsvFile(fileId, fileName);
            return;
        }
        
        // Check if it's a Google Sheet
        if (!mimeType.includes('spreadsheet')) {
            showError('Error', `Selected file is not supported (${mimeType}). Please select either a Google Sheet or a CSV file.`);
            return;
        }
        
        // It's a Google Sheet - load sheet tabs
        document.getElementById('selectedSheetId').value = fileId;
        document.getElementById('selectedSheetName').textContent = `✓ ${fileName}`;
        loadSheetTabs(fileId);
    } else if (action === google.picker.Action.CANCEL) {
        console.log('Picker cancelled');
    }
}

async function downloadAndUseCsvFile(fileId, fileName) {
    try {
        console.log('Downloading CSV file:', fileName);
        
        // Use Google Drive API to export file as CSV
        const response = await fetch(`/api/drive/file/${fileId}/csv`, {
            method: 'GET'
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            showError('Error', errorData.error || 'Failed to download CSV file');
            return;
        }
        
        const data = await response.json();
        
        // Store CSV content for form submission
        csvFromDriveContent = data.csv_content;
        
        // Show file info and populate CSV content
        document.getElementById('selectedSheetId').value = `csv:${fileId}`;  // Mark as CSV
        document.getElementById('selectedSheetName').textContent = `✓ ${fileName} (CSV)`;
        
        // Show preview
        populateCsvPreview(data.csv_content, data.rows_count);
        
        // Show sheet tabs group as info
        const sheetTabsGroup = document.getElementById('sheetTabsGroup');
        sheetTabsGroup.innerHTML = `<div class="form-group"><small>CSV file selected: ${data.rows_count} data rows</small></div>`;
        sheetTabsGroup.style.display = 'block';
        
        // Show preview container
        showCsvPreview(data.csv_content);
        
    } catch (error) {
        console.error('Error downloading CSV file:', error);
        showError('Error', 'Failed to download CSV file. Check your internet connection.');
    }
}

function populateCsvPreview(csvContent, rowCount) {
    console.log(`CSV preview: ${rowCount} rows`);
}

function showCsvPreview(csvContent) {
    // Parse CSV and show preview
    const lines = csvContent.trim().split('\n').slice(0, 6);  // First 5 rows + header
    const rows = lines.map(line => {
        // Simple CSV parsing (handles basic cases)
        return line.split(',').map(cell => cell.trim());
    });
    
    const previewContainer = document.getElementById('previewContainer');
    const previewHead = document.getElementById('previewHead');
    const previewBody = document.getElementById('previewBody');
    const rowCount = document.getElementById('rowCount');
    
    // Clear existing
    previewHead.innerHTML = '';
    previewBody.innerHTML = '';
    
    if (rows.length > 0) {
        // Header row
        const headerRow = document.createElement('tr');
        rows[0].forEach(cell => {
            const th = document.createElement('th');
            th.textContent = cell;
            headerRow.appendChild(th);
        });
        previewHead.appendChild(headerRow);
        
        // Data rows
        rows.slice(1).forEach(row => {
            const tr = document.createElement('tr');
            row.forEach(cell => {
                const td = document.createElement('td');
                td.textContent = cell;
                tr.appendChild(td);
            });
            previewBody.appendChild(tr);
        });
    }
    
    previewContainer.style.display = 'block';
}

async function loadSheetTabs(sheetId) {
    try {
        console.log('Loading sheet tabs for ID:', sheetId);
        
        if (!sheetId || sheetId.length < 20) {
            showError('Error', 'Invalid spreadsheet ID format');
            return;
        }
        
        const response = await fetch(`/api/drive/sheets/${sheetId}/names`);
        
        if (!response.ok) {
            const errorData = await response.json();
            const errorMsg = errorData.error || `HTTP ${response.status}`;
            showError('Error', errorMsg);
            return;
        }
        
        const data = await response.json();
        populateDriveSheetTabs(data.sheets);
    } catch (error) {
        console.error('Error loading sheet tabs:', error);
        showError('Error', 'Failed to load sheet tabs. Check your internet connection and try again.');
    }
}

function populateDriveSheetTabs(sheets) {
    const select = document.getElementById('sheetSelect');
    select.innerHTML = '';
    
    sheets.forEach(sheet => {
        const option = document.createElement('option');
        option.value = sheet.properties.title;
        option.textContent = sheet.properties.title;
        select.appendChild(option);
    });
    
    // Show the sheet tabs selector
    document.getElementById('sheetTabsGroup').style.display = 'block';
    
    // Auto-select first sheet if available
    if (sheets.length > 0) {
        select.selectedIndex = 0;
        selectedSheetsLoaded = true;  // Mark sheets as loaded
        const firstSheet = sheets[0].properties.title;
        const sheetId = document.getElementById('selectedSheetId').value;
        previewSheetData(sheetId, firstSheet);
    } else {
        selectedSheetsLoaded = false;
    }
}

async function previewSheetData(sheetId, sheetName) {
    try {
        // Use the Google Sheets API via preview endpoint
        const response = await fetch('/api/sheets/list', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ 
                sheets_url: `https://docs.google.com/spreadsheets/d/${sheetId}/`,
                sheet_name: sheetName,
                rows: 5
            })
        });
        
        if (!response.ok) {
            console.error('Error loading preview');
            return;
        }
        
        const data = await response.json();
        displayPreview(data.headers, data.rows, data.total_rows);
    } catch (error) {
        console.error('Error previewing sheet:', error);
    }
}

function switchTab(tabName) {
    // Hide all tabs
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    
    // Remove active from all buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Show selected tab
    document.getElementById(tabName + '-tab').classList.add('active');
    
    // Mark button as active
    document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
}

function populateSheetSelector(sheets) {
    const select = document.getElementById('sheetSelect');
    select.innerHTML = '';
    
    sheets.forEach(sheet => {
        const option = document.createElement('option');
        option.value = sheet.properties.title;
        option.textContent = sheet.properties.title;
        select.appendChild(option);
    });
    
    // Auto-select first sheet if available
    if (sheets.length > 0) {
        select.selectedIndex = 0;
        const firstSheet = sheets[0].properties.title;
        const sheetsUrl = document.getElementById('sheetsUrl').value;
        previewSheetData(sheetsUrl, firstSheet);
    }
}

async function previewSheetData(sheetsUrl, sheetName) {
    try {
        const response = await fetch('/api/sheets/preview', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ 
                sheets_url: sheetsUrl,
                sheet_name: sheetName,
                rows: 5
            })
        });
        
        if (!response.ok) {
            console.error('Error loading preview');
            return;
        }
        
        const data = await response.json();
        displayPreview(data.headers, data.rows, data.total_rows);
    } catch (error) {
        console.error('Error previewing sheet:', error);
    }
}

function displayPreview(headers, rows, totalRows) {
    const previewDiv = document.getElementById('previewContainer');
    const thead = document.getElementById('previewHead');
    const tbody = document.getElementById('previewBody');
    const rowCount = document.getElementById('rowCount');
    
    // Create header
    thead.innerHTML = '<tr>' + headers.map(h => `<th>${h}</th>`).join('') + '</tr>';
    
    // Create body rows
    tbody.innerHTML = rows.map(row => {
        return '<tr>' + row.map(cell => `<td>${cell || '-'}</td>`).join('') + '</tr>';
    }).join('');
    
    rowCount.textContent = `Total rows: ${totalRows}`;
    previewDiv.style.display = 'block';
}

// Submit form with CSV content from Google Drive
async function submitFormWithDriveCSV(csvContent, templateId) {
    try {
        showLoading('Generating certificates from CSV file...');
        
        // Create a Blob from CSV content and convert to File object
        const csvBlob = new Blob([csvContent], { type: 'text/csv' });
        const csvFile = new File([csvBlob], 'data.csv', { type: 'text/csv' });
        
        const formData = new FormData();
        formData.append('csv_file', csvFile);
        formData.append('template_id', templateId);
        formData.append('output_folder', document.getElementById('outputFolder')?.value || 'Certificate Generator');
        
        const response = await fetch('/api/generate', {
            method: 'POST',
            body: formData
        });
        
        hideLoading();
        
        if (!response.ok) {
            const error = await response.json();
            showError('Error', error.error || 'Failed to generate certificates');
            return;
        }
        
        const result = await response.json();
        showSuccess('Success', result.message, `
            <p><strong>Results:</strong></p>
            <ul>
                <li>Generated: ${result.summary.success || 0}</li>
                <li>Failed: ${result.summary.failed || 0}</li>
                <li>Duration: ${result.summary.duration || 'N/A'}s</li>
            </ul>
            <p>Certificates saved to your Google Drive!</p>
        `);
    } catch (error) {
        hideLoading();
        showError('Error', error.message || 'Request failed');
    }
}

// Submit form with CSV file
async function submitFormWithCSV(csvFile, templateId) {
    try {
        showLoading('Generating certificates...');
        
        const formData = new FormData();
        formData.append('csv_file', csvFile);
        formData.append('template_id', templateId);
        formData.append('output_folder', document.getElementById('outputFolder')?.value || 'Certificate Generator');
        
        const response = await fetch('/api/generate', {
            method: 'POST',
            body: formData
        });
        
        hideLoading();
        
        if (!response.ok) {
            const error = await response.json();
            showError('Error', error.error || 'Failed to generate certificates');
            return;
        }
        
        const result = await response.json();
        showSuccess('Success', result.message, `
            <p><strong>Results:</strong></p>
            <ul>
                <li>Generated: ${result.summary.success || 0}</li>
                <li>Failed: ${result.summary.failed || 0}</li>
                <li>Duration: ${result.summary.duration || 'N/A'}s</li>
            </ul>
            <p>Certificates saved to your Google Drive!</p>
        `);
    } catch (error) {
        hideLoading();
        showError('Error', error.message || 'Request failed');
    }
}

// Submit form with Google Sheets (using Sheet ID)
async function submitFormWithSheetsId(sheetId, sheetName, templateId) {
    try {
        showLoading('Generating certificates from Google Sheets...');
        
        const formData = new FormData();
        formData.append('sheets_id', sheetId);
        formData.append('sheet_name', sheetName);
        formData.append('template_id', templateId);
        formData.append('output_folder', document.getElementById('outputFolder')?.value || 'Certificate Generator');
        
        const response = await fetch('/api/generate', {
            method: 'POST',
            body: formData
        });
        
        hideLoading();
        
        if (!response.ok) {
            const error = await response.json();
            showError('Error', error.error || 'Failed to generate certificates');
            return;
        }
        
        const result = await response.json();
        showSuccess('Success', result.message, `
            <p><strong>Results:</strong></p>
            <ul>
                <li>Generated: ${result.summary.success || 0}</li>
                <li>Failed: ${result.summary.failed || 0}</li>
                <li>Duration: ${result.summary.duration || 'N/A'}s</li>
            </ul>
            <p>Certificates saved to your Google Drive!</p>
        `);
    } catch (error) {
        hideLoading();
        showError('Error', error.message || 'Request failed');
    }
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
function showSuccess(title, message, details) {
    const container = document.getElementById('resultContainer');
    const successDiv = document.getElementById('successResult');
    const successMsg = document.getElementById('successMessage');
    const successDetails = document.getElementById('successDetails');
    
    if (successMsg) successMsg.textContent = message;
    if (successDetails) successDetails.innerHTML = details;
    
    if (container) container.style.display = 'block';
    if (successDiv) successDiv.style.display = 'block';
    
    document.getElementById('errorResult').style.display = 'none';
}

// Show error message
function showError(title, message) {
    const container = document.getElementById('resultContainer');
    const errorDiv = document.getElementById('errorResult');
    const errorMsg = document.getElementById('errorMessage');
    
    if (errorMsg) errorMsg.textContent = message;
    
    if (container) container.style.display = 'block';
    if (errorDiv) errorDiv.style.display = 'block';
    
    document.getElementById('successResult').style.display = 'none';
}

// Validate inputs
function validateForm() {
    const csvFile = document.getElementById('csvFile');
    const templateId = document.getElementById('templateId');
    
    if (!csvFile || !csvFile.files.length) {
        showError('Error', 'Please select a CSV file');
        return false;
    }
    
    if (!templateId || !templateId.value.trim()) {
        showError('Error', 'Please enter template ID');
        return false;
    }
    
    const id = templateId.value.trim();
    if (id.length < 20) {
        showError('Error', 'Template ID appears to be invalid (too short). Copy from Google Slides URL.');
        return false;
    }
    
    return true;
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
