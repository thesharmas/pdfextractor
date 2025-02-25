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
        uploadContent.classList.toggle('collapsed');
        toggleBtn.classList.toggle('collapsed');
        uploadSection.classList.toggle('collapsed');
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
        resultsSection.style.display = 'none';
        resultsSection.classList.remove('visible');
        resultsContent.innerHTML = '';
        statusList.innerHTML = '';
        
        // Show loading container
        loadingContainer.style.display = 'flex';
        
        // Disable submit button
        submitBtn.disabled = true;
        
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
            loadingContainer.style.display = 'none';
            
            // Display results
            displayResults(result);
            
        } catch (error) {
            console.error('Error:', error);
            
            // Hide loading container
            loadingContainer.style.display = 'none';
            
            // Show error in results section
            resultsSection.style.display = 'block';
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
        const statusItem = document.createElement('div');
        statusItem.className = `status-item ${status.status.toLowerCase()}`;
        
        statusItem.innerHTML = `
            <span class="status-step">${status.step}</span>
            <span class="status-message">${status.details || status.status}</span>
        `;
        
        statusList.appendChild(statusItem);
        statusList.scrollTop = statusList.scrollHeight;
    }
});

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
            <div class="metric">
                <strong>Analysis Summary</strong>
                <p>${recommendation.detailed_analysis || 'No analysis available'}</p>
            </div>
        `;
    }
    
    // Update Key Metrics
    if (keyMetrics) {
        keyMetrics.innerHTML = `
            <div class="metrics-grid">
                <div class="metric">
                    <strong>Payment Coverage</strong>
                    <p>${(metrics.payment_coverage_ratio || 0).toFixed(2)}x</p>
                </div>
                <div class="metric">
                    <strong>Balance Trend</strong>
                    <p>${metrics.average_daily_balance_trend || 'N/A'}</p>
                </div>
                <div class="metric">
                    <strong>Lowest Balance</strong>
                    <p>$${formatNumber((metrics.lowest_monthly_balance || 0).toFixed(2))}</p>
                </div>
            </div>
        `;
    }
    
    // Update Monthly Data
    const monthlyData = response?.metrics?.monthly_financials?.monthly_data || {};
    const monthlyDataHtml = Object.entries(monthlyData)
        .map(([month, data]) => `
            <div class="month-group">
                <h5>${month}</h5>
                <div class="stat-item">
                    <span class="stat-label">Revenue:</span>
                    <span class="stat-value">$${formatNumber(data.revenue.toFixed(2))}</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">Expenses:</span>
                    <span class="stat-value">$${formatNumber(data.expenses.toFixed(2))}</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">Cash Flow:</span>
                    <span class="stat-value ${data.cashflow >= 0 ? 'positive' : 'negative'}">
                        $${formatNumber(data.cashflow.toFixed(2))}
                    </span>
                </div>
            </div>
        `).join('');
    document.querySelector('.monthly-data').innerHTML = monthlyDataHtml || '<p>No monthly data available</p>';

    // Update Financial Statistics
    const avgBalanceHtml = `
        <div class="stat-group">
            <h5>Monthly Averages</h5>
            <div class="stat-item">
                <span class="stat-label">Revenue:</span>
                <span class="stat-value">$${formatNumber((monthlyFinancials?.revenue?.average || 0).toFixed(2))}</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">Expenses:</span>
                <span class="stat-value">$${formatNumber((monthlyFinancials?.expenses?.average || 0).toFixed(2))}</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">Cash Flow:</span>
                <span class="stat-value ${(monthlyFinancials?.cashflow?.average || 0) >= 0 ? 'positive' : 'negative'}">
                    $${formatNumber((monthlyFinancials?.cashflow?.average || 0).toFixed(2))}
                </span>
            </div>
        </div>
        <div class="stat-group">
            <h5>Standard Deviations</h5>
            <div class="stat-item">
                <span class="stat-label">Revenue:</span>
                <span class="stat-value">$${formatNumber((monthlyFinancials?.revenue?.std_deviation || 0).toFixed(2))}</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">Expenses:</span>
                <span class="stat-value">$${formatNumber((monthlyFinancials?.expenses?.std_deviation || 0).toFixed(2))}</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">Cash Flow:</span>
                <span class="stat-value">$${formatNumber((monthlyFinancials?.cashflow?.std_deviation || 0).toFixed(2))}</span>
            </div>
        </div>`;
    document.querySelector('.avg-balance').innerHTML = avgBalanceHtml;

    // Update NSF Information
    const nsfHtml = `
        <div class="stat-item">
            <span class="stat-label">Total NSF Incidents:</span>
            <span class="stat-value">${nsfData.incident_count || 0}</span>
        </div>
        <div class="stat-item">
            <span class="stat-label">Total NSF Fees:</span>
            <span class="stat-value">$${formatNumber((nsfData.total_fees || 0).toFixed(2))}</span>
        </div>
        <div class="stat-item">
            <span class="stat-label">Highest NSF Month:</span>
            <span class="stat-value">${nsfData.highest_nsf_month || 'N/A'}</span>
        </div>`;
    document.querySelector('.nsf-info').innerHTML = nsfHtml;

    // Update Monthly Closing Balances
    const monthlyBalances = response?.metrics?.monthly_financials?.monthly_balances || [];
    if (monthlyBalances && monthlyBalances.length > 0) {
        const closingBalanceHtml = monthlyBalances.map(balance => `
            <div class="stat-item">
                <span class="stat-label">${balance.month}:</span>
                <span class="stat-value">
                    $${formatNumber((balance.closing_balance || 0).toFixed(2))}
                    <small class="balance-type">${balance.is_complete ? '(Complete)' : '(Partial)'}</small>
                </span>
            </div>
        `).join('');
        document.querySelector('.closing-balance').innerHTML = closingBalanceHtml;
    } else {
        document.querySelector('.closing-balance').innerHTML = `
            <div class="stat-item">
                <p>No monthly balance data available</p>
            </div>
        `;
    }

    // Update the daily balance chart if it exists
    const dailyBalanceChart = document.querySelector('.daily-balance-chart');
    if (dailyBalanceChart) {
        const dailyBalances = response?.metrics?.daily_balances?.daily_balances || [];
        if (dailyBalances.length > 0) {
            const balanceItems = dailyBalances.map(balance => `
                <div class="stat-item">
                    <span class="stat-label">${balance.date}:</span>
                    <span class="stat-value">
                        $${formatNumber((balance.balance || 0).toFixed(2))}
                        <small class="balance-type">${balance.balance_type === 'direct' ? '(Direct)' : '(Calculated)'}</small>
                    </span>
                </div>
            `).join('');

            dailyBalanceChart.innerHTML = `
                <div class="metric-content">
                    ${balanceItems}
                </div>
            `;
        } else {
            dailyBalanceChart.innerHTML = `
                <div class="metric-content">
                    <div class="stat-item">
                        <p>No daily balance data available</p>
                    </div>
                </div>
            `;
        }
    }
    
    // Update Credit Decision Tab
    if (decisionHeader) {
        decisionHeader.innerHTML = `
            <div class="decision ${recommendation.approval_decision ? 'approve' : 'decline'}">
                ${recommendation.approval_decision ? 'APPROVED' : 'DECLINED'}
            </div>
            <div class="confidence">
                Confidence Score: ${((recommendation.confidence_score || 0) * 100).toFixed(1)}%
            </div>
            <div class="decision-amount">
                Maximum Loan Amount: $${formatNumber((recommendation.max_loan_amount || 0).toFixed(2))}
                <br>
                Monthly Payment: $${formatNumber((recommendation.max_monthly_payment_amount || 0).toFixed(2))}
            </div>
        `;
    }
    
    if (positiveFactor) {
        positiveFactor.innerHTML = `
            <h3>Mitigating Factors</h3>
            <ul class="factor-list">
                ${(recommendation.mitigating_factors || [])
                    .map(factor => `<li>${factor}</li>`)
                    .join('') || '<li>No mitigating factors identified</li>'}
            </ul>
        `;
    }
    
    if (negativeFactor) {
        negativeFactor.innerHTML = `
            <h3>Risk Factors</h3>
            <ul class="factor-list">
                ${(recommendation.risk_factors || [])
                    .map(factor => `<li>${factor}</li>`)
                    .join('') || '<li>No risk factors identified</li>'}
            </ul>
        `;
    }
    
    if (recommendations) {
        recommendations.innerHTML = `
            <h3>Conditions</h3>
            <ul class="recommendation-list">
                ${(recommendation.conditions_if_approved || [])
                    .map(condition => `<li>${condition}</li>`)
                    .join('') || '<li>No conditions specified</li>'}
            </ul>
        `;
    }
    
    // Update Raw JSON Tab
    if (resultsContent) {
        resultsContent.innerHTML = `<pre>${JSON.stringify(response, null, 2)}</pre>`;
    }
    
    // Show results section with animation
    resultsSection.style.display = 'block';
    setTimeout(() => {
        resultsSection.classList.add('visible');
    }, 10);
    
    // Add tab switching functionality
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabPanes = document.querySelectorAll('.tab-pane');
    
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            // Remove active class from all buttons and panes
            tabBtns.forEach(b => b.classList.remove('active'));
            tabPanes.forEach(p => p.classList.remove('active'));
            
            // Add active class to clicked button and corresponding pane
            btn.classList.add('active');
            const tabId = btn.dataset.tab;
            document.getElementById(`${tabId}-tab`).classList.add('active');
        });
    });
}

// Helper function to format numbers with commas
function formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

// Tab functionality
document.querySelectorAll('.tab-btn').forEach(button => {
    button.addEventListener('click', () => {
        // Remove active class from all buttons and panes
        document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
        document.querySelectorAll('.tab-pane').forEach(pane => pane.classList.remove('active'));
        
        // Add active class to clicked button and corresponding pane
        button.classList.add('active');
        const tabId = button.getAttribute('data-tab');
        document.getElementById(`${tabId}-tab`).classList.add('active');
    });
}); 