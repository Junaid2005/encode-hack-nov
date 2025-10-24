import os
import json
import streamlit as st
import sys
from pathlib import Path
from openai import OpenAI


# Ensure project root is on sys.path so `from src.backend ...` works under Streamlit
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
import pandas as pd
import numpy as np

# Add the backend directory to the path
backend_path = os.path.join(os.path.dirname(__file__), "..", "backend")
sys.path.insert(0, backend_path)
from yfinance_crypto import CryptoDataFetcher

# Import backend SDK (pure Python, no web server needed)
from src.backend import (
    fetch_data as sdk_fetch,
    process_data as sdk_process,
    analyze_data as sdk_analyze,
    query_and_analyze as sdk_query_and_analyze,
    fetch_transactions as sdk_fetch_transactions,
    fetch_addresses as sdk_fetch_addresses,
    fetch_blocks as sdk_fetch_blocks,
    fetch_logs as sdk_fetch_logs,
    fetch_token_transfers as sdk_fetch_token_transfers,
    fetch_traces as sdk_fetch_traces,
    fetch_internal_transactions as sdk_fetch_internal_transactions,
    fetch_receipts as sdk_fetch_receipts,
    fetch_deployments as sdk_fetch_deployments,
)

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
    detect_button = st.button("Detect Fraud")
    if detect_button:
        if np.random.random() < 0.5:
            st.success("Fraud detected!", icon="🚨")
            st.balloons()
        else:
            st.error("No fraud detected.")
            st.snow()
        scatter_data = pd.DataFrame(
            {
                "X": np.random.normal(0, 1, 100),
                "Y": np.random.normal(0, 1, 100),
                "Size": np.random.randint(10, 100, 100),
            }
        )

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

# Helper to handle Pydantic v1/v2 model serialization


def to_dict(obj):
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    return obj


# Example query template from prompt.txt
DEFAULT_QUERY = {
    "from_block": 0,
    "to_block": 1300000,
    "inputs": [
        {
            "asset_id": [
                "0x2a0d0ed9d2217ec7f32dcd9a1902ce2a66d68437aeff84e3a3cc8bebee0d2eea"
            ]
        }
    ],
    "field_selection": {
        "input": [
            "block_height",
            "tx_id",
            "input.asset_id",
            "input.amount",
            "input.address",
        ]
    },
}

# Small-range example defaults (safe, may return zero results depending on network)
EX_SAMPLE = {
    "address": "0x0000000000000000000000000000000000000000",
    "contract": None,
    "tx_hash": "0x",
    "start_block": 0,
    "end_block": 100,
}

# Persistent state for last fetched data
if "last_data" not in st.session_state:
    st.session_state.last_data = []

st.subheader("1) Build HyperSync Query")
query_text = st.text_area(
    "Query JSON",
    value=json.dumps(DEFAULT_QUERY, indent=2),
    height=260,
)

col1, col2 = st.columns(2)

with col1:
    if st.button("Fetch data via HyperSync", type="primary"):
        try:
            query = json.loads(query_text)
        except json.JSONDecodeError as e:
            st.error(f"Invalid JSON for query: {e}")
        else:
            with st.spinner("Fetching data..."):
                try:
                    data = sdk_fetch(query)
                except Exception as e:  # surface DAL exceptions like HyperSyncError
                    st.exception(e)
                else:
                    st.session_state.last_data = data
                    st.success(f"Fetched {len(data)} record(s)")
                    st.caption("First 10 records:")
                    st.json(data[:10])

with col2:
    if st.button("Fetch + Process + Analyze"):
        try:
            query = json.loads(query_text)
        except json.JSONDecodeError as e:
            st.error(f"Invalid JSON for query: {e}")
        else:
            with st.spinner("Querying, processing, and analyzing..."):
                try:
                    combined = sdk_query_and_analyze(query)
                except Exception as e:
                    st.exception(e)
                else:
                    st.success("Completed query + analysis")
                    st.json(to_dict(combined))

st.divider()

st.subheader("2) Work with Last Fetched Data")
col3, col4 = st.columns(2)

with col3:
    if st.button("Process last data"):
        if not st.session_state.last_data:
            st.warning("No data found. Use 'Fetch' first.")
        else:
            with st.spinner("Processing..."):
                try:
                    processed = sdk_process(st.session_state.last_data)
                except Exception as e:
                    st.exception(e)
                else:
                    st.success("Processed aggregates computed")
                    st.json(to_dict(processed))

with col4:
    if st.button("Analyze last data"):
        if not st.session_state.last_data:
            st.warning("No data found. Use 'Fetch' first.")
        else:
            with st.spinner("Analyzing..."):
                try:
                    analysis = sdk_analyze(st.session_state.last_data)
                except Exception as e:
                    st.exception(e)
                else:
                    st.success("Analysis complete")
                    st.json(to_dict(analysis))

st.divider()

st.subheader("3) Explorer")

explorer_tabs = st.tabs(
    [
        "Transactions",
        "Addresses",
        "Blocks",
        "Logs",
        "Traces",
        "Internal Tx",
        "Receipts",
        "Deployments",
        "Token Transfers",
    ]
)

# Transactions
with explorer_tabs[0]:
    st.markdown("#### Fetch Transactions by Address")
    tx_addr = st.text_input("Address (from/to)", placeholder="0x...", key="tx_addr")
    tx_from_block = st.number_input(
        "Start Block",
        min_value=0,
        value=EX_SAMPLE["start_block"],
        step=1,
        key="tx_from_block",
    )
    tx_to_block = st.number_input(
        "End Block",
        min_value=0,
        value=EX_SAMPLE["end_block"],
        step=1,
        key="tx_to_block",
    )
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Fetch Transactions"):
            if not tx_addr:
                st.warning("Enter an address")
            else:
                with st.spinner("Fetching transactions..."):
                    try:
                        txs = sdk_fetch_transactions(
                            tx_addr, tx_from_block, tx_to_block
                        )
                    except Exception as e:
                        st.exception(e)
                    else:
                        st.success(f"Fetched {len(txs)} transaction(s)")
                        st.json(txs[:20])
    with col_b:
        with st.expander("Example"):
            example = {
                "address": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",  # Uniswap V2 Router
                "from_block": 17000000,
                "to_block": 17001000,
            }
            st.json(example)
            if st.button("Prefill Fields (Transactions)", key="prefill_tx"):
                st.session_state["tx_addr"] = example["address"]
                st.session_state["tx_from_block"] = example["from_block"]
                st.session_state["tx_to_block"] = example["to_block"]
            if st.button("Run Example (Transactions)", key="ex_tx"):
                with st.spinner("Running example..."):
                    try:
                        txs = sdk_fetch_transactions(
                            example["address"],
                            example["from_block"],
                            example["to_block"],
                        )
                    except Exception as e:
                        st.exception(e)
                    else:
                        st.success(f"Fetched {len(txs)} transaction(s)")
                        st.json(txs[:20])

# Addresses by Tx Hash
with explorer_tabs[1]:
    st.markdown("#### Fetch Addresses by Transaction Hash")
    tx_hash = st.text_input("Transaction hash", placeholder="0x...", key="addr_tx_hash")
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Fetch Addresses"):
            if not tx_hash:
                st.warning("Enter a transaction hash")
            else:
                with st.spinner("Fetching addresses..."):
                    try:
                        addrs = sdk_fetch_addresses(tx_hash)
                    except Exception as e:
                        st.exception(e)
                    else:
                        st.success(f"Fetched {len(addrs)} record(s)")
                        st.json(addrs[:20])
    with col_b:
        with st.expander("Example"):
            example = {
                "tx_hash": "0xc5eee3ae9cf10fbee05325e3a25c3b19489783612e36cb55b054c2cb4f82fc28"
            }
            st.json(example)
            if st.button("Prefill Fields (Addresses)", key="prefill_addr"):
                st.session_state["addr_tx_hash"] = example["tx_hash"]
            if st.button("Run Example (Addresses)", key="ex_addr"):
                with st.spinner("Running example (may return none)..."):
                    try:
                        addrs = sdk_fetch_addresses(example["tx_hash"])
                    except Exception as e:
                        st.exception(e)
                    else:
                        st.success(f"Fetched {len(addrs)} record(s)")
                        st.json(addrs[:20])

# Blocks
with explorer_tabs[2]:
    st.markdown("#### Fetch Block by Number")
    blk_num = st.number_input(
        "Block number", min_value=0, value=0, step=1, key="blk_num"
    )
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Fetch Block"):
            with st.spinner("Fetching block..."):
                try:
                    blk = sdk_fetch_blocks(blk_num)
                except Exception as e:
                    st.exception(e)
                else:
                    st.success(f"Fetched {len(blk)} record(s)")
                    st.json(blk[:5])
    with col_b:
        with st.expander("Example"):
            example = {"block_number": 17000000}
            st.json(example)
            if st.button("Prefill Fields (Block)", key="prefill_block"):
                st.session_state["blk_num"] = example["block_number"]
            if st.button("Run Example (Block)", key="ex_block"):
                with st.spinner("Running example..."):
                    try:
                        blk = sdk_fetch_blocks(example["block_number"])
                    except Exception as e:
                        st.exception(e)
                    else:
                        st.success(f"Fetched {len(blk)} record(s)")
                        st.json(blk[:5])

# Logs / Events
with explorer_tabs[3]:
    st.markdown("#### Fetch Logs for Contract")
    lg_addr = st.text_input("Contract address", placeholder="0x...", key="lg_addr")
    lg_from = st.number_input(
        "From block", min_value=0, value=EX_SAMPLE["start_block"], step=1, key="lg_from"
    )
    lg_to = st.number_input(
        "To block", min_value=0, value=EX_SAMPLE["end_block"], step=1, key="lg_to"
    )
    lg_topic0 = st.text_input(
        "Topic0 (event signature hash, optional)", placeholder="0x...", key="lg_topic0"
    )
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Fetch Logs"):
            if not lg_addr:
                st.warning("Enter a contract address")
            else:
                with st.spinner("Fetching logs..."):
                    try:
                        logs = sdk_fetch_logs(
                            lg_addr, lg_from, lg_to, lg_topic0 or None
                        )
                    except Exception as e:
                        st.exception(e)
                    else:
                        st.success(f"Fetched {len(logs)} log record(s)")
                        st.json(logs[:20])
    with col_b:
        with st.expander("Example"):
            example = {
                "contract_address": "0xA0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",  # USDC
                "from_block": 17000000,
                "to_block": 17000100,
                "topic0": "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",  # Transfer
            }
            st.json(example)
            if st.button("Prefill Fields (Logs)", key="prefill_logs"):
                st.session_state["lg_addr"] = example["contract_address"]
                st.session_state["lg_from"] = example["from_block"]
                st.session_state["lg_to"] = example["to_block"]
                st.session_state["lg_topic0"] = example["topic0"]
            if st.button("Run Example (Logs)", key="ex_logs"):
                with st.spinner(
                    "Running example (may be empty/large if no contract)..."
                ):
                    try:
                        logs = sdk_fetch_logs(
                            example["contract_address"],
                            example["from_block"],
                            example["to_block"],
                            example["topic0"],
                        )
                    except Exception as e:
                        st.exception(e)
                    else:
                        st.success(f"Fetched {len(logs)} log record(s)")
                        st.json(logs[:20])

# Traces
with explorer_tabs[4]:
    st.markdown("#### Fetch Traces")
    tr_from = st.text_input("From address (optional)", key="tr_from")
    tr_to = st.text_input("To address (optional)", key="tr_to")
    tr_call_types_csv = st.text_input(
        "Call types (comma-separated, optional)",
        placeholder="call,delegatecall,create",
        key="tr_ct",
    )
    tr_start = st.number_input(
        "Start block",
        min_value=0,
        value=EX_SAMPLE["start_block"],
        step=1,
        key="tr_start",
    )
    tr_end = st.number_input(
        "End block", min_value=0, value=EX_SAMPLE["end_block"], step=1, key="tr_end"
    )
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Fetch Traces", key="btn_traces"):
            call_types = (
                [s.strip() for s in tr_call_types_csv.split(",") if s.strip()]
                if tr_call_types_csv
                else None
            )
            with st.spinner("Fetching traces..."):
                try:
                    traces = sdk_fetch_traces(
                        from_addr=tr_from or None,
                        to_addr=tr_to or None,
                        call_types=call_types,
                        start_block=tr_start,
                        end_block=tr_end,
                    )
                except Exception as e:
                    st.exception(e)
                else:
                    st.success(f"Fetched {len(traces)} trace record(s)")
                    st.json(traces[:20])
    with col_b:
        with st.expander("Example"):
            example = {
                "from_addr": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",  # Uniswap V2 Router
                "to_addr": "0xA0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",  # USDC
                "call_types": ["call", "delegatecall"],
                "from_block": 17000000,
                "to_block": 17000100,
            }
            st.json(example)
            if st.button("Prefill Fields (Traces)", key="prefill_traces"):
                st.session_state["tr_from"] = example["from_addr"]
                st.session_state["tr_to"] = example["to_addr"]
                st.session_state["tr_ct"] = ",".join(example["call_types"])
                st.session_state["tr_start"] = example["from_block"]
                st.session_state["tr_end"] = example["to_block"]
            if st.button("Run Example (Traces)", key="ex_traces"):
                with st.spinner("Running example..."):
                    try:
                        traces = sdk_fetch_traces(
                            from_addr=example["from_addr"],
                            to_addr=example["to_addr"],
                            call_types=example["call_types"],
                            start_block=example["from_block"],
                            end_block=example["to_block"],
                        )
                    except Exception as e:
                        st.exception(e)
                    else:
                        st.success(f"Fetched {len(traces)} trace record(s)")
                        st.json(traces[:20])

# Internal Transactions
with explorer_tabs[5]:
    st.markdown("#### Fetch Internal Transactions (type=call)")
    it_from = st.text_input("From address (optional)", key="it_from")
    it_to = st.text_input("To address (optional)", key="it_to")
    it_start = st.number_input(
        "Start block",
        min_value=0,
        value=EX_SAMPLE["start_block"],
        step=1,
        key="it_start",
    )
    it_end = st.number_input(
        "End block", min_value=0, value=EX_SAMPLE["end_block"], step=1, key="it_end"
    )
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Fetch Internal Tx", key="btn_it"):
            with st.spinner("Fetching internal transactions..."):
                try:
                    internals = sdk_fetch_internal_transactions(
                        from_addr=it_from or None,
                        to_addr=it_to or None,
                        start_block=it_start,
                        end_block=it_end,
                    )
                except Exception as e:
                    st.exception(e)
                else:
                    st.success(f"Fetched {len(internals)} internal tx record(s)")
                    st.json(internals[:20])
    with col_b:
        with st.expander("Example"):
            example = {
                "from_addr": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
                "to_addr": "0x6B175474E89094C44Da98b954EedeAC495271d0F",  # DAI
                "from_block": 17000000,
                "to_block": 17000100,
            }
            st.json(example)
            if st.button("Prefill Fields (Internal Tx)", key="prefill_it"):
                st.session_state["it_from"] = example["from_addr"]
                st.session_state["it_to"] = example["to_addr"]
                st.session_state["it_start"] = example["from_block"]
                st.session_state["it_end"] = example["to_block"]
            if st.button("Run Example (Internal Tx)", key="ex_it"):
                with st.spinner("Running example..."):
                    try:
                        internals = sdk_fetch_internal_transactions(
                            from_addr=example["from_addr"],
                            to_addr=example["to_addr"],
                            start_block=example["from_block"],
                            end_block=example["to_block"],
                        )
                    except Exception as e:
                        st.exception(e)
                    else:
                        st.success(f"Fetched {len(internals)} internal tx record(s)")
                        st.json(internals[:20])

# Receipts
with explorer_tabs[6]:
    st.markdown("#### Fetch Receipts")
    rc_tx_hash = st.text_input(
        "Transaction hash (optional)", placeholder="0x...", key="rc_hash"
    )
    rc_from = st.number_input(
        "Start block (required if no tx hash)",
        min_value=0,
        value=EX_SAMPLE["start_block"],
        step=1,
        key="rc_from",
    )
    rc_to = st.number_input(
        "End block (required if no tx hash)",
        min_value=0,
        value=EX_SAMPLE["start_block"] + 1,
        step=1,
        key="rc_to",
    )
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Fetch Receipts", key="btn_receipts"):
            with st.spinner("Fetching receipts..."):
                try:
                    if rc_tx_hash:
                        receipts = sdk_fetch_receipts(tx_hash=rc_tx_hash)
                    else:
                        receipts = sdk_fetch_receipts(
                            start_block=rc_from, end_block=rc_to
                        )
                except Exception as e:
                    st.exception(e)
                else:
                    st.success(f"Fetched {len(receipts)} receipt record(s)")
                    st.json(receipts[:20])
    with col_b:
        with st.expander("Example"):
            example_by_hash = {
                "tx_hash": "0xc5eee3ae9cf10fbee05325e3a25c3b19489783612e36cb55b054c2cb4f82fc28"
            }
            example_by_range = {"from_block": 17000000, "to_block": 17000050}
            st.write("By transaction hash:")
            st.json(example_by_hash)
            st.write("By range:")
            st.json(example_by_range)
            if st.button("Prefill Fields (Receipts)", key="prefill_receipts"):
                st.session_state["rc_hash"] = example_by_hash["tx_hash"]
                st.session_state["rc_from"] = example_by_range["from_block"]
                st.session_state["rc_to"] = example_by_range["to_block"]
            if st.button("Run Example (Receipts by Range)", key="ex_receipts"):
                with st.spinner("Running example..."):
                    try:
                        receipts = sdk_fetch_receipts(
                            start_block=example_by_range["from_block"],
                            end_block=example_by_range["to_block"],
                        )
                    except Exception as e:
                        st.exception(e)
                    else:
                        st.success(f"Fetched {len(receipts)} receipt record(s)")
                        st.json(receipts[:20])

# Deployments
with explorer_tabs[7]:
    st.markdown("#### Fetch Contract Deployments")
    dp_sender = st.text_input("Sender address (optional)", key="dp_sender")
    dp_from = st.number_input(
        "Start block",
        min_value=0,
        value=EX_SAMPLE["start_block"],
        step=1,
        key="dp_from",
    )
    dp_to = st.number_input(
        "End block", min_value=0, value=EX_SAMPLE["end_block"], step=1, key="dp_to"
    )
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Fetch Deployments", key="btn_deployments"):
            with st.spinner("Fetching deployments..."):
                try:
                    deployments = sdk_fetch_deployments(
                        start_block=dp_from, end_block=dp_to, sender=dp_sender or None
                    )
                except Exception as e:
                    st.exception(e)
                else:
                    st.success(f"Fetched {len(deployments)} deployment record(s)")
                    st.json(deployments[:20])
    with col_b:
        with st.expander("Example"):
            example = {"from_block": 17000000, "to_block": 17000200, "sender": None}
            st.json(example)
            if st.button("Prefill Fields (Deployments)", key="prefill_deployments"):
                st.session_state["dp_sender"] = example["sender"]
                st.session_state["dp_from"] = example["from_block"]
                st.session_state["dp_to"] = example["to_block"]
            if st.button("Run Example (Deployments)", key="ex_deployments"):
                with st.spinner("Running example..."):
                    try:
                        deployments = sdk_fetch_deployments(
                            start_block=example["from_block"],
                            end_block=example["to_block"],
                            sender=example["sender"],
                        )
                    except Exception as e:
                        st.exception(e)
                    else:
                        st.success(f"Fetched {len(deployments)} deployment record(s)")
                        st.json(deployments[:20])

# Token Transfers
with explorer_tabs[8]:
    st.markdown("#### Fetch Token Transfers (ERC-20/721)")
    tt_contract = st.text_input("Contract address (optional)", key="tt_contract")
    tt_from_holder = st.text_input("From holder (optional)", key="tt_from_holder")
    tt_to_holder = st.text_input("To holder (optional)", key="tt_to_holder")
    tt_from = st.number_input(
        "Start block",
        min_value=0,
        value=EX_SAMPLE["start_block"],
        step=1,
        key="tt_from",
    )
    tt_to = st.number_input(
        "End block", min_value=0, value=EX_SAMPLE["end_block"], step=1, key="tt_to"
    )
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Fetch Token Transfers", key="btn_tt"):
            with st.spinner("Fetching token transfers..."):
                try:
                    transfers = sdk_fetch_token_transfers(
                        contract_address=tt_contract or None,
                        from_holder=tt_from_holder or None,
                        to_holder=tt_to_holder or None,
                        start_block=tt_from,
                        end_block=tt_to,
                    )
                except Exception as e:
                    st.exception(e)
                else:
                    st.success(f"Fetched {len(transfers)} transfer record(s)")
                    st.json(transfers[:20])
    with col_b:
        with st.expander("Example"):
            example = {
                "contract_address": "0xA0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",  # USDC
                "from_holder": "0x28C6c06298d514Db089934071355E5743bf21d60",  # Binance hot wallet
                "to_holder": None,
                "from_block": 17000000,
                "to_block": 17001000,
            }
            st.json(example)
            if st.button("Prefill Fields (Token Transfers)", key="prefill_tt"):
                st.session_state["tt_contract"] = example["contract_address"]
                st.session_state["tt_from_holder"] = example["from_holder"]
                st.session_state["tt_to_holder"] = example["to_holder"]
                st.session_state["tt_from"] = example["from_block"]
                st.session_state["tt_to"] = example["to_block"]
            if st.button("Run Example (Token Transfers)", key="ex_tt"):
                with st.spinner(
                    "Running example (may be empty/large if no contract)..."
                ):
                    try:
                        transfers = sdk_fetch_token_transfers(
                            contract_address=example["contract_address"],
                            from_holder=example["from_holder"],
                            to_holder=example["to_holder"],
                            start_block=example["from_block"],
                            end_block=example["to_block"],
                        )
                    except Exception as e:
                        st.exception(e)
                    else:
                        st.success(f"Fetched {len(transfers)} transfer record(s)")
                        st.json(transfers[:20])
