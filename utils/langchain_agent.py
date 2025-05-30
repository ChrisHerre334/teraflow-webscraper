import os
import json
import requests
from langchain.agents import initialize_agent
from langchain_openai import ChatOpenAI
from langchain.tools import tool

@tool
def search_company_sites(company: str):
    """Searches company URLs using Serper."""
    res = requests.post("https://google.serper.dev/search", headers={
        "X-API-KEY": os.getenv("SERPER_API_KEY")
    }, json={"q": company})
    urls = [r["link"] for r in res.json().get("organic", [])[:5]]
    return "\n".join(urls)

@tool
def scrape_website(url: str):
    """Scrapes 10–15 pages from the site."""
    response = requests.post("https://api.firecrawl.dev/v1/scrape", headers={
        "Authorization": f"Bearer {os.getenv('FIRECRAWL_API_KEY')}",
        "Content-Type": "application/json"
    }, json={"url": url})
    return response.json()["data"]["markdown"]

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

@tool
def send_to_n8n(json_payload: str):
    """Triggers n8n workflow for Airtable + Email."""
    url = os.getenv("N8N_WEBHOOK_URL")
    payload = json.loads(json_payload)
    res = requests.post(url, json=payload)
    return f"✅ Sent to n8n. Status: {res.status_code}"

# Agent wrapper
def run_agent_logic(user_message: str) -> str:
    tools = [search_company_sites, scrape_website, analyze_content, send_to_n8n]
    llm = ChatOpenAI(model="gpt-4", temperature=0)
    agent = initialize_agent(tools, llm, agent="zero-shot-react-description", verbose=True)

    return agent.run(user_message)
