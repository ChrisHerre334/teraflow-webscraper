import streamlit as st
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import our agent and utilities
from utils.research_agent import ResearchAgent
from utils.session_helpers import init_session, update_chat, get_session_state

# Configure Streamlit
st.set_page_config(
    page_title="AI Research Assistant", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for better UI
st.markdown("""
<style>
    .main-header {
        text-align: center;
        padding: 1rem 0;
        margin-bottom: 2rem;
    }
    .status-indicator {
        padding: 0.5rem 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
        font-weight: bold;
    }
    .status-loading {
        background-color: #fff3cd;
        color: #856404;
        border: 1px solid #ffeaa7;
    }
    .status-complete {
        background-color: #d1ecf1;
        color: #0c5460;
        border: 1px solid #bee5eb;
    }
    .status-error {
        background-color: #f8d7da;
        color: #721c24;
        border: 1px solid #f5c6cb;
    }
    .url-container {
        background-color: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 0.375rem;
        padding: 1rem;
        margin: 0.5rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Main title
st.markdown('<div class="main-header"><h1>🤖 AI Research Assistant</h1><p>Your intelligent company research companion</p></div>', unsafe_allow_html=True)

# Initialize session state
init_session()

# Initialize agent
if 'agent' not in st.session_state:
    st.session_state.agent = ResearchAgent()

# Display status indicator
session_data = get_session_state()
if session_data.get('current_status'):
    status_class = "status-loading"
    if "✅" in session_data['current_status']:
        status_class = "status-complete"
    elif "❌" in session_data['current_status']:
        status_class = "status-error"
    
    st.markdown(f'<div class="{status_class}">{session_data["current_status"]}</div>', unsafe_allow_html=True)

# Display chat history
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        if msg["role"] == "assistant" and "urls" in msg:
            # Special handling for URL selection
            st.markdown(msg["content"])
            if msg["urls"]:
                st.markdown('<div class="url-container">', unsafe_allow_html=True)
                st.markdown("**Please select the correct URL by copying and pasting it:**")
                for i, url in enumerate(msg["urls"], 1):
                    st.code(url, language=None)
                st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.markdown(msg["content"])

# Chat input
if user_input := st.chat_input("Talk to me..."):
    # Add user message to chat
    update_chat("user", user_input)
    
    with st.chat_message("user"):
        st.markdown(user_input)

    # Process with agent
    with st.chat_message("assistant"):
        with st.spinner("🤔 Processing your request..."):
            try:
                response = st.session_state.agent.process_message(user_input)
                
                # Handle different response types
                if isinstance(response, dict) and "urls" in response:
                    # URL selection response
                    update_chat("assistant", response["message"], urls=response["urls"])
                    st.markdown(response["message"])
                    if response["urls"]:
                        st.markdown('<div class="url-container">', unsafe_allow_html=True)
                        st.markdown("**Please select the correct URL by copying and pasting it:**")
                        for i, url in enumerate(response["urls"], 1):
                            st.code(url, language=None)
                        st.markdown('</div>', unsafe_allow_html=True)
                else:
                    # Regular text response
                    update_chat("assistant", response)
                    st.markdown(response)
                    
            except Exception as e:
                error_msg = f"❌ An error occurred: {str(e)}"
                update_chat("assistant", error_msg)
                st.error(error_msg)

# Optional: Show session state for debugging (remove in production)
if st.checkbox("Show Debug Info"):
    with st.expander("Session State"):
        st.json(get_session_state())