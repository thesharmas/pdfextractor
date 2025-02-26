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

// Update displayResults function
function displayResults(response) {
    console.log('displayResults called with:', response);
    
    const resultsSection = document.getElementById('results-section');
    const resultsContent = document.getElementById('results-content');
    const decisionHeader = document.querySelector('.decision-header');
    const positiveFactor = document.querySelector('.positive-factors');
    const negativeFactor = document.querySelector('.negative-factors');
    const recommendations = document.querySelector('.recommendations');
    
    if (!resultsSection) {
        console.error('Results section not found!');
        return;
    }

    // Show results section
    resultsSection.classList.remove('hidden');
    
    // Change this line to correctly access the nested loan recommendation
    const recommendation = response?.credit_analysis?.loan_recommendation || {};
    const metrics = response?.metrics || {};
    const monthlyFinancials = metrics?.monthly_financials?.statistics || {};
    const nsfData = metrics?.nsf_information || {};

    // Update Credit Decision Tab
    if (decisionHeader) {
        // Handle both boolean and string approval decisions
        const approvalDecision = recommendation.approval_decision;
        const isApproved = typeof approvalDecision === 'boolean' ? 
            approvalDecision : 
            approvalDecision?.toString().toLowerCase() === 'approved';
        
        const decisionColor = isApproved ? 'green' : 'red';
        
        decisionHeader.innerHTML = `
            <div class="flex flex-col md:flex-row gap-6 items-stretch">
                <!-- Decision Status Card -->
                <div class="flex-1 bg-${decisionColor}-50 border-2 border-${decisionColor}-500 rounded-xl p-6 text-center">
                    <div class="inline-flex items-center justify-center w-16 h-16 rounded-full bg-${decisionColor}-100 mb-4">
                        ${isApproved ? 
                            `<svg class="w-8 h-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
                            </svg>` :
                            `<svg class="w-8 h-8 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                            </svg>`
                        }
                    </div>
                    <h3 class="text-2xl font-bold text-${decisionColor}-700 mb-2">
                        ${approvalDecision.toString().toUpperCase()}
                    </h3>
                    <div class="text-${decisionColor}-600 font-medium">
                        Confidence Score: ${((recommendation.confidence_score || 0) * 100).toFixed(1)}%
                    </div>
                </div>

                <!-- Loan Details Card -->
                <div class="flex-1 bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
                    <h4 class="text-lg font-semibold text-gray-800 mb-4">Loan Parameters</h4>
                    <div class="space-y-3">
                        <div class="flex justify-between items-center">
                            <span class="text-gray-600">Maximum Loan Amount</span>
                            <span class="text-xl font-bold text-gray-800">
                                $${formatNumber((recommendation.max_loan_amount || 0).toFixed(2))}
                            </span>
                        </div>
                        <div class="h-px bg-gray-200"></div>
                        <div class="flex justify-between items-center">
                            <span class="text-gray-600">Monthly Payment</span>
                            <span class="text-xl font-bold text-gray-800">
                                $${formatNumber((recommendation.max_monthly_payment_amount || 0).toFixed(2))}
                            </span>
                        </div>
                    </div>
                </div>
            </div>
        `;
    } else {
        console.error('Decision header element not found');
    }

    // Add error handling for missing elements
    if (!decisionHeader) console.error('Decision header element not found');
    if (!positiveFactor) console.error('Positive factors element not found');
    if (!negativeFactor) console.error('Negative factors element not found');
    if (!recommendations) console.error('Recommendations element not found');

    // Update Summary Tab Content
    const summaryTabContent = document.getElementById('summary-tab');
    if (summaryTabContent) {
        const loanRecommendation = response?.credit_analysis?.loan_recommendation || {};
        const approvalDecision = loanRecommendation.approval_decision;
        
        summaryTabContent.innerHTML = `
            <!-- Approval Status Pill -->
            <div class="mb-6 flex justify-center">
                <div class="inline-flex items-center ${approvalDecision ? 'bg-green-100' : 'bg-red-100'} px-6 py-2 rounded-full">
                    <span class="mr-2">
                        ${approvalDecision ? 
                            `<svg class="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
                            </svg>` :
                            `<svg class="w-5 h-5 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                            </svg>`
                        }
                    </span>
                    <span class="${approvalDecision ? 'text-green-800' : 'text-red-800'} font-semibold text-lg">
                        Loan ${approvalDecision ? 'Approved' : 'Denied'}
                    </span>
                    <span class="ml-2 ${approvalDecision ? 'text-green-600' : 'text-red-600'} text-sm">
                        (${(loanRecommendation.confidence_score * 100).toFixed(1)}% confidence)
                    </span>
                </div>
            </div>

            <!-- Statement Overview Card -->
            <div class="bg-white rounded-xl shadow-sm p-6 mb-6">
                <h3 class="text-lg font-semibold text-gray-800 mb-4">
                    <span class="inline-block mr-2">
                        <svg class="w-5 h-5 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                    </span>
                    Statement Overview
                </h3>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div class="bg-gray-50 rounded-lg p-4">
                        <p class="text-sm text-gray-600 mb-2">Period Covered</p>
                        <p class="font-semibold text-gray-800">
                            ${response?.metrics?.statement_continuity?.statement_periods?.[0]?.start_date || 'N/A'} to 
                            ${response?.metrics?.statement_continuity?.statement_periods?.slice(-1)[0]?.end_date || 'N/A'}
                        </p>
                    </div>
                    <div class="bg-gray-50 rounded-lg p-4">
                        <p class="text-sm text-gray-600 mb-2">Statement Status</p>
                        <p class="font-semibold text-gray-800">
                            ${response?.metrics?.statement_continuity?.analysis?.is_contiguous ? 'Complete' : 'Incomplete'}
                        </p>
                    </div>
                </div>
            </div>

            <!-- Key Metrics Card -->
            <div class="bg-white rounded-xl shadow-sm p-6">
                <h3 class="text-lg font-semibold text-gray-800 mb-4">
                    <span class="inline-block mr-2">
                        <svg class="w-5 h-5 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                        </svg>
                    </span>
                    Key Metrics
                </h3>
                <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                    <!-- Average Monthly Revenue -->
                    <div class="bg-gray-50 rounded-lg p-4">
                        <p class="text-sm text-gray-600 mb-2">Avg Monthly Revenue</p>
                        <p class="text-xl font-bold text-gray-800">
                            ${formatNumber(monthlyFinancials?.revenue?.average || 0)}
                        </p>
                    </div>
                    <!-- Average Monthly Expenses -->
                    <div class="bg-gray-50 rounded-lg p-4">
                        <p class="text-sm text-gray-600 mb-2">Avg Monthly Expenses</p>
                        <p class="text-xl font-bold text-gray-800">
                            ${formatNumber(monthlyFinancials?.expenses?.average || 0)}
                        </p>
                    </div>
                    <!-- NSF Incidents -->
                    <div class="bg-gray-50 rounded-lg p-4">
                        <p class="text-sm text-gray-600 mb-2">NSF Incidents</p>
                        <p class="text-xl font-bold text-gray-800">
                            ${nsfData?.incident_count || 0}
                        </p>
                    </div>
                    <!-- Lowest Monthly Balance -->
                    <div class="bg-gray-50 rounded-lg p-4">
                        <p class="text-sm text-gray-600 mb-2">Lowest Monthly Balance</p>
                        <p class="text-xl font-bold text-gray-800">
                            ${formatNumber(metrics?.lowest_monthly_balance || 0)}
                        </p>
                    </div>
                </div>
            </div>
        `;
    }

    // Update Raw JSON tab
    if (resultsContent) {
        resultsContent.textContent = JSON.stringify(response, null, 2);
    }

    // Initialize tabs if not already done
    initializeTabs();

    // In the displayResults function, update the financial analysis section
    const financialsTab = document.getElementById('financials-tab');
    if (financialsTab) {
        const loanRecommendation = response.credit_analysis?.loan_recommendation;
        if (loanRecommendation) {
            const content = `
                <div class="space-y-4">
                    <!-- Loan Decision Card -->
                    <div class="bg-white rounded-lg shadow p-6">
                        <div class="flex items-center justify-between mb-4">
                            <h3 class="text-lg font-semibold">Loan Decision</h3>
                            <span class="px-4 py-1 rounded-full ${loanRecommendation.approval_decision ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}">
                                ${loanRecommendation.approval_decision ? 'Approved' : 'Not Approved'}
                            </span>
                        </div>
                        <div class="grid grid-cols-2 gap-4">
                            <div>
                                <p class="text-gray-600">Confidence Score</p>
                                <p class="text-lg font-semibold">${(loanRecommendation.confidence_score * 100).toFixed(1)}%</p>
                            </div>
                            <div>
                                <p class="text-gray-600">Max Loan Amount</p>
                                <p class="text-lg font-semibold">$${formatNumber(loanRecommendation.max_loan_amount)}</p>
                            </div>
                            <div>
                                <p class="text-gray-600">Max Monthly Payment</p>
                                <p class="text-lg font-semibold">$${formatNumber(loanRecommendation.max_monthly_payment_amount)}</p>
                            </div>
                        </div>
                    </div>

                    <!-- Key Metrics Card -->
                    <div class="bg-white rounded-lg shadow p-6">
                        <h3 class="text-lg font-semibold mb-4">Key Metrics</h3>
                        <div class="grid grid-cols-2 gap-4">
                            <div>
                                <p class="text-gray-600">Average Daily Balance Trend</p>
                                <p class="text-lg font-semibold capitalize">${loanRecommendation.key_metrics.average_daily_balance_trend}</p>
                            </div>
                            <div>
                                <p class="text-gray-600">Highest NSF Month Count</p>
                                <p class="text-lg font-semibold">${loanRecommendation.key_metrics.highest_nsf_month_count}</p>
                            </div>
                            <div>
                                <p class="text-gray-600">Lowest Monthly Balance</p>
                                <p class="text-lg font-semibold">$${formatNumber(loanRecommendation.key_metrics.lowest_monthly_balance)}</p>
                            </div>
                            <div>
                                <p class="text-gray-600">Payment Coverage Ratio</p>
                                <p class="text-lg font-semibold">${loanRecommendation.key_metrics.payment_coverage_ratio.toFixed(2)}</p>
                            </div>
                        </div>
                    </div>

                    <!-- Analysis Details Card -->
                    <div class="bg-white rounded-lg shadow p-6">
                        <h3 class="text-lg font-semibold mb-4">Detailed Analysis</h3>
                        <p class="text-gray-700 mb-4">${loanRecommendation.detailed_analysis}</p>
                        
                        <div class="grid grid-cols-2 gap-6">
                            <div>
                                <h4 class="font-semibold text-gray-700 mb-2">Risk Factors</h4>
                                <ul class="list-disc pl-5 text-red-600">
                                    ${loanRecommendation.risk_factors.map(factor => `<li>${factor}</li>`).join('')}
                                </ul>
                            </div>
                            <div>
                                <h4 class="font-semibold text-gray-700 mb-2">Mitigating Factors</h4>
                                <ul class="list-disc pl-5 text-green-600">
                                    ${loanRecommendation.mitigating_factors.map(factor => `<li>${factor}</li>`).join('')}
                                </ul>
                            </div>
                        </div>
                    </div>

                    <!-- Conditions Card -->
                    <div class="bg-white rounded-lg shadow p-6">
                        <h3 class="text-lg font-semibold mb-4">Conditions if Approved</h3>
                        <ul class="list-disc pl-5 text-gray-700">
                            ${loanRecommendation.conditions_if_approved.map(condition => `<li>${condition}</li>`).join('')}
                        </ul>
                    </div>
                </div>
            `;
            financialsTab.innerHTML = content;
        } else {
            financialsTab.innerHTML = '<div class="p-4 text-gray-600">No financial analysis data available.</div>';
        }
    }

    // In the displayResults function, add the following section to handle the Financial Summary tab
    const financialTab = document.getElementById('financial-tab');
    if (financialTab) {
        // Get the data
        const dailyBalances = response.metrics?.daily_balances?.daily_balances || [];
        const monthlyBalances = response.metrics?.closing_balances?.monthly_closing_balances || [];
        const monthlyFinancials = response.metrics?.monthly_financials?.monthly_data || {};
        const statistics = response.metrics?.monthly_financials?.statistics || {};

        // Create Daily Balance Chart
        const ctx = document.getElementById('dailyBalanceChart').getContext('2d');
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
                                return `Balance: $${formatNumber(context.raw)}`;
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

        // Populate Monthly Balance Table
        const monthlyBalanceTable = document.getElementById('monthlyBalanceTable');
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
                        ${monthlyBalances.map(balance => `
                            <tr>
                                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${balance.month}</td>
                                <td class="px-6 py-4 whitespace-nowrap text-sm text-right text-gray-900">$${formatNumber(balance.balance)}</td>
                                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${balance.verification}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;

        // Populate Monthly Cash Flow Summary
        const monthlyCashFlow = document.getElementById('monthlyCashFlow');
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
                            ${Object.entries(monthlyFinancials).map(([month, data]) => `
                                <tr>
                                    <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${month}</td>
                                    <td class="px-6 py-4 whitespace-nowrap text-sm text-right text-gray-900">$${formatNumber(data.revenue)}</td>
                                    <td class="px-6 py-4 whitespace-nowrap text-sm text-right text-gray-900">$${formatNumber(data.expenses)}</td>
                                    <td class="px-6 py-4 whitespace-nowrap text-sm text-right ${data.cashflow >= 0 ? 'text-green-600' : 'text-red-600'}">
                                        $${formatNumber(data.cashflow)}
                                    </td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>

                <!-- Statistics Summary -->
                <div class="bg-gray-50 rounded-lg p-6">
                    <h4 class="text-md font-semibold text-gray-800 mb-4">Aggregate Statistics</h4>
                    <div class="space-y-4">
                        <div>
                            <p class="text-sm text-gray-600">Average Monthly Revenue</p>
                            <p class="text-lg font-semibold">$${formatNumber(statistics.revenue.average)}</p>
                        </div>
                        <div>
                            <p class="text-sm text-gray-600">Average Monthly Expenses</p>
                            <p class="text-lg font-semibold">$${formatNumber(statistics.expenses.average)}</p>
                        </div>
                        <div>
                            <p class="text-sm text-gray-600">Average Monthly Cash Flow</p>
                            <p class="text-lg font-semibold ${statistics.cashflow.average >= 0 ? 'text-green-600' : 'text-red-600'}">
                                $${formatNumber(statistics.cashflow.average)}
                            </p>
                        </div>
                        <div class="pt-4 border-t border-gray-200">
                            <p class="text-sm text-gray-600">Standard Deviations</p>
                            <div class="grid grid-cols-2 gap-4 mt-2">
                                <div>
                                    <p class="text-xs text-gray-500">Revenue</p>
                                    <p class="text-sm font-medium">$${formatNumber(statistics.revenue.std_deviation)}</p>
                                </div>
                                <div>
                                    <p class="text-xs text-gray-500">Expenses</p>
                                    <p class="text-sm font-medium">$${formatNumber(statistics.expenses.std_deviation)}</p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }
}

// Helper function for number formatting
function formatNumber(number) {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(number);
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