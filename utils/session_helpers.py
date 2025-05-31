import streamlit as st

def init_session():
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = [
            {"role": "assistant", "content": "👋 Hello! What company would you like me to research, and what email should I send the summary to?"}
        ]
    if "company_name" not in st.session_state:
        st.session_state.company_name = None
    if "user_email" not in st.session_state:
        st.session_state.user_email = None
    if "confirmed_url" not in st.session_state:
        st.session_state.confirmed_url = None
    if "candidate_urls" not in st.session_state:
        st.session_state.candidate_urls = []

def update_chat(role, message):
    st.session_state.chat_history.append({"role": role, "content": message})

def reset_session():
    st.session_state.chat_history = [
        {"role": "assistant", "content": "👋 Hello! What company would you like me to research, and what email should I send the summary to?"}
    ]
    st.session_state.company_name = None
    st.session_state.user_email = None
    st.session_state.confirmed_url = None
    st.session_state.candidate_urls = []
