import os
import streamlit as st
from dotenv import load_dotenv
from utils.langchain_agent import run_agent_logic
from utils.session_helpers import init_session, update_chat

load_dotenv()

st.set_page_config(page_title="AI Research Assistant", layout="wide")
st.title("🤖 Research Assistant")

# Session state init
init_session()

# Display past messages
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# User input
if user_input := st.chat_input("Ask me to research a company..."):
    update_chat("user", user_input)
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("💬 Thinking..."):
            response = run_agent_logic(user_input)
            update_chat("assistant", response)
            st.markdown(response)
