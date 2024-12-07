// static/js/scripts.js

document.addEventListener('DOMContentLoaded', function() {
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
                // 'x-api-key': API_KEY  // Removed as per user's request
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
                // headers: {
                //     'x-api-key': API_KEY  // Removed as per user's request
                // }
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
                    document.getElementById('download-section').style.display = 'block';
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
            // headers: {
            //     'x-api-key': API_KEY  // Removed as per user's request
            // }
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
