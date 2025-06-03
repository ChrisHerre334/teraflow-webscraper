import os
import re
import json
import textwrap
import requests
import streamlit as st
from typing import Dict, List, Optional, Union
from dataclasses import dataclass, asdict
import unicodedata

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
        self.WAITING_URL_CONFIRMATION = "waiting_url_confirmation"
        self.SCRAPING_WEBSITE = "scraping_website"
        self.ANALYZING_CONTENT = "analyzing_content"
        self.READY_FOR_QUESTIONS = "ready_for_questions"
        self.COMPLETE = "complete"
        
        # Initialize session state
        st.session_state.setdefault("agent_state", self.GREETING)
        st.session_state.setdefault("company_name", None)
        st.session_state.setdefault("recipient_email", None)
        st.session_state.setdefault("candidate_urls", [])
        st.session_state.setdefault("selected_url", None)
        st.session_state.setdefault("scraped_content", "")
        st.session_state.setdefault("research_data", None)

    def process_message(self, user_input: str) -> Union[str, Dict]:
        """Main agent processing logic"""
        try:
            state = st.session_state.agent_state
            
            if state == self.GREETING:
                return self._handle_greeting(user_input)
            elif state == self.COLLECTING_INFO:
                return self._handle_info_collection(user_input)
            elif state == self.WAITING_URL_CONFIRMATION:
                return self._handle_url_confirmation(user_input)
            elif state in [self.SCRAPING_WEBSITE, self.ANALYZING_CONTENT]:
                return "⏳ Please wait, I’m still working on the current request..."
            elif state == self.READY_FOR_QUESTIONS:
                return self._handle_follow_up_questions(user_input)
            else:
                return "I'm currently processing your request. Please wait..."

        except Exception as e:
            update_session_state(current_status=f"❌ Error: {str(e)}")
            return f"I encountered an error: {str(e)}. Please try again."

    def _handle_greeting(self, user_input: str) -> str:
        update_session_state(current_status="🤖 Getting started...")
        company_name = self._extract_company_name(user_input)
        if company_name:
            st.session_state.company_name = company_name
            st.session_state.agent_state = self.COLLECTING_INFO
            return f"Great! I'll research **{company_name}** for you. What email address should I send the final results to?"
        return "Hello! I'm your AI research assistant. Which company would you like me to research today?"

    def _handle_info_collection(self, user_input: str) -> Union[str, Dict]:
        email = self._extract_email(user_input)
        if email:
            st.session_state.recipient_email = email
            update_session_state(current_status="🔍 Searching for company website...")
            urls = self._search_company_urls(st.session_state.company_name)
            if urls:
                st.session_state.candidate_urls = urls
                st.session_state.agent_state = self.WAITING_URL_CONFIRMATION
                return {
                    "message": f"Perfect! I found several potential websites for **{st.session_state.company_name}**. Please copy and paste the correct URL from the list below:",
                    "urls": urls
                }
            return f"I couldn't find any websites for {st.session_state.company_name}. Please provide the URL directly if you have it."
        return "Please provide a valid email address."

    def _handle_url_confirmation(self, user_input: str) -> str:
        # Gracefully handle malformed or empty candidate_urls
        raw_urls = st.session_state.get("candidate_urls", [])

        # Flatten if it's a list of lists
        candidate_urls = []
        for item in raw_urls:
            if isinstance(item, str):
                candidate_urls.append(item)
            elif isinstance(item, list):
                candidate_urls.extend([url for url in item if isinstance(url, str)])

        if not candidate_urls:
            return "Hmm, I don't seem to have any URLs to match yet. Try asking me to look up a company again."

        # Try to match a URL from user input
        selected_url = next((url for url in candidate_urls if url.lower() in user_input.lower()), None)

        # Fallback to regex
        if not selected_url:
            matches = re.findall(r'https?://[^\s]+', user_input)
            selected_url = matches[0] if matches else None

        if selected_url:
            st.session_state.selected_url = selected_url
            st.session_state.agent_state = self.SCRAPING_WEBSITE
            return self._start_scraping_and_analysis()

        return "Please paste one of the URLs I provided, or enter a valid website."


    def _start_scraping_and_analysis(self) -> str:
        try:
            update_session_state(current_status="🕷️ Scraping website content...")
            content = self.web_scraper.scrape_website(st.session_state.selected_url, max_pages=15)

            if not content or len(content.strip()) < 500:
                return "The scraped content was too short or empty. Try a different URL."

            st.session_state.scraped_content = content
            st.session_state.agent_state = self.ANALYZING_CONTENT
            update_session_state(current_status="🧠 Analyzing company information...")

            analysis = self._analyze_company_content(content)
            if analysis:
                research_data = CompanyResearch(
                    company_name=st.session_state.company_name,
                    scraped_content=content,
                    what_they_sell=analysis["what_they_sell"],
                    who_they_target=analysis["who_they_target"],
                    condensed_summary=analysis["condensed_summary"],
                    recipient_email=st.session_state.recipient_email
                )
                st.session_state.research_data = research_data

                update_session_state(current_status="📤 Sending results...")
                self._send_to_n8n_webhook(research_data)

                st.session_state.agent_state = self.READY_FOR_QUESTIONS
                update_session_state(current_status="✅ Research complete! Ask me any follow-up questions.")

                return f"""
## Research Complete! ✅

Here's what I found about **{research_data.company_name}**:

### What They Sell
{research_data.what_they_sell}

### Who They Target
{research_data.who_they_target}

---

I've saved this to Airtable and emailed **{research_data.recipient_email}**.
\n\nPlease feel free to ask me any further questions.
"""
            return "I had trouble analyzing the content. Try a different site or rephrase your query."
        except Exception as e:
            update_session_state(current_status=f"❌ Error during analysis: {e}")
            return f"An error occurred: {e}"

    def _analyze_company_content(self, content: str) -> Optional[Dict[str, str]]:
        prompt = textwrap.dedent(f"""
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
        """)

        response = self.llm_client.generate_response(prompt)

        try:
            json_str = re.search(r"\{.*\}", response, re.DOTALL).group(0)
            return json.loads(json_str)
        except Exception:
            print(f"[LLM JSON Parse Error] Raw output:\n{response}")
            return self._parse_text_analysis(response)

    def _handle_follow_up_questions(self, user_input: str) -> str:
        try:
            research = st.session_state.research_data
            context = st.session_state.scraped_content[:3000]
            prompt = f"""
Based on the research I conducted about {research.company_name}, please answer this question:

Q: {user_input}

Context:
{context}

Previous analysis:
- What they sell: {research.what_they_sell}
- Who they target: {research.who_they_target}

Answer:
"""
            return self.llm_client.generate_response(prompt)
        except Exception as e:
            return f"Follow-up question failed: {e}"

    def _search_company_urls(self, company_name: str) -> List[str]:
        try:
            results = self.search_api.search(f"{company_name} official website")
            return [r["url"] for r in results if "url" in r][:5]
        except Exception as e:
            print(f"Search error: {e}")
            return []

    def _send_to_n8n_webhook(self, research_data: CompanyResearch) -> bool:
        """Send research data to n8n webhook, safely truncating and sanitizing long content fields"""
        try:
            payload = asdict(research_data)

            # Truncate and clean ScrapedContent to avoid Airtable API rejection
            max_length = 10000
            scraped = payload["scraped_content"][:max_length]
            cleaned = unicodedata.normalize("NFKD", scraped).encode("ascii", "ignore").decode("ascii")
            payload["clean_scraped_content"] = cleaned  # Ensure proper Airtable field casing
            del payload["scraped_content"]  # Remove original key

            # Log info for debugging
            print("Sending to webhook:")
            print("clean_scraped_content type:", type(payload["clean_scraped_content"]))
            print("clean_scraped_content preview:", payload["clean_scraped_content"][:300])

            return self.n8n_webhook.send_data(payload)

        except Exception as e:
            print(f"Webhook error: {e}")
            return False

    def _extract_company_name(self, text: str) -> Optional[str]:
        text = text.strip()
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
        words = text.split()
        if len(words) <= 4 and not any(words.lower() in ['please', 'can', 'you', 'research', 'analyze', 'tell', 'me', 'about', 'i', 'want', 'to']):
            return text.title()
        return None

    def _extract_email(self, text: str) -> Optional[str]:
        matches = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
        return matches[0] if matches else None

    def _parse_text_analysis(self, text: str) -> Dict[str, str]:
        fallback = {
            "what_they_sell": "Unable to determine products/services",
            "who_they_target": "Unable to determine target audience",
            "condensed_summary": "Company analysis completed."
        }
        try:
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
        except Exception:
            pass
        result = {}
        sections = {
            "what_they_sell": r"(what they sell|products|services)[^\n]*[:\-–]?\s*(.*?)(?=\n|$)",
            "who_they_target": r"(who they target|audience|customers)[^\n]*[:\-–]?\s*(.*?)(?=\n|$)",
            "condensed_summary": r"(summary|condensed)[^\n]*[:\-–]?\s*(.*?)(?=\n|$)"
        }
        for key, pattern in sections.items():
            match = re.search(pattern, text, re.IGNORECASE)
            result[key] = match.group(2).strip() if match else fallback[key]
        return result
