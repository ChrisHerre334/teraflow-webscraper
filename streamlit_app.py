import streamlit as st

# 🔧 Monkeypatch Streamlit to prevent torch.classes crash
import streamlit.watcher.local_sources_watcher as lsw

def safe_extract_paths(module):
    try:
        return list(module.__path__)
    except Exception:
        return []

lsw.extract_paths = safe_extract_paths

# Now proceed with your imports and app logic
import os
from dotenv import load_dotenv
from utils.langchain_agent import run_agent_logic
from utils.session_helpers import init_session, update_chat

load_dotenv()

st.set_page_config(page_title="AI Research Assistant", layout="wide")
st.title("🤖 Research Assistant")

# Initialize session state variables
init_session()

# Display chat history
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Chat input
if user_input := st.chat_input("What company would you like me to research?"):
    update_chat("user", user_input)
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("💬 Thinking..."):
            try:
                response = run_agent_logic(user_input)
                update_chat("assistant", response)
                st.markdown(response)
            except Exception as e:
                error_msg = f"❌ An error occurred: {e}"
                update_chat("assistant", error_msg)
                st.error(error_msg)
