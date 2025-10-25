import os
import sys
from pathlib import Path
from typing import List
from openai import OpenAI
import numpy as np
import pandas as pd
import streamlit as st

backend_path = os.path.join(os.path.dirname(__file__), "..", "backend")
sys.path.insert(0, backend_path)
from yfinance_crypto import CryptoDataFetcher

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.backend import (
    collect_wallet_activity,
    fetch_contract_logs,
    fetch_event_logs,
    fetch_swap_events,
    fetch_transaction_by_hash,
    top_token_senders,
)

ERC20_TRANSFER_TOPIC = (
    "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
)

st.set_page_config(
    page_title="Sniffer",
    page_icon="🐕",
    layout="wide",
)

st.title("Sniffer 🐕")
st.caption("🔎 Sniff out suspicious activity by the power of HyperSync")


# Crypto metrics
col1, col2, col3 = st.columns(3)


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


@st.cache_data
def generate_scatter_data(button_pressed: bool, random_seed: int):
    """Generate scatter data - cached but refreshes when button is pressed"""
    np.random.seed(random_seed)  # Use seed for reproducibility
    return pd.DataFrame(
        {
            "X": np.random.normal(0, 1, 100),
            "Y": np.random.normal(0, 1, 100),
            "Size": np.random.randint(10, 100, 100),
        }
    )


show_crypto_data()

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

if "openai_model" not in st.session_state:
    st.session_state["openai_model"] = "gpt-3.5-turbo"

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

col1, col2 = st.columns([0.7, 0.3])
with col1:
    st.subheader("Fraud in the Market")
    detect_button = st.button("Sniff Fraud 🔎")
    if detect_button:
        # Generate new data when button is pressed
        scatter_data = generate_scatter_data(
            button_pressed=True, random_seed=np.random.randint(0, 10000)
        )
        st.scatter_chart(scatter_data)
    else:
        scatter_data = generate_scatter_data(button_pressed=False, random_seed=42)
        st.scatter_chart(scatter_data)


with col2:
    if prompt := st.chat_input("How can I help you today?"):
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

# Show env status for the HyperSync token
_token = st.secrets["HYPERSYNC_API_TOKEN"] or st.secrets["hypersync_api_token"]
if not _token:
    st.warning(
        "No HyperSync API token found. Set HYPERSYNC_API_TOKEN or hypersync_api_token before fetching."
    )


def _split_addresses(value: str) -> List[str]:
    parts = [segment.strip() for segment in value.replace("\n", ",").split(",")]
    return [part for part in parts if part]


def _emit_summary(label: str, value) -> None:
    st.markdown(f"**{label}:**")
    st.write(value)


def _emit_counts(name: str, payload) -> None:
    st.info(
        {
            "records": len(payload) if payload is not None else 0,
        }
    )


HYPERSYNC_URL = 'http://eth.hypersync.xyz/'
TOKEN = st.secrets["HYPERSYNC_API_TOKEN"] or st.secrets["hypersync_api_token"]

with st.sidebar:
    st.header("Connection")
    st.write("API URL:")
    st.code(HYPERSYNC_URL or "<default>")
    st.write("Bearer token present:" if TOKEN else "Bearer token missing")
    if not TOKEN:
        st.warning(
            "Set HYPERSYNC_API_TOKEN (or hypersync_api_token) for authenticated endpoints."
        )

st.header("Available Tools")

(
    tab_wallet,
    tab_contract_logs,
    tab_event_logs,
    tab_swap,
    tab_tx,
    tab_top,
) = st.tabs(
    [
        "Wallet Activity",
        "Contract Logs",
        "Event Logs",
        "Swap Events",
        "Tx Lookup",
        "Top Token Senders",
    ]
)

with tab_wallet:
    st.subheader("Collect wallet activity")
    wallet_addresses = st.text_area(
        "Wallet addresses",
        placeholder="Enter addresses separated by commas or new lines",
        height=120,
    )
    wallet_from_block = st.number_input("Start block", min_value=0, value=0, step=1)
    wallet_topic = st.text_input(
        "Transfer event topic0",
        value=ERC20_TRANSFER_TOPIC,
        help="Defaults to the ERC20 Transfer event signature.",
    )

    if st.button("Run wallet query", key="wallet_query"):
        addresses = _split_addresses(wallet_addresses)
        if not addresses:
            st.warning("Provide at least one wallet address.")
        else:
            with st.spinner("Querying HyperSync..."):
                try:
                    result = collect_wallet_activity(
                        addresses,
                        from_block=int(wallet_from_block),
                        transfer_topic=wallet_topic or ERC20_TRANSFER_TOPIC,
                    )
                except Exception as exc:  # pragma: no cover - UI feedback
                    st.exception(exc)
                else:
                    st.success(
                        f"Next block {result['next_block']} (archive height {result['archive_height']})"
                    )
                    st.json(
                        {
                            "addresses": addresses,
                            "erc20_volume": result["erc20_volume"],
                            "wei_volume": result["wei_volume"],
                            "logs_returned": len(result["logs"]),
                            "transactions_returned": len(result["transactions"]),
                            "blocks_returned": len(result["blocks"]),
                        }
                    )

with tab_contract_logs:
    st.subheader("Fetch contract logs")
    contract_address = st.text_input("Contract address", placeholder="0x...")
    contract_start = st.number_input(
        "Start block", min_value=0, value=17_000_000, step=1, key="cl_start"
    )
    contract_end = st.number_input(
        "End block", min_value=0, value=17_000_050, step=1, key="cl_end"
    )

    if st.button("Fetch logs", key="contract_logs"):
        if not contract_address:
            st.warning("Enter the contract address.")
        else:
            with st.spinner("Fetching logs..."):
                try:
                    result = fetch_contract_logs(
                        contract_address.strip(),
                        start_block=int(contract_start),
                        end_block=int(contract_end),
                    )
                except Exception as exc:
                    st.exception(exc)
                else:
                    st.success(
                        f"Returned {len(result['logs'])} log record(s). Next block {result['next_block']}."
                    )
                    _emit_summary("Logs", result["logs"])

with tab_event_logs:
    st.subheader("Fetch event logs")
    event_contract = st.text_input(
        "Contract address", placeholder="0x...", key="event_contract"
    )
    event_topic = st.text_input(
        "Topic0 hash",
        value=ERC20_TRANSFER_TOPIC,
        help="Topic0 for the event signature (default is ERC20 Transfer).",
    )
    event_start = st.number_input(
        "Start block", min_value=0, value=17_000_000, step=1, key="event_start"
    )
    event_end = st.number_input(
        "End block", min_value=0, value=17_000_050, step=1, key="event_end"
    )

    if st.button("Fetch event logs", key="event_logs"):
        if not event_contract:
            st.warning("Enter the contract address.")
        else:
            with st.spinner("Fetching event logs..."):
                try:
                    result = fetch_event_logs(
                        event_contract.strip(),
                        topic0=event_topic or ERC20_TRANSFER_TOPIC,
                        start_block=int(event_start),
                        end_block=int(event_end),
                    )
                except Exception as exc:
                    st.exception(exc)
                else:
                    st.success(
                        f"Returned {len(result['logs'])} event log(s). Next block {result['next_block']}."
                    )
                    _emit_summary("Logs", result["logs"])
                    if result.get("decoded_logs"):
                        _emit_summary("Decoded logs", result["decoded_logs"])

with tab_swap:
    st.subheader("Fetch swap events")
    pool_address = st.text_input(
        "Pool contract address", placeholder="0x...", key="swap_pool"
    )
    swap_topic = st.text_input(
        "Swap event topic0",
        placeholder="0xd78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822",
    )
    swap_start = st.number_input(
        "Start block", min_value=0, value=0, step=1, key="swap_start"
    )
    swap_end = st.number_input(
        "End block", min_value=0, value=20_000_000, step=1, key="swap_end"
    )

    if st.button("Fetch swap events", key="swap_events"):
        if not pool_address or not swap_topic:
            st.warning("Provide both pool address and topic0.")
        else:
            with st.spinner("Fetching swap logs..."):
                try:
                    result = fetch_swap_events(
                        pool_address.strip(),
                        topic0=swap_topic,
                        start_block=int(swap_start),
                        end_block=int(swap_end),
                    )
                except Exception as exc:
                    st.exception(exc)
                else:
                    st.success(
                        f"Returned {len(result['logs'])} swap log(s). Next block {result['next_block']}."
                    )
                    _emit_summary("Logs", result["logs"])

with tab_tx:
    st.subheader("Lookup transaction by hash")
    tx_hash_value = st.text_input("Transaction hash", placeholder="0x...")
    tx_from_block = st.number_input(
        "Start block", min_value=0, value=0, step=1, key="tx_from_block"
    )

    if st.button("Fetch transaction", key="tx_lookup"):
        if not tx_hash_value:
            st.warning("Enter the transaction hash.")
        else:
            with st.spinner("Fetching transaction..."):
                try:
                    result = fetch_transaction_by_hash(
                        tx_hash_value.strip(),
                        from_block=int(tx_from_block),
                    )
                except Exception as exc:
                    st.exception(exc)
                else:
                    count = len(result["transactions"])
                    st.success(
                        f"Returned {count} transaction record(s). Next block {result['next_block']}."
                    )
                    _emit_summary("Transactions", result["transactions"])

with tab_top:
    st.subheader("Top token senders")
    top_contract = st.text_input("Token contract", placeholder="0x...")
    top_window = st.number_input(
        "Blocks to look back", min_value=1, value=int(1e4), step=1, key="top_window"
    )
    top_topic = st.text_input(
        "Transfer event topic0",
        value=ERC20_TRANSFER_TOPIC,
        key="top_topic",
    )
    top_n = st.number_input("Top N", min_value=1, value=10, step=1, key="top_n")

    if st.button("Rank senders", key="top_senders"):
        if not top_contract:
            st.warning("Enter the token contract address.")
        else:
            with st.spinner("Ranking senders..."):
                try:
                    result = top_token_senders(
                        top_contract.strip(),
                        window_blocks=int(top_window),
                        topic0=top_topic or ERC20_TRANSFER_TOPIC,
                        top_n=int(top_n),
                    )
                except Exception as exc:
                    st.exception(exc)
                else:
                    st.success(
                        f"Calculated top {len(result['leaders'])} sender(s). Next block {result['next_block']}."
                    )
                    st.dataframe(result["leaders"])
