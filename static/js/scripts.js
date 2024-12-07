// static/js/scripts.js
document.addEventListener('DOMContentLoaded', function() {
    // API Key for secure communication
    const API_KEY = 'your-secure-api-key'; // Replace with your actual API key

    // Handle configuration form submission
    const configForm = document.getElementById('config-form');
    configForm.addEventListener('submit', function(e) {
        e.preventDefault();
        const output_dir = document.getElementById('output_dir').value.trim();
        const max_items = document.getElementById('max_items').value;
        const max_pages = document.getElementById('max_pages').value;
        
        // Gather categories and subcategories
        const categories = [];
        const categoryDivs = document.querySelectorAll('.category');
        categoryDivs.forEach(function(catDiv) {
            const main_class = catDiv.querySelector('h4').innerText.trim();
            const subcats = [];
            const subcatLis = catDiv.querySelectorAll('ul li');
            subcatLis.forEach(function(li) {
                const subcat = li.firstChild.textContent.trim();
                if(subcat) {
                    subcats.push(subcat);
                }
            });
            categories.push({'main_class': main_class, 'subcategories': subcats});
        });
        
        // Validate inputs
        if(!output_dir) {
            alert('Output directory cannot be empty.');
            return;
        }
        if(max_items < 1) {
            alert('Max items must be at least 1.');
            return;
        }
        if(max_pages < 1) {
            alert('Max pages must be at least 1.');
            return;
        }
        
        const data = {
            'output_dir': output_dir,
            'max_items': max_items,
            'max_pages': max_pages,
            'categories': categories
        };
        
        fetch('/config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'x-api-key': API_KEY
            },
            body: JSON.stringify(data)
        }).then(response => response.json())
          .then(result => {
              if(result.status === 'success') {
                  alert('Configuration updated successfully!');
              } else {
                  alert('Error updating configuration: ' + result.message);
              }
          })
          .catch(error => {
              console.error('Error:', error);
          });
    });
    
    // Handle adding subcategories
    const addSubcatButtons = document.querySelectorAll('.add-subcat');
    addSubcatButtons.forEach(function(button) {
        button.addEventListener('click', function() {
            const main_class = this.getAttribute('data-main');
            const input = this.previousElementSibling;
            const subcat = input.value.trim();
            if(subcat === '') {
                alert('Subcategory cannot be empty.');
                return;
            }
            // Append to the list
            const categoryDiv = this.parentElement;
            const ul = categoryDiv.querySelector('ul');
            const li = document.createElement('li');
            li.innerHTML = `${subcat} <button type="button" class="remove-subcat" data-main="${main_class}" data-sub="${subcat}">Remove</button>`;
            ul.appendChild(li);
            input.value = '';
        });
    });
    
    // Handle removing subcategories
    document.getElementById('categories-container').addEventListener('click', function(e) {
        if(e.target && e.target.classList.contains('remove-subcat')) {
            const main_class = e.target.getAttribute('data-main');
            const subcat = e.target.getAttribute('data-sub');
            if(confirm(`Remove subcategory "${subcat}" from "${main_class}"?`)) {
                e.target.parentElement.remove();
            }
        }
    });
    
    // Handle scrape form submission
    const scrapeForm = document.getElementById('scrape-form');
    scrapeForm.addEventListener('submit', function(e) {
        e.preventDefault();
        const selectedClasses = [];
        const mainClassCheckboxes = document.querySelectorAll('.main-class');
        mainClassCheckboxes.forEach(function(mainCheckbox) {
            if(mainCheckbox.checked) {
                const main_class = mainCheckbox.getAttribute('data-main');
                const subcatCheckboxes = document.querySelectorAll(`.subcat-checkbox[data-main="${main_class}"]:checked`);
                const subcategories = [];
                subcatCheckboxes.forEach(function(subCheckbox) {
                    subcategories.push(subCheckbox.getAttribute('data-sub'));
                });
                if(subcategories.length > 0) {
                    selectedClasses.push({'main_class': main_class, 'subcategories': subcategories});
                }
            }
        });
        
        if(selectedClasses.length === 0) {
            alert('Please select at least one subcategory to scrape.');
            return;
        }
        
        fetch('/start_scraping', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'x-api-key': API_KEY
            },
            body: JSON.stringify({'selected_classes': selectedClasses})
        }).then(response => response.json())
          .then(result => {
              if(result.status === 'started') {
                  alert('Scraping started!');
                  // Start polling for progress
                  pollProgress();
              } else {
                  alert('Error starting scraping: ' + result.message);
              }
          })
          .catch(error => {
              console.error('Error:', error);
          });
    });
    
    // Polling function to update progress
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
                    document.getElementById('status').innerText = data.status;
                    document.getElementById('current_class').innerText = data.current_class || 'None';
                    document.getElementById('current_subcategory').innerText = data.current_subcategory || 'None';
                    document.getElementById('items_found').innerText = data.items_found;
                    document.getElementById('processed_items').innerText = data.processed_items;
                    document.getElementById('error').innerText = data.error || 'None';
                    document.getElementById('current_task').innerText = data.current_task || 'None';
                    
                    if(data.status === 'completed') {
                        clearInterval(progressInterval);
                        alert('Scraping and dataset creation completed!');
                        document.getElementById('download-button').style.display = 'block';
                    }
                    if(data.status === 'error') {
                        clearInterval(progressInterval);
                        alert('An error occurred during scraping. Check logs for details.');
                    }
                })
                .catch(error => {
                    console.error('Error fetching progress:', error);
                });
        }, 5000); // Poll every 5 seconds
    }
    
    // Handle dataset download
    const downloadButton = document.getElementById('download-button');
    downloadButton.addEventListener('click', function() {
        fetch('/download_dataset', {
            method: 'GET',
            headers: {
                'x-api-key': API_KEY
            }
        })
        .then(response => {
            if(response.ok) {
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
