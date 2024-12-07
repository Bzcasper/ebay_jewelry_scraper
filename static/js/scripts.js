// static/js/scripts.js

document.addEventListener('DOMContentLoaded', function() {
    // Retrieve API Key from a secure source or environment variable
    // For security reasons, avoid hardcoding API keys in frontend code.
    // Instead, consider implementing secure authentication mechanisms.
    const API_KEY = 'your-secure-api-key'; // Replace with your actual API key or fetch securely

    // Handle Configuration Form Submission
    const configForm = document.getElementById('config-form');
    configForm.addEventListener('submit', function(e) {
        e.preventDefault();

        // Gather form data
        const outputDir = document.getElementById('output_dir').value.trim();
        const maxItems = parseInt(document.getElementById('max_items').value, 10);
        const maxPages = parseInt(document.getElementById('max_pages').value, 10);

        // Validate inputs
        if (!outputDir) {
            alert('Output directory cannot be empty.');
            return;
        }
        if (isNaN(maxItems) || maxItems < 1) {
            alert('Max items must be a positive integer.');
            return;
        }
        if (isNaN(maxPages) || maxPages < 1) {
            alert('Max pages must be a positive integer.');
            return;
        }

        // Gather categories and subcategories
        const categories = [];
        const categoryDivs = document.querySelectorAll('.category');
        categoryDivs.forEach(function(catDiv) {
            const mainClass = catDiv.querySelector('h4').innerText.trim();
            const subcategories = [];
            const subcatLis = catDiv.querySelectorAll('ul li');
            subcatLis.forEach(function(li) {
                const subcatText = li.firstChild.textContent.trim();
                if (subcatText) {
                    subcategories.push(subcatText);
                }
            });
            categories.push({
                'main_class': mainClass,
                'subcategories': subcategories
            });
        });

        // Prepare data payload
        const data = {
            'output_dir': outputDir,
            'max_items': maxItems,
            'max_pages': maxPages,
            'categories': categories
        };

        // Send POST request to update configuration
        fetch('/config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'x-api-key': API_KEY
            },
            body: JSON.stringify(data)
        })
        .then(response => response.json())
        .then(result => {
            if (result.status === 'success') {
                alert('Configuration updated successfully!');
                // Optionally, update the UI with new configuration
            } else {
                alert('Error updating configuration: ' + result.message);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('An error occurred while updating configuration.');
        });
    });

    // Handle Adding Subcategories
    const addSubcatButtons = document.querySelectorAll('.add-subcat');
    addSubcatButtons.forEach(function(button) {
        button.addEventListener('click', function() {
            const mainClass = this.getAttribute('data-main');
            const input = this.previousElementSibling;
            const newSubcat = input.value.trim();

            if (newSubcat === '') {
                alert('Subcategory cannot be empty.');
                return;
            }

            // Check for duplicate subcategories
            const existingSubcats = Array.from(this.parentElement.querySelectorAll('ul li')).map(li => li.firstChild.textContent.trim().toLowerCase());
            if (existingSubcats.includes(newSubcat.toLowerCase())) {
                alert('Subcategory already exists.');
                return;
            }

            // Create new list item
            const li = document.createElement('li');
            li.innerHTML = `${newSubcat} <button type="button" class="remove-subcat" data-main="${mainClass}" data-sub="${newSubcat}">Remove</button>`;
            this.parentElement.querySelector('ul').appendChild(li);
            input.value = '';
        });
    });

    // Handle Removing Subcategories (Event Delegation)
    document.getElementById('categories-container').addEventListener('click', function(e) {
        if (e.target && e.target.classList.contains('remove-subcat')) {
            const mainClass = e.target.getAttribute('data-main');
            const subcat = e.target.getAttribute('data-sub');

            if (confirm(`Are you sure you want to remove the subcategory "${subcat}" from "${mainClass}"?`)) {
                e.target.parentElement.remove();
            }
        }
    });

    // Handle Scraping Form Submission
    const scrapeForm = document.getElementById('scrape-form');
    scrapeForm.addEventListener('submit', function(e) {
        e.preventDefault();

        // Gather selected classes and subcategories
        const selectedClasses = [];
        const mainClassCheckboxes = document.querySelectorAll('.main-class:checked');
        mainClassCheckboxes.forEach(function(mainCheckbox) {
            const mainClass = mainCheckbox.getAttribute('data-main');
            const subcatCheckboxes = document.querySelectorAll(`.subcat-checkbox[data-main="${mainClass}"]:checked`);
            const selectedSubcats = Array.from(subcatCheckboxes).map(subCheckbox => subCheckbox.getAttribute('data-sub'));

            if (selectedSubcats.length > 0) {
                selectedClasses.push({
                    'main_class': mainClass,
                    'subcategories': selectedSubcats
                });
            }
        });

        if (selectedClasses.length === 0) {
            alert('Please select at least one subcategory to scrape.');
            return;
        }

        // Confirm scraping action
        if (!confirm('Are you sure you want to start scraping the selected subcategories?')) {
            return;
        }

        // Send POST request to start scraping
        fetch('/start_scraping', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'x-api-key': API_KEY
            },
            body: JSON.stringify({'selected_classes': selectedClasses})
        })
        .then(response => response.json())
        .then(result => {
            if (result.status === 'started') {
                alert('Scraping has started successfully!');
                // Start polling for progress updates
                pollProgress();
            } else {
                alert('Error starting scraping: ' + result.message);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('An error occurred while starting the scraping process.');
        });
    });

    // Polling Function to Update Scraping Progress
    function pollProgress() {
        const progressInterval = setInterval(function() {
            fetch('/progress', {
                method: 'GET',
                headers: {
                    'x-api-key': API_KEY
                }
            })
            .then(response => response.json())
            .then(data => {
                document.getElementById('status').innerText = data.status || 'Unknown';
                document.getElementById('current_class').innerText = data.current_class || 'None';
                document.getElementById('current_subcategory').innerText = data.current_subcategory || 'None';
                document.getElementById('items_found').innerText = data.items_found || 0;
                document.getElementById('processed_items').innerText = data.processed_items || 0;
                document.getElementById('error').innerText = data.error || 'None';
                document.getElementById('current_task').innerText = data.current_task || 'None';

                if (data.status === 'completed') {
                    clearInterval(progressInterval);
                    alert('Scraping and dataset creation completed successfully!');
                    document.getElementById('download-button').style.display = 'block';
                }

                if (data.status === 'error') {
                    clearInterval(progressInterval);
                    alert('An error occurred during scraping. Please check the logs for details.');
                }
            })
            .catch(error => {
                console.error('Error fetching progress:', error);
            });
        }, 5000); // Poll every 5 seconds
    }

    // Handle Dataset Download
    const downloadButton = document.getElementById('download-button');
    downloadButton.addEventListener('click', function() {
        fetch('/download_dataset', {
            method: 'GET',
            headers: {
                'x-api-key': API_KEY
            }
        })
        .then(response => {
            if (response.ok) {
                return response.blob();
            } else {
                return response.json().then(data => { throw new Error(data.message); });
            }
        })
        .then(blob => {
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'datasets.zip';
            document.body.appendChild(a);
            a.click();
            a.remove();
            window.URL.revokeObjectURL(url);
        })
        .catch(error => {
            alert('Error downloading dataset: ' + error.message);
            console.error('Download error:', error);
        });
    });
});
