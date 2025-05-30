import streamlit as st

def init_session():
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = [
            {"role": "assistant", "content": "👋 Hello! What company would you like me to research, and what email should I send the summary to?"}
        ]

def update_chat(role, message):
    st.session_state.chat_history.append({"role": role, "content": message})
