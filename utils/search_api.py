import os
import requests
from typing import List, Dict, Optional
import json

class SearchAPI:
    """
    Search API client supporting multiple providers (Serper, Tavily, Perplexity)
    Falls back between providers if one fails.
    """
    
    def __init__(self):
        # Check available API keys
        self.serper_api_key = os.getenv('SERPER_API_KEY')
        
        # Determine which provider to use
        self.providers = []
        if self.serper_api_key:
            self.providers.append('serper')
        
        if not self.providers:
            raise ValueError("A SERPER_API_KEY is required: ")
        
        print(f"Search API initialized with providers: {', '.join(self.providers)}")
    
    def search(self, query: str, num_results: int = 10) -> List[Dict[str, str]]:
        """
        Search for URLs using available providers.
        
        Args:
            query: Search query
            num_results: Number of results to return
            
        Returns:
            List of dictionaries with 'url', 'title', and 'snippet' keys
        """
        for provider in self.providers:
            try:
                print(f"Trying search with {provider}")
                
                if provider == 'serper':
                    results = self._search_serper(query, num_results)
                else:
                    continue
                
                if results:
                    print(f"Successfully got {len(results)} results from {provider}")
                    return results
                    
            except Exception as e:
                print(f"Error with {provider}: {e}")
                continue
        
        print("All search providers failed")
        return []
    
    def _search_serper(self, query: str, num_results: int) -> List[Dict[str, str]]:
        """Search using Serper.dev API"""
        url = "https://google.serper.dev/search"
        
        payload = {
            'q': query,
            'num': num_results
        }
        
        headers = {
            'X-API-KEY': self.serper_api_key,
            'Content-Type': 'application/json'
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        results = []
        
        # Process organic results
        for item in data.get('organic', [])[:num_results]:
            results.append({
                'url': item.get('link', ''),
                'title': item.get('title', ''),
                'snippet': item.get('snippet', '')
            })
        
        return results
    
    def test_connection(self) -> Dict[str, bool]:
        """Test connection to all available providers"""
        results = {}
        
        for provider in self.providers:
            try:
                if provider == 'serper':
                    test_results = self._search_serper("test query", 1)
                
                results[provider] = len(test_results) > 0
                
            except Exception as e:
                print(f"Test failed for {provider}: {e}")
                results[provider] = False
        
        return results