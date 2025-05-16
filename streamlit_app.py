import streamlit as st
import requests
import openai
import os
from pyairtable import Table
from dotenv import load_dotenv
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

load_dotenv()

# --- API Keys & Config ---
SERPER_API_KEY = os.getenv("SERPER_API_KEY")
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
AIRTABLE_TABLE_NAME = os.getenv("AIRTABLE_TABLE_NAME")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
FROM_EMAIL = os.getenv("FROM_EMAIL")
print("FIRECRAWL_API_KEY:", FIRECRAWL_API_KEY)
print("ENV FILE PATH:", os.path.abspath(".env"))

openai.api_key = OPENAI_API_KEY

# --- Functions ---

def search_company_website(company_name):
    url = "https://google.serper.dev/search"
    headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}
    data = {"q": company_name}
    res = requests.post(url, json=data, headers=headers)
    results = res.json()
    try:
        return results["organic"][0]["link"]
    except:
        return None

def crawl_website(website):
    api_key = FIRECRAWL_API_KEY
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {"url": website}
    response = requests.post("https://api.firecrawl.dev/v1/scrape", headers=headers, json=payload)
    print("Status Code:", response.status_code)
    print("Raw Response:", response.text)
    try:
        data = response.json()
        if data.get("success"):
            return data["data"]["text"]  # Return just the text content
        else:
            print("Firecrawl error:", data.get("error", "Unknown error"))
            return ""
    except requests.exceptions.JSONDecodeError:
        print("❌ Could not decode JSON.")
        return ""

def analyze_with_openai(text):
    prompt = f"""
You are analyzing company websites.

Based on the content below, extract:
1. What the company sells (products or services).
2. Who they sell to (target customers or ICP).
3. A short summary combining both.

Content:
{text[:12000]}  # truncate to avoid token limit
"""

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )
    return response.choices[0].message.content.strip()

def parse_analysis(analysis_text):
    what_they_sell = who_they_target = condensed_summary = ""
    lines = analysis_text.split("\n")
    for line in lines:
        if line.lower().startswith("1.") or "what they sell" in line.lower():
            parts = line.split(":", 1)
            if len(parts) > 1:
                what_they_sell = parts[1].strip()
        elif line.lower().startswith("2.") or "who they sell to" in line.lower():
            parts = line.split(":", 1)
            if len(parts) > 1:
                who_they_target = parts[1].strip()
        elif line.lower().startswith("3.") or "summary" in line.lower():
            parts = line.split(":", 1)
            if len(parts) > 1:
                condensed_summary = parts[1].strip()
    if not condensed_summary:
        condensed_summary = analysis_text.strip()
    return what_they_sell, who_they_target, condensed_summary

def save_to_airtable(content, what_they_sell, who_they_target, summary):
    table = Table(AIRTABLE_API_KEY, AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME)
    record = table.create({
        "Scraped Content": content[:10000],  # Airtable limit
        "What They Sell": what_they_sell,
        "Who They Target": who_they_target,
        "Condensed Summary": summary
    })
    return record["id"]

def send_email(to_email, summary):
    message = Mail(
        from_email=FROM_EMAIL,
        to_emails=to_email,
        subject="Chris Project: Company Summary",
        plain_text_content=f"Your research is complete:\n\n{summary}"
    )
    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        sg.send(message)
        return True
    except Exception as e:
        print("Email error:", e)
        return False

# --- Streamlit UI ---

st.title("🔎 Chris Project: Company Analyzer")

company_name = st.text_input("Enter Company Name")
email = st.text_input("Enter Your Email")

if st.button("Run Research") and company_name and email:
    with st.spinner("Searching for company website..."):
        website = search_company_website(company_name)
    
    if not website:
        st.error("❌ Could not find website.")
        st.stop()

    st.success(f"🌐 Website found: {website}")

    with st.spinner("Scraping website..."):
        content = crawl_website(website)
    
    if not content:
        st.error("❌ Failed to scrape content.")
        st.stop()

    with st.spinner("Analyzing content with GPT..."):
        analysis = analyze_with_openai(content)

    what_they_sell, who_they_target, condensed_summary = parse_analysis(analysis)

    with st.spinner("Saving to Airtable..."):
        airtable_id = save_to_airtable(content, what_they_sell, who_they_target, condensed_summary)

    with st.spinner("Sending email..."):
        email_sent = send_email(email, condensed_summary)

    st.success("✅ Research complete!")
    st.write("**Summary:**", condensed_summary)
    if email_sent:
        st.info("📬 Summary sent to your email.")
