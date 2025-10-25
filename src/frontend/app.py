import os
import sys
from pathlib import Path
from typing import List, Mapping
from openai import OpenAI
import numpy as np
import pandas as pd
import streamlit as st
from crypto_widgets import show_crypto_data
from chat_widget import ChatWidget

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.backend import (
    analyze_swap_price_impact,
    collect_wallet_activity,
    compute_address_centrality,
    decode_transaction_methods,
    detect_large_transfers,
    detect_suspicious_patterns,
    detect_swap_wash_trades,
    detect_value_anomalies,
    fetch_contract_logs,
    fetch_event_logs,
    fetch_swap_events,
    fetch_transaction_by_hash,
    label_transaction_risk,
    score_wallet_activity,
    summarize_counterparties,
    top_token_senders,
)

ERC20_TRANSFER_TOPIC = (
    "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
)
KNOWN_METHOD_SELECTORS: Mapping[str, str] = {
    "0xa9059cbb": "transfer(address,uint256)",
    "0x095ea7b3": "approve(address,uint256)",
    "0x23b872dd": "transferFrom(address,address,uint256)",
    "0x2e1a7d4d": "withdraw(uint256)",
    "0x5ea1a71c": "claim()",
    "0xb6b55f25": "deposit()",
    "0x0d295980": "multicall(bytes[])",
    "0xf305d719": "addLiquidityETH(address,uint256,uint256,uint256,address,uint256)",
}

st.set_page_config(
    page_title="Sniffer",
    page_icon="🐕",
    layout="wide",
)

st.title("Sniffer 🐕")
st.caption("Sniff out suspicious activity on the blockchain 🔎")

show_crypto_data()

chat_widget = ChatWidget(api_key=st.secrets["OPENAI_API_KEY"])
chat_widget.render()

# Show env status for the HyperSync token
_token = st.secrets["HYPERSYNC_API_TOKEN"] or st.secrets["hypersync_api_token"]
if not _token:
    st.warning(
        "No HyperSync API token found. Set HYPERSYNC_API_TOKEN or hypersync_api_token before fetching."
    )


def _split_addresses(value: str) -> List[str]:
    parts = [segment.strip() for segment in value.replace("\n", ",").split(",")]
    return [part for part in parts if part]


def _parse_int(value: str, default: int) -> int:
    try:
        return int(value, 0)
    except (TypeError, ValueError):
        return default


def _emit_summary(label: str, value) -> None:
    st.markdown(f"**{label}:**")
    st.write(value)


def _emit_counts(name: str, payload) -> None:
    st.info(
        {
            "records": len(payload) if payload is not None else 0,
        }
    )


def _sanitize_large_ints(obj):
    if isinstance(obj, dict):
        return {key: _sanitize_large_ints(value) for key, value in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_large_ints(item) for item in obj]
    if isinstance(obj, int) and abs(obj) > (2**63 - 1):
        return str(obj)
    return obj


def _prepare_scores_table(records: List[Mapping]) -> pd.DataFrame:
    rows = []
    for item in records:
        rows.append(
            {
                "address": item.get("address"),
                "score": item.get("score"),
                "factor_count": len(item.get("factors", [])),
            }
        )
    return pd.DataFrame(rows)


HYPERSYNC_URL = "http://eth.hypersync.xyz/"
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
    st.markdown("**Fraud analytics**")
    wallet_enable_overlay = st.checkbox(
        "Enable fraud overlay",
        value=True,
        key="wallet_overlay_enabled",
    )
    wallet_z_threshold = st.number_input(
        "Z-score threshold",
        min_value=0.5,
        max_value=10.0,
        value=2.0,
        step=0.5,
        key="wallet_z_threshold",
    )
    wallet_large_threshold = st.text_input(
        "Large transfer threshold (wei)",
        value="1000000000000000000",
        key="wallet_large_threshold",
    )
    wallet_min_degree = st.number_input(
        "Minimum degree for centrality alert",
        min_value=1,
        value=3,
        step=1,
        key="wallet_min_degree",
    )
    wallet_include_self = st.checkbox(
        "Highlight self-transfers",
        value=True,
        key="wallet_include_self",
    )
    wallet_include_zero = st.checkbox(
        "Highlight zero-value transfers",
        value=True,
        key="wallet_include_zero",
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
                    decoded_events = result.get("decoded_logs") or []
                    if decoded_events and wallet_enable_overlay:
                        st.markdown("**Fraud analytics overlay**")
                        anomalies = detect_value_anomalies(
                            decoded_events, z_threshold=float(wallet_z_threshold)
                        )
                        large_threshold_value = _parse_int(
                            wallet_large_threshold, int(1e18)
                        )
                        large_transfers = detect_large_transfers(
                            decoded_events, min_value=large_threshold_value
                        )
                        central_addresses = compute_address_centrality(
                            decoded_events, min_degree=int(wallet_min_degree)
                        )
                        suspicious = detect_suspicious_patterns(decoded_events)
                        filtered_patterns = []
                        for finding in suspicious:
                            if (
                                finding.get("type") == "self_transfer"
                                and wallet_include_self
                            ):
                                filtered_patterns.append(finding)
                            if (
                                finding.get("type") == "zero_value"
                                and wallet_include_zero
                            ):
                                filtered_patterns.append(finding)

                        scores = score_wallet_activity(
                            addresses,
                            anomalies,
                            large_transfers,
                            central_addresses,
                        )
                        counterparty_summary = summarize_counterparties(
                            decoded_events, addresses
                        )

                        col_anom, col_large, col_cent = st.columns(3)
                        with col_anom:
                            st.metric("Anomalous transfers", len(anomalies))
                        with col_large:
                            st.metric("Large transfers", len(large_transfers))
                        with col_cent:
                            st.metric("High-degree addresses", len(central_addresses))

                        st.markdown("**Risk scores**")
                        st.dataframe(_prepare_scores_table(scores))

                        if anomalies:
                            st.markdown("**Anomaly details**")
                            st.json(_sanitize_large_ints(anomalies))

                        if large_transfers:
                            st.markdown("**Large transfers**")
                            st.json(_sanitize_large_ints(large_transfers))

                        if central_addresses:
                            st.markdown("**Address centrality (degree)**")
                            st.dataframe(pd.DataFrame(central_addresses))

                        if filtered_patterns:
                            st.markdown("**Suspicious heuristics**")
                            st.json(_sanitize_large_ints(filtered_patterns))

                        watched = counterparty_summary.get("watched") or []
                        counterparties = counterparty_summary.get("counterparties") or []
                        if watched:
                            st.markdown("**Watched address summary**")
                            st.dataframe(pd.DataFrame(watched))
                        if counterparties:
                            st.markdown("**Top counterparties**")
                            st.dataframe(pd.DataFrame(counterparties).head(10))

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
    st.markdown("**Fraud analytics**")
    event_enable_overlay = st.checkbox(
        "Enable anomaly overlay",
        value=True,
        key="event_overlay_enabled",
    )
    event_z_threshold = st.number_input(
        "Z-score threshold",
        min_value=0.5,
        max_value=10.0,
        value=2.0,
        step=0.5,
        key="event_z_threshold",
    )
    event_large_threshold = st.text_input(
        "Large transfer threshold (wei)",
        value="1000000000000000000",
        key="event_large_threshold",
    )
    event_min_degree = st.number_input(
        "Minimum degree for centrality alert",
        min_value=1,
        value=3,
        step=1,
        key="event_min_degree",
    )
    event_include_self = st.checkbox(
        "Highlight self-transfers",
        value=True,
        key="event_include_self",
    )
    event_include_zero = st.checkbox(
        "Highlight zero-value transfers",
        value=True,
        key="event_include_zero",
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
                        f"Returned {len(result['logs'])} event log(s). Next block {result['next_block']}"
                    )
                    _emit_summary("Logs", result["logs"])
                    if result.get("decoded_logs"):
                        _emit_summary("Decoded logs", result["decoded_logs"])
                        if event_enable_overlay:
                            decoded_events = result["decoded_logs"]
                            st.markdown("**Fraud analytics overlay**")
                            anomalies = detect_value_anomalies(
                                decoded_events, z_threshold=float(event_z_threshold)
                            )
                            large_threshold_value = _parse_int(
                                event_large_threshold, int(1e18)
                            )
                            large_transfers = detect_large_transfers(
                                decoded_events, min_value=large_threshold_value
                            )
                            central_addresses = compute_address_centrality(
                                decoded_events, min_degree=int(event_min_degree)
                            )
                            suspicious = detect_suspicious_patterns(decoded_events)

                            filtered_patterns = []
                            for finding in suspicious:
                                if (
                                    finding.get("type") == "self_transfer"
                                    and event_include_self
                                ):
                                    filtered_patterns.append(finding)
                                if (
                                    finding.get("type") == "zero_value"
                                    and event_include_zero
                                ):
                                    filtered_patterns.append(finding)

                            col_anom, col_large, col_cent = st.columns(3)
                            with col_anom:
                                st.metric("Anomalous transfers", len(anomalies))
                            with col_large:
                                st.metric("Large transfers", len(large_transfers))
                            with col_cent:
                                st.metric("High-degree addresses", len(central_addresses))

                            if anomalies:
                                st.markdown("**Anomaly details**")
                                st.json(_sanitize_large_ints(anomalies))

                            if large_transfers:
                                st.markdown("**Large transfers**")
                                st.json(_sanitize_large_ints(large_transfers))

                            if central_addresses:
                                st.markdown("**Address centrality (degree)**")
                                st.dataframe(pd.DataFrame(central_addresses))

                            if filtered_patterns:
                                st.markdown("**Suspicious heuristics**")
                                st.json(_sanitize_large_ints(filtered_patterns))

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
    st.markdown("**Fraud analytics**")
    swap_enable_overlay = st.checkbox(
        "Enable price impact overlay",
        value=True,
        key="swap_overlay_enabled",
    )
    swap_min_bps = st.number_input(
        "Minimum price impact (bps)",
        min_value=1.0,
        max_value=10_000.0,
        value=50.0,
        step=10.0,
        key="swap_min_bps",
    )
    swap_min_notional = st.text_input(
        "Minimum notional (abs amount)",
        value="0",
        key="swap_min_notional",
    )
    swap_detect_cycles = st.checkbox(
        "Highlight wash-trade pairs",
        value=True,
        key="swap_washdetect",
    )
    swap_max_swaps = st.number_input(
        "Wash trade swap threshold",
        min_value=2,
        max_value=20,
        value=3,
        step=1,
        key="swap_max_swaps",
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
                        f"Returned {len(result['logs'])} swap log(s). Next block {result['next_block']}"
                    )
                    _emit_summary("Logs", result["logs"])
                    decoded_events = result.get("decoded_logs") or []
                    if swap_enable_overlay and decoded_events:
                        min_notional_value = _parse_int(swap_min_notional, 0)
                        price_impacts = analyze_swap_price_impact(
                            decoded_events,
                            min_price_delta_bps=float(swap_min_bps),
                            min_notional=min_notional_value,
                        )
                        st.markdown("**Swap price impact**")
                        st.metric("High-impact swaps", len(price_impacts))
                        if price_impacts:
                            st.json(_sanitize_large_ints(price_impacts))

                        if swap_detect_cycles:
                            wash_trades = detect_swap_wash_trades(
                                decoded_events, max_swaps=int(swap_max_swaps)
                            )
                            st.markdown("**Wash trade signals**")
                            st.metric("Suspicious pairs", len(wash_trades))
                            if wash_trades:
                                st.json(_sanitize_large_ints(wash_trades))

with tab_tx:
    st.subheader("Lookup transaction by hash")
    tx_hash_value = st.text_input("Transaction hash", placeholder="0x...")
    tx_from_block = st.number_input(
        "Start block", min_value=0, value=0, step=1, key="tx_from_block"
    )
    st.markdown("**Enhancements**")
    tx_enable_decoding = st.checkbox(
        "Decode method selectors",
        value=True,
        key="tx_decode_methods",
    )
    tx_watchlist = st.text_area(
        "Watchlist addresses",
        placeholder="Comma separated 0x...",
        height=80,
        key="tx_watchlist",
    )
    tx_large_threshold = st.text_input(
        "Large value threshold (wei)",
        value="100000000000000000000",
        key="tx_large_threshold",
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
                        f"Returned {count} transaction record(s). Next block {result['next_block']}"
                    )
                    _emit_summary("Transactions", result["transactions"])
                    if tx_enable_decoding and result["transactions"]:
                        decoded_txs = decode_transaction_methods(
                            result["transactions"], known_selectors=KNOWN_METHOD_SELECTORS
                        )
                        watchlist = _split_addresses(tx_watchlist)
                        large_threshold_value = _parse_int(
                            tx_large_threshold, int(1e20)
                        )
                        enriched = label_transaction_risk(
                            decoded_txs,
                            watchlist=watchlist,
                            large_value_threshold=large_threshold_value,
                        )
                        st.markdown("**Decoded transactions**")
                        st.json(_sanitize_large_ints(enriched))

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
