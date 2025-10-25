import streamlit as st

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
