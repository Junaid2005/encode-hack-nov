import streamlit as st
from typing import List, Mapping
import pandas as pd
from pathlib import Path
import sys
import json
import time

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.backend import (
    analyze_event_logs,
    analyze_swap_events,
    analyze_transaction,
    analyze_wallet_activity,
    EventAnalysisOptions,
    SwapAnalysisOptions,
    TransactionAnalysisOptions,
    WalletAnalysisOptions,
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


def stream_data(text):
    for letter in text:
        yield letter
        time.sleep(0.01)


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


def _to_arrow_safe_dataframe(records: List[Mapping]) -> pd.DataFrame:
    sanitized = _sanitize_large_ints(records)
    df = pd.DataFrame(sanitized)
    for column in df.columns:
        series = df[column]
        has_str = series.map(lambda v: isinstance(v, str)).any()
        has_bytes = series.map(lambda v: isinstance(v, (bytes, bytearray))).any()
        has_int = series.map(lambda v: isinstance(v, int)).any()
        has_mapping = series.map(lambda v: isinstance(v, Mapping)).any()
        has_sequence = series.map(lambda v: isinstance(v, (list, tuple))).any()
        if has_mapping or has_sequence:
            df[column] = series.map(
                lambda v: json.dumps(v) if isinstance(v, (Mapping, list, tuple)) else v
            )
        if has_str and has_int:
            df[column] = series.map(lambda v: str(v) if isinstance(v, int) else v)
        if has_bytes:
            df[column] = series.map(
                lambda v: v.decode("utf-8") if isinstance(v, (bytes, bytearray)) else v
            )
        df[column] = df[column].astype(str)
    return df


st.set_page_config(
    page_title="Sniffer Client",
    page_icon="🐕‍🦺",
    layout="wide",
)

st.header("Sniffer Client 🐕‍🦺")
if not st.session_state.get("sniffer_client_visited", False):
    st.session_state["sniffer_client_visited"] = True
    st.write_stream(stream_data("MCP Interface for HyperSync API ❤️"))
    progress_text = "Loading HyperSync API..."
    progress_bar = st.progress(0, text=progress_text)

    for percent_complete in range(100):
        time.sleep(0.0025)
        progress_bar.progress(
            percent_complete + 1,
            text=f"Loading. Hypersync Client.. {percent_complete + 1}%",
        )

    progress_bar.empty()
else:
    st.write("MCP Interface for HyperSync API ❤️")

tab_wallet, tab_event_logs, tab_swap, tab_tx = st.tabs(
    [
        "Wallet Activity",
        "Event Logs",
        "Swap Events",
        "Tx Lookup",
    ]
)

with tab_wallet:
    st.subheader("Collect wallet activity")
    st.caption(
        "Purpose: investigate specific wallets by pulling complete transfer history, heuristics, baselines, and AI-ready alerts."
    )
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
    wallet_baseline_window = st.number_input(
        "Baseline window (transfers)",
        min_value=1,
        value=20,
        step=1,
        key="wallet_baseline_window",
    )
    wallet_trend_window = st.number_input(
        "Trend window (transfers)",
        min_value=5,
        value=30,
        step=5,
        key="wallet_trend_window",
    )
    wallet_trend_z_threshold = st.number_input(
        "Trend z-score threshold",
        min_value=1.0,
        max_value=10.0,
        value=3.0,
        step=0.5,
        key="wallet_trend_z_threshold",
    )
    wallet_trend_cusum_limit = st.number_input(
        "Trend CUSUM limit",
        min_value=1.0,
        max_value=50.0,
        value=5.0,
        step=0.5,
        key="wallet_trend_cusum_limit",
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
                    result = analyze_wallet_activity(
                        addresses,
                        from_block=int(wallet_from_block),
                        transfer_topic=wallet_topic or ERC20_TRANSFER_TOPIC,
                        options=WalletAnalysisOptions(
                            z_threshold=float(wallet_z_threshold),
                            large_transfer_threshold=_parse_int(
                                wallet_large_threshold, int(1e18)
                            ),
                            min_centrality_degree=int(wallet_min_degree),
                            include_self_transfers=wallet_include_self,
                            include_zero_value=wallet_include_zero,
                            baseline_window=int(wallet_baseline_window),
                            trend_window=int(wallet_trend_window),
                            trend_z_threshold=float(wallet_trend_z_threshold),
                            trend_cusum_limit=float(wallet_trend_cusum_limit),
                        ),
                    )
                except Exception as exc:  # pragma: no cover - UI feedback
                    st.exception(exc)
                else:
                    summary = result.get("summary", {})
                    st.success(
                        f"Next block {summary.get('next_block')} (archive height {summary.get('archive_height')})"
                    )
                    st.json(_sanitize_large_ints(summary))

                    verdict = summary.get("verdict", "clear").title()
                    severity = summary.get("severity", "low").title()
                    st.metric("Fraud verdict", verdict, severity)

                    alerts = result.get("alerts", [])
                    metrics = result.get("metrics", {})
                    raw = result.get("raw", {})

                    if alerts and wallet_enable_overlay:
                        st.markdown("**Alerts**")
                        st.dataframe(_to_arrow_safe_dataframe(alerts))

                    if metrics.get("risk_scores"):
                        st.markdown("**Risk scores**")
                        st.dataframe(
                            _prepare_scores_table(metrics.get("risk_scores", []))
                        )

                    if metrics.get("baselines"):
                        st.markdown("**Wallet baselines**")
                        st.dataframe(_to_arrow_safe_dataframe(metrics["baselines"]))

                    counterparties = metrics.get("counterparties") or {}
                    watched = counterparties.get("watched") or []
                    top_counterparties = counterparties.get("counterparties") or []
                    if watched:
                        st.markdown("**Watched address summary**")
                        st.dataframe(_to_arrow_safe_dataframe(watched))
                    if top_counterparties:
                        st.markdown("**Top counterparties**")
                        st.dataframe(
                            _to_arrow_safe_dataframe(top_counterparties).head(10)
                        )

                    if raw.get("decoded_logs") and wallet_enable_overlay:
                        st.markdown("**Decoded logs**")
                        st.json(_sanitize_large_ints(raw["decoded_logs"]))

with tab_event_logs:
    st.subheader("Fetch event logs")
    st.caption(
        "Purpose: monitor targeted event signatures (ERC-20 transfers, custom emitters) and surface anomaly overlays for watchlisted contracts."
    )
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
    event_baseline_window = st.number_input(
        "Baseline window (events)",
        min_value=1,
        value=20,
        step=1,
        key="event_baseline_window",
    )
    event_trend_window = st.number_input(
        "Trend window (events)",
        min_value=5,
        value=30,
        step=5,
        key="event_trend_window",
    )
    event_trend_z_threshold = st.number_input(
        "Trend z-score threshold",
        min_value=1.0,
        max_value=10.0,
        value=3.0,
        step=0.5,
        key="event_trend_z_threshold",
    )
    event_trend_cusum_limit = st.number_input(
        "Trend CUSUM limit",
        min_value=1.0,
        max_value=50.0,
        value=5.0,
        step=0.5,
        key="event_trend_cusum_limit",
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
                    result = analyze_event_logs(
                        event_contract.strip(),
                        topic0=event_topic or ERC20_TRANSFER_TOPIC,
                        start_block=int(event_start),
                        end_block=int(event_end),
                        options=EventAnalysisOptions(
                            z_threshold=float(event_z_threshold),
                            large_transfer_threshold=_parse_int(
                                event_large_threshold, int(1e18)
                            ),
                            min_centrality_degree=int(event_min_degree),
                            baseline_window=int(event_baseline_window),
                            trend_window=int(event_trend_window),
                            trend_z_threshold=float(event_trend_z_threshold),
                            trend_cusum_limit=float(event_trend_cusum_limit),
                            include_self_transfers=event_include_self,
                            include_zero_value=event_include_zero,
                        ),
                    )
                except Exception as exc:
                    st.exception(exc)
                else:
                    summary = result.get("summary", {})
                    st.success(
                        f"Returned {summary.get('total_logs', 0)} event log(s). Next block {summary.get('next_block')}"
                    )
                    st.json(_sanitize_large_ints(summary))

                    verdict = summary.get("verdict", "clear").title()
                    severity = summary.get("severity", "low").title()
                    st.metric("Fraud verdict", verdict, severity)

                    alerts = result.get("alerts", [])
                    metrics = result.get("metrics", {})
                    raw = result.get("raw", {})

                    if alerts and event_enable_overlay:
                        st.markdown("**Alerts**")
                        st.dataframe(_to_arrow_safe_dataframe(alerts).head(25))

                    if metrics.get("baselines"):
                        st.markdown("**Wallet baselines**")
                        st.dataframe(
                            _to_arrow_safe_dataframe(metrics["baselines"]).head(15)
                        )

                    if raw.get("logs"):
                        _emit_summary("Logs", raw["logs"])

                    if raw.get("decoded_logs") and event_enable_overlay:
                        _emit_summary("Decoded logs", raw["decoded_logs"])

with tab_swap:
    st.subheader("Fetch swap events")
    st.caption(
        "Purpose: examine liquidity pool activity to spot unusual price impact or wash-trade patterns in AMM swaps."
    )
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
                    result = analyze_swap_events(
                        pool_address.strip(),
                        topic0=swap_topic,
                        start_block=int(swap_start),
                        end_block=int(swap_end),
                        options=SwapAnalysisOptions(
                            min_price_delta_bps=float(swap_min_bps),
                            min_notional=_parse_int(swap_min_notional, 0),
                            wash_trade_threshold=int(swap_max_swaps),
                        ),
                    )
                except Exception as exc:
                    st.exception(exc)
                else:
                    summary = result.get("summary", {})
                    st.success(
                        f"Returned {summary.get('total_logs', 0)} swap log(s). Next block {summary.get('next_block')}"
                    )
                    st.json(_sanitize_large_ints(summary))

                    verdict = summary.get("verdict", "clear").title()
                    severity = summary.get("severity", "low").title()
                    st.metric("Fraud verdict", verdict, severity)

                    alerts = result.get("alerts", [])
                    raw = result.get("raw", {})

                    if alerts:
                        st.markdown("**Alerts**")
                        st.dataframe(_to_arrow_safe_dataframe(alerts).head(25))

                    if raw.get("logs"):
                        _emit_summary("Logs", raw["logs"])

with tab_tx:
    st.subheader("Lookup transaction by hash")
    st.caption(
        "Purpose: fetch full transaction payloads, decode selectors, and apply risk heuristics for single-hash investigations."
    )
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
                    result = analyze_transaction(
                        tx_hash_value.strip(),
                        from_block=int(tx_from_block),
                        options=TransactionAnalysisOptions(
                            decode_methods=tx_enable_decoding,
                            large_value_threshold=_parse_int(
                                tx_large_threshold, int(1e20)
                            ),
                            watchlist=_split_addresses(tx_watchlist),
                        ),
                    )
                except Exception as exc:
                    st.exception(exc)
                else:
                    summary = result.get("summary", {})
                    st.success(
                        f"Returned {summary.get('total_transactions', 0)} transaction record(s). Next block {summary.get('next_block')}"
                    )
                    st.json(_sanitize_large_ints(summary))

                    verdict = summary.get("verdict", "clear").title()
                    severity = summary.get("severity", "low").title()
                    st.metric("Fraud verdict", verdict, severity)

                    alerts = result.get("alerts", [])
                    data = result.get("data", [])
                    raw = result.get("raw", {})

                    if alerts:
                        st.markdown("**Alerts**")
                        st.dataframe(_to_arrow_safe_dataframe(alerts))

                    if data and tx_enable_decoding:
                        st.markdown("**Decoded transactions**")
                        st.dataframe(_to_arrow_safe_dataframe(data))

                    if raw.get("transactions"):
                        _emit_summary("Transactions", raw["transactions"])
