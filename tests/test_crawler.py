import pytest
import sys
import os
from crawler import WebCrawler

# Example Test for URL Validation
def test_is_valid_url():
    crawler = WebCrawler(max_depth=2, domains=["example.com"], blacklist=[".jpg", ".png"])
    
    # Valid URL (correct domain, not blacklisted)
    assert crawler.is_valid_url("https://www.example.com/page") == True
    
    # Invalid URL (blacklisted extension in the path)
    assert crawler.is_valid_url("https://www.example.com/image.jpg") == False
    
    # Invalid URL (blacklisted extension in the path with query string)
    assert crawler.is_valid_url("https://www.example.com/image.jpg?query=1") == False

    # Invalid URL (blacklisted extension in the fragment)
    assert crawler.is_valid_url("https://www.example.com/page#image.jpg") == False
    
    # Invalid URL (wrong domain)
    assert crawler.is_valid_url("https://www.otherdomain.com/page") == False


# Example Test for Title Extraction
def test_get_title():
    crawler = WebCrawler(max_depth=2)
    html_content = "<html><head><title>Test Page</title></head><body>Content</body></html>"
    
    title = crawler.get_title(html_content)
    assert title == "Test Page"
    
    # Case where title is missing
    html_no_title = "<html><head></head><body>Content</body></html>"
    title_no_title = crawler.get_title(html_no_title)
    assert title_no_title == "No Title"

# Example Test for Crawl Depth
def test_max_depth():
    crawler = WebCrawler(max_depth=1)
    
    # Test that it won't crawl beyond max_depth
    crawler.crawled_urls = {}  # Reset crawled URLs
    start_url = "https://example.com"
    
    def mock_crawl_recursive(url, depth):
        if depth > crawler.max_depth:
            return False
        return True
    
    crawler._crawl_recursive = mock_crawl_recursive
    
    assert crawler._crawl_recursive(start_url, 0) == True
    assert crawler._crawl_recursive(start_url, 2) == False



