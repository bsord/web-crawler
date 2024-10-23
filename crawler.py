import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
import warnings
import json
from collections import deque
from urllib.robotparser import RobotFileParser
from database import Session
from models import CrawlResult

class WebCrawler:
    def __init__(self, max_depth, domains=None, blacklist=None):
        self.max_depth = max_depth
        self.domains = set(domains) if domains else set()
        self.blacklist = self.load_blacklist(blacklist)
        
        self.crawled_urls = set()
        self.url_data = {}
        self.queue = deque()
        
        self.total_urls_crawled = 0
        self.total_errors = 0
        self.status_code_stats = {}
        self.domain_stats = {}
        self.robot_parsers = {}
        self.db_session = Session()

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

    def crawl(self, start_url):
        self.queue.append((start_url, 0, None))  # (url, depth, parent_url)
        
        while self.queue:
            url, depth, parent_url = self.queue.popleft()
            print(f"Crawling URL: {url}")
            
            if depth > self.max_depth or url in self.crawled_urls:
                continue
            
            self.crawled_urls.add(url)
            
            try:
                response = requests.get(url, timeout=5)
                content = response.content
                status_code = response.status_code
                
                links = self.extract_links(content, url) if 'text/html' in response.headers.get('Content-Type', '') else []
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
                
                for link in valid_links:
                    if link not in self.crawled_urls:
                        self.queue.append((link, depth + 1, url))
                
                # Save to database
                existing_record = self.db_session.query(CrawlResult).filter_by(url=url).first()
                if existing_record:
                    existing_record.parent_url = parent_url
                    existing_record.status_code = status_code
                    existing_record.content_size = len(content)
                    existing_record.title = title
                    existing_record.statistics = self.url_data[url]['statistics']
                else:
                    crawl_result = CrawlResult(
                        url=url,
                        parent_url=parent_url,
                        status_code=status_code,
                        content_size=len(content),
                        title=title,
                        statistics=self.url_data[url]['statistics']
                    )
                    self.db_session.add(crawl_result)
                self.db_session.commit()
                
            except requests.RequestException as e:
                status_code = e.response.status_code if hasattr(e, 'response') and e.response is not None else None
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
                
                # Save error to database
                existing_record = self.db_session.query(CrawlResult).filter_by(url=url).first()
                if existing_record:
                    existing_record.parent_url = parent_url
                    existing_record.status_code = status_code
                    existing_record.content_size = 0
                    existing_record.title = 'Error'
                    existing_record.statistics = self.url_data[url]['statistics']
                else:
                    crawl_result = CrawlResult(
                        url=url,
                        parent_url=parent_url,
                        status_code=status_code,
                        content_size=0,
                        title='Error',
                        statistics=self.url_data[url]['statistics']
                    )
                    self.db_session.add(crawl_result)
                self.db_session.commit()

            if parent_url:
                self.update_parent_statistics(parent_url, url)

        self.db_session.close()
        return list(self.url_data.items())

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
        parent_stats = self.url_data[parent_url]['statistics']
        child_info = self.url_data[child_url]
        status_code = child_info['status_code']
        is_error = status_code >= 400

        parent_stats['total_urls_crawled'] += 1
        parent_stats['total_errors'] += 1 if is_error else 0
        
        # Update domain statistics
        child_domain = urlparse(child_url).netloc
        parent_stats['domain_stats'][child_domain] = parent_stats['domain_stats'].get(child_domain, 0) + 1

        # Update status code statistics
        parent_stats['status_code_stats'][status_code] = parent_stats['status_code_stats'].get(status_code, 0) + 1

        # Update existing record in database
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

# Example usage
if __name__ == "__main__":
    start_url = "https://toscrape.com/"
    max_depth = 2
    domains = []  # This will allow crawling of subdomains
    blacklist = ['.jpg', '.css', '.js', '.png']

    crawler = WebCrawler(max_depth=max_depth, domains=domains, blacklist=blacklist)
    results = crawler.crawl(start_url)
    
    print("First 25 crawled URLs and their data:")
    for url, data in results:
        print(f"\nURL: {url}")
        print(f"Status Code: {data['status_code']}")
        print(f"Content Size: {data['content_size']}")
        print(f"Title: {data['title']}")
        print("Statistics:")
        print(json.dumps(data['statistics'], indent=2))
