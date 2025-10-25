import os
import sys
import streamlit as st

backend_path = os.path.join(os.path.dirname(__file__), "..", "backend")
sys.path.insert(0, backend_path)
from yfinance_crypto import CryptoDataFetcher


# Fetch crypto data using our backend method
# @st.cache_data(ttl=60)  # Cache for 60 seconds
# Lets not cache, refreshing on rerendering is fine
def show_crypto_data():
    try:
        fetcher = CryptoDataFetcher()
        crypto_data = fetcher.get_multiple_crypto_prices(
            ["BTC", "ETH", "SOL", "SPY", "USD/GBP"]
        )
        # print(crypto_data)

        # Create columns for each crypto
        cols = st.columns(len(crypto_data))

        # Iterate through crypto data and display metrics
        for i, symbol in enumerate(crypto_data.keys()):
            with cols[i]:
                # with st.container(border=True):
                st.metric(
                    label=f"{symbol}",
                    value=crypto_data[symbol]["price"],
                    delta=crypto_data[symbol]["change_percent"],
                    chart_data=crypto_data[symbol]["chart_data"],
                    border=True,
                )

    except Exception as e:
        st.error(f"Error loading crypto data: {e}")
        print("Error loading crypto data", e)
