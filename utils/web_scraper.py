import os
import requests
import time
from typing import Optional, List, Dict
from urllib.parse import urljoin, urlparse
import re

class WebScraper:
    """
    Web scraping utility using FireCrawl API v1 to scrape 10-15 relevant pages
    from a company website and return clean, readable content.
    """
    
    def __init__(self):
        self.firecrawl_api_key = os.getenv('FIRECRAWL_API_KEY')
        self.base_url = "https://api.firecrawl.dev/v1"
        
        if not self.firecrawl_api_key:
            raise ValueError("FIRECRAWL_API_KEY environment variable is required")
    
    def scrape_website(self, url: str, max_pages: int = 15) -> Optional[str]:
        """
        Scrape multiple pages from a website and return combined content.
        
        Args:
            url: The base URL to scrape
            max_pages: Maximum number of pages to scrape (default 15)
            
        Returns:
            Combined markdown content from all scraped pages
        """
        try:
            print(f"Starting website scrape for: {url}")
            
            # Use crawl mode to get multiple pages at once
            crawl_result = self._crawl_website(url, max_pages)
            
            if crawl_result and len(crawl_result) > 0:
                # Combine all content with clear page breaks
                combined_content = []
                
                for i, page_data in enumerate(crawl_result[:max_pages]):
                    page_url = page_data.get('url', url)
                    page_content = page_data.get('markdown', '')
                    
                    if page_content.strip():
                        header = f"=== PAGE {i+1}: {page_url} ==="
                        combined_content.append(f"{header}\n\n{page_content}")
                
                if combined_content:
                    final_content = "\n\n---PAGE BREAK---\n\n".join(combined_content)
                    print(f"Successfully scraped {len(combined_content)} pages")
                    return final_content
            
            # Fallback to single page scraping if crawl fails
            print("Crawl failed, falling back to single page scrape")
            return self._scrape_single_page(url)
            
        except Exception as e:
            print(f"Error in website scraping: {e}")
            return None
    
    def _crawl_website(self, url: str, max_pages: int) -> Optional[List[Dict]]:
        """Use FireCrawl's crawl endpoint to get multiple pages."""
        headers = {
            'Authorization': f'Bearer {self.firecrawl_api_key}',
            'Content-Type': 'application/json'
        }
        
        # Updated payload structure for v1 API
        payload = {
            'url': url,
            'limit': max_pages,
            'scrapeOptions': {
                'formats': ['markdown'],
                'onlyMainContent': True,
                'includeTags': [],
                'excludeTags': ['nav', 'footer', 'header', 'aside'],
                'removeBase64Images': True
            },
            'allowBackwardLinks': False,
            'allowExternalLinks': False,
            'includePaths': [
                '/about*',
                '/products*',
                '/services*',
                '/solutions*',
                '/features*',
                '/pricing*',
                '/customers*',
                '/industries*',
                '/company*',
                '/team*'
            ],
            'excludePaths': [
                '/blog*',
                '/news*',
                '/careers*',
                '/jobs*',
                '/contact*',
                '/support*',
                '/help*',
                '/faq*',
                '/terms*',
                '/privacy*',
                '/legal*'
            ]
        }
        
        try:
            # Start crawl job
            response = requests.post(
                f"{self.base_url}/crawl",
                headers=headers,
                json=payload,
                timeout=10
            )
            
            if response.status_code != 200:
                print(f"Crawl start failed: {response.status_code} - {response.text}")
                return None
            
            crawl_data = response.json()
            job_id = crawl_data.get('id')
            
            if not job_id:
                print("No job ID returned from crawl start")
                return None
            
            # Poll for results
            max_wait = 120  # 2 minutes max wait
            wait_time = 0
            
            while wait_time < max_wait:
                time.sleep(5)
                wait_time += 5
                
                status_response = requests.get(
                    f"{self.base_url}/crawl/{job_id}",
                    headers=headers,
                    timeout=10
                )
                
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    status = status_data.get('status')
                    
                    if status == 'completed':
                        return status_data.get('data', [])
                    elif status == 'failed':
                        print(f"Crawl job failed: {status_data.get('error', 'Unknown error')}")
                        return None
                    # Continue polling if still running
                else:
                    print(f"Status check failed: {status_response.status_code}")
                    return None
            
            print("Crawl job timed out")
            return None
            
        except Exception as e:
            print(f"Error in crawl operation: {e}")
            return None
    
    def _scrape_single_page(self, url: str) -> Optional[str]:
        """Scrape a single page using FireCrawl API."""
        headers = {
            'Authorization': f'Bearer {self.firecrawl_api_key}',
            'Content-Type': 'application/json'
        }
        
        # Updated payload structure for v1 API
        payload = {
            'url': url,
            'formats': ['markdown'],
            'onlyMainContent': True,
            'includeTags': [],
            'excludeTags': ['nav', 'footer', 'header', 'aside'],
            'removeBase64Images': True
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/scrape",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success') and data.get('data'):
                    content = data['data'].get('markdown', '')
                    if content:
                        return f"=== PAGE: {url} ===\n\n{content}"
            else:
                print(f"FireCrawl API error: {response.status_code} - {response.text}")
                
        except Exception as e:
            print(f"Error scraping single page {url}: {e}")
        
        return None
    
    def test_connection(self) -> bool:
        """Test the FireCrawl API connection."""
        try:
            test_url = "https://example.com"
            result = self._scrape_single_page(test_url)
            return result is not None
        except Exception as e:
            print(f"Connection test failed: {e}")
            return False