// Global state
let isScrapingActive = false;
let progressInterval = null;

// Category Management Functions
async function addCategory() {
    const input = document.getElementById('newCategory');
    const category = input.value.trim();
    
    if (!category) return;
    
    try {
        const response = await axios.post('/api/categories', {
            main_category: category
        });
        
        if (response.data.status === 'success') {
            window.location.reload();
        }
    } catch (error) {
        console.error('Error adding category:', error);
        alert('Failed to add category');
    }
    
    input.value = '';
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
            window.location.reload();
        }
    } catch (error) {
        console.error('Error adding subcategory:', error);
        alert('Failed to add subcategory');
    }
    
    input.value = '';
}

async function removeCategory(category) {
    if (!confirm(`Are you sure you want to remove ${category} and all its subcategories?`)) {
        return;
    }
    
    try {
        const response = await axios.delete('/api/categories', {
            data: { main_category: category }
        });
        
        if (response.data.status === 'success') {
            window.location.reload();
        }
    } catch (error) {
        console.error('Error removing category:', error);
        alert('Failed to remove category');
    }
}

async function removeSubcategory(mainCategory, subcategory) {
    if (!confirm(`Are you sure you want to remove ${subcategory}?`)) {
        return;
    }
    
    try {
        const response = await axios.delete('/api/categories', {
            data: {
                main_category: mainCategory,
                subcategory: subcategory
            }
        });
        
        if (response.data.status === 'success') {
            window.location.reload();
        }
    } catch (error) {
        console.error('Error removing subcategory:', error);
        alert('Failed to remove subcategory');
    }
}

// Scraping Control Functions
async function startScraping() {
    if (isScrapingActive) return;
    
    // Get selected categories
    const selectedCategories = [];
    document.querySelectorAll('.category-checkbox:checked').forEach(checkbox => {
        const mainCategory = checkbox.value;
        const subcategories = [];
        
        document.querySelectorAll(`input[data-category="${mainCategory}"]:checked`)
            .forEach(subCheckbox => {
                subcategories.push(subCheckbox.value);
            });
            
        if (subcategories.length > 0) {
            selectedCategories.push({
                main_category: mainCategory,
                subcategories: subcategories
            });
        }
    });
    
    if (selectedCategories.length === 0) {
        alert('Please select at least one category and subcategory to scrape');
        return;
    }
    
    try {
        const response = await axios.post('/api/start-scraping', {
            categories: selectedCategories
        });
        
        if (response.data.status === 'success') {
            isScrapingActive = true;
            startProgressTracking();
            document.getElementById('startButton').disabled = true;
        }
    } catch (error) {
        console.error('Error starting scraping:', error);
        alert('Failed to start scraping');
    }
}

function startProgressTracking() {
    updateProgress();
    progressInterval = setInterval(updateProgress, 1000);
}

async function updateProgress() {
    try {
        const response = await axios.get('/api/scraping-status');
        const status = response.data;
        
        // Update status display
        document.getElementById('statusText').textContent = status.status;
        document.getElementById('itemCount').textContent = status.items_scraped;
        document.getElementById('currentCategory').textContent = status.current_category || '-';
        document.getElementById('lastUpdate').textContent = formatDateTime(status.last_update);
        
        // Update progress bar
        if (status.total_items > 0) {
            const progress = (status.items_scraped / status.total_items) * 100;
            document.getElementById('progressBar').style.width = `${progress}%`;
        }
        
        // Handle errors
        const errorDisplay = document.getElementById('errorDisplay');
        const errorList = document.getElementById('errorList');
        if (status.errors && status.errors.length > 0) {
            errorDisplay.classList.remove('hidden');
            errorList.innerHTML = status.errors
                .map(error => `<li>${error}</li>`)
                .join('');
        } else {
            errorDisplay.classList.add('hidden');
            errorList.innerHTML = '';
        }
        
        // Update stats if available
        if (status.resnet_stats || status.llava_stats) {
            document.getElementById('statsDisplay').classList.remove('hidden');
            updateDatasetStats(status);
        }
        
        // Check if scraping is complete
        if (status.status === 'completed' || status.status === 'error') {
            stopProgressTracking();
        }
        
    } catch (error) {
        console.error('Error updating progress:', error);
    }
}

function stopProgressTracking() {
    if (progressInterval) {
        clearInterval(progressInterval);
        progressInterval = null;
    }
    isScrapingActive = false;
    document.getElementById('startButton').disabled = false;
}

function updateDatasetStats(status) {
    if (status.resnet_stats) {
        document.getElementById('resnetTotal').textContent = status.resnet_stats.total_samples;
        document.getElementById('resnetTrain').textContent = status.resnet_stats.train_samples;
        document.getElementById('resnetVal').textContent = status.resnet_stats.val_samples;
    }
    
    if (status.llava_stats) {
        document.getElementById('llavaTotal').textContent = status.llava_stats.total_samples;
        document.getElementById('llavaTrain').textContent = status.llava_stats.train_samples;
        document.getElementById('llavaAvgLen').textContent = 
            status.llava_stats.caption_stats.avg_length.toFixed(1);
    }
}

async function downloadDataset(type) {
    try {
        window.location.href = `/api/download-dataset/${type}`;
    } catch (error) {
        console.error('Error downloading dataset:', error);
        alert('Failed to download dataset');
    }
}

// Utility Functions
function formatDateTime(isoString) {
    if (!isoString) return '-';
    return new Date(isoString).toLocaleString();
}

// Initialize page
document.addEventListener('DOMContentLoaded', function() {
    // If scraping is already in progress, start tracking
    const status = document.getElementById('statusText').textContent;
    if (status === 'running') {
        isScrapingActive = true;
        startProgressTracking();
        document.getElementById('startButton').disabled = true;
    }
    
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
});