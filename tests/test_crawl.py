import pytest
from unittest.mock import patch
import requests
import sys
import os
from crawler import WebCrawler

# Example Test with Mocking HTTP Request
@patch('requests.get')
def test_crawl(mock_get):
    # Mocking a response object
    mock_get.return_value.status_code = 200
    mock_get.return_value.content = "<html><head><title>Mock Page</title></head><body>Content</body></html>"
    
    crawler = WebCrawler(max_depth=2)
    
    start_url = "https://www.example.com"
    crawler.crawl(start_url)
    
    # Verify the crawled URL is in the results
    assert start_url in crawler.crawled_urls
    assert crawler.url_data[start_url]['status_code'] == 200
    assert crawler.url_data[start_url]['title'] == "Mock Page"
