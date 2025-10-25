"""Streamlit dashboard for Sniffer's fraud analytics."""

from __future__ import annotations
import streamlit as st


import json
import os
import re
import sys
from pathlib import Path
from typing import List, Mapping

import pandas as pd
import streamlit as st
from crypto_widgets import show_crypto_data
from mcp.chat_widget import ChatWidget

st.set_page_config(
    page_title="Sniffer",
    page_icon="🐕",
    layout="wide",
)

home_page = st.Page("sniffer_home.py", title="Sniffer Home", icon="🏠")
core_page = st.Page("sniffer_core.py", title="Sniffer Core", icon="🐶")
client_page = st.Page("sniffer_client.py", title="Sniffer Client", icon="🐕‍🦺")

# Create navigation
pg = st.navigation([home_page, core_page, client_page])

# Run the selected page
pg.run()
logo_path = Path(__file__).resolve().parents[2] / "src" / "sniffer_logo.png"
if logo_path.exists():
    st.image(str(logo_path), width=160)
else:
    st.title("Sniffer 🐕")
st.caption("Sniff out suspicious activity on the blockchain 🔎")
