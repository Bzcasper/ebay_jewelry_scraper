// State management
let isScrapingActive = false;
let progressInterval = null;

// Category Management
async function addCategory() {
    const input = document.getElementById('newCategory');
    const category = input.value.trim();
    
    if (!category) return;
    
    try {
        const response = await axios.post('/api/categories', {
            main_category: category
        });
        
        if (response.data.status === 'success') {
            location.reload();
        }
    } catch (error) {
        showError('Failed to add category');
        console.error(error);
    }
}

async function addSubcategory(mainCategory) {
    const input = document.getElementById(`newSub_${mainCategory}`);
    const subcategory = input.value.trim();
    
    if (!subcategory) return;
    
    try {
        const response = await axios.post('/api/categories', {
            main_category: mainCategory,
            subcategory: subcategory
        });
        
        if (response.data.status === 'success') {
            location.reload();
        }
    } catch (error) {
        showError('Failed to add subcategory');
        console.error(error);
    }
}

async function removeCategory(category) {
    if (!confirm(`Remove ${category} and all its subcategories?`)) {
        return;
    }
    
    try {
        const response = await axios.delete('/api/categories', {
            data: { main_category: category }
        });
        
        if (response.data.status === 'success') {
            location.reload();
        }
    } catch (error) {
        showError('Failed to remove category');
        console.error(error);
    }
}

// Scraping Control
async function startScraping() {
    if (isScrapingActive) return;
    
    const selectedCategories = getSelectedCategories();
    if (selectedCategories.length === 0) {
        showError('Please select at least one category');
        return;
    }
    
    try {
        const response = await axios.post('/api/scrape', {
            categories: selectedCategories
        });
        
        if (response.data.status === 'success') {
            isScrapingActive = true;
            startProgressTracking(response.data.task_id);
            disableControls();
        }
    } catch (error) {
        showError('Failed to start scraping');
        console.error(error);
    }
}

function getSelectedCategories() {
    const categories = [];
    document.querySelectorAll('.category-checkbox:checked').forEach(checkbox => {
        const mainCategory = checkbox.value;
        const subcategories = [];
        
        document.querySelectorAll(`input[data-category="${mainCategory}"]:checked`)
            .forEach(subCheckbox => {
                subcategories.push(subCheckbox.value);
            });
            
        if (subcategories.length > 0) {
            categories.push({
                main_category: mainCategory,
                subcategories: subcategories
            });
        }
    });
    
    return categories;
}

async function updateProgress(taskId) {
    try {
        const response = await axios.get(`/api/task/${taskId}`);
        const status = response.data;
        
        updateUI(status);
        
        if (status.status === 'completed' || status.status === 'error') {
            stopProgressTracking();
            enableControls();
            
            if (status.status === 'completed') {
                showSuccess('Scraping completed successfully');
            } else {
                showError(`Scraping failed: ${status.error}`);
            }
        }
    } catch (error) {
        console.error('Error updating progress:', error);
    }
}

function updateUI(status) {
    // Update progress bar
    const progressBar = document.getElementById('progressBar');
    const progressText = document.getElementById('progressText');
    
    if (status.total_items > 0) {
        const progress = (status.items_scraped / status.total_items) * 100;
        progressBar.style.width = `${progress}%`;
        progressText.textContent = `${status.items_scraped} / ${status.total_items} items`;
    }
    
    // Update status text
    const statusText = document.getElementById('statusText');
    statusText.textContent = status.status;
    
    // Update current category
    if (status.current_category) {
        const categoryText = document.getElementById('currentCategory');
        categoryText.textContent = status.current_category;
    }
    
    // Show errors if any
    if (status.errors && status.errors.length > 0) {
        const errorList = document.getElementById('errorList');
        errorList.innerHTML = status.errors
            .map(error => `<li class="text-red-600">${error}</li>`)
            .join('');
    }
}

function startProgressTracking(taskId) {
    updateProgress(taskId);
    progressInterval = setInterval(() => updateProgress(taskId), 1000);
}

function stopProgressTracking() {
    if (progressInterval) {
        clearInterval(progressInterval);
        progressInterval = null;
    }
    isScrapingActive = false;
}

// Dataset Management
async function createDatasets() {
    try {
        const response = await axios.post('/api/create-datasets');
        
        if (response.data.status === 'success') {
            showSuccess('Dataset creation started');
            startProgressTracking(response.data.task_id);
        }
    } catch (error) {
        showError('Failed to start dataset creation');
        console.error(error);
    }
}

async function downloadDataset(type) {
    try {
        window.location.href = `/api/download/dataset/${type}`;
    } catch (error) {
        showError('Failed to download dataset');
        console.error(error);
    }
}

// UI Utilities
function showError(message) {
    const alert = document.createElement('div');
    alert.className = 'alert alert-error slide-in';
    alert.textContent = message;
    
    const alertContainer = document.getElementById('alertContainer');
    alertContainer.appendChild(alert);
    
    setTimeout(() => alert.remove(), 5000);
}

function showSuccess(message) {
    const alert = document.createElement('div');
    alert.className = 'alert alert-success slide-in';
    alert.textContent = message;
    
    const alertContainer = document.getElementById('alertContainer');
    alertContainer.appendChild(alert);
    
    setTimeout(() => alert.remove(), 5000);
}

function disableControls() {
    document.querySelectorAll('button, input[type="checkbox"]').forEach(el => {
        el.disabled = true;
    });
}

function enableControls() {
    document.querySelectorAll('button, input[type="checkbox"]').forEach(el => {
        el.disabled = false;
    });
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    // Setup category checkbox behavior
    document.querySelectorAll('.category-checkbox').forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            const subcategories = document.querySelectorAll(
                `input[data-category="${this.value}"]`
            );
            subcategories.forEach(sub => {
                sub.disabled = !this.checked;
                if (!this.checked) sub.checked = false;
            });
        });
    });

    // Initialize tooltips
    document.querySelectorAll('[data-tooltip]').forEach(element => {
        tippy(element, {
            content: element.getAttribute('data-tooltip'),
            placement: 'top'
        });
    });

    // Setup real-time stats updating
    startStatsUpdates();
    
    // Check for active tasks
    checkActiveTasks();
});

// Real-time statistics updates
function startStatsUpdates() {
    setInterval(async () => {
        try {
            const response = await axios.get('/api/stats');
            updateStatistics(response.data);
        } catch (error) {
            console.error('Error updating stats:', error);
        }
    }, 5000);
}

function updateStatistics(stats) {
    // Update scraping stats
    if (stats.scraping) {
        document.getElementById('totalScraped').textContent = stats.scraping.total_items;
        document.getElementById('successRate').textContent = 
            `${stats.scraping.success_rate.toFixed(1)}%`;
    }

    // Update dataset stats
    if (stats.dataset) {
        document.getElementById('resnetTotal').textContent = stats.dataset.resnet.total_images;
        document.getElementById('llavaTotal').textContent = stats.dataset.llava.total_images;
    }

    // Update resource usage
    if (stats.resources) {
        document.getElementById('cpuUsage').textContent = 
            `${stats.resources.cpu_usage.toFixed(1)}%`;
        document.getElementById('memoryUsage').textContent = 
            formatBytes(stats.resources.memory_usage);
    }
}

async function checkActiveTasks() {
    try {
        const response = await axios.get('/api/active-tasks');
        const tasks = response.data;
        
        tasks.forEach(task => {
            if (task.status === 'running') {
                isScrapingActive = true;
                startProgressTracking(task.id);
                disableControls();
            }
        });
    } catch (error) {
        console.error('Error checking active tasks:', error);
    }
}

// Utility functions
function formatBytes(bytes) {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function formatDuration(seconds) {
    if (seconds < 60) return `${seconds}s`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
    return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
}