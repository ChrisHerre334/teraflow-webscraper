import os
import requests
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI
import json
import re

# Load environment variables
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

st.set_page_config(page_title="AI Research Assistant", layout="wide")
st.title("🤖 Research Assistant")

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hi there! 👋 Which company would you like me to research today?"}
    ]

if "awaiting_confirmation" not in st.session_state:
    st.session_state.awaiting_confirmation = False

if "pending_website" not in st.session_state:
    st.session_state.pending_website = None

if "company_name" not in st.session_state:
    st.session_state.company_name = None

# Render chat messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# === Function Definitions ===

def find_company_website(company_name):
    try:
        res = requests.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": os.getenv("SERPER_API_KEY")},
            json={"q": company_name},
            timeout=20
        )
        res.raise_for_status()
        return res.json()["organic"][0]["link"]
    except Exception as e:
        return f"Error: {str(e)}"

def crawl_website(url):
    try:
        response = requests.post(
            "https://api.firecrawl.dev/v1/scrape",
            headers={
                "Authorization": f"Bearer {os.getenv('FIRECRAWL_API_KEY')}",
                "Content-Type": "application/json"
            },
            json={"url": url},
            timeout=45
        )
        return response.json()["data"]["markdown"]
    except Exception as e:
        return f"Error: {str(e)}"

def analyze_with_openai(text):
    prompt = f"""
You are a website analyst. Analyze the content below and return a JSON object with the following fields:
- WhatTheySell
- WhoTheyTarget
- CondensedSummary
CONTENT:
{text[:12000]}
"""
    try:
        result = client.chat.completions.create(
            model="o4-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        raw = result.choices[0].message.content.strip()
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        return json.loads(match.group(0)) if match else {"WhatTheySell": "N/A", "WhoTheyTarget": "N/A", "CondensedSummary": raw[:400]}
    except Exception as e:
        return {"WhatTheySell": "N/A", "WhoTheyTarget": "N/A", "CondensedSummary": f"Error: {e}"}

def trigger_n8n_webhook(payload):
    try:
        webhook_url = os.getenv("N8N_WEBHOOK_URL")
        response = requests.post(webhook_url, json=payload)
        response.raise_for_status()
        return True
    except Exception as e:
        return False

# === Chat Interaction ===
if user_input := st.chat_input("Type here..."):
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    if st.session_state.awaiting_confirmation:
        if user_input.lower().strip() in ["yes", "y"]:
            with st.chat_message("assistant"):
                with st.spinner("📄 Crawling website for relevant content..."):
                    scraped = crawl_website(st.session_state.pending_website)

                if scraped.startswith("Error"):
                    st.markdown(f"❌ {scraped}")
                else:
                    with st.spinner("🧠 Analyzing with OpenAI..."):
                        analysis = analyze_with_openai(scraped)

                    st.markdown("## 📝 Here's what I found:")
                    st.markdown(f"**What They Sell:**\n{analysis.get('WhatTheySell', 'N/A')}")
                    st.markdown(f"**Who They Target:**\n{analysis.get('WhoTheyTarget', 'N/A')}")
                    st.markdown(f"**Condensed Summary:**\n{analysis.get('CondensedSummary', 'N/A')}")

                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": f"Here's the summary for **{st.session_state.company_name}**:\n\n**What They Sell:** {analysis.get('WhatTheySell')}\n\n**Who They Target:** {analysis.get('WhoTheyTarget')}\n\n**Summary:** {analysis.get('CondensedSummary')}"
                    })

                    with st.spinner("📤 Sending data to Airtable and emailing Chris..."):
                        payload = {
                            "company": st.session_state.company_name,
                            "website": st.session_state.pending_website,
                            "scraped": scraped[:100000],
                            "summary": analysis.get("CondensedSummary"),
                            "what": analysis.get("WhatTheySell"),
                            "who": analysis.get("WhoTheyTarget")
                        }
                        success = trigger_n8n_webhook(payload)
                        if success:
                            st.success("✅ Sent to Airtable and email dispatched.")
                        else:
                            st.error("❌ Failed to trigger n8n workflow.")

            st.session_state.awaiting_confirmation = False
            st.session_state.pending_website = None
            st.session_state.company_name = None
        else:
            st.session_state.messages.append({"role": "assistant", "content": "Okay, please enter the correct company name you'd like me to research."})
            st.session_state.awaiting_confirmation = False
            st.session_state.pending_website = None
            st.session_state.company_name = None
    else:
        # Initial input (company name)
        st.session_state.company_name = user_input
        with st.chat_message("assistant"):
            with st.spinner("🔍 Searching for the company website..."):
                website = find_company_website(user_input)

            if website.startswith("Error"):
                st.markdown(f"❌ {website}")
            else:
                st.session_state.awaiting_confirmation = True
                st.session_state.pending_website = website
                st.markdown(f"🌐 I found this website: [{website}]({website})\n\nIs this the correct site? Please reply with 'yes' or 'no'.")
