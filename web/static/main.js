/* Certificate Generator Web App - JavaScript */

// Google Picker API key and credentials
let pickerApiLoaded = false;
let pickerAuthToken = null;

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
            
            // Get active tab
            const sheetsTab = document.getElementById('sheets-tab');
            const csvTab = document.getElementById('csv-tab');
            const isGoogleSheetsActive = sheetsTab && sheetsTab.classList.contains('active');
            
            // Validate inputs based on active tab
            if (isGoogleSheetsActive) {
                // Google Sheets validation
                const sheetId = document.getElementById('selectedSheetId').value;
                const sheetName = document.getElementById('sheetSelect').value;
                const templateId = document.getElementById('templateId').value.trim();
                
                if (!sheetId) {
                    showError('Error', 'Please select a Google Sheet');
                    return;
                }
                
                if (!sheetName) {
                    showError('Error', 'Please select a sheet tab');
                    return;
                }
                
                if (!templateId) {
                    showError('Error', 'Please enter template ID');
                    return;
                }
                
                if (templateId.length < 20) {
                    showError('Error', 'Template ID appears to be invalid (too short)');
                    return;
                }
                
                await submitFormWithSheetsId(sheetId, sheetName, templateId);
            } else {
                // CSV validation
                const csvFile = document.getElementById('csvFile').files[0];
                const templateId = document.getElementById('templateId').value.trim();
                
                if (!csvFile) {
                    showError('Error', 'Please select a CSV or Excel file');
                    return;
                }
                
                if (!templateId) {
                    showError('Error', 'Please enter template ID');
                    return;
                }
                
                if (templateId.length < 20) {
                    showError('Error', 'Template ID appears to be invalid (too short)');
                    return;
                }
                
                await submitFormWithCSV(csvFile, templateId);
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
    
    // Create Picker with Google Sheets view
    const picker = new google.picker.PickerBuilder()
        .addView(google.picker.ViewId.SPREADSHEETS)
        .setOAuthToken(pickerAuthToken)
        .setCallback(handlePickerResponse)
        .build();
    
    picker.setVisible(true);
}

function handlePickerResponse(data) {
    const action = data[google.picker.Response.ACTION];
    
    if (action === google.picker.Action.PICKED) {
        const doc = data[google.picker.Response.DOCUMENTS][0];
        const sheetId = doc.id;
        const sheetName = doc.name;
        
        // Store selected sheet
        document.getElementById('selectedSheetId').value = sheetId;
        document.getElementById('selectedSheetName').textContent = `✓ ${sheetName}`;
        
        // Load sheet tabs
        loadSheetTabs(sheetId);
    } else if (action === google.picker.Action.CANCEL) {
        console.log('Picker cancelled');
    }
}

async function loadSheetTabs(sheetId) {
    try {
        const response = await fetch(`/api/drive/sheets/${sheetId}/names`);
        
        if (!response.ok) {
            showError('Error', 'Failed to load sheet tabs. Make sure this is a Google Sheets document.');
            return;
        }
        
        const data = await response.json();
        populateDriveSheetTabs(data.sheets);
    } catch (error) {
        console.error('Error loading sheet tabs:', error);
        showError('Error', 'Failed to load sheet tabs');
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
        const firstSheet = sheets[0].properties.title;
        const sheetId = document.getElementById('selectedSheetId').value;
        previewSheetData(sheetId, firstSheet);
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
