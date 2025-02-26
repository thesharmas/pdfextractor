document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('upload-form');
    const fileInput = document.getElementById('pdf-files');
    const fileNames = document.getElementById('file-names');
    const submitBtn = document.getElementById('submit-btn');
    const clearBtn = document.getElementById('clear-files');
    const resultsSection = document.getElementById('results-section');
    const loadingContainer = document.querySelector('.loading-container');
    const loadingText = document.getElementById('loading-text');
    const resultsContent = document.getElementById('results-content');
    const toggleBtn = document.getElementById('toggle-upload-btn');
    const uploadContent = document.getElementById('upload-content');
    const uploadSection = document.querySelector('.upload-section');
    const openJsonLoaderBtn = document.getElementById('openJsonLoader');
    const modal = document.getElementById('jsonLoaderModal');
    const cancelBtn = document.getElementById('cancelJsonLoad');
    const loadBtn = document.getElementById('loadJson');
    const jsonInput = document.getElementById('jsonInput');
    
    console.log('Setting up JSON loader...');
    
    // Log if we found all elements
    console.log('Found elements:', {
        openJsonLoaderBtn: !!openJsonLoaderBtn,
        modal: !!modal,
        cancelBtn: !!cancelBtn,
        loadBtn: !!loadBtn,
        jsonInput: !!jsonInput
    });
    
    // Toggle upload section
    function toggleUploadSection() {
        uploadContent.classList.toggle('hidden');
        const icon = toggleBtn.querySelector('.toggle-icon');
        icon.textContent = uploadContent.classList.contains('hidden') ? '▼' : '▲';
    }
    
    toggleBtn.addEventListener('click', toggleUploadSection);
    
    // Selected files storage
    let selectedFiles = [];
    
    // Add status list to loading container
    const statusList = document.createElement('div');
    statusList.className = 'status-list';
    loadingContainer.appendChild(statusList);
    
    // Handle file selection
    fileInput.addEventListener('change', function(e) {
        const files = Array.from(e.target.files);
        
        // Add new files to our array
        files.forEach(file => {
            if (file.type === 'application/pdf') {
                selectedFiles.push(file);
            }
        });
        
        // Update the UI
        updateFileList();
    });
    
    // Handle clearing files
    clearBtn.addEventListener('click', async function() {
        // Clear the file input
        fileInput.value = '';
        
        // Clear selected files array
        selectedFiles = [];
        
        // Update UI
        updateFileList();
        
        // Hide results section
        resultsSection.style.display = 'none';
        resultsContent.innerHTML = '';
        
        // Clear uploaded files on the server
        try {
            const response = await fetch('/clear-uploads', {
                method: 'POST'
            });
            
            if (!response.ok) {
                console.error('Failed to clear uploaded files on server');
            }
        } catch (error) {
            console.error('Error clearing uploads:', error);
        }
    });
    
    // Update the file list in the UI
    function updateFileList() {
        fileNames.innerHTML = '';
        
        if (selectedFiles.length === 0) {
            fileNames.style.display = 'none';
            clearBtn.disabled = true;
            return;
        }
        
        fileNames.style.display = 'block';
        clearBtn.disabled = false;
        
        selectedFiles.forEach((file, index) => {
            const fileItem = document.createElement('div');
            fileItem.className = 'file-item';
            
            const fileName = document.createElement('span');
            fileName.textContent = file.name;
            
            const removeBtn = document.createElement('span');
            removeBtn.className = 'remove-file';
            removeBtn.textContent = '×';
            removeBtn.addEventListener('click', function() {
                selectedFiles.splice(index, 1);
                updateFileList();
            });
            
            fileItem.appendChild(fileName);
            fileItem.appendChild(removeBtn);
            fileNames.appendChild(fileItem);
        });
        
        // Enable/disable submit button based on file selection
        submitBtn.disabled = selectedFiles.length === 0;
    }
    
    // Initialize clear button state
    clearBtn.disabled = true;
    
    // Debug log to check if form is found
    console.log('Form element found:', !!form);

    if (form) {
        // Handle form submission
        form.addEventListener('submit', async function(e) {
            e.preventDefault();
            console.log('Form submitted');

            // Clear previous results and status
            resultsSection.classList.add('hidden');
            resultsContent.innerHTML = '';
            
            const statusList = document.querySelector('.status-list');
            statusList.innerHTML = ''; // Clear previous status messages

            // Show loading container
            loadingContainer.classList.remove('hidden');

            // Disable submit button
            submitBtn.disabled = true;

            // Hide the upload section when underwriting starts
            const uploadContent = document.getElementById('upload-content');
            uploadContent.classList.add('hidden');
            const toggleBtn = document.getElementById('toggle-upload-btn');
            if (toggleBtn) {
                const icon = toggleBtn.querySelector('.toggle-icon');
                if (icon) icon.textContent = '▼';
            }

            // Start listening for status updates BEFORE making the request
            const eventSource = new EventSource('/status');
            
            eventSource.onmessage = function(event) {
                try {
                    const status = JSON.parse(event.data);
                    updateStatus(status);
                    
                    // If we receive a "complete" or "error" status, close the connection
                    if (status.status === 'Success' || status.status === 'Error') {
                        eventSource.close();
                    }
                } catch (error) {
                    console.error('Error parsing status update:', error);
                }
            };

            try {
                // First, upload the files
                const uploadedFiles = await uploadFiles(selectedFiles);
                console.log('Files uploaded:', uploadedFiles);

                // Then process them with the underwrite endpoint
                const provider = document.getElementById('provider').value;
                const debugMode = document.getElementById('debug').checked;
                
                console.log('Sending underwrite request:', {
                    file_paths: uploadedFiles,
                    provider: provider,
                    debug: debugMode
                });

                const response = await fetch('/underwrite', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        file_paths: uploadedFiles,
                        provider: provider.toLowerCase(),
                        debug: debugMode
                    })
                });

                if (!response.ok) {
                    throw new Error(`Server responded with ${response.status}: ${response.statusText}`);
                }

                const result = await response.json();
                console.log('Underwrite response:', result);

                // Display results
                displayResults(result);

            } catch (error) {
                console.error('Error during underwriting:', error);

                // Show error in results section
                resultsSection.classList.remove('hidden');
                resultsContent.innerHTML = `
                    <div class="error bg-red-50 border border-red-200 rounded-lg p-4">
                        <h3 class="text-red-800 font-semibold mb-2">Error</h3>
                        <p class="text-red-600">${error.message}</p>
                    </div>
                `;

            } finally {
                // Re-enable submit button
                submitBtn.disabled = false;
                
                // Hide loading container only after we're done with everything
                loadingContainer.classList.add('hidden');
                
                // Close the event source if it hasn't been closed already
                if (eventSource.readyState !== EventSource.CLOSED) {
                    eventSource.close();
                }
            }
        });
    } else {
        console.error('Upload form not found!');
    }

    // Function to upload files
    async function uploadFiles(files) {
        console.log('Uploading files:', files);
        const formData = new FormData();
        
        files.forEach(file => {
            formData.append('files', file);
        });
        
        const response = await fetch('/upload', {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            throw new Error(`File upload failed: ${response.status} ${response.statusText}`);
        }
        
        const result = await response.json();
        return result.file_paths;
    }
    
    // Function to update status display
    function updateStatus(status) {
        const statusList = document.querySelector('.status-list');
        if (!statusList) return;

        // Try to find existing status item for this step
        let statusItem = Array.from(statusList.children).find(
            item => item.getAttribute('data-step') === status.step
        );
        
        // If no existing item, create new one
        if (!statusItem) {
            statusItem = document.createElement('div');
            statusItem.setAttribute('data-step', status.step);
            statusItem.className = 'flex items-center p-4 bg-white rounded-lg shadow-sm border border-gray-100 animate-fade-in';
            statusList.appendChild(statusItem);
        }
        
        // Determine status color and icon
        let statusColor = 'blue';
        let icon = '';
        
        switch(status.status.toLowerCase()) {
            case 'complete':
                statusColor = 'green';
                icon = `<svg class="w-5 h-5 text-green-500 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
                </svg>`;
                break;
            case 'error':
                statusColor = 'red';
                icon = `<svg class="w-5 h-5 text-red-500 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
                </svg>`;
                break;
            default:
                icon = `<svg class="w-5 h-5 text-blue-500 mr-3 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
                </svg>`;
        }
        
        statusItem.innerHTML = `
            ${icon}
            <div class="flex-1">
                <div class="flex items-center justify-between">
                    <span class="font-medium text-gray-800">${status.step}</span>
                    <span class="text-sm text-${statusColor}-600 font-medium">${status.status}</span>
                </div>
                ${status.details ? `<p class="text-sm text-gray-600 mt-1">${status.details}</p>` : ''}
            </div>
        `;

        // Scroll to the bottom of the status list
        statusList.scrollTop = statusList.scrollHeight;
    }

    // Add tab functionality
    document.querySelectorAll('.tab-btn').forEach(button => {
        button.addEventListener('click', handleTabClick);
    });

    // Initialize copy button if it exists
    initializeJsonCopy();

    // Open modal
    openJsonLoaderBtn.addEventListener('click', () => {
        console.log('Opening modal');
        modal.classList.remove('hidden');
    });

    // Close modal
    cancelBtn.addEventListener('click', () => {
        console.log('Canceling');
        modal.classList.add('hidden');
        jsonInput.value = '';
    });

    // Close modal if clicking outside
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.classList.add('hidden');
            jsonInput.value = '';
        }
    });

    // Load JSON
    loadBtn.addEventListener('click', () => {
        console.log('Load button clicked');
        const inputValue = jsonInput.value;
        console.log('Input value:', inputValue);
        
        try {
            const jsonData = JSON.parse(inputValue);
            console.log('Parsed JSON:', jsonData);
            
            // Make sure results section is visible
            const resultsSection = document.getElementById('results-section');
            if (resultsSection) {
                resultsSection.classList.remove('hidden');
            }
            
            displayResults(jsonData);
            modal.classList.add('hidden');
            jsonInput.value = '';
        } catch (e) {
            console.error('JSON parse error:', e);
            alert('Invalid JSON format. Please check your input.');
        }
    });
});

// Define the initializeJsonCopy function
function initializeJsonCopy() {
    const copyButton = document.getElementById('copy-json');
    if (!copyButton) return;

    copyButton.addEventListener('click', async () => {
        const jsonContent = document.getElementById('results-content');
        
        try {
            // Get the text content and format it
            const jsonText = jsonContent.textContent;
            await navigator.clipboard.writeText(jsonText);
            
            // Update button to show success state
            const originalContent = copyButton.innerHTML;
            copyButton.innerHTML = `
                <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
                </svg>
                Copied!
            `;
            copyButton.classList.remove('bg-blue-50', 'text-blue-600');
            copyButton.classList.add('bg-green-50', 'text-green-600');
            
            // Reset button after 2 seconds
            setTimeout(() => {
                copyButton.innerHTML = originalContent;
                copyButton.classList.remove('bg-green-50', 'text-green-600');
                copyButton.classList.add('bg-blue-50', 'text-blue-600');
            }, 2000);
            
        } catch (err) {
            // Show error state
            copyButton.innerHTML = `
                <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                Failed to copy
            `;
            copyButton.classList.remove('bg-blue-50', 'text-blue-600');
            copyButton.classList.add('bg-red-50', 'text-red-600');
            
            // Reset button after 2 seconds
            setTimeout(() => {
                copyButton.innerHTML = originalContent;
                copyButton.classList.remove('bg-red-50', 'text-red-600');
                copyButton.classList.add('bg-blue-50', 'text-blue-600');
            }, 2000);
            
            console.error('Failed to copy JSON:', err);
        }
    });
}

const ResultsState = {
    CONTINUITY_ERROR: 'CONTINUITY_ERROR',
    SUCCESS: 'SUCCESS',
    ERROR: 'ERROR'
};

function determineResultsState(response) {
    if (!response) return ResultsState.ERROR;
    
    const continuityAnalysis = safeAccess(response, 'metrics.statement_continuity.analysis');
    if (continuityAnalysis && !continuityAnalysis.is_contiguous) {
        return ResultsState.CONTINUITY_ERROR;
    }
    
    return ResultsState.SUCCESS;
}

function displayResults(response) {
    console.log('Response received:', response); // Debug log

    const resultsSection = document.getElementById('results-section');
    if (!resultsSection) {
        console.error('Results section not found');
        return;
    }

    // Make sure results section is visible
    resultsSection.classList.remove('hidden');

    // 1. First check for error response (non-contiguous statements case)
    if (response.error === "Bank statements are not contiguous") {
        console.log('Non-contiguous statements error detected'); // Debug log
        
        // Show the summary tab content
        const summaryTab = document.getElementById('summary-tab');
        if (summaryTab) {
            const continuityData = safeAccess(response, 'metrics.statement_continuity', {});
            const errorDetails = safeAccess(response, 'details', {});
            
            summaryTab.innerHTML = `
                <div class="bg-red-50 border-l-4 border-red-500 rounded-lg p-6 my-4">
                    <div class="flex items-center mb-4">
                        <div class="flex-shrink-0">
                            <svg class="h-6 w-6 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
                            </svg>
                        </div>
                        <div class="ml-4">
                            <h3 class="text-lg font-medium text-red-800">${response.error}</h3>
                        </div>
                    </div>
                    
                    <div class="ml-10">
                        <p class="text-red-700 mb-4">${errorDetails.explanation}</p>
                        
                        ${errorDetails.gap_details && errorDetails.gap_details.length > 0 ? `
                            <div class="mt-4">
                                <h4 class="text-sm font-semibold text-red-800 mb-2">Statement Gaps Found:</h4>
                                <ul class="list-disc list-inside space-y-1 text-red-700">
                                    ${errorDetails.gap_details.map(gap => `
                                        <li class="text-sm">${gap}</li>
                                    `).join('')}
                                </ul>
                            </div>
                        ` : ''}

                        <div class="mt-6 pt-4 border-t border-red-200">
                            <h4 class="text-sm font-semibold text-red-800 mb-2">Uploaded Statement Periods:</h4>
                            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                                ${continuityData.statement_periods ? continuityData.statement_periods.map(period => `
                                    <div class="text-sm text-red-700 bg-red-50 rounded p-2">
                                        ${period.start_date} to ${period.end_date}
                                    </div>
                                `).join('') : ''}
                            </div>
                        </div>
                    </div>
                </div>
            `;
        }

        // Update raw JSON tab
        const rawTab = document.getElementById('raw-tab');
        if (rawTab) {
            rawTab.innerHTML = `
                <div class="flex justify-between items-center mb-4">
                    <h3 class="text-lg font-semibold text-gray-800">Raw JSON Data</h3>
                    <button id="copy-json" class="flex items-center px-3 py-2 bg-blue-50 text-blue-600 rounded-lg hover:bg-blue-100 transition-colors">
                        <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                        </svg>
                        Copy JSON
                    </button>
                </div>
                <pre class="bg-gray-100 rounded-lg p-4 font-mono text-sm overflow-x-auto">${JSON.stringify(response, null, 2)}</pre>
            `;
        }

        // Initialize copy button functionality
        initializeJsonCopy();
        return;
    }

    // 2. For success case, update all tabs
    // Update Summary tab (Credit Decision)
    const summaryTab = document.getElementById('summary-tab');
    if (summaryTab) {
        const recommendation = safeAccess(response, 'credit_analysis.loan_recommendation');
        if (recommendation) {
            summaryTab.innerHTML = `
                <div class="bg-white shadow rounded-lg p-6">
                    <h2 class="text-2xl font-bold mb-4 ${recommendation.approval_decision ? 'text-green-600' : 'text-red-600'}">
                        ${recommendation.approval_decision ? 'Approved' : 'Not Approved'}
                    </h2>
                    
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
                        <div class="p-4 bg-gray-50 rounded-lg">
                            <h3 class="font-semibold mb-2">Maximum Loan Amount</h3>
                            <p class="text-2xl font-bold">$${formatNumber(recommendation.max_loan_amount)}</p>
                        </div>
                        <div class="p-4 bg-gray-50 rounded-lg">
                            <h3 class="font-semibold mb-2">Monthly Payment</h3>
                            <p class="text-2xl font-bold">$${formatNumber(recommendation.max_monthly_payment_amount)}</p>
                        </div>
                    </div>

                    <div class="mb-6">
                        <h3 class="font-semibold mb-2">Risk Factors</h3>
                        <ul class="list-disc list-inside space-y-1">
                            ${recommendation.risk_factors.map(factor => `
                                <li class="text-red-600">${factor}</li>
                            `).join('')}
                        </ul>
                    </div>

                    <div class="mb-6">
                        <h3 class="font-semibold mb-2">Mitigating Factors</h3>
                        <ul class="list-disc list-inside space-y-1">
                            ${recommendation.mitigating_factors.map(factor => `
                                <li class="text-green-600">${factor}</li>
                            `).join('')}
                        </ul>
                    </div>

                    ${recommendation.conditions_if_approved ? `
                        <div class="mb-6">
                            <h3 class="font-semibold mb-2">Conditions if Approved</h3>
                            <ul class="list-disc list-inside space-y-1">
                                ${recommendation.conditions_if_approved.map(condition => `
                                    <li>${condition}</li>
                                `).join('')}
                            </ul>
                        </div>
                    ` : ''}

                    <div class="mt-4 p-4 bg-gray-50 rounded-lg">
                        <h3 class="font-semibold mb-2">Detailed Analysis</h3>
                        <p>${recommendation.detailed_analysis}</p>
                    </div>
                </div>
            `;
        }
    }

    // Update Financial Summary tab
    if (response.metrics) {
        updateFinancialTab(response);
    }

    // Update Credit Decision tab
    if (response.credit_analysis) {
        updateFinancialsTab(response);
    }

    // Update Raw JSON tab
    const rawTab = document.getElementById('raw-tab');
    if (rawTab) {
        rawTab.innerHTML = `
            <div class="flex justify-between items-center mb-4">
                <h3 class="text-lg font-semibold text-gray-800">Raw JSON Data</h3>
                <button id="copy-json" class="flex items-center px-3 py-2 bg-blue-50 text-blue-600 rounded-lg hover:bg-blue-100 transition-colors">
                    <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                    </svg>
                    Copy JSON
                </button>
            </div>
            <pre class="bg-gray-100 rounded-lg p-4 font-mono text-sm overflow-x-auto">${JSON.stringify(response, null, 2)}</pre>
        `;
    }

    // Initialize copy button functionality
    initializeJsonCopy();

    // Show the summary tab by default
    const summaryTabBtn = document.querySelector('[data-tab="summary"]');
    if (summaryTabBtn) {
        summaryTabBtn.click();
    }
}

// Helper function for safe object access
function safeAccess(obj, path, defaultValue = null) {
    try {
        return path.split('.').reduce((acc, part) => acc?.[part], obj) ?? defaultValue;
    } catch (e) {
        console.warn(`Error accessing path ${path}:`, e);
        return defaultValue;
    }
}

// Helper function to format numbers
function formatNumber(num) {
    return num ? num.toLocaleString('en-US', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }) : '0.00';
}

// Tab initialization function
function initializeTabs() {
    const tabs = document.querySelectorAll('.tab-btn');
    const tabPanes = document.querySelectorAll('.tab-pane');

    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            // Remove active class from all tabs
            tabs.forEach(t => t.classList.remove('active'));
            // Add active class to clicked tab
            tab.classList.add('active');
            
            // Hide all tab panes
            tabPanes.forEach(pane => pane.classList.add('hidden'));
            // Show the selected tab pane
            const targetPane = document.getElementById(`${tab.dataset.tab}-tab`);
            if (targetPane) {
                targetPane.classList.remove('hidden');
            }
        });
    });

    // Show summary tab by default
    const summaryTab = document.querySelector('[data-tab="summary"]');
    if (summaryTab) {
        summaryTab.click();
    }
}

// Helper function to format numbers with commas
function formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

// Add this CSS to your HTML file or update the existing loading container styles
document.addEventListener('DOMContentLoaded', function() {
    // ... existing code ...

    // Update loading container styles
    const loadingContainer = document.querySelector('.loading-container');
    loadingContainer.className = 'loading-container hidden bg-white rounded-lg shadow-md p-6 mb-8 max-w-2xl mx-auto';
    
    // Update status list styles
    const statusList = document.querySelector('.status-list');
    statusList.className = 'status-list space-y-2 mt-4 max-h-60 overflow-y-auto';
    
    // Add loading text styles
    const loadingText = document.getElementById('loading-text');
    loadingText.className = 'text-xl font-semibold text-gray-800 mb-4';
});

// Add this to your existing styles or in a <style> tag in your HTML
const styleSheet = document.createElement('style');
styleSheet.textContent = `
    @keyframes fade-in {
        from { opacity: 0; transform: translateY(-10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    .animate-fade-in {
        animation: fade-in 0.3s ease-out forwards;
    }
    
    .status-list::-webkit-scrollbar {
        width: 6px;
    }
    
    .status-list::-webkit-scrollbar-track {
        background: #f1f1f1;
        border-radius: 3px;
    }
    
    .status-list::-webkit-scrollbar-thumb {
        background: #cbd5e1;
        border-radius: 3px;
    }
    
    .status-list::-webkit-scrollbar-thumb:hover {
        background: #94a3b8;
    }
`;
document.head.appendChild(styleSheet);

// Add this function to handle tab clicks
function handleTabClick(e) {
    // Get all tab buttons and content panes
    const tabs = document.querySelectorAll('.tab-btn');
    const panes = document.querySelectorAll('.tab-pane');
    
    // Remove active classes from all tabs
    tabs.forEach(tab => {
        tab.classList.remove('active', 'text-blue-600', 'border-b-2', 'border-blue-600');
        tab.classList.add('text-gray-500');
    });
    
    // Hide all panes
    panes.forEach(pane => {
        pane.classList.add('hidden');
    });
    
    // Add active classes to clicked tab
    e.target.classList.add('active', 'text-blue-600', 'border-b-2', 'border-blue-600');
    e.target.classList.remove('text-gray-500');
    
    // Show corresponding pane
    const tabId = e.target.getAttribute('data-tab');
    const pane = document.getElementById(`${tabId}-tab`);
    if (pane) {
        pane.classList.remove('hidden');
    }
}

// Update Financial Analysis tab with safety checks
function updateFinancialsTab(response) {
    const financialsTab = document.getElementById('financials-tab');
    if (!financialsTab) return;

    const recommendation = safeAccess(response, 'credit_analysis.loan_recommendation', {});
    if (!recommendation) {
        financialsTab.innerHTML = '<div class="p-4 text-gray-600">No financial analysis data available.</div>';
        return;
    }

    const content = `
        <div class="space-y-4">
            <!-- Loan Decision Card -->
            <div class="bg-white rounded-lg shadow p-6">
                <div class="flex items-center justify-between mb-4">
                    <h3 class="text-lg font-semibold">Loan Decision</h3>
                    <span class="px-4 py-1 rounded-full ${recommendation.approval_decision ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}">
                        ${recommendation.approval_decision ? 'Approved' : 'Not Approved'}
                    </span>
                </div>
                <div class="grid grid-cols-2 gap-4">
                    <div>
                        <p class="text-gray-600">Confidence Score</p>
                        <p class="text-lg font-semibold">${(safeAccess(recommendation, 'confidence_score', 0) * 100).toFixed(1)}%</p>
                    </div>
                    <div>
                        <p class="text-gray-600">Max Loan Amount</p>
                        <p class="text-lg font-semibold">$${formatNumber(safeAccess(recommendation, 'max_loan_amount', 0))}</p>
                    </div>
                    <div>
                        <p class="text-gray-600">Max Monthly Payment</p>
                        <p class="text-lg font-semibold">$${formatNumber(safeAccess(recommendation, 'max_monthly_payment_amount', 0))}</p>
                    </div>
                </div>
            </div>

            <!-- Key Metrics Card -->
            <div class="bg-white rounded-lg shadow p-6">
                <h3 class="text-lg font-semibold mb-4">Key Metrics</h3>
                <div class="grid grid-cols-2 gap-4">
                    <div>
                        <p class="text-gray-600">Average Daily Balance Trend</p>
                        <p class="text-lg font-semibold capitalize">${safeAccess(recommendation, 'key_metrics.average_daily_balance_trend', 'N/A')}</p>
                    </div>
                    <div>
                        <p class="text-gray-600">Highest NSF Month Count</p>
                        <p class="text-lg font-semibold">${safeAccess(recommendation, 'key_metrics.highest_nsf_month_count', 0)}</p>
                    </div>
                    <div>
                        <p class="text-gray-600">Lowest Monthly Balance</p>
                        <p class="text-lg font-semibold">$${formatNumber(safeAccess(recommendation, 'key_metrics.lowest_monthly_balance', 0))}</p>
                    </div>
                    <div>
                        <p class="text-gray-600">Payment Coverage Ratio</p>
                        <p class="text-lg font-semibold">${(safeAccess(recommendation, 'key_metrics.payment_coverage_ratio', 0)).toFixed(2)}</p>
                    </div>
                </div>
            </div>

            <!-- Analysis Details Card -->
            <div class="bg-white rounded-lg shadow p-6">
                <h3 class="text-lg font-semibold mb-4">Detailed Analysis</h3>
                <p class="text-gray-700 mb-4">${safeAccess(recommendation, 'detailed_analysis', 'No detailed analysis available.')}</p>
                
                <div class="grid grid-cols-2 gap-6">
                    <div>
                        <h4 class="font-semibold text-gray-700 mb-2">Risk Factors</h4>
                        <ul class="list-disc pl-5 text-red-600">
                            ${(safeAccess(recommendation, 'risk_factors', []))
                                .map(factor => `<li>${factor}</li>`)
                                .join('') || '<li>No risk factors identified</li>'}
                        </ul>
                    </div>
                    <div>
                        <h4 class="font-semibold text-gray-700 mb-2">Mitigating Factors</h4>
                        <ul class="list-disc pl-5 text-green-600">
                            ${(safeAccess(recommendation, 'mitigating_factors', []))
                                .map(factor => `<li>${factor}</li>`)
                                .join('') || '<li>No mitigating factors identified</li>'}
                        </ul>
                    </div>
                </div>
            </div>

            <!-- Conditions Card -->
            <div class="bg-white rounded-lg shadow p-6">
                <h3 class="text-lg font-semibold mb-4">Conditions if Approved</h3>
                <ul class="list-disc pl-5 text-gray-700">
                    ${(safeAccess(recommendation, 'conditions_if_approved', []))
                        .map(condition => `<li>${condition}</li>`)
                        .join('') || '<li>No conditions specified</li>'}
                </ul>
            </div>
        </div>
    `;
    financialsTab.innerHTML = content;
}

// Update Financial Summary tab with safety checks
function updateFinancialTab(response) {
    const financialTab = document.getElementById('financial-tab');
    if (!financialTab) return;

    const dailyBalances = safeAccess(response, 'metrics.daily_balances.daily_balances', []);
    const monthlyBalances = safeAccess(response, 'metrics.closing_balances.monthly_closing_balances', []);
    const monthlyFinancialsData = safeAccess(response, 'metrics.monthly_financials.monthly_data', {});
    const statistics = safeAccess(response, 'metrics.monthly_financials.statistics', {});

    // Create Daily Balance Chart
    const chartCanvas = document.getElementById('dailyBalanceChart');
    if (chartCanvas?.getContext && dailyBalances.length > 0) {
        const ctx = chartCanvas.getContext('2d');
        try {
            new Chart(ctx, {
                type: 'line',
                data: {
                    labels: dailyBalances.map(item => item.date),
                    datasets: [{
                        label: 'Daily Balance',
                        data: dailyBalances.map(item => item.balance),
                        borderColor: 'rgb(59, 130, 246)',
                        backgroundColor: 'rgba(59, 130, 246, 0.1)',
                        fill: true,
                        tension: 0.4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    return `Balance: $${formatNumber(context.raw || 0)}`;
                                }
                            }
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            ticks: {
                                callback: function(value) {
                                    return '$' + formatNumber(value);
                                }
                            }
                        }
                    }
                }
            });
        } catch (error) {
            console.error('Error creating chart:', error);
            chartCanvas.parentElement.innerHTML = '<div class="p-4 text-gray-600">Error creating chart</div>';
        }
    }

    // Update Monthly Balance Table
    const monthlyBalanceTable = document.getElementById('monthlyBalanceTable');
    if (monthlyBalanceTable) {
        monthlyBalanceTable.innerHTML = `
            <div class="overflow-x-auto">
                <table class="min-w-full divide-y divide-gray-200">
                    <thead class="bg-gray-50">
                        <tr>
                            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Month</th>
                            <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Closing Balance</th>
                            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Verification</th>
                        </tr>
                    </thead>
                    <tbody class="bg-white divide-y divide-gray-200">
                        ${monthlyBalances.length > 0 ? monthlyBalances.map(balance => `
                            <tr>
                                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${balance.month || 'N/A'}</td>
                                <td class="px-6 py-4 whitespace-nowrap text-sm text-right text-gray-900">$${formatNumber(balance.balance || 0)}</td>
                                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${balance.verification || 'Unverified'}</td>
                            </tr>
                        `).join('') : `
                            <tr>
                                <td colspan="3" class="px-6 py-4 text-center text-gray-500">No monthly balance data available</td>
                            </tr>
                        `}
                    </tbody>
                </table>
            </div>
        `;
    }

    // Update Monthly Cash Flow Summary
    const monthlyCashFlow = document.getElementById('monthlyCashFlow');
    if (monthlyCashFlow) {
        monthlyCashFlow.innerHTML = `
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                <!-- Monthly Data Table -->
                <div class="overflow-x-auto">
                    <table class="min-w-full divide-y divide-gray-200">
                        <thead class="bg-gray-50">
                            <tr>
                                <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Month</th>
                                <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Revenue</th>
                                <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Expenses</th>
                                <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Cash Flow</th>
                            </tr>
                        </thead>
                        <tbody class="bg-white divide-y divide-gray-200">
                            ${Object.entries(monthlyFinancialsData).length > 0 ? 
                                Object.entries(monthlyFinancialsData).map(([month, data]) => `
                                    <tr>
                                        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${month}</td>
                                        <td class="px-6 py-4 whitespace-nowrap text-sm text-right text-gray-900">$${formatNumber(data.revenue || 0)}</td>
                                        <td class="px-6 py-4 whitespace-nowrap text-sm text-right text-gray-900">$${formatNumber(data.expenses || 0)}</td>
                                        <td class="px-6 py-4 whitespace-nowrap text-sm text-right ${(data.cashflow || 0) >= 0 ? 'text-green-600' : 'text-red-600'}">
                                            $${formatNumber(data.cashflow || 0)}
                                        </td>
                                    </tr>
                                `).join('') : `
                                    <tr>
                                        <td colspan="4" class="px-6 py-4 text-center text-gray-500">No monthly financial data available</td>
                                    </tr>
                            `}
                        </tbody>
                    </table>
                </div>

                <!-- Statistics Summary -->
                <div class="bg-gray-50 rounded-lg p-6">
                    <h4 class="text-md font-semibold text-gray-800 mb-4">Aggregate Statistics</h4>
                    <div class="space-y-4">
                        <div>
                            <p class="text-sm text-gray-600">Average Monthly Revenue</p>
                            <p class="text-lg font-semibold">$${formatNumber(safeAccess(statistics, 'revenue.average', 0))}</p>
                        </div>
                        <div>
                            <p class="text-sm text-gray-600">Average Monthly Expenses</p>
                            <p class="text-lg font-semibold">$${formatNumber(safeAccess(statistics, 'expenses.average', 0))}</p>
                        </div>
                        <div>
                            <p class="text-sm text-gray-600">Average Monthly Cash Flow</p>
                            <p class="text-lg font-semibold ${safeAccess(statistics, 'cashflow.average', 0) >= 0 ? 'text-green-600' : 'text-red-600'}">
                                $${formatNumber(safeAccess(statistics, 'cashflow.average', 0))}
                            </p>
                        </div>
                        <div class="pt-4 border-t border-gray-200">
                            <p class="text-sm text-gray-600">Standard Deviations</p>
                            <div class="grid grid-cols-2 gap-4 mt-2">
                                <div>
                                    <p class="text-xs text-gray-500">Revenue</p>
                                    <p class="text-sm font-medium">$${formatNumber(safeAccess(statistics, 'revenue.std_deviation', 0))}</p>
                                </div>
                                <div>
                                    <p class="text-xs text-gray-500">Expenses</p>
                                    <p class="text-sm font-medium">$${formatNumber(safeAccess(statistics, 'expenses.std_deviation', 0))}</p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }
} 