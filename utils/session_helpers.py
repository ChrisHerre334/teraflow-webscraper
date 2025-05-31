import streamlit as st
from typing import Dict, Any, List, Optional

def init_session():
    """Initialize all session state variables."""
    
    # Chat history
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = [
            {
                "role": "assistant", 
                "content": "👋 Hello! I'm your AI research assistant. Tell me which company you'd like me to research and your email address, and I'll provide you with a comprehensive analysis.\n\nFor example: *'Research Stripe, send results to john@company.com'*"
            }
        ]
    
    # Research session data
    session_defaults = {
        "company_name": None,
        "user_email": None,
        "confirmed_url": None,
        "candidate_urls": [],
        "scraped_content": None,
        "what_they_sell": None,
        "who_they_sell_to": None,
        "airtable_record_id": None,
        "agent_state": "initial",
        "current_status": None
    }
    
    for key, default_value in session_defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

def update_chat(role: str, message: str, urls: Optional[List[str]] = None):
    """Add a message to the chat history."""
    chat_entry = {"role": role, "content": message}
    if urls:
        chat_entry["urls"] = urls
    st.session_state.chat_history.append(chat_entry)

def update_session_state(key: str, value: Any):
    """Update a specific session state variable."""
    st.session_state[key] = value

def get_session_state() -> Dict[str, Any]:
    """Get all session state data as a dictionary."""
    session_keys = [
        "company_name", "user_email", "confirmed_url", "candidate_urls",
        "scraped_content", "what_they_sell", "who_they_sell_to",
        "airtable_record_id", "agent_state", "current_status"
    ]
    
    return {key: st.session_state.get(key) for key in session_keys}

def reset_session():
    """Reset the session for a new research."""
    # Keep chat history but reset research data
    st.session_state.chat_history = [
        {
            "role": "assistant", 
            "content": "👋 Hello! I'm your AI research assistant. Tell me which company you'd like me to research and your email address, and I'll provide you with a comprehensive analysis.\n\nFor example: *'Research Stripe, send results to john@company.com'*"
        }
    ]
    
    # Reset all research-related session variables
    reset_keys = [
        "company_name", "user_email", "confirmed_url", "candidate_urls",
        "scraped_content", "what_they_sell", "who_they_sell_to",
        "airtable_record_id", "current_status"
    ]
    
    for key in reset_keys:
        st.session_state[key] = None if key != "candidate_urls" else []
    
    st.session_state.agent_state = "initial"

def get_research_progress() -> Dict[str, bool]:
    """Get the current progress of the research workflow."""
    session_data = get_session_state()
    
    return {
        "company_identified": bool(session_data.get("company_name")),
        "email_provided": bool(session_data.get("user_email")),
        "urls_found": bool(session_data.get("candidate_urls")),
        "url_confirmed": bool(session_data.get("confirmed_url")),
        "content_scraped": bool(session_data.get("scraped_content")),
        "analysis_complete": bool(session_data.get("what_they_sell")),
        "airtable_updated": bool(session_data.get("airtable_record_id"))
    }

def is_research_complete() -> bool:
    """Check if the research workflow is complete."""
    progress = get_research_progress()
    return all(progress.values())