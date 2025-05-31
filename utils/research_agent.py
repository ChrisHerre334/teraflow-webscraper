import os
import re
import json
import requests
from typing import Dict, List, Optional, Union
import openai
from utils.session_helpers import update_session_state, get_session_state
from utils.web_scraper import WebScraper

class ResearchAgent:
    """
    True agent-powered research assistant that governs the entire conversation flow.
    Handles company research from initial query to final email delivery.
    """
    
    def __init__(self):
        self.openai_client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.web_scraper = WebScraper()
        self.airtable_manager = AirtableManager()
        self.email_sender = EmailSender()
        
        # Agent states
        self.STATES = {
            'INITIAL': 'initial',
            'AWAITING_COMPANY': 'awaiting_company',
            'AWAITING_EMAIL': 'awaiting_email',
            'SEARCHING_URLS': 'searching_urls',
            'AWAITING_URL_SELECTION': 'awaiting_url_selection',
            'SCRAPING_WEBSITE': 'scraping_website',
            'ANALYZING_CONTENT': 'analyzing_content',
            'ANSWERING_FOLLOWUP': 'answering_followup',
            'UPDATING_AIRTABLE': 'updating_airtable',
            'SENDING_EMAIL': 'sending_email',
            'COMPLETE': 'complete'
        }
    
    def process_message(self, user_message: str) -> Union[str, Dict]:
        """
        Main agent logic - interprets user intent and decides what action to take.
        This is where the agent governs the conversation flow.
        """
        session_data = get_session_state()
        current_state = session_data.get('agent_state', self.STATES['INITIAL'])
        
        try:
            # Determine user intent using LLM
            intent = self._analyze_user_intent(user_message, current_state, session_data)
            
            # Route to appropriate handler based on intent and current state
            if intent['action'] == 'provide_company_and_email':
                return self._handle_initial_request(user_message, intent)
            elif intent['action'] == 'provide_company':
                return self._handle_company_name(intent['company'])
            elif intent['action'] == 'provide_email':
                return self._handle_email_address(intent['email'])
            elif intent['action'] == 'select_url':
                return self._handle_url_selection(user_message)
            elif intent['action'] == 'ask_followup':
                return self._handle_followup_question(user_message)
            elif intent['action'] == 'start_over':
                return self._reset_session()
            else:
                return self._handle_unclear_input(user_message, current_state)
                
        except Exception as e:
            update_session_state('current_status', f"❌ Error: {str(e)}")
            return f"❌ I encountered an error: {str(e)}. Please try again."
    
    def _analyze_user_intent(self, message: str, current_state: str, session_data: Dict) -> Dict:
        """Use LLM to analyze user intent based on current conversation state."""
        
        system_prompt = f"""
You are an AI research assistant agent analyzer. Based on the user's message and current conversation state, determine their intent.

Current state: {current_state}
Session data: {json.dumps(session_data, indent=2)}

User message: "{message}"

Analyze the intent and respond with a JSON object containing:
- action: one of [provide_company_and_email, provide_company, provide_email, select_url, ask_followup, start_over, unclear]
- company: extracted company name (if any)
- email: extracted email address (if any)  
- url_selection: number or indication of URL choice (if any)
- confidence: float between 0-1

Be intelligent about extracting company names and emails from natural language.
"""

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "system", "content": system_prompt}],
                temperature=0.1
            )
            
            return json.loads(response.choices[0].message.content)
        except:
            # Fallback to simple pattern matching
            return self._fallback_intent_analysis(message, current_state)
    
    def _fallback_intent_analysis(self, message: str, current_state: str) -> Dict:
        """Simple fallback intent analysis using regex patterns."""
        intent = {'action': 'unclear', 'confidence': 0.5}
        
        # Check for email
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        email_match = re.search(email_pattern, message)
        if email_match:
            intent['email'] = email_match.group()
            intent['action'] = 'provide_email'
        
        # Check for URL selection
        if current_state == self.STATES['AWAITING_URL_SELECTION']:
            number_match = re.search(r'\b(\d+)\b', message)
            if number_match:
                intent['action'] = 'select_url'
                intent['url_selection'] = int(number_match.group(1))
        
        # Check for company name (simple heuristic)
        if not intent.get('email') and len(message.split()) <= 5:
            intent['company'] = message.strip()
            intent['action'] = 'provide_company'
        
        return intent
    
    def _handle_initial_request(self, message: str, intent: Dict) -> str:
        """Handle initial request with both company and email."""
        if intent.get('company') and intent.get('email'):
            update_session_state('company_name', intent['company'])
            update_session_state('user_email', intent['email'])
            update_session_state('agent_state', self.STATES['SEARCHING_URLS'])
            return self._search_company_urls(intent['company'])
        else:
            return "👋 Hello! To get started, please tell me:\n1. Which company you'd like me to research\n2. Your email address for the final summary\n\nFor example: 'Research Apple Inc, send results to john@example.com'"
    
    def _handle_company_name(self, company: str) -> str:
        """Handle company name extraction and ask for email."""
        update_session_state('company_name', company)
        update_session_state('agent_state', self.STATES['AWAITING_EMAIL'])
        return f"🏢 Great! I'll research **{company}**.\n\nNow, what email address should I send the research summary to?"
    
    def _handle_email_address(self, email: str) -> str:
        """Handle email address and start URL search."""
        update_session_state('user_email', email)
        update_session_state('agent_state', self.STATES['SEARCHING_URLS'])
        
        company = get_session_state().get('company_name')
        return self._search_company_urls(company)
    
    def _search_company_urls(self, company: str) -> Union[str, Dict]:
        """Search for company URLs using Serper API."""
        update_session_state('current_status', '🔍 Searching for company website...')
        
        try:
            # Call Serper API
            headers = {'X-API-KEY': os.getenv('SERPER_API_KEY')}
            payload = {'q': f'{company} official website'}
            
            response = requests.post('https://google.serper.dev/search', 
                                   headers=headers, json=payload, timeout=10)
            response.raise_for_status()
            
            results = response.json()
            urls = []
            
            # Extract top 3-5 URLs from organic results
            for result in results.get('organic', [])[:5]:
                if 'link' in result:
                    urls.append(result['link'])
            
            if not urls:
                update_session_state('current_status', '❌ No URLs found')
                return f"❌ I couldn't find any websites for {company}. Please try a different company name."
            
            # Store URLs and update state
            update_session_state('candidate_urls', urls)
            update_session_state('agent_state', self.STATES['AWAITING_URL_SELECTION'])
            update_session_state('current_status', '✅ Found candidate URLs')
            
            return {
                'message': f"🔍 I found these potential websites for **{company}**. Please select the correct one by typing its number:",
                'urls': urls
            }
            
        except Exception as e:
            update_session_state('current_status', f'❌ Search failed: {str(e)}')
            return f"❌ I encountered an error searching for {company}: {str(e)}"
    
    def _handle_url_selection(self, message: str) -> str:
        """Handle URL selection from candidate list."""
        session_data = get_session_state()
        urls = session_data.get('candidate_urls', [])
        
        # Extract number from message
        number_match = re.search(r'\b(\d+)\b', message)
        if not number_match:
            return "❓ Please provide the number of the URL you want me to use (e.g., '1', '2', etc.)"
        
        selection = int(number_match.group(1))
        
        if selection < 1 or selection > len(urls):
            return f"❌ Please choose a number between 1 and {len(urls)}."
        
        selected_url = urls[selection - 1]
        update_session_state('confirmed_url', selected_url)
        update_session_state('agent_state', self.STATES['SCRAPING_WEBSITE'])
        
        return self._scrape_website(selected_url)
    
    def _scrape_website(self, url: str) -> str:
        """Scrape the selected website using FireCrawl."""
        update_session_state('current_status', '🕷️ Scraping website content...')
        
        try:
            scraped_content = self.web_scraper.scrape_website(url)
            
            if not scraped_content:
                update_session_state('current_status', '❌ Scraping failed')
                return "❌ I couldn't scrape the website. Please try selecting a different URL."
            
            update_session_state('scraped_content', scraped_content)
            update_session_state('agent_state', self.STATES['ANALYZING_CONTENT'])
            
            return self._analyze_content(scraped_content)
            
        except Exception as e:
            update_session_state('current_status', f'❌ Scraping error: {str(e)}')
            return f"❌ Error scraping website: {str(e)}"
    
    def _analyze_content(self, content: str) -> str:
        """Analyze scraped content to extract key information."""
        update_session_state('current_status', '🧠 Analyzing website content...')
        
        try:
            company = get_session_state().get('company_name')
            
            analysis_prompt = f"""
Analyze this website content for {company} and provide detailed insights:

CONTENT:
{content[:15000]}  # Limit content to avoid token limits

Please provide a comprehensive analysis in the following format:

## What They Sell
[Detailed description of products/services, key features, unique value propositions]

## Who They Sell To  
[Detailed description of target audience, customer segments, industries served, business model]

Be thorough and specific. Extract as much relevant detail as possible.
"""

            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": analysis_prompt}],
                temperature=0.1,
                max_tokens=1500
            )
            
            analysis = response.choices[0].message.content
            
            # Parse the analysis into structured data
            what_they_sell = ""
            who_they_sell_to = ""
            
            sections = analysis.split("## ")
            for section in sections:
                if section.startswith("What They Sell"):
                    what_they_sell = section.replace("What They Sell", "").strip()
                elif section.startswith("Who They Sell To"):
                    who_they_sell_to = section.replace("Who They Sell To", "").strip()
            
            # Store analysis results
            update_session_state('what_they_sell', what_they_sell)
            update_session_state('who_they_sell_to', who_they_sell_to)
            update_session_state('agent_state', self.STATES['ANSWERING_FOLLOWUP'])
            update_session_state('current_status', '✅ Analysis complete')
            
            # Now update Airtable and send email
            self._finalize_research()
            
            return f"""
## 📊 Research Complete for {company}

{analysis}

---

✅ **Research saved to Airtable and email sent!**

Feel free to ask any follow-up questions about this company, or say "start over" to research a new company.
"""
            
        except Exception as e:
            update_session_state('current_status', f'❌ Analysis error: {str(e)}')
            return f"❌ Error analyzing content: {str(e)}"
    
    def _finalize_research(self):
        """Update Airtable and send email with results."""
        session_data = get_session_state()
        
        try:
            # Update Airtable
            record_id = self.airtable_manager.create_record(
                company_name=session_data.get('company_name'),
                what_they_sell=session_data.get('what_they_sell'),
                who_they_sell_to=session_data.get('who_they_sell_to'),
                scraped_content=session_data.get('scraped_content', '')[:50000]  # Limit size
            )
            
            if record_id:
                update_session_state('airtable_record_id', record_id)
                
                # Send email
                self.email_sender.send_research_summary(
                    email=session_data.get('user_email'),
                    company_name=session_data.get('company_name'),
                    what_they_sell=session_data.get('what_they_sell'),
                    who_they_sell_to=session_data.get('who_they_sell_to'),
                    airtable_record_id=record_id
                )
                
        except Exception as e:
            print(f"Error in finalization: {e}")
            update_session_state('current_status', f'⚠️ Research complete but error in final steps: {str(e)}')
    
    def _handle_followup_question(self, question: str) -> str:
        """Handle follow-up questions about the researched company."""
        session_data = get_session_state()
        
        if not session_data.get('scraped_content'):
            return "❓ I don't have any research data to answer questions about. Please start a new research session."
        
        try:
            # Use the scraped content to answer the question
            context = session_data.get('scraped_content', '')
            company = session_data.get('company_name', 'the company')
            
            qa_prompt = f"""
Based on the website content I've analyzed for {company}, please answer this question: {question}

Website content:
{context[:10000]}

Provide a helpful, specific answer based on the available information. If the information isn't available in the content, say so clearly.
"""

            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": qa_prompt}],
                temperature=0.1,
                max_tokens=500
            )
            
            return f"💡 **Answer about {company}:**\n\n{response.choices[0].message.content}"
            
        except Exception as e:
            return f"❌ Error answering your question: {str(e)}"
    
    def _reset_session(self) -> str:
        """Reset the session for a new research."""
        from utils.session_helpers import reset_session
        reset_session()
        return "🔄 Session reset! What company would you like me to research, and what email should I send the summary to?"
    
    def _handle_unclear_input(self, message: str, current_state: str) -> str:
        """Handle unclear or unexpected input based on current state."""
        if current_state == self.STATES['AWAITING_EMAIL']:
            return "📧 I need your email address to send you the research summary. Please provide a valid email address."
        elif current_state == self.STATES['AWAITING_URL_SELECTION']:
            return "🔢 Please select a URL by typing its number (1, 2, 3, etc.)"
        elif current_state == self.STATES['AWAITING_COMPANY']:
            return "🏢 Please tell me which company you'd like me to research."
        else:
            return "❓ I'm not sure what you mean. Could you please clarify? You can also say 'start over' to begin a new research session."