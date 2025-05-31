import streamlit as st
from typing import Dict, Any, Optional, List
from datetime import datetime

def init_session():
    """Initialize session state variables"""
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []
    
    if 'current_status' not in st.session_state:
        st.session_state.current_status = ""
    
    if 'session_data' not in st.session_state:
        st.session_state.session_data = {
            'company_name': None,
            'recipient_email': None,
            'selected_url': None,
            'research_completed': False,
            'current_status': ""
        }

def update_chat(role: str, content: str, urls: Optional[List[str]] = None):
    """Add a message to the chat history"""
    message = {
        "role": role,
        "content": content,
        "timestamp": str(datetime.now())
    }
    
    if urls:
        message["urls"] = urls
    
    st.session_state.chat_history.append(message)

def update_session_state(**kwargs):
    """Update session state variables"""
    for key, value in kwargs.items():
        if key in st.session_state.session_data:
            st.session_state.session_data[key] = value
        
        # Also update direct session state
        setattr(st.session_state, key, value)

def get_session_state() -> Dict[str, Any]:
    """Get current session state"""
    return st.session_state.session_data

def clear_session():
    """Clear all session state (useful for starting over)"""
    keys_to_keep = ['chat_history']  # Keep chat history
    
    for key in list(st.session_state.keys()):
        if key not in keys_to_keep:
            del st.session_state[key]
    
    init_session()

def get_chat_history() -> List[Dict[str, Any]]:
    """Get the current chat history"""
    return st.session_state.chat_history

def add_system_message(message: str):
    """Add a system message to chat"""
    update_chat("assistant", f"ℹ️ {message}")

def is_research_complete() -> bool:
    """Check if research has been completed"""
    return st.session_state.session_data.get('research_completed', False)