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
    
    // Handle form submission
    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        // Clear previous results and status
        resultsSection.classList.add('hidden');
        resultsContent.innerHTML = '';
        statusList.innerHTML = '';
        
        // Show loading container
        loadingContainer.classList.remove('hidden');
        
        // Disable submit button
        submitBtn.disabled = true;
        
        // Hide the upload section when underwriting starts
        uploadContent.classList.add('hidden');
        const icon = toggleBtn.querySelector('.toggle-icon');
        icon.textContent = '▼';
        
        // Start listening for status updates
        const eventSource = new EventSource('/status');
        
        eventSource.onmessage = function(event) {
            const status = JSON.parse(event.data);
            updateStatus(status);
        };
        
        try {
            // First, upload the files
            const uploadedFiles = await uploadFiles(selectedFiles);
            
            // Then process them with the underwrite endpoint
            const provider = document.getElementById('provider').value;
            const debugMode = document.getElementById('debug-mode').checked;
            
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
            
            // Hide loading container
            loadingContainer.classList.add('hidden');
            
            // Display results
            displayResults(result);
            
        } catch (error) {
            console.error('Error:', error);
            
            // Hide loading container
            loadingContainer.classList.add('hidden');
            
            // Show error in results section
            resultsSection.classList.remove('hidden');
            resultsContent.innerHTML = `
                <div class="error">
                    <h3>Error</h3>
                    <p>${error.message}</p>
                </div>
            `;
            setTimeout(() => resultsSection.classList.add('visible'), 10);
            
        } finally {
            // Re-enable submit button
            submitBtn.disabled = false;
            // Close the event source
            eventSource.close();
        }
    });
    
    // Function to upload files
    async function uploadFiles(files) {
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
            statusItem.className = 'flex items-center p-4 border-b border-gray-100 animate-fade-in';
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

        statusList.scrollTop = statusList.scrollHeight;
    }

    // Add tab functionality
    document.querySelectorAll('.tab-btn').forEach(button => {
        button.addEventListener('click', handleTabClick);
    });

    // Initialize copy button if it exists
    initializeJsonCopy();
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
    const resultsSection = document.getElementById('results-section');
    const resultsContent = document.getElementById('results-content');
    const statementContinuity = document.querySelector('.statement-continuity');
    const keyMetrics = document.querySelector('.key-metrics');
    const avgBalance = document.querySelector('.avg-balance');
    const nsfInfo = document.querySelector('.nsf-info');
    const closingBalance = document.querySelector('.closing-balance');
    const decisionHeader = document.querySelector('.decision-header');
    const positiveFactor = document.querySelector('.positive-factors');
    const negativeFactor = document.querySelector('.negative-factors');
    const recommendations = document.querySelector('.recommendations');
    
    // Safely access nested properties
    const recommendation = response?.credit_analysis?.loan_recommendation || {};
    const metrics = recommendation?.key_metrics || {};
    const monthlyFinancials = response?.metrics?.monthly_financials?.statistics || {};
    const nsfData = response?.metrics?.nsf_information || {};
    
    // Update Statement Overview
    if (statementContinuity) {
        statementContinuity.innerHTML = `
            <div class="bg-white border border-gray-200 rounded-xl p-6 shadow-sm h-full">
                <div class="flex items-center gap-2 mb-4">
                    <svg class="w-5 h-5 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/>
                    </svg>
                    <h3 class="text-lg font-semibold text-gray-800">Analysis Summary</h3>
                </div>
                <div class="prose prose-sm max-w-none text-gray-600">
                    ${recommendation.detailed_analysis || 'No analysis available'}
                </div>
            </div>
        `;
    }
    
    // Update Key Metrics
    if (keyMetrics) {
        keyMetrics.innerHTML = `
            <div class="bg-white border border-gray-200 rounded-xl p-6 shadow-sm h-full">
                <div class="flex items-center gap-2 mb-4">
                    <svg class="w-5 h-5 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>
                    </svg>
                    <h3 class="text-lg font-semibold text-gray-800">Key Metrics</h3>
                </div>
                <div class="grid gap-6">
                    <div class="p-4 bg-gray-50 rounded-lg">
                        <div class="text-sm text-gray-600 mb-1">Payment Coverage</div>
                        <div class="text-2xl font-bold text-gray-900">
                            ${(metrics.payment_coverage_ratio || 0).toFixed(2)}x
                        </div>
                    </div>
                    
                    <div class="p-4 bg-gray-50 rounded-lg">
                        <div class="text-sm text-gray-600 mb-1">Balance Trend</div>
                        <div class="text-2xl font-bold text-gray-900">
                            ${metrics.average_daily_balance_trend || 'N/A'}
                        </div>
                    </div>
                    
                    <div class="p-4 bg-gray-50 rounded-lg">
                        <div class="text-sm text-gray-600 mb-1">Lowest Balance</div>
                        <div class="text-2xl font-bold text-gray-900">
                            $${formatNumber((metrics.lowest_monthly_balance || 0).toFixed(2))}
                        </div>
                    </div>
                </div>
            </div>
        `;
    }
    
    // Update Monthly Data
    const monthlyData = response?.metrics?.monthly_financials?.monthly_data || {};
    const monthlyDataHtml = `
        <div class="bg-white border border-gray-200 rounded-xl p-6 shadow-sm h-full">
            <div class="flex items-center gap-2 mb-4">
                <svg class="w-5 h-5 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/>
                </svg>
                <h3 class="text-lg font-semibold text-gray-800">Monthly Data</h3>
            </div>
            <div class="space-y-4">
                ${Object.entries(monthlyData).map(([month, data]) => `
                    <div class="bg-gray-50 rounded-lg p-4">
                        <h5 class="font-semibold text-gray-700 mb-3">${month}</h5>
                        <div class="space-y-2">
                            <div class="flex justify-between items-center">
                                <span class="text-gray-600">Revenue</span>
                                <span class="font-medium text-gray-900">$${formatNumber(data.revenue.toFixed(2))}</span>
                            </div>
                            <div class="flex justify-between items-center">
                                <span class="text-gray-600">Expenses</span>
                                <span class="font-medium text-gray-900">$${formatNumber(data.expenses.toFixed(2))}</span>
                            </div>
                            <div class="flex justify-between items-center">
                                <span class="text-gray-600">Cash Flow</span>
                                <span class="font-medium ${data.cashflow >= 0 ? 'text-green-600' : 'text-red-600'}">
                                    $${formatNumber(data.cashflow.toFixed(2))}
                                </span>
                            </div>
                        </div>
                    </div>
                `).join('')}
            </div>
        </div>
    `;
    document.querySelector('.monthly-data').innerHTML = monthlyDataHtml || '<p class="text-gray-500">No monthly data available</p>';

    // Update Financial Statistics
    const avgBalanceHtml = `
        <div class="bg-white border border-gray-200 rounded-xl p-6 shadow-sm h-full">
            <div class="flex items-center gap-2 mb-4">
                <svg class="w-5 h-5 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>
                </svg>
                <h3 class="text-lg font-semibold text-gray-800">Financial Statistics</h3>
            </div>
            <div class="space-y-6">
                <div class="bg-gray-50 rounded-lg p-4">
                    <h4 class="font-medium text-gray-700 mb-3">Monthly Averages</h4>
                    <div class="space-y-2">
                        <div class="flex justify-between items-center">
                            <span class="text-gray-600">Revenue</span>
                            <span class="font-medium text-gray-900">$${formatNumber((monthlyFinancials?.revenue?.average || 0).toFixed(2))}</span>
                        </div>
                        <div class="flex justify-between items-center">
                            <span class="text-gray-600">Expenses</span>
                            <span class="font-medium text-gray-900">$${formatNumber((monthlyFinancials?.expenses?.average || 0).toFixed(2))}</span>
                        </div>
                        <div class="flex justify-between items-center">
                            <span class="text-gray-600">Cash Flow</span>
                            <span class="font-medium ${(monthlyFinancials?.cashflow?.average || 0) >= 0 ? 'text-green-600' : 'text-red-600'}">
                                $${formatNumber((monthlyFinancials?.cashflow?.average || 0).toFixed(2))}
                            </span>
                        </div>
                    </div>
                </div>
                <div class="bg-gray-50 rounded-lg p-4">
                    <h4 class="font-medium text-gray-700 mb-3">Standard Deviations</h4>
                    <div class="space-y-2">
                        <div class="flex justify-between items-center">
                            <span class="text-gray-600">Revenue</span>
                            <span class="font-medium text-gray-900">$${formatNumber((monthlyFinancials?.revenue?.std_deviation || 0).toFixed(2))}</span>
                        </div>
                        <div class="flex justify-between items-center">
                            <span class="text-gray-600">Expenses</span>
                            <span class="font-medium text-gray-900">$${formatNumber((monthlyFinancials?.expenses?.std_deviation || 0).toFixed(2))}</span>
                        </div>
                        <div class="flex justify-between items-center">
                            <span class="text-gray-600">Cash Flow</span>
                            <span class="font-medium text-gray-900">$${formatNumber((monthlyFinancials?.cashflow?.std_deviation || 0).toFixed(2))}</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
    document.querySelector('.avg-balance').innerHTML = avgBalanceHtml;

    // Update NSF Information
    const nsfHtml = `
        <div class="bg-white border border-gray-200 rounded-xl p-6 shadow-sm h-full">
            <div class="flex items-center gap-2 mb-4">
                <svg class="w-5 h-5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
                </svg>
                <h3 class="text-lg font-semibold text-gray-800">NSF Activity</h3>
            </div>
            <div class="bg-gray-50 rounded-lg p-4 space-y-3">
                <div class="flex justify-between items-center">
                    <span class="text-gray-600">Total NSF Incidents</span>
                    <span class="font-medium text-red-600">${nsfData.incident_count || 0}</span>
                </div>
                <div class="h-px bg-gray-200"></div>
                <div class="flex justify-between items-center">
                    <span class="text-gray-600">Total NSF Fees</span>
                    <span class="font-medium text-red-600">$${formatNumber((nsfData.total_fees || 0).toFixed(2))}</span>
                </div>
                <div class="h-px bg-gray-200"></div>
                <div class="flex justify-between items-center">
                    <span class="text-gray-600">Highest NSF Month</span>
                    <span class="font-medium text-gray-900">${nsfData.highest_nsf_month || 'N/A'}</span>
                </div>
            </div>
        </div>
    `;
    document.querySelector('.nsf-info').innerHTML = nsfHtml;

    // Update Monthly Closing Balances
    const monthlyBalances = response?.metrics?.closing_balances?.monthly_closing_balances || [];
    const closingBalanceHtml = `
        <div class="bg-white border border-gray-200 rounded-xl p-6 shadow-sm h-full">
            <div class="flex items-center gap-2 mb-4">
                <svg class="w-5 h-5 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2z"/>
                </svg>
                <h3 class="text-lg font-semibold text-gray-800">Monthly Closing</h3>
            </div>
            ${monthlyBalances.length > 0 ? `
                <div class="space-y-3">
                    ${monthlyBalances.map(balance => `
                        <div class="bg-gray-50 rounded-lg p-4">
                            <div class="flex justify-between items-center">
                                <span class="text-gray-600">${balance.month}</span>
                                <div class="text-right">
                                    <span class="block font-medium text-gray-900">$${formatNumber((balance.balance || 0).toFixed(2))}</span>
                                    <span class="text-sm text-gray-500">${balance.verification}</span>
                                </div>
                            </div>
                        </div>
                    `).join('')}
                </div>
            ` : '<p class="text-gray-500">No monthly balance data available</p>'}
        </div>
    `;
    document.querySelector('.closing-balance').innerHTML = closingBalanceHtml;

    // Update the daily balance chart if it exists
    const dailyBalanceChart = document.querySelector('.daily-balance-chart');
    if (dailyBalanceChart) {
        const dailyBalances = response?.metrics?.daily_balances?.daily_balances || [];
        if (dailyBalances.length > 0) {
            dailyBalanceChart.innerHTML = `
                <div class="bg-white border border-gray-200 rounded-xl p-6 shadow-sm h-full">
                    <div class="flex items-center gap-2 mb-4">
                        <svg class="w-5 h-5 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z"/>
                        </svg>
                        <h3 class="text-lg font-semibold text-gray-800">Daily Balance Trend</h3>
                    </div>
                    <div class="h-[300px] relative">
                        <canvas id="dailyBalanceCanvas"></canvas>
                    </div>
                    <div class="mt-4 text-sm text-gray-500 text-right">
                        ● Direct Balance  ● Calculated Balance
                    </div>
                </div>
            `;

            // Prepare data for the chart
            const dates = dailyBalances.map(item => item.date);
            const directBalances = dailyBalances.map(item => 
                item.balance_type === 'direct' ? item.balance : null
            );
            const calculatedBalances = dailyBalances.map(item => 
                item.balance_type === 'calculated' ? item.balance : null
            );

            // Create the chart
            const ctx = document.getElementById('dailyBalanceCanvas').getContext('2d');
            new Chart(ctx, {
                type: 'line',
                data: {
                    labels: dates,
                    datasets: [
                        {
                            label: 'Direct Balance',
                            data: directBalances,
                            borderColor: '#2563eb',
                            backgroundColor: '#2563eb',
                            pointBackgroundColor: '#2563eb',
                            pointRadius: 4,
                            pointHoverRadius: 6,
                            spanGaps: false,
                            segment: {
                                borderDash: [0, 0]
                            }
                        },
                        {
                            label: 'Calculated Balance',
                            data: calculatedBalances,
                            borderColor: '#64748b',
                            backgroundColor: '#64748b',
                            pointBackgroundColor: '#64748b',
                            pointRadius: 4,
                            pointHoverRadius: 6,
                            spanGaps: false,
                            segment: {
                                borderDash: [4, 4]
                            }
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {
                        intersect: false,
                        mode: 'index'
                    },
                    plugins: {
                        legend: {
                            display: false
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    let label = context.dataset.label || '';
                                    if (label) {
                                        label += ': ';
                                    }
                                    if (context.parsed.y !== null) {
                                        label += new Intl.NumberFormat('en-US', {
                                            style: 'currency',
                                            currency: 'USD'
                                        }).format(context.parsed.y);
                                    }
                                    return label;
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            grid: {
                                display: false
                            },
                            ticks: {
                                maxRotation: 45,
                                minRotation: 45
                            }
                        },
                        y: {
                            beginAtZero: false,
                            ticks: {
                                callback: function(value) {
                                    return new Intl.NumberFormat('en-US', {
                                        style: 'currency',
                                        currency: 'USD',
                                        maximumFractionDigits: 0
                                    }).format(value);
                                }
                            }
                        }
                    }
                }
            });
        } else {
            dailyBalanceChart.innerHTML = `
                <div class="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
                    <div class="flex items-center gap-2 mb-4">
                        <svg class="w-5 h-5 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z"/>
                        </svg>
                        <h3 class="text-lg font-semibold text-gray-800">Daily Balance Trend</h3>
                    </div>
                    <p class="text-gray-500">No daily balance data available</p>
                </div>
            `;
        }
    }
    
    // Update Credit Decision Tab
    if (decisionHeader) {
        // Safely check the approval decision
        const approvalDecision = recommendation.approval_decision || '';
        const isApproved = approvalDecision.toString().toLowerCase() === 'approved';
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
    }
    
    // Update Factors and Conditions sections
    const factorsSection = document.querySelector('.grid.grid-cols-1.md\\:grid-cols-2.gap-6.mb-6');
    if (factorsSection) {
        // Update Mitigating Factors
        const positiveFactor = factorsSection.querySelector('.positive-factors');
        if (positiveFactor) {
            positiveFactor.innerHTML = `
                <div class="h-full bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
                    <div class="flex items-center gap-2 mb-4">
                        <svg class="w-5 h-5 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
                        </svg>
                        <h3 class="text-lg font-semibold text-gray-800">Mitigating Factors</h3>
                    </div>
                    <ul class="space-y-2">
                        ${(recommendation.mitigating_factors || [])
                            .map(factor => `
                                <li class="flex items-start gap-2 text-gray-700">
                                    <span class="text-green-500 mt-1">•</span>
                                    <span>${factor}</span>
                                </li>
                            `).join('') || '<li class="text-gray-500">No mitigating factors identified</li>'}
                    </ul>
                </div>
            `;
        }

        // Update Risk Factors
        const negativeFactor = factorsSection.querySelector('.negative-factors');
        if (negativeFactor) {
            negativeFactor.innerHTML = `
                <div class="h-full bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
                    <div class="flex items-center gap-2 mb-4">
                        <svg class="w-5 h-5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
                        </svg>
                        <h3 class="text-lg font-semibold text-gray-800">Risk Factors</h3>
                    </div>
                    <ul class="space-y-2">
                        ${(recommendation.risk_factors || [])
                            .map(factor => `
                                <li class="flex items-start gap-2 text-gray-700">
                                    <span class="text-red-500 mt-1">•</span>
                                    <span>${factor}</span>
                                </li>
                            `).join('') || '<li class="text-gray-500">No risk factors identified</li>'}
                    </ul>
                </div>
            `;
        }
    }

    // Update Conditions section
    const recommendationsSection = document.querySelector('.recommendations');
    if (recommendationsSection) {
        recommendationsSection.innerHTML = `
            <div class="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
                <div class="flex items-center gap-2 mb-4">
                    <svg class="w-5 h-5 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/>
                    </svg>
                    <h3 class="text-lg font-semibold text-gray-800">Conditions</h3>
                </div>
                <ul class="space-y-3">
                    ${(recommendation.conditions_if_approved || [])
                        .map(condition => `
                            <li class="flex items-start gap-3 p-3 bg-blue-50 rounded-lg text-gray-700">
                                <span class="text-blue-500 mt-1">•</span>
                                <span>${condition}</span>
                            </li>
                        `).join('') || '<li class="text-gray-500">No conditions specified</li>'}
                </ul>
            </div>
        `;
    }
    
    // Update Raw JSON Tab
    if (resultsContent) {
        resultsContent.innerHTML = `<pre>${JSON.stringify(response, null, 2)}</pre>`;
    }
    
    // Show results section
    document.getElementById('results-section').classList.remove('hidden');
    
    // Initialize copy functionality
    initializeJsonCopy();
    
    // Manually trigger click on summary tab
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