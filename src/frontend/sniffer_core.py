import os
import time

import streamlit as st

from crypto_widgets import show_crypto_data
from mcp.chat_widget import ChatWidget


def stream_data(text):
    for letter in text:
        yield letter
        time.sleep(0.01)


st.set_page_config(
    page_title="Sniffer AI",
    page_icon="🐶",
    layout="wide",
)

st.title("Sniffer AI 🐕")
if not st.session_state.get("sniffer_core_visited", False):
    st.session_state["sniffer_core_visited"] = True
    st.write_stream(stream_data("Sniff out suspicious activity on the blockchain! 🔎"))
else:
    st.write("Sniff out suspicious activity on the blockchain! 🔎")

with st.spinner("Fetching market context..."):
    show_crypto_data()

chat_widget = ChatWidget(
    api_key=st.secrets.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY"),
)

chat_widget.render()
