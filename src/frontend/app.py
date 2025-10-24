from openai import OpenAI
import streamlit as st
import sys
import os

# Add the backend directory to the path
backend_path = os.path.join(os.path.dirname(__file__), '..', 'backend')
sys.path.insert(0, backend_path)
from yfinance_crypto import CryptoDataFetcher

# Page configuration
st.set_page_config(
    page_title="HyperSync",
    page_icon="🚀",
    layout="wide",
)

st.title("HyperSync")

# Crypto metrics
col1, col2, col3 = st.columns(3)

# Fetch crypto data using our backend method
# @st.cache_data(ttl=60)  # Cache for 60 seconds
def show_crypto_data():
    try:
        fetcher = CryptoDataFetcher()
        crypto_data = fetcher.get_multiple_crypto_prices(['BTC', 'ETH', 'SOL', 'SPY', 'USD/GBP'])
        # print(crypto_data)
        
        # Create columns for each crypto
        cols = st.columns(len(crypto_data))
        
        # Iterate through crypto data and display metrics
        for i, symbol in enumerate(crypto_data.keys()):
            with cols[i]:
                # with st.container(border=True):
                st.metric(
                    label=f"{symbol}",
                    value=crypto_data[symbol]['price'],
                    delta=crypto_data[symbol]['change_percent'],
                    chart_data=crypto_data[symbol]['chart_data'],
                    border=True,
                )

    except Exception as e:
        st.error(f"Error loading crypto data: {e}")
        print("Error loading crypto data", e)

show_crypto_data()

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

if "openai_model" not in st.session_state:
    st.session_state["openai_model"] = "gpt-3.5-turbo"

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("What is up?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        stream = client.chat.completions.create(
            model=st.session_state["openai_model"],
            messages=[
                {"role": m["role"], "content": m["content"]}
                for m in st.session_state.messages
            ],
            stream=True,
        )
        response = st.write_stream(stream)
    st.session_state.messages.append({"role": "assistant", "content": response})