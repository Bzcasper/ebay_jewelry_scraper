# **eBay Jewelry Scraper

Table of Contents
📖 Overview
✨ Features
📁 Project Structure
🔧 Prerequisites
🚀 Installation
⚙️ Configuration
🛠️ Usage
☁️ Deployment
🐳 Containerization with Docker
☁️ Deploying to Google Cloud Run
🔒 Security Considerations
📈 Logging and Monitoring
🔧 Advanced Features
🤝 Contributing
📄 License
🙏 Acknowledgements
⚠️ Disclaimer
📖 Overview
The eBay Jewelry Scraper is a comprehensive web scraping tool designed to collect images and metadata of jewelry items from eBay. It focuses on six main classes—Necklace, Pendant, Bracelet, Ring, Earring, and Wristwatch—with the ability to manage subcategories dynamically. The scraper processes and augments images to create optimized datasets suitable for training ResNet50 and LLaVA models. The entire application is containerized for seamless deployment and is secured with robust authentication and input validation mechanisms.

✨ Features
Dynamic Category Management: Add or remove subcategories for six main jewelry classes via a user-friendly Flask interface.
Proxy Rotation & User-Agent Spoofing: Enhance scraping stealth by rotating proxies and varying user-agent strings.
Robust Error Handling: Implement granular exception handling to manage network failures and unexpected page structures.
Secure Endpoints: Protect sensitive routes with API key authentication.
Input Validation: Ensure all user inputs are validated to prevent injection attacks and misuse.
Image Augmentation: Enhance image datasets with augmentation techniques suitable for ResNet50 and LLaVA models.
Optimized Dataset Creation: Generate two separate, highly optimized datasets for training machine learning models.
Containerized Deployment: Use Docker for consistent environments across development and production.
Google Cloud Integration: Deploy on Google Cloud Run with integrated logging and monitoring.
Real-Time Progress Monitoring: Monitor scraping progress and status through the web interface.
Downloadable Datasets: Obtain the final datasets as a downloadable zip file containing separate datasets for each model.
📁 Project Structure
ebay_jewelry_scraper/
├── app.py
├── config.py
├── requirements.txt
├── Dockerfile
├── .dockerignore
├── scraper/
│ ├── **init**.py
│ ├── core.py
│ ├── data_processors.py
│ ├── selenium_utils.py
│ └── logger.py
├── templates/
│ └── index.html
└── static/
├── css/
│ └── styles.css
└── js/
└── scripts.js
Description of Each File:
app.py: The main Flask application handling routes, configurations, scraping initiation, and dataset downloads.
config.py: Configuration settings, including main classes, subcategories, scraping parameters, proxy lists, and user-agent strings.
requirements.txt: Python dependencies.
Dockerfile: Instructions to build the Docker image.
.dockerignore: Specifies files/directories to ignore when building the Docker image.
scraper/: Contains all scraping-related modules.
init.py: Makes scraper a Python package.
core.py: The main scraper class implementing proxy rotation, user-agent spoofing, and enhanced error handling.
data_processors.py: Processes and stores scraped data, augments images, and creates optimized datasets.
selenium_utils.py: Selenium utility functions, including WebDriver setup with proxy rotation and user-agent spoofing.
logger.py: Centralized logging configuration integrating with Google Cloud Logging.
templates/: HTML templates for Flask.
index.html: The main interface allowing configuration management, scraping initiation, progress monitoring, and dataset download.
static/: Static files like CSS and JavaScript.
css/styles.css: Styling for the web interface.
js/scripts.js: JavaScript for interactivity, AJAX calls, and secure endpoint interactions.
🔧 Prerequisites
Before setting up the project, ensure you have the following installed on your local machine:

Python 3.10+
Docker
Google Cloud SDK (for deployment to Google Cloud Run)
Google Cloud Account with billing enabled
Note: While Docker and Google Cloud SDK are essential for containerization and deployment, the scraper can also be run locally without Docker.

🚀 Installation

1. Clone the Repository
   git clone https://github.com/yourusername/ebay_jewelry_scraper.git
   cd ebay_jewelry_scraper
2. Create a Virtual Environment
   It's recommended to use a virtual environment to manage dependencies.

python3 -m venv venv
source venv/bin/activate # On Windows: venv\Scripts\activate 3. Install Dependencies
pip install --upgrade pip
pip install -r requirements.txt
⚙️ Configuration

1. Update config.py
   Configure the main classes, subcategories, proxies, and user-agent strings in config.py.

# config.py

from dataclasses import dataclass, field
from typing import List, Dict

@dataclass
class ScraperConfig:
output_dir: str = "jewelry_dataset"
max_items: int = 100 # Maximum items per subcategory
max_pages: int = 5 # Maximum pages per subcategory # Initialize with six main classes and their subcategories
categories: List[Dict] = field(default_factory=lambda: [
{'main_class': 'Necklace', 'subcategories': ['Choker', 'Pendant', 'Chain']},
{'main_class': 'Pendant', 'subcategories': ['Heart', 'Cross', 'Star']},
{'main_class': 'Bracelet', 'subcategories': ['Tennis', 'Charm', 'Bangle']},
{'main_class': 'Ring', 'subcategories': ['Engagement', 'Wedding', 'Fashion']},
{'main_class': 'Earring', 'subcategories': ['Stud', 'Hoop', 'Drop']},
{'main_class': 'Wristwatch', 'subcategories': ['Analog', 'Digital', 'Smart']}
]) # Proxy list for rotation
proxies: List[str] = field(default_factory=lambda: [

# Add your proxy addresses here in the format "http://ip:port"

"http://123.456.789.0:8080",
"http://234.567.890.1:8080",
"http://345.678.901.2:8080",

# Add more proxies as needed

]) # User-Agent list for rotation
user_agents: List[str] = field(default_factory=lambda: [
"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36",
"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Safari/605.1.15",
"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36",

# Add more user agents as needed

]) 2. Set Up API Key
To secure the application endpoints, set an API key as an environment variable.

export API_KEY='your-secure-api-key'
Replace 'your-secure-api-key' with a strong, unique key.

3. Google Cloud Credentials
   To enable Google Cloud Logging, set the GOOGLE_APPLICATION_CREDENTIALS environment variable to the path of your service account key JSON file.

export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/credentials.json"
Note: Ensure the service account has the necessary permissions for logging.

🛠️ Usage

1. Run Locally
   Ensure your virtual environment is activated and run the Flask application.

python app.py
Access the interface by navigating to http://localhost:5000 in your web browser.

2. Using the Interface
   Configure Scraping Parameters:

Output Directory: Specify where scraped data and images will be stored.
Max Items per Subcategory: Number of items to scrape per subcategory.
Max Pages per Subcategory: Number of pages to scrape per subcategory.
Manage Subcategories:

Add Subcategory: Enter a new subcategory name and click "Add Subcategory".
Remove Subcategory: Click the "Remove" button next to the subcategory you wish to delete.
Select Classes and Subcategories:

Check the boxes next to the main classes and their respective subcategories you want to scrape.
Start Scraping:

Click the "Start Scraping" button to initiate the scraping process.
Monitor Progress:

The "Scraping Progress" section will display real-time updates on the scraping status, including the number of items found and processed.
Download Datasets:

Once scraping and dataset creation are completed, a "Download Dataset" button will appear. Click it to download a zip file containing two zip files: one for ResNet50 and one for LLaVA.
☁️ Deployment
🐳 Containerization with Docker
Containerizing the application ensures consistency across different environments and simplifies deployment.

1. Build the Docker Image
   Navigate to the project directory and build the Docker image.

docker build -t ebay-jewelry-scraper .
Note: The . specifies the current directory as the build context.

2. Run the Docker Container Locally
   After successfully building the image, run the container to ensure everything works as expected.

docker run -d -p 5000:5000 \
 -e API_KEY='your-secure-api-key' \
 -e GOOGLE_APPLICATION_CREDENTIALS='/path/to/credentials.json' \
 -v /local/path/to/credentials.json:/path/to/credentials.json \
 ebay-jewelry-scraper
-d: Run the container in detached mode.
-p 5000:5000: Map port 5000 of the host to port 5000 of the container.
-e: Set environment variables.
-v: Mount the Google Cloud credentials file inside the container.
Important: Replace 'your-secure-api-key' and /path/to/credentials.json with your actual API key and credentials path.

3. Access the Application
   Open your browser and navigate to http://localhost:5000 to access the Flask interface.

☁️ Deploying to Google Cloud Run
Deploy the Docker container to Google Cloud Run for scalable and managed hosting.

1. Authenticate with Google Cloud
   gcloud auth login
   gcloud config set project YOUR_PROJECT_ID
   Replace YOUR_PROJECT_ID with your actual Google Cloud project ID.

2. Enable Necessary Services
   gcloud services enable run.googleapis.com
   gcloud services enable containerregistry.googleapis.com
3. Build and Push the Docker Image to Google Container Registry
   Use Cloud Build to build the Docker image directly on Google Cloud.

gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/ebay-jewelry-scraper
Replace YOUR_PROJECT_ID with your actual project ID.

Note: This command uploads your local code to Google Cloud, builds the Docker image, and pushes it to the Google Container Registry.

4. Deploy to Google Cloud Run
   gcloud run deploy ebay-jewelry-scraper \
    --image gcr.io/YOUR_PROJECT_ID/ebay-jewelry-scraper \
    --platform managed \
    --region us-central1 \
    --allow-unauthenticated \
    --memory 2Gi \
    --set-env-vars API_KEY=your-secure-api-key,GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json
   --platform managed: Deploy to the fully managed Cloud Run.
   --region us-central1: Choose a region closest to your users.
   --allow-unauthenticated: Allow public access. Adjust based on your security needs.
   --memory 2Gi: Allocate sufficient memory. Adjust as needed.
   --set-env-vars: Set environment variables for API key and Google Cloud credentials.
   Important:

Replace YOUR_PROJECT_ID with your actual project ID.
Replace your-secure-api-key with your actual API key.
Ensure that the GOOGLE_APPLICATION_CREDENTIALS path points to your service account key JSON file in the Cloud Run environment. 5. Access the Deployed Application
After deployment, Cloud Run will provide a URL where your application is accessible.

🔒 Security Considerations
Protect Sensitive Endpoints
API Key Authentication: All sensitive endpoints are secured with API key authentication. Ensure the API key is kept confidential and not exposed in client-side code.
Environment Variables: Use environment variables to manage sensitive information like API keys and Google Cloud credentials securely.
Validate User Inputs
Server-Side Validation: All inputs received from the client are validated on the server to prevent injection attacks and misuse.
Client-Side Validation: Forms include client-side validation to enhance user experience and reduce invalid data submissions.
Best Practices
Use Strong API Keys: Generate strong, unique API keys and rotate them regularly.
Limit API Key Scope: If possible, limit the API key's scope and permissions to only what is necessary.
Secure Storage: Store API keys and credentials using secure storage solutions like environment variables or secret management services.
📈 Logging and Monitoring
Cloud Logging
Integration: The application integrates with Google Cloud Logging for centralized log management.
Setup: Ensure the GOOGLE_APPLICATION_CREDENTIALS environment variable is set to enable logging.
Usage: Monitor application logs through the Google Cloud Console to track scraping activities, errors, and performance metrics.
Performance Monitoring
Cloud Monitoring: Utilize Google Cloud's monitoring tools to observe application performance.
Alerts: Set up alerts for critical issues like scraping failures, high error rates, or resource exhaustion.
🔧 Advanced Features
Proxy Rotation and User-Agent Spoofing
Implementation: The scraper rotates proxies and user-agent strings from predefined lists to minimize the risk of being blocked by eBay.
Configuration: Update the proxies and user_agents lists in config.py with reliable proxies and diverse user-agent strings.
Error Handling Enhancements
Granular Exceptions: The scraper handles specific exceptions to manage network failures, unexpected page structures, and other anomalies gracefully.
Retries: Implements retry mechanisms for transient errors during scraping and image processing.
Advanced Data Processing
Image Augmentation: Uses torchvision to apply transformations like resizing, cropping, flipping, and rotation to enhance image datasets.
Dataset Optimization: Creates separate datasets optimized for ResNet50 and LLaVA models, ensuring compatibility and performance.
🤝 Contributing
Contributions are welcome! Please follow these steps to contribute to the project:

Fork the Repository

Click the "Fork" button at the top-right corner of the repository page to create a copy in your GitHub account.

Clone the Repository

git clone https://github.com/yourusername/ebay_jewelry_scraper.git
cd ebay_jewelry_scraper
Create a New Branch

git checkout -b feature/YourFeatureName
Make Your Changes

Implement your feature or bug fix.

Commit Your Changes

git add .
git commit -m "Add feature: YourFeatureName"
Push to Your Fork

git push origin feature/YourFeatureName
Create a Pull Request

Navigate to your repository on GitHub and click the "Compare & pull request" button to submit your changes for review.

📄 License
This project is licensed under the MIT License.

🙏 Acknowledgements
Flask
Selenium
BeautifulSoup
Torch
Google Cloud
Docker
WebDriver Manager
⚠️ Disclaimer
Use Responsibly: Ensure that your scraping activities comply with eBay's Terms of Service. Unauthorized scraping can lead to legal consequences or account bans. Use this tool responsibly and ethically.

Feel free to reach out if you have any questions or need further assistance!
**
