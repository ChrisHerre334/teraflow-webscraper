import os
import re
import json
import requests
import streamlit as st
from typing import Dict, List, Optional, Union
from dataclasses import dataclass
from datetime import datetime

# Import your utilities
from .session_helpers import update_session_state
from .web_scraper import WebScraper
from .search_api import SearchAPI
from .llm_client import LLMClient
from .n8n_webhook import N8NWebhook

@dataclass
class CompanyResearch:
    company_name: str
    scraped_content: str
    what_they_sell: str
    who_they_target: str
    condensed_summary: str
    recipient_email: str

class ResearchAgent:
    def __init__(self):
        self.search_api = SearchAPI()
        self.web_scraper = WebScraper()
        self.llm_client = LLMClient()
        self.n8n_webhook = N8NWebhook()
        
        # Agent states
        self.GREETING = "greeting"
        self.COLLECTING_INFO = "collecting_info"
        self.SEARCHING_URLS = "searching_urls"
        self.WAITING_URL_CONFIRMATION = "waiting_url_confirmation"
        self.SCRAPING_WEBSITE = "scraping_website"
        self.ANALYZING_CONTENT = "analyzing_content"
        self.READY_FOR_QUESTIONS = "ready_for_questions"
        self.COMPLETE = "complete"
        
        # Initialize agent state
        if 'agent_state' not in st.session_state:
            st.session_state.agent_state = self.GREETING
            
        if 'company_name' not in st.session_state:
            st.session_state.company_name = None
            
        if 'recipient_email' not in st.session_state:
            st.session_state.recipient_email = None
            
        if 'candidate_urls' not in st.session_state:
            st.session_state.candidate_urls = []
            
        if 'selected_url' not in st.session_state:
            st.session_state.selected_url = None
            
        if 'scraped_content' not in st.session_state:
            st.session_state.scraped_content = ""
            
        if 'research_data' not in st.session_state:
            st.session_state.research_data = None

    def process_message(self, user_input: str) -> Union[str, Dict]:
        """Main agent processing logic"""
        try:
            current_state = st.session_state.agent_state
            
            if current_state == self.GREETING:
                return self._handle_greeting(user_input)
            elif current_state == self.COLLECTING_INFO:
                return self._handle_info_collection(user_input)
            elif current_state == self.WAITING_URL_CONFIRMATION:
                return self._handle_url_confirmation(user_input)
            elif current_state == self.READY_FOR_QUESTIONS:
                return self._handle_follow_up_questions(user_input)
            else:
                return "I'm currently processing your request. Please wait..."
                
        except Exception as e:
            update_session_state(current_status=f"❌ Error: {str(e)}")
            return f"I encountered an error: {str(e)}. Please try again."

    def _handle_greeting(self, user_input: str) -> str:
        """Handle initial greeting and company name extraction"""
        update_session_state(current_status="🤖 Getting started...")
        
        # Try to extract company name from the message
        company_name = self._extract_company_name(user_input)
        
        if company_name:
            st.session_state.company_name = company_name
            st.session_state.agent_state = self.COLLECTING_INFO
            return f"Great! I'll research **{company_name}** for you. What email address should I send the final results to?"
        else:
            return "Hello! I'm your AI research assistant. Which company would you like me to research today? Please provide the company name."

    def _handle_info_collection(self, user_input: str) -> Union[str, Dict]:
        """Collect email and start search process"""
        # Extract email from user input
        email = self._extract_email(user_input)
        
        if email:
            st.session_state.recipient_email = email
            update_session_state(current_status="🔍 Searching for company website...")
            
            # Start URL search
            urls = self._search_company_urls(st.session_state.company_name)
            
            if urls:
                st.session_state.candidate_urls = urls
                st.session_state.agent_state = self.WAITING_URL_CONFIRMATION
                
                message = f"Perfect! I found several potential websites for **{st.session_state.company_name}**. Please copy and paste the correct URL from the list below:"
                
                return {
                    "message": message,
                    "urls": urls
                }
            else:
                return f"I couldn't find any websites for {st.session_state.company_name}. Could you provide a different company name or the website URL directly?"
        else:
            return "Please provide a valid email address where I should send the research results."

    def _handle_url_confirmation(self, user_input: str) -> str:
        """Handle URL selection and start scraping"""
        # Check if user input contains one of the candidate URLs
        selected_url = None
        user_input_lower = user_input.lower().strip()
        
        for url in st.session_state.candidate_urls:
            if url.lower() in user_input_lower:
                selected_url = url
                break
                
        # Also check for direct URL patterns
        if not selected_url:
            url_pattern = r'https?://[^\s]+'
            matches = re.findall(url_pattern, user_input)
            if matches:
                selected_url = matches[0]
        
        if selected_url:
            st.session_state.selected_url = selected_url
            st.session_state.agent_state = self.SCRAPING_WEBSITE
            
            # Start scraping process
            return self._start_scraping_and_analysis()
        else:
            return "Please copy and paste one of the URLs I provided, or provide a valid website URL for the company."

    def _start_scraping_and_analysis(self) -> str:
        """Scrape website and perform analysis"""
        try:
            update_session_state(current_status="🕷️ Scraping website content...")
            
            # Scrape the website
            scraped_content = self.web_scraper.scrape_website(
                st.session_state.selected_url, 
                max_pages=15
            )
            
            if not scraped_content:
                return "I couldn't scrape content from that website. Please try a different URL."
            
            st.session_state.scraped_content = scraped_content
            
            update_session_state(current_status="🧠 Analyzing company information...")
            
            # Analyze the content
            analysis = self._analyze_company_content(scraped_content)
            
            if analysis:
                # Create research data object
                research_data = CompanyResearch(
                    company_name=st.session_state.company_name,
                    scraped_content=scraped_content,
                    what_they_sell=analysis['what_they_sell'],
                    who_they_target=analysis['who_they_target'],
                    condensed_summary=analysis['condensed_summary'],
                    recipient_email=st.session_state.recipient_email
                )
                
                st.session_state.research_data = research_data
                
                # Send to n8n webhook
                update_session_state(current_status="📤 Saving to Airtable and sending email...")
                
                webhook_success = self._send_to_n8n_webhook(research_data)
                
                if webhook_success:
                    st.session_state.agent_state = self.READY_FOR_QUESTIONS
                    update_session_state(current_status="✅ Research complete! Ask me any follow-up questions.")
                    
                    return f"""
## Research Complete! ✅

Here's what I found about **{st.session_state.company_name}**:

### What They Sell
{analysis['what_they_sell']}

### Who They Target
{analysis['who_they_target']}

---

I've saved this information to Airtable and sent a summary to **{st.session_state.recipient_email}**.

Feel free to ask me any follow-up questions about the company!
"""
                else:
                    return "I completed the research but encountered an issue saving the data. The analysis is ready above."
            else:
                return "I had trouble analyzing the website content. Please try again or provide a different URL."
                
        except Exception as e:
            update_session_state(current_status=f"❌ Error during analysis: {str(e)}")
            return f"I encountered an error during analysis: {str(e)}"

    def _handle_follow_up_questions(self, user_input: str) -> str:
        """Handle follow-up questions about the research"""
        try:
            # Use the scraped content and LLM to answer questions
            context = st.session_state.scraped_content
            research_data = st.session_state.research_data
            
            prompt = f"""
Based on the research I conducted about {research_data.company_name}, please answer the following question:

Question: {user_input}

Context from website:
{context[:3000]}...

Previous analysis:
What they sell: {research_data.what_they_sell}
Who they target: {research_data.who_they_target}

Please provide a helpful and specific answer based on this information.
"""
            
            response = self.llm_client.generate_response(prompt)
            return response
            
        except Exception as e:
            return f"I had trouble answering your question: {str(e)}"

    def _search_company_urls(self, company_name: str) -> List[str]:
        """Search for company URLs"""
        try:
            search_results = self.search_api.search(f"{company_name} official website")
            urls = []
            
            for result in search_results:
                if 'url' in result:
                    urls.append(result['url'])
                    
            return urls[:5]  # Return top 5 URLs
            
        except Exception as e:
            print(f"Search error: {e}")
            return []

    def _analyze_company_content(self, content: str) -> Optional[Dict[str, str]]:
        """Analyze scraped content to extract key information"""
        try:
            prompt = f"""
            You are an expert business analyst. Your job is to extract meaningful insights from company websites.

            Given the website content below, analyze and return the following:

            1. "what_they_sell" — Summarize their core products, services, features, or business model.
            2. "who_they_target" — Describe their main audience, demographics, industries, or customer types.
            3. "condensed_summary" — Combine both insights into a short 3–4 sentence executive summary.

            If you cannot find relevant information, explain *why*, but still return valid JSON.

            Respond ONLY in JSON format like this:
            {{
            "what_they_sell": "...",
            "who_they_target": "...",
            "condensed_summary": "..."
            }}

            Content:
            {content[:4000]}...
            """
            
            response = self.llm_client.generate_response(prompt)
            
            # Try to parse JSON response
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                # Fallback to text parsing if JSON fails
                return self._parse_text_analysis(response)
                
        except Exception as e:
            print(f"Analysis error: {e}")
            return None

    def _send_to_n8n_webhook(self, research_data: CompanyResearch) -> bool:
        """Send research data to n8n webhook"""
        try:
            payload = {
                "CompanyName": research_data.company_name,
                "ScrapedContent": research_data.scraped_content,
                "WhatTheySell": research_data.what_they_sell,
                "WhoTheyTarget": research_data.who_they_target,
                "CondensedSummary": research_data.condensed_summary,
                "recipientEmail": research_data.recipient_email
            }
            
            success = self.n8n_webhook.send_data(payload)
            return success
            
        except Exception as e:
            print(f"Webhook error: {e}")
            return False

    def _extract_company_name(self, text: str) -> Optional[str]:
        """Extract company name from user input"""
        # Simple extraction logic - can be enhanced with NLP
        text = text.strip()
        
        # Look for patterns like "research [company]" or "I want to research [company]"
        patterns = [
            r"research\s+(.+?)(?:\s+for\s+me)?$",
            r"analyze\s+(.+?)(?:\s+for\s+me)?$",
            r"tell me about\s+(.+?)$",
            r"look up\s+(.+?)$"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text.lower())
            if match:
                return match.group(1).strip().title()
        
        # If no pattern matches, assume the whole message is the company name
        # if it's not too long and doesn't contain obvious non-company words
        words = text.split()
        non_company_words = ['please', 'can', 'you', 'research', 'analyze', 'tell', 'me', 'about', 'i', 'want', 'to']
        
        if len(words) <= 4 and not any(word.lower() in non_company_words for word in words):
            return text.title()
            
        return None

    def _extract_email(self, text: str) -> Optional[str]:
        """Extract email address from user input"""
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        matches = re.findall(email_pattern, text)
        return matches[0] if matches else None

    def _parse_text_analysis(self, text: str) -> Dict[str, str]:
        """Fallback if LLM doesn't return valid JSON"""
        default_fallbacks = {
            "what_they_sell": "Unable to determine products/services",
            "who_they_target": "Unable to determine target audience",
            "condensed_summary": "Company analysis completed."
        }

        try:
            # Try to find JSON-like blocks
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                possible_json = json_match.group(0)
                return json.loads(possible_json)

        except Exception:
            pass  # fallback to regex parsing

        # Loose parsing
        sections = {
            "what_they_sell": re.search(r"(what they sell|products|services)[^\n]*[:\-–]?\s*(.*?)(?=\n|$)", text, re.IGNORECASE),
            "who_they_target": re.search(r"(who they target|audience|customers)[^\n]*[:\-–]?\s*(.*?)(?=\n|$)", text, re.IGNORECASE),
            "condensed_summary": re.search(r"(summary|condensed)[^\n]*[:\-–]?\s*(.*?)(?=\n|$)", text, re.IGNORECASE)
        }

        result = {}
        for key, match in sections.items():
            result[key] = match.group(2).strip() if match else default_fallbacks[key]

        return result
