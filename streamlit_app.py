import os
import requests
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

st.set_page_config(page_title="Website Analyzer", layout="wide")
st.title("🔍 Company Website Analyzer")

# === Functions ===

def find_company_website(company_name):
    """Use Serper.dev API to find the most likely company website from a search."""
    api_key = os.getenv("SERPER_API_KEY")
    endpoint = "https://google.serper.dev/search"
    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
    payload = {"q": company_name}

    try:
        res = requests.post(endpoint, headers=headers, json=payload)
        res.raise_for_status()
        results = res.json()
        return results["organic"][0]["link"] if results.get("organic") else None
    except Exception as e:
        st.error(f"Search failed: {e}")
        return None

from urllib.parse import urlparse

def crawl_website(url):
    """Use Firecrawl to extract website content."""
    api_key = os.getenv("FIRECRAWL_API_KEY")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    # Ensure URL has scheme
    parsed_url = urlparse(url)
    if not parsed_url.scheme:
        url = f"https://{url}"

    payload = {
        "url": url,
        "maxPagesToCrawl": 1,
        "crawlType": "single",
        "waitForContent": True
    }

    try:
        st.write("🔍 Sending payload to Firecrawl:", payload)  # DEBUG LINE
        response = requests.post("https://api.firecrawl.dev/v1/scrape", headers=headers, json=payload, timeout=30)
        st.write("📩 Firecrawl raw response:", response.text)  # DEBUG LINE

        response.raise_for_status()
        data = response.json()
        if not data.get("success"):
            raise ValueError(data.get("error", "Unknown error"))
        return data["data"]["markdown"]
    except requests.exceptions.RequestException as e:
        st.error(f"🔥 Firecrawl API error: {e}")
    except Exception as e:
        st.error(f"🔥 Firecrawl failed: {e}")
    return None

def analyze_with_openai(text):
    """Send content to OpenAI for summarization and analysis."""
    prompt = f"""
You are an analyst. Based on the website markdown content below, extract and summarize the following:
- What the company does
- Target customers
- Key products/services
- Unique value propositions
- Tone and branding style
- Any other insights

Only use the information provided. Format your response in markdown.

CONTENT:
{text[:12000]}  # truncate to avoid token limit
"""
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"OpenAI analysis failed: {e}")
        return None

# === Streamlit UI ===

company_name = st.text_input("Enter Company Name", placeholder="e.g. Tesla")
user_email = st.text_input("Enter Your Email", placeholder="you@example.com")

if st.button("Analyze Website") and company_name and user_email:
    with st.spinner("🔎 Searching for company website..."):
        website_url = find_company_website(company_name)

    if website_url:
        st.success(f"Found website: {website_url}")
        with st.spinner("📄 Crawling site content..."):
            content = crawl_website(website_url)

        if content:
            with st.spinner("🧠 Analyzing website with OpenAI..."):
                analysis = analyze_with_openai(content)

            if analysis:
                st.subheader("📝 Analysis Summary")
                st.markdown(analysis)
    else:
        st.error("❌ Could not find website for that company.")
