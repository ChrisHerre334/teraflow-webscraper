import os
import requests
import spacy
from transformers import pipeline
from langchain.agents import initialize_agent
from langchain_openai import ChatOpenAI
from langchain.memory import ConversationBufferMemory
from langchain.tools import tool
from utils.session_helpers import reset_session

# Load spaCy and transformer pipeline once
spacy_model = spacy.load('en_core_web_sm')
token_classifier = pipeline(
    "token-classification",
    model="dslim/bert-base-NER",
    aggregation_strategy="simple"
)

# In-memory session state
session_state = {
    "company_name": None,
    "user_email": None,
    "confirmed_url": None,
    "candidate_urls": []
}

# ----------- Helper Functions -----------

def extract_company_name(text: str):
    results = token_classifier(text)
    orgs = [ent["word"] for ent in results if ent["entity_group"] == "ORG"]
    return list(set(orgs))

# ----------- LangChain Tools -----------

@tool
def search_company_sites(company: str):
    """Searches company URLs using Serper."""
    res = requests.post("https://google.serper.dev/search", headers={
        "X-API-KEY": os.getenv("SERPER_API_KEY")
    }, json={"q": company})
    
    urls = [r["link"] for r in res.json().get("organic", [])[:5]]
    session_state["candidate_urls"] = urls

    if not urls:
        return "No URLs found."
    
    numbered_urls = "\n".join([f"{i+1}. {url}" for i, url in enumerate(urls)])
    return f"Found these URLs:\n{numbered_urls}\n\nPlease reply with the number of the correct one."

@tool
def select_url(selection: str):
    """Selects a URL based on a plain text number."""
    import re
    match = re.search(r'(\d+)', selection)
    if match:
        index = int(match.group(1)) - 1
        if 0 <= index < len(session_state["candidate_urls"]):
            session_state["confirmed_url"] = session_state["candidate_urls"][index]
            return f"✅ URL confirmed: {session_state['confirmed_url']}"
        else:
            return "❌ Invalid number. Please choose from the list."
    return "❌ Couldn't understand your selection. Please enter a number."

@tool(return_direct=True)
def scrape_website(dummy_input: str):
    """Scrapes 10–15 pages from the confirmed site. Input can be anything."""
    url = session_state.get("confirmed_url")
    if not url:
        return "❌ No URL confirmed. Please choose a URL first."
    
    response = requests.post("https://api.firecrawl.dev/v1/scrape", headers={
        "Authorization": f"Bearer {os.getenv('FIRECRAWL_API_KEY')}",
        "Content-Type": "application/json"
    }, json={"url": url})
    
    try:
        return response.json()["data"]["markdown"]
    except KeyError:
        return "❌ Failed to retrieve markdown content."

@tool
def analyze_content(text: str):
    """Uses LLM to extract WhatTheySell, WhoTheyTarget, and CondensedSummary."""
    llm = ChatOpenAI(model="gpt-4", temperature=0)
    prompt = f"""
Analyze the content below. Return a JSON with:
- WhatTheySell
- WhoTheyTarget
- CondensedSummary

CONTENT:
{text[:12000]}
"""
    return llm.predict(prompt)

@tool(return_direct=True)
def send_to_n8n(input_text: str):
    """Triggers n8n workflow for Airtable + Email, then resets session."""
    if not session_state["user_email"] or not session_state["company_name"]:
        return "❌ Missing email or company name."
    
    url = os.getenv("N8N_WEBHOOK_URL")
    payload = {
        "email": session_state["user_email"],
        "company": session_state["company_name"]
    }
    res = requests.post(url, json=payload)

    # Reset session after sending
    reset_session()

    return f"✅ Sent to n8n. Status: {res.status_code}"

# ----------- Agent Runner -----------

memory = ConversationBufferMemory()

def run_agent_logic(user_message: str) -> str:
    tools = [search_company_sites, select_url, scrape_website, analyze_content, send_to_n8n]
    llm = ChatOpenAI(model="gpt-4", temperature=0)
    agent = initialize_agent(tools, llm, agent="zero-shot-react-description", verbose=True, memory=memory)

    # Capture email
    if "@" in user_message and "." in user_message:
        session_state["user_email"] = user_message.strip()
        return "📩 Thanks! Now searching for the company website..."

    # Extract company name if not yet stored
    if not session_state["company_name"]:
        orgs = extract_company_name(user_message)
        if orgs:
            session_state["company_name"] = orgs[0]
            return f"🏢 Got the company name: {orgs[0]}\n\nPlease provide your email to receive the summary."
        else:
            return "❓ I couldn't detect a company name. Could you rephrase or clarify?"

    # Let agent handle the rest
    return agent.run(user_message)
