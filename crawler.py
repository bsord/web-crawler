import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin

class WebCrawler:
    def __init__(self, max_depth, domains=None, blacklist=None):
        self.max_depth = max_depth
        self.domains = domains if domains else []
        self.blacklist = blacklist if blacklist else []
        self.crawled_urls = {}
        self.errors = 0
        self.status_code_stats = {}
        self.domain_stats = {}

    def is_valid_url(self, url):
        # Parse the URL
        parsed_url = urlparse(url)
        
        # Ignore blacklisted file extensions in the path or fragment
        if any(parsed_url.path.endswith(ext) or parsed_url.fragment.endswith(ext) for ext in self.blacklist):
            return False

        # Restrict crawling to specific domains
        if self.domains:
            domain = parsed_url.netloc
            if not any(domain.endswith(d) for d in self.domains):
                return False

        return True



    def crawl(self, start_url):
        self._crawl_recursive(start_url, 0)

    def _crawl_recursive(self, url, depth):
        if depth > self.max_depth or url in self.crawled_urls:
            return

        try:
            response = requests.get(url, timeout=5)
            self.crawled_urls[url] = {
                'status_code': response.status_code,
                'content_size': len(response.content),
                'title': self.get_title(response.content)
            }

            # Update status code statistics
            self.status_code_stats[response.status_code] = self.status_code_stats.get(response.status_code, 0) + 1

            # Update domain statistics
            domain = urlparse(url).netloc
            self.domain_stats[domain] = self.domain_stats.get(domain, 0) + 1

            # Continue crawling the links on this page if it's an HTML page
            if 'text/html' in response.headers['Content-Type']:
                soup = BeautifulSoup(response.text, 'html.parser')
                for link in soup.find_all('a', href=True):
                    print('link', link['href'])
                    next_url = urljoin(url, link['href'])
                    if self.is_valid_url(next_url):
                        self._crawl_recursive(next_url, depth + 1)

        except requests.RequestException as e:
            self.errors += 1
            self.crawled_urls[url] = {
                'status_code': None,
                'content_size': 0,
                'title': 'Error'
            }

    def get_title(self, html_content):
        soup = BeautifulSoup(html_content, 'html.parser')
        title_tag = soup.find('title')
        return title_tag.string if title_tag else 'No Title'

    def print_statistics(self):
        print("Total URLs crawled:", len(self.crawled_urls))
        print("Total errors encountered:", self.errors)
        print("\nStatus Code Statistics:")
        for code, count in self.status_code_stats.items():
            print(f"  {code}: {count}")
        print("\nDomain Statistics:")
        for domain, count in self.domain_stats.items():
            print(f"  {domain}: {count}")

# Example usage
if __name__ == "__main__":
    start_url = "https://www.reddit.com/r/TechSEO/comments/mzlvzj/crawler_test_site/"
    max_depth = 2
    domains = ["reddit.com"]
    blacklist = ['.jpg', '.css', '.js', '.png']

    crawler = WebCrawler(max_depth=max_depth, domains=domains, blacklist=blacklist)
    crawler.crawl(start_url)
    crawler.print_statistics()
