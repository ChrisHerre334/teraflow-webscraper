import os
import requests
import time
from typing import Optional, List, Dict
from urllib.parse import urljoin, urlparse
import json

class WebScraper:
    """
    Web scraping utility using FireCrawl API to scrape 10-15 relevant pages
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
            
            # First, scrape the main page to get site structure
            main_content = self._scrape_single_page(url)
            if not main_content:
                return None
            
            # Get additional pages to scrape using crawl mode
            all_content = [main_content]
            additional_pages = self._get_crawl_pages(url, max_pages - 1)
            
            if additional_pages:
                print(f"Found {len(additional_pages)} additional pages to scrape")
                
                for page_url in additional_pages[:max_pages-1]:  # -1 because we already have main page
                    try:
                        page_content = self._scrape_single_page(page_url)
                        if page_content:
                            all_content.append(page_content)
                        time.sleep(0.5)  # Rate limiting
                    except Exception as e:
                        print(f"Error scraping {page_url}: {e}")
                        continue
            
            # Combine all content
            combined_content = "\n\n---PAGE BREAK---\n\n".join(all_content)
            print(f"Successfully scraped {len(all_content)} pages")
            
            return combined_content
            
        except Exception as e:
            print(f"Error in website scraping: {e}")
            return None
    
    def _scrape_single_page(self, url: str) -> Optional[str]:
        """Scrape a single page using FireCrawl API."""
        headers = {
            'Authorization': f'Bearer {self.firecrawl_api_key}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'url': url,
            'formats': ['markdown'],
            'includeTags': ['main', 'article', 'section', 'div'],
            'excludeTags': ['nav', 'footer', 'header', 'aside', 'script', 'style'],
            'onlyMainContent': True
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
                    return data['data'].get('markdown', '')
            else:
                print(f"FireCrawl API error: {response.status_code} - {response.text}")
                
        except Exception as e:
            print(f"Error scraping single page {url}: {e}")
        
        return