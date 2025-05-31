import os
import requests
from typing import Dict, List, Optional, Any
import json
import time

class LLMClient:
    """
    LLM client supporting OpenAI with fallback capabilities and optimized for company research tasks.
    """
    
    def __init__(self):
        # Check available API keys
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        
        # Determine available providers in order of preference
        self.providers = []
        if self.openai_api_key:
            self.providers.append('openai')
        
        if not self.providers:
            raise ValueError("An OPENAI_API_KEY is required")
        
        print(f"LLM Client initialized with providers: {', '.join(self.providers)}")
    
    def generate_response(self, prompt: str, max_tokens: int = 1000, temperature: float = 0.7) -> str:
        """
        Generate a response using available LLM providers with fallback.
        
        Args:
            prompt: The input prompt
            max_tokens: Maximum tokens to generate
            temperature: Temperature for generation (0.0-1.0)
            
        Returns:
            Generated response string
        """
        for provider in self.providers:
            try:
                print(f"Trying LLM generation with {provider}")
                
                if provider == 'openai':
                    response = self._generate_openai(prompt, max_tokens, temperature)
                else:
                    continue
                
                if response:
                    print(f"Successfully generated response with {provider}")
                    return response
                    
            except Exception as e:
                print(f"Error with {provider}: {e}")
                continue
        
        return "I apologize, but I'm having trouble generating a response right now. Please try again."
    
    def analyze_company_content(self, content: str, company_name: str) -> Dict[str, str]:
        """
        Specialized method for analyzing company website content.
        
        Args:
            content: Scraped website content
            company_name: Name of the company
            
        Returns:
            Dictionary with analysis results
        """
        prompt = f"""
Analyze the following website content for {company_name} and provide detailed information about:

1. What They Sell: Products, services, features, offerings, etc. (be comprehensive and detailed)
2. Who They Target: Target audience, customer segments, industries, use cases, etc. (be specific and detailed)
3. Condensed Summary: A brief 3-4 sentence summary combining both aspects

Website Content:
{content[:8000]}...

Please format your response as JSON with keys: "what_they_sell", "who_they_target", "condensed_summary"

Make sure each section is detailed and informative - this will be used for business research purposes.
"""
        
        response = self.generate_response(prompt, max_tokens=1500, temperature=0.3)
        
        # Try to parse JSON response
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            # Fallback to text parsing if JSON fails
            return self._parse_text_analysis(response)
    
    def answer_followup_question(self, question: str, context: str, company_name: str) -> str:
        """
        Answer follow-up questions about the company using scraped content.
        
        Args:
            question: User's question
            context: Scraped website content
            company_name: Name of the company
            
        Returns:
            Answer to the question
        """
        prompt = f"""
Based on the research about {company_name}, please answer the following question:

Question: {question}

Context from website:
{context[:4000]}...

Please provide a helpful, specific, and accurate answer based on the available information. If the information isn't available in the context, say so clearly.
"""
        
        return self.generate_response(prompt, max_tokens=800, temperature=0.5)
    
    def _generate_openai(self, prompt: str, max_tokens: int, temperature: float) -> str:
        """Generate response using OpenAI API"""
        url = "https://api.openai.com/v1/chat/completions"
        
        headers = {
            'Authorization': f'Bearer {self.openai_api_key}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'model': 'gpt-4-turbo-preview',
            'messages': [
                {'role': 'system', 'content': 'You are a helpful AI assistant specialized in business research and analysis.'},
                {'role': 'user', 'content': prompt}
            ],
            'max_tokens': max_tokens,
            'temperature': temperature
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        return data['choices'][0]['message']['content']
    
    def _parse_text_analysis(self, text: str) -> Dict[str, str]:
        """
        Fallback text parsing if JSON parsing fails.
        """
        lines = text.split('\n')
        
        what_they_sell = ""
        who_they_target = ""
        condensed_summary = ""
        
        current_section = None
        
        for line in lines:
            line = line.strip()
            if 'what they sell' in line.lower() or 'what_they_sell' in line.lower():
                current_section = 'sell'
            elif 'who they target' in line.lower() or 'who_they_target' in line.lower():
                current_section = 'target'
            elif 'condensed summary' in line.lower() or 'condensed_summary' in line.lower() or 'summary' in line.lower():
                current_section = 'summary'
            elif line and current_section and not line.startswith('{') and not line.startswith('}'):
                if current_section == 'sell':
                    what_they_sell += line + " "
                elif current_section == 'target':
                    who_they_target += line + " "
                elif current_section == 'summary':
                    condensed_summary += line + " "
        
        return {
            "what_they_sell": what_they_sell.strip() or "Unable to determine products/services from available content",
            "who_they_target": who_they_target.strip() or "Unable to determine target audience from available content",
            "condensed_summary": condensed_summary.strip() or f"Research completed for company analysis"
        }
    
    def test_connection(self) -> Dict[str, bool]:
        """Test connection to all available LLM providers"""
        results = {}
        
        for provider in self.providers:
            try:
                if provider == 'openai':
                    response = self._generate_openai("Say 'test successful'", 50, 0.1)
                
                results[provider] = 'test' in response.lower()
                
            except Exception as e:
                print(f"Test failed for {provider}: {e}")
                results[provider] = False
        
        return results