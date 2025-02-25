document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('upload-form');
    const fileInput = document.getElementById('pdf-files');
    const fileNames = document.getElementById('file-names');
    const submitBtn = document.getElementById('submit-btn');
    const resultsSection = document.getElementById('results-section');
    const loadingIndicator = document.getElementById('loading-indicator');
    const resultsContent = document.getElementById('results-content');
    
    // Selected files storage
    let selectedFiles = [];
    
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
    
    // Update the file list in the UI
    function updateFileList() {
        fileNames.innerHTML = '';
        
        if (selectedFiles.length === 0) {
            fileNames.style.display = 'none';
            return;
        }
        
        fileNames.style.display = 'block';
        
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
    
    // Handle form submission
    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        if (selectedFiles.length === 0) {
            alert('Please select at least one PDF file.');
            return;
        }
        
        // Show loading state
        submitBtn.disabled = true;
        resultsSection.style.display = 'block';
        loadingIndicator.style.display = 'block';
        resultsContent.innerHTML = '';
        
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
            
            // Display results
            loadingIndicator.style.display = 'none';
            resultsContent.innerHTML = `<pre>${JSON.stringify(result, null, 2)}</pre>`;
            
        } catch (error) {
            console.error('Error:', error);
            loadingIndicator.style.display = 'none';
            resultsContent.innerHTML = `<div class="error">Error: ${error.message}</div>`;
        } finally {
            submitBtn.disabled = false;
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
}); 