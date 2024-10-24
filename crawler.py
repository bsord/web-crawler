import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
import warnings
import json
from collections import deque
from urllib.robotparser import RobotFileParser
from database import Session
from models import CrawlResult
import time
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, before_sleep_log
import logging
import os

class WebCrawler:
    def __init__(self, max_depth, domains=None, blacklist=None, requests_per_second=2, max_retries=3, max_redirect_count=5):
        self.max_depth = max_depth
        self.max_redirect_count = max_redirect_count
        self.domains = set(domains) if domains else set()
        self.blacklist = self.load_blacklist(blacklist)
        self.requests_per_second = requests_per_second
        self.last_request_time = 0
        self.logger = logging.getLogger(__name__)
        
        self.crawled_urls = set()
        self.url_data = {}
        self.queue = deque()
        
        self.total_urls_crawled = 0
        self.total_errors = 0
        self.status_code_stats = {}
        self.domain_stats = {}
        self.robot_parsers = {}
        self.db_session = None  # Don't create session in init
        self.ensure_db_session()  # Create session when needed
        self.is_paused = False
        self.state_file = "crawler_state.json"

    def load_blacklist(self, blacklist):
        if isinstance(blacklist, list):
            return set(blacklist)
        elif isinstance(blacklist, str):
            try:
                with open(blacklist, 'r') as f:
                    return set(line.strip() for line in f if line.strip())
            except FileNotFoundError:
                warnings.warn(f"Blacklist file '{blacklist}' not found. Using empty blacklist.")
                return set()
        elif blacklist is None:
            return set()
        else:
            raise ValueError("Blacklist must be a list of extensions, a file path, or None")

    def wait_for_rate_limit(self):
        """Ensure we don't exceed our rate limit by waiting if necessary."""
        if self.requests_per_second <= 0:
            return
            
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        time_to_wait = (1.0 / self.requests_per_second) - time_since_last_request
        
        if time_to_wait > 0:
            time.sleep(time_to_wait)
        
        self.last_request_time = time.time()

    def make_request(self, url):
        """Make a single request with rate limiting"""
        self.wait_for_rate_limit()
        return requests.get(url, timeout=5, allow_redirects=False)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.RequestException
        )),
        before_sleep=before_sleep_log(logging.getLogger(__name__), logging.WARNING)
    )
    def crawl_url_with_retry(self, url):
        """Attempt to get the URL content with retries"""
        response = self.make_request(url)
        return response.content, response.status_code, response.headers

    def ensure_db_session(self):
        """Ensure we have a valid database session"""
        if not self.db_session or not self.db_session.is_active:
            if self.db_session:
                self.db_session.close()
            self.db_session = Session()

    def save_state(self):
        """Save current crawler state to a file"""
        if self.db_session:
            self.db_session.close()  # Close existing session before saving state
            self.db_session = None
            
        state = {
            'queue': list(self.queue),
            'crawled_urls': list(self.crawled_urls),
            'url_data': self.url_data
        }
        with open(self.state_file, 'w') as f:
            json.dump(state, f)

    def clear_state(self):
        """Remove the state file"""
        try:
            os.remove(self.state_file)
        except FileNotFoundError:
            pass  # File doesn't exist, which is fine

    def load_state(self):
        """Load crawler state from file"""
        try:
            with open(self.state_file, 'r') as f:
                state = json.load(f)
                self.queue = deque(state['queue'])
                self.crawled_urls = set(state['crawled_urls'])
                self.url_data = state['url_data']
                return True
        except FileNotFoundError:
            return False

    def pause(self):
        """Pause the crawler and save its state"""
        self.is_paused = True
        self.save_state()
        self.logger.info("Crawler paused. State saved.")

    def resume(self):
        """Resume crawler from saved state"""
        self.ensure_db_session()  # Ensure fresh database session
        self.is_paused = False
        
        if not self.load_state():
            raise ValueError("No saved state found")
            
        self.logger.info("Resuming from saved state")
        return self.crawl()

    def stop(self):
        """Stop the crawler and clean up state"""
        self.is_paused = False
        self.clear_state()
        if self.db_session:
            self.db_session.close()
            self.db_session = None
        self.logger.info("Crawler stopped. State cleared.")

    def start(self, start_url):
        """Start a fresh crawl"""
        self.ensure_db_session()
        self.is_paused = False
        self.crawled_urls.clear()
        self.url_data.clear()
        self.queue.clear()
        return self.crawl(start_url)

    def crawl(self, start_url=None):
        self.ensure_db_session()  # Ensure fresh database session
        
        if start_url:
            self.queue.append((start_url, 0, None, 0))

        try:
            while self.queue and not self.is_paused:
                url, depth, parent_url, redirect_count = self.queue.popleft()
                print(f"Crawling URL: {url}")
                
                if depth > self.max_depth or url in self.crawled_urls:
                    continue
                if redirect_count > self.max_redirect_count:
                    continue
                
                self.crawled_urls.add(url)
                
                try:
                    # Attempt to crawl with retries
                    content, status_code, headers = self.crawl_url_with_retry(url)
                    
                    if not headers.get('location'): # no redirect
                        
                        # Process successful response
                        links = self.extract_links(content, url) if 'text/html' in headers.get('Content-Type', '') else []
                        valid_links = [link for link in links if self.is_valid_url(link)]
                        
                        title = self.extract_title(content)

                        self.url_data[url] = {
                            'url': url,
                            'status_code': status_code,
                            'content_size': len(content),
                            'title': title,
                            'parent_url': parent_url,
                            'statistics': {
                                'total_urls_crawled': 0,
                                'total_errors': 0,
                                'status_code_stats': {},
                                'domain_stats': {}
                            }
                        }
                        
                        # Save successful crawl to database
                        self.save_to_database(url, parent_url, status_code, len(content), title)
                        
                        # Add valid links to queue
                        for link in valid_links:
                            if link not in self.crawled_urls:
                                self.queue.append((link, depth + 1, url, 0))
                    else: # redirect
                        self.url_data[url] = {
                            'url': url,
                            'status_code': status_code,
                            'content_size': len(content),
                            'title': 'no title',
                            'parent_url': parent_url,
                            'statistics': {
                                'total_urls_crawled': 0,
                                'total_errors': 0,
                                'status_code_stats': {},
                                'domain_stats': {}
                            }
                        }
                        print(f"Redirected {url} to: {headers.get('location')}")
                        self.queue.append((headers.get('location'), depth, url, redirect_count + 1))
                        
                    
                except Exception as e:
                    # This will only execute after all retries have failed
                    self.logger.error(f"Failed to crawl {url} after all retries: {str(e)}")
                    status_code = getattr(getattr(e, 'response', None), 'status_code', None)
                    
                    self.url_data[url] = {
                        'url': url,
                        'status_code': status_code,
                        'content_size': 0,
                        'title': 'Error',
                        'parent_url': parent_url,
                        'statistics': {
                            'total_urls_crawled': 0,
                            'total_errors': 0,
                            'status_code_stats': {},
                            'domain_stats': {}
                        }
                    }
                    
                    # Save error to database only after all retries have failed
                    self.save_to_database(url, parent_url, status_code, 0, 'Error')

                if parent_url:
                    self.update_parent_statistics(parent_url, url)

            if self.is_paused:
                self.save_state()
                return list(self.url_data.items())
            else:
                # Crawling completed naturally, clean up state file
                self.clear_state()
            
            return list(self.url_data.items())
            
        finally:
            if self.db_session:
                self.db_session.close()
                self.db_session = None

    def extract_links(self, content, base_url):
        soup = BeautifulSoup(content, 'html.parser')
        return [urljoin(base_url, link.get('href')) for link in soup.find_all('a', href=True)]

    def extract_title(self, content):
        soup = BeautifulSoup(content, 'html.parser')
        title_tag = soup.find('title')
        return title_tag.string if title_tag else 'No Title'

    def is_valid_url(self, url):
        parsed_url = urlparse(url)
        if any(parsed_url.path.endswith(ext) or parsed_url.fragment.endswith(ext) for ext in self.blacklist):
            return False
        if self.domains:
            return any(parsed_url.netloc == d or parsed_url.netloc.endswith('.' + d) for d in self.domains)
        return True

    def can_fetch(self, url):
        parsed_url = urlparse(url)
        robots_url = f"{parsed_url.scheme}://{parsed_url.netloc}/robots.txt"
        
        if robots_url not in self.robot_parsers:
            rp = RobotFileParser()
            rp.set_url(robots_url)
            rp.read()
            self.robot_parsers[robots_url] = rp
        
        return self.robot_parsers[robots_url].can_fetch("*", url)

    def update_parent_statistics(self, parent_url, child_url):
        """Update parent URL statistics"""
        self.ensure_db_session()  # Ensure valid session
        
        try:
            parent_stats = self.url_data[parent_url]['statistics']
            child_info = self.url_data[child_url]
            status_code = child_info['status_code']
            is_error = status_code >= 400 if status_code else True

            parent_stats['total_urls_crawled'] += 1
            parent_stats['total_errors'] += 1 if is_error else 0
            
            # Update domain statistics
            child_domain = urlparse(child_url).netloc
            parent_stats['domain_stats'][child_domain] = parent_stats['domain_stats'].get(child_domain, 0) + 1

            # Update status code statistics
            parent_stats['status_code_stats'][status_code] = parent_stats['status_code_stats'].get(status_code, 0) + 1

            # Update database
            existing_record = self.db_session.query(CrawlResult).filter_by(url=parent_url).first()
            if existing_record:
                existing_record.statistics = parent_stats
                existing_record.parent_url = self.url_data[parent_url].get('parent_url')
                existing_record.status_code = self.url_data[parent_url].get('status_code')
                existing_record.content_size = self.url_data[parent_url].get('content_size')
                existing_record.title = self.url_data[parent_url].get('title')
            else:
                crawl_result = CrawlResult(
                    url=parent_url,
                    parent_url=self.url_data[parent_url].get('parent_url'),
                    status_code=self.url_data[parent_url].get('status_code'),
                    content_size=self.url_data[parent_url].get('content_size'),
                    title=self.url_data[parent_url].get('title'),
                    statistics=parent_stats
                )
                self.db_session.add(crawl_result)
            
            self.db_session.commit()
            
        except Exception as e:
            self.logger.error(f"Error updating parent statistics: {str(e)}")
            self.db_session.rollback()
            raise

    def save_to_database(self, url, parent_url, status_code, content_size, title):
        """Helper method to handle database operations"""
        self.ensure_db_session()  # Ensure valid session
        
        try:
            existing_record = self.db_session.query(CrawlResult).filter_by(url=url).first()
            if existing_record:
                existing_record.parent_url = parent_url
                existing_record.status_code = status_code
                existing_record.content_size = content_size
                existing_record.title = title
                existing_record.statistics = self.url_data[url]['statistics']
            else:
                crawl_result = CrawlResult(
                    url=url,
                    parent_url=parent_url,
                    status_code=status_code,
                    content_size=content_size,
                    title=title,
                    statistics=self.url_data[url]['statistics']
                )
                self.db_session.add(crawl_result)
            
            self.db_session.commit()
            
        except Exception as e:
            self.logger.error(f"Error saving to database: {str(e)}")
            self.db_session.rollback()
            raise

# Example usage
if __name__ == "__main__":
    start_url = "https://toscrape.com/"
    max_depth = 2
    domains = []  # This will allow crawling of subdomains
    blacklist = ['.jpg', '.css', '.js', '.png']

    crawler = WebCrawler(max_depth=max_depth, domains=domains, blacklist=blacklist, requests_per_second=.5, max_redirect_count=5)
    
    # Example of pausing after 5 seconds
    import threading
    timer = threading.Timer(5.0, crawler.pause)
    timer.start()
    
    # Start crawling
    results = crawler.crawl(start_url)
    print("Crawler paused. Processed URLs:", len(results))
    
    # Resume crawling
    results = crawler.resume()
    print("Crawler finished. Total URLs:", len(results))
