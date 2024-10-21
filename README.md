# Python Web Crawler

This Python web crawler allows you to crawl websites up to a specified depth, capture status codes, content size, and titles of each page, and restrict crawling to specific domains while avoiding certain file types using a blacklist.

## Features
- **Max Depth**: Set the maximum depth of links to crawl.
- **Domain Restriction**: Crawl only within specified domains.
- **Blacklist**: Ignore URLs that match certain file extensions (e.g., `.jpg`, `.css`, etc.).
- **Output**: For each crawled URL, the following information is captured:
  - HTTP Status Code
  - Content Size (in bytes)
  - Page Title (if available)
- **Statistics**: Total URLs crawled, errors encountered, and status code/domain statistics.

## Getting Started

### Prerequisites

Ensure you have the following installed on your machine:

- **Python 3.x**
  - You can download it [here](https://www.python.org/downloads/)

### Step-by-Step Guide

### 1. Clone the Repository or Download

To clone the repository using `git`, run:
```sh
git clone https://github.com/bsord/web-crawler.git
cd web-crawler
```

Alternatively, download the repository as a ZIP file, extract it, and navigate to the project folder.

### 2. Create a Virtual Environment

Create a virtual environment to isolate the project dependencies:

- **On macOS/Linux**:
    ```
    python3 -m venv venv
    source venv/bin/activate
    ```

- **On Windows**:
    ```
    python -m venv venv
    venv\Scripts\activate
    ```

### 3. Install Dependencies

With the virtual environment activated, install the required dependencies:
```sh
pip install -r requirements.txt
```

### 4. Run the Web Crawler

You can now run the web crawler:
```sh
python crawler.py
```

### 5. Run tests

Execute tests using pytest:
```sh
pytest
```

### 6. Deactivate the Virtual Environment

When you're done, deactivate the virtual environment by running:
```sh
deactivate
```