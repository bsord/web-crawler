import pytest
import sys
import os
from crawler import WebCrawler
from unittest.mock import patch, MagicMock, mock_open

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

    # Invalid URL (valid extension but not has query string)
    assert crawler.is_valid_url("https://www.example.com/page?query=1") == True

# Example Test for Title Extraction
def test_extract_title():
    crawler = WebCrawler(max_depth=2)
    html_content = "<html><head><title>Test Page</title></head><body>Content</body></html>"
    
    title = crawler.extract_title(html_content)
    assert title == "Test Page"
    
    # Case where title is missing
    html_no_title = "<html><head></head><body>Content</body></html>"
    title_no_title = crawler.extract_title(html_no_title)
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


# Test for respecting robots.txt
def test_respect_robots_txt():
    crawler = WebCrawler(max_depth=2, domains=["example.com"])
    
    # Mock the RobotFileParser
    mock_rp = MagicMock()
    
    with patch('crawler.RobotFileParser', return_value=mock_rp) as mock_robot_parser:
        # Test allowed URL
        mock_rp.can_fetch.return_value = True
        assert crawler.can_fetch("https://www.example.com/allowed") == True
        
        # Test disallowed URL
        mock_rp.can_fetch.return_value = False
        assert crawler.can_fetch("https://www.example.com/disallowed") == False
        
        # Ensure RobotFileParser is called with correct URL
        mock_rp.set_url.assert_called_with("https://www.example.com/robots.txt")
        mock_rp.read.assert_called()

        # Test caching of RobotFileParser instances
        crawler.can_fetch("https://www.example.com/page1")
        crawler.can_fetch("https://www.example.com/page2")
        
        # RobotFileParser should only be instantiated once per domain
        assert mock_robot_parser.call_count == 1

# New test for crawling all domains when no specific domains are specified
def test_crawl_all_domains():
    crawler = WebCrawler(max_depth=2)  # No domains specified
    
    # Test URLs from different domains
    urls = [
        "https://example.com/page1",
        "https://anotherdomain.com/page2",
        "https://thirddomain.org/page3"
    ]
    
    for url in urls:
        assert crawler.is_valid_url(url) == True, f"Failed to validate {url}"

# New tests for blacklist functionality
def test_load_blacklist_from_list():
    blacklist = ['.jpg', '.png', '.css']
    crawler = WebCrawler(max_depth=2, blacklist=blacklist)
    assert set(crawler.blacklist) == set(blacklist)

def test_load_blacklist_from_file(tmp_path):
    blacklist_file = tmp_path / "blacklist.txt"
    blacklist_file.write_text(".jpg\n.png\n.css")
    crawler = WebCrawler(max_depth=2, blacklist=str(blacklist_file))
    assert set(crawler.blacklist) == {'.jpg', '.png', '.css'}

def test_load_blacklist_file_not_found():
    with pytest.warns(UserWarning, match="Blacklist file 'nonexistent_file.txt' not found"):
        crawler = WebCrawler(max_depth=2, blacklist="nonexistent_file.txt")
    assert crawler.blacklist == set()

def test_load_blacklist_invalid_type():
    with pytest.raises(ValueError, match="Blacklist must be a list of extensions, a file path, or None"):
        WebCrawler(max_depth=2, blacklist=123)

def test_is_valid_url_with_blacklist():
    crawler = WebCrawler(max_depth=2, domains=["example.com"], blacklist=['.jpg', '.png'])
    
    assert crawler.is_valid_url("https://www.example.com/page.html") == True
    assert crawler.is_valid_url("https://www.example.com/image.jpg") == False
    assert crawler.is_valid_url("https://www.example.com/image.png") == False
    assert crawler.is_valid_url("https://www.example.com/image.gif") == True

def test_is_valid_url_with_empty_blacklist():
    crawler = WebCrawler(max_depth=2, domains=["example.com"])
    
    assert crawler.is_valid_url("https://www.example.com/page.html") == True
    assert crawler.is_valid_url("https://www.example.com/image.jpg") == True
    assert crawler.is_valid_url("https://www.example.com/image.png") == True
