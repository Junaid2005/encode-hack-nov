"""Frontend MCP wrappers that surface backend fraud analytics with narration."""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Mapping, MutableMapping, Sequence
import re


PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.backend import (  # type: ignore  # noqa: E402
    EventAnalysisOptions,
    SwapAnalysisOptions,
    TransactionAnalysisOptions,
    WalletAnalysisOptions,
    analyze_event_logs,
    analyze_swap_events,
    analyze_transaction,
    analyze_wallet_activity,
)
from src.backend.fraud_detection import (  # type: ignore  # noqa: E402
    ERC20_TRANSFER_TOPIC,
)


def _maybe_sequence(value: Any) -> Sequence[str]:
    if value is None:
        return []
    if isinstance(value, str):
        parts = [segment.strip() for segment in value.replace("\n", ",").split(",")]
        return [part for part in parts if part]
    if isinstance(value, Sequence):
        return [str(item) for item in value]
    raise TypeError("Expected a string or sequence of strings")


def _maybe_int(value: Any) -> int:
    if value is None:
        raise TypeError("Integer value expected, received None")
    if isinstance(value, bool):
        raise TypeError("Boolean is not a valid integer value")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value, 0)
    raise TypeError(f"Cannot convert {type(value)!r} to int")


def _maybe_float(value: Any) -> float:
    if value is None:
        raise TypeError("Float value expected, received None")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, str):
        return float(value)
    raise TypeError(f"Cannot convert {type(value)!r} to float")


def _maybe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "y"}:
            return True
        if lowered in {"false", "0", "no", "n"}:
            return False
    raise TypeError(f"Cannot convert {value!r} to bool")


def _normalize_tx_hash(tx_hash: Any) -> str:
    if not isinstance(tx_hash, str):
        raise ValueError("'tx_hash' must be a hexadecimal string")
    candidate = tx_hash.strip().lower()
    if not candidate:
        raise ValueError("'tx_hash' is required")
    if not candidate.startswith("0x"):
        candidate = "0x" + candidate
    if len(candidate) != 66:
        raise ValueError(
            "'tx_hash' must be 32 bytes (0x prefixed with 64 hex characters)"
        )
    hex_part = candidate[2:]
    if not all(ch in "0123456789abcdef" for ch in hex_part):
        raise ValueError("'tx_hash' contains non-hexadecimal characters")
    return candidate


def _options_from_payload(dataclass_type, payload: Mapping[str, Any] | None):
    if not payload:
        return None

    data: MutableMapping[str, Any] = dict(payload)

    if dataclass_type is WalletAnalysisOptions:
        converters: Dict[str, Any] = {
            "z_threshold": _maybe_float,
            "large_transfer_threshold": _maybe_int,
            "min_centrality_degree": _maybe_int,
            "include_self_transfers": _maybe_bool,
            "include_zero_value": _maybe_bool,
            "baseline_window": _maybe_int,
            "trend_window": _maybe_int,
            "trend_z_threshold": _maybe_float,
            "trend_cusum_limit": _maybe_float,
        }
    elif dataclass_type is EventAnalysisOptions:
        converters = {
            "z_threshold": _maybe_float,
            "large_transfer_threshold": _maybe_int,
            "min_centrality_degree": _maybe_int,
            "baseline_window": _maybe_int,
            "trend_window": _maybe_int,
            "trend_z_threshold": _maybe_float,
            "trend_cusum_limit": _maybe_float,
            "include_self_transfers": _maybe_bool,
            "include_zero_value": _maybe_bool,
        }
    elif dataclass_type is SwapAnalysisOptions:
        converters = {
            "min_price_delta_bps": _maybe_float,
            "min_notional": _maybe_int,
            "wash_trade_threshold": _maybe_int,
        }
    elif dataclass_type is TransactionAnalysisOptions:
        converters = {
            "decode_methods": _maybe_bool,
            "large_value_threshold": _maybe_int,
            "watchlist": _maybe_sequence,
        }
    else:
        converters = {}

    coerced: Dict[str, Any] = {}
    for key, converter in converters.items():
        if key not in data or data[key] is None:
            continue
        value = data[key]
        try:
            coerced[key] = converter(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid value for '{key}': {value!r}") from exc

    return dataclass_type(**coerced)


def _human(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        return f"{value:,.2f}"
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(item) for item in value)
    return str(value)


def _summarize_details(details: Mapping[str, Any] | None) -> str:
    if not isinstance(details, Mapping):
        return ""
    preferred = [
        "value",
        "z_score",
        "delta_bps",
        "participants",
        "swaps",
        "degree",
        "risk_flags",
        "latest_value",
        "rolling_volume",
    ]
    parts: list[str] = []
    for key in preferred:
        if key in details and details[key] not in (None, [], {}):
            parts.append(f"{key}={_human(details[key])}")
    if parts:
        return "; ".join(parts)
    for idx, (key, value) in enumerate(details.items()):
        if idx >= 3:
            break
        parts.append(f"{key}={_human(value)}")
    return "; ".join(parts)


PERSONA_METHODS_WALLET = [
    "Statistical baselines (z-scores) for value anomalies",
    "Large-transfer threshold checks",
    "Graph centrality analysis",
    "Rolling trend monitors (CUSUM / z-score)",
]

PERSONA_METHODS_EVENT = [
    "Event-level z-score anomaly detection",
    "Large-transfer thresholds",
    "Address network centrality",
    "Rolling trend monitoring",
]

PERSONA_METHODS_SWAP = [
    "Price-impact analysis versus prior sqrtPriceX96",
    "Notional size filters",
    "Pair-frequency checks for wash trading",
]

PERSONA_METHODS_TX = [
    "Method selector decoding (4-byte signatures)",
    "Watchlist screening of senders/receivers",
    "Large-value threshold comparison",
]

MAX_ALERT_PREVIEW = 8
MAX_METRIC_PREVIEW = 6
MAX_DATA_PREVIEW = 8
WEI_PER_ETH = float(10**18)


def _format_methods(methods: Sequence[str]) -> list[str]:
    if not methods:
        return []
    lines = ["Detection methods applied:"]
    for method in methods:
        lines.append(f"- {method}")
    return lines


def _format_alerts(
    alerts: Sequence[Mapping[str, Any]], *, max_items: int = 5
) -> list[str]:
    if not alerts:
        return ["Alerts: none detected."]
    lines = [f"Alerts (showing up to {max_items} of {len(alerts)}):"]
    for idx, alert in enumerate(alerts[:max_items], start=1):
        alert_type = alert.get("type", "unknown")
        severity = alert.get("severity", "unknown")
        address = alert.get("address") or "n/a"
        detail_text = _summarize_details(alert.get("details"))
        suffix = f" | {detail_text}" if detail_text else ""
        lines.append(f"{idx}. [{severity}] {alert_type} → {address}{suffix}")
    if len(alerts) > max_items:
        lines.append(f"… {len(alerts) - max_items} additional alerts not shown")
    return lines


def _format_wallet_metrics(metrics: Mapping[str, Any]) -> list[str]:
    if not isinstance(metrics, Mapping):
        return []
    lines: list[str] = []
    risk_scores = metrics.get("risk_scores") or []
    if risk_scores:
        lines.append("Top Risk Scores (0-100 scale):")
        for item in risk_scores[:3]:
            addr = item.get("address", "n/a")
            score = item.get("score")
            lines.append(
                f"- {addr}: score {_human(score)} (drivers: {_human([f.get('type') for f in item.get('factors', [])])})"
            )
        if len(risk_scores) > 3:
            lines.append(f"… {len(risk_scores) - 3} more addresses scored")

    baselines = metrics.get("baselines") or []
    if baselines:
        lines.append("Baseline Snapshot:")
        for item in baselines[:3]:
            addr = item.get("address", "n/a")
            total_volume = _human(item.get("total_volume"))
            transfers = _human(item.get("transfer_count"))
            rolling = _human(item.get("rolling_volume"))
            lines.append(
                f"- {addr}: lifetime volume {total_volume} over {transfers} transfers; recent window {rolling}"
            )
        if len(baselines) > 3:
            lines.append(f"… {len(baselines) - 3} more baselines not shown")

    counterparties = (metrics.get("counterparties", {}) or {}).get(
        "counterparties"
    ) or []
    if counterparties:
        lines.append("Top Counterparties:")
        for item in counterparties[:3]:
            addr = item.get("address", "n/a")
            interactions = _human(item.get("interactions"))
            total_value = _human(item.get("total_value"))
            lines.append(
                f"- {addr}: {interactions} interaction(s), total value {total_value}"
            )
        if len(counterparties) > 3:
            lines.append(f"… {len(counterparties) - 3} more counterparties not shown")
    return lines


def _format_event_metrics(metrics: Mapping[str, Any]) -> list[str]:
    if not isinstance(metrics, Mapping):
        return []
    baselines = metrics.get("baselines") or []
    if not baselines:
        return []
    lines = ["Baseline Snapshot:"]
    for item in baselines[:3]:
        addr = item.get("address", "n/a")
        total_volume = _human(item.get("total_volume"))
        transfers = _human(item.get("transfer_count"))
        lines.append(
            f"- {addr}: total volume {total_volume} over {transfers} transfers"
        )
    if len(baselines) > 3:
        lines.append(f"… {len(baselines) - 3} additional baselines hidden")
    return lines


def _format_transaction_data(records: Sequence[Mapping[str, Any]]) -> list[str]:
    if not records:
        return []
    flagged = [item for item in records if item.get("risk_flags")]
    if not flagged:
        return ["Flagged Transactions: none"]
    lines = ["Flagged Transactions:"]
    for item in flagged[:3]:
        tx_hash = item.get("hash") or item.get("transaction_hash") or "n/a"
        flags = ", ".join(item.get("risk_flags", []))
        value = _human(item.get("value"))
        method = item.get("method") or item.get("selector")
        method_suffix = f" | method {method}" if method else ""
        lines.append(f"- {tx_hash}: flags [{flags}] | value {value}{method_suffix}")
    if len(flagged) > 3:
        lines.append(f"… {len(flagged) - 3} additional flagged transactions")
    return lines


def _safe_top(items: Sequence[Any] | None, limit: int = 10) -> List[Any]:
    if not items:
        return []
    return list(items)[:limit]


def _limit_records(records: Sequence[Any] | None, limit: int) -> List[Any]:
    if not records:
        return []
    limited = []
    for item in list(records)[:limit]:
        if isinstance(item, Mapping):
            limited.append(dict(item))
        else:
            limited.append(item)
    return limited


def _limit_metrics(metrics: Mapping[str, Any] | None, limit: int) -> Dict[str, Any]:
    if not isinstance(metrics, Mapping):
        return {}
    limited: Dict[str, Any] = {}
    for key, value in metrics.items():
        if isinstance(value, Mapping):
            limited[key] = _limit_metrics(value, limit)
        elif isinstance(value, Sequence) and not isinstance(
            value, (str, bytes, bytearray)
        ):
            limited[key] = _limit_records(value, limit)
        else:
            limited[key] = value
    return limited


_NUMERIC_SANITIZE_PATTERN = re.compile(r"[,_\s]")


def _normalize_numeric_string(value: str) -> str:
    stripped = value.strip()
    # Remove common thousands separators and whitespace
    cleaned = _NUMERIC_SANITIZE_PATTERN.sub("", stripped)
    # Drop unit suffixes we do not chart directly
    for suffix in ["wei", "eth", "gwei"]:
        if cleaned.lower().endswith(suffix):
            cleaned = cleaned[: -len(suffix)]
            break
    return cleaned


def _coerce_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        normalized = _normalize_numeric_string(value)
        if not normalized:
            return None
        try:
            return float(normalized)
        except ValueError:
            return None
    return None


def _coerce_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        normalized = _normalize_numeric_string(value)
        if not normalized:
            return None
        try:
            return int(float(normalized))
        except ValueError:
            return None
    return None


def _build_chart(
    *,
    key: str,
    title: str,
    description: str,
    mark: Mapping[str, Any],
    encoding: Mapping[str, Any],
    data: Sequence[Mapping[str, Any]] | None,
) -> Dict[str, Any] | None:
    if not data:
        return None
    return {
        "key": key,
        "title": title,
        "description": description,
        "spec": {
            "mark": dict(mark),
            "encoding": dict(encoding),
            "width": 520,
            "height": 280,
        },
        "data": list(data),
    }


def _finalize_response(payload: Dict[str, Any]) -> str:
    charts = payload.get("charts") or []
    chart_count = sum(1 for chart in charts if chart and chart.get("data"))
    payload["chart_count"] = chart_count
    return json.dumps(payload)


def _summarize_alerts(alerts: Sequence[Mapping[str, Any]]) -> list[Dict[str, Any]]:
    summarized: list[Dict[str, Any]] = []
    for item in _limit_records(alerts, MAX_ALERT_PREVIEW):
        summarized.append(
            {
                "type": item.get("type", ""),
                "severity": item.get("severity", ""),
                "address": item.get("address", ""),
                "summary": _summarize_details(item.get("details")),
            }
        )
    return summarized


def _build_bar_chart(
    *,
    key: str,
    title: str,
    description: str,
    label_field: str,
    value_field: str,
    label_title: str,
    value_title: str,
    data: Sequence[Mapping[str, Any]] | None,
) -> Dict[str, Any] | None:
    if not data:
        return None
    return _build_chart(
        key=key,
        title=title,
        description=description,
        mark={"type": "bar", "tooltip": True},
        encoding={
            "x": {
                "field": label_field,
                "type": "nominal",
                "title": label_title,
            },
            "y": {
                "field": value_field,
                "type": "quantitative",
                "title": value_title,
            },
            "tooltip": [
                {"field": label_field, "type": "nominal", "title": label_title},
                {"field": value_field, "type": "quantitative", "title": value_title},
            ],
        },
        data=data,
    )


def _build_severity_chart(
    alerts: Sequence[Mapping[str, Any]],
    *,
    key: str,
    title: str,
    description: str,
) -> Dict[str, Any] | None:
    if not alerts:
        return None
    severity_counts: Counter[str] = Counter()
    for alert in alerts:
        severity_label = str(alert.get("severity", "unknown")).title()
        severity_counts[severity_label] += 1
    data = [
        {"severity": label, "count": count}
        for label, count in severity_counts.most_common()
    ]
    if not data:
        return None
    return _build_bar_chart(
        key=key,
        title=title,
        description=description,
        label_field="severity",
        value_field="count",
        label_title="Severity",
        value_title="Alert count",
        data=data,
    )


def wallet_activity(
    *,
    addresses: Sequence[str] | str,
    from_block: int | str = 0,
    transfer_topic: str = ERC20_TRANSFER_TOPIC,
    options: Mapping[str, Any] | None = None,
) -> str:
    address_list = list(_maybe_sequence(addresses))
    if not address_list:
        raise ValueError("Provide at least one wallet address")

    start_block = _maybe_int(from_block)
    if start_block is None or start_block <= 0:
        raise ValueError(
            "Missing 'from_block'. Ask the investigator for a recent starting block or block range before running wallet_activity."
        )
    wallet_options = _options_from_payload(WalletAnalysisOptions, options)
    result = analyze_wallet_activity(
        address_list,
        from_block=start_block,
        transfer_topic=transfer_topic or ERC20_TRANSFER_TOPIC,
        options=wallet_options,
    )

    summary = result.get("summary", {})
    lines = [
        "Wallet Fraud Summary:",
        f"• Address focus: {', '.join(address_list)}",
        f"• Verdict: {summary.get('verdict', 'unknown')} (severity {summary.get('severity', 'n/a')})",
        f"• Data scanned: {_human(summary.get('total_logs'))} logs | {_human(summary.get('total_transactions'))} transactions",
    ]

    alerts = result.get("alerts", []) or []
    metrics_payload = result.get("metrics", {}) or {}

    lines.extend(_format_alerts(alerts))
    metric_lines = _format_wallet_metrics(metrics_payload)
    if metric_lines:
        lines.append("")
        lines.extend(metric_lines)

    method_lines = _format_methods(PERSONA_METHODS_WALLET)
    if method_lines:
        lines.append("")
        lines.extend(method_lines)

    lines.append("")
    lines.append(
        "Investigator guidance: review the high-severity alerts first, vet the top counterparties, "
        "and pull transaction traces around the standout transfers for context."
    )

    charts: list[Dict[str, Any]] = []

    counterparties_payload = (metrics_payload.get("counterparties", {}) or {}).get(
        "counterparties"
    )
    counterparties_chart_data: list[Dict[str, Any]] = []
    for item in _safe_top(counterparties_payload, MAX_METRIC_PREVIEW):
        address = item.get("address") or "n/a"
        total_value = _coerce_float(item.get("total_value"))
        if total_value is None:
            continue
        counterparties_chart_data.append(
            {
                "address": address,
                "value_eth": total_value / WEI_PER_ETH,
            }
        )
    chart = _build_bar_chart(
        key="wallet_counterparties",
        title="Largest Counterparties (ETH)",
        description="Total wei moved with each top counterparty, converted to ETH.",
        label_field="address",
        value_field="value_eth",
        label_title="Counterparty",
        value_title="Value (ETH)",
        data=counterparties_chart_data,
    )
    if chart:
        charts.append(chart)

    severity_chart = _build_severity_chart(
        alerts,
        key="wallet_alert_severity",
        title="Alert Severity Mix",
        description="Counts of alerts grouped by severity levels.",
    )
    if severity_chart:
        charts.append(severity_chart)

    risk_scores = metrics_payload.get("risk_scores") or []
    risk_chart_data: list[Dict[str, Any]] = []
    for item in _safe_top(risk_scores):
        address = item.get("address") or "n/a"
        score_value = _coerce_float(item.get("score"))
        if score_value is None:
            continue
        risk_chart_data.append({"address": address, "score": score_value})
    chart = _build_bar_chart(
        key="wallet_risk_scores",
        title="Wallet Risk Scores",
        description="Top wallet risk scores (0-100 scale).",
        label_field="address",
        value_field="score",
        label_title="Address",
        value_title="Risk score",
        data=_safe_top(risk_chart_data, MAX_METRIC_PREVIEW),
    )
    if chart:
        charts.append(chart)

    baselines = metrics_payload.get("baselines") or []
    baseline_chart_data: list[Dict[str, Any]] = []
    for item in _safe_top(baselines):
        address = item.get("address") or "n/a"
        transfer_count = _coerce_int(item.get("transfer_count"))
        total_volume = _coerce_float(item.get("total_volume"))
        if transfer_count is None:
            continue
        baseline_chart_data.append(
            {
                "address": address,
                "transfers": transfer_count,
                "volume_eth": (total_volume or 0.0) / WEI_PER_ETH,
            }
        )
    transfer_chart = _build_bar_chart(
        key="wallet_transfer_counts",
        title="Transfer Counts",
        description="Total transfers observed per wallet in scope.",
        label_field="address",
        value_field="transfers",
        label_title="Address",
        value_title="Transfer count",
        data=_safe_top(baseline_chart_data, MAX_METRIC_PREVIEW),
    )
    if transfer_chart:
        charts.append(transfer_chart)

    volume_chart = _build_bar_chart(
        key="wallet_volume_eth",
        title="Aggregate Volume (ETH)",
        description="Total transfer volume converted from wei to ETH.",
        label_field="address",
        value_field="volume_eth",
        label_title="Address",
        value_title="Volume (ETH)",
        data=_safe_top(baseline_chart_data, MAX_METRIC_PREVIEW),
    )
    if volume_chart:
        charts.append(volume_chart)

    payload = {
        "narrative": "\n".join(lines),
        "charts": charts,
        "summary": summary,
        "alerts": _summarize_alerts(alerts),
        "metrics": _limit_metrics(metrics_payload, MAX_METRIC_PREVIEW),
    }
    return _finalize_response(payload)


def event_logs(
    *,
    contract: str,
    start_block: int | str,
    end_block: int | str,
    topic0: str = ERC20_TRANSFER_TOPIC,
    options: Mapping[str, Any] | None = None,
) -> str:
    if not contract:
        raise ValueError("'contract' is required")

    start = _maybe_int(start_block)
    end = _maybe_int(end_block)
    if end < start:
        raise ValueError("'end_block' must be greater than or equal to 'start_block'")

    event_options = _options_from_payload(EventAnalysisOptions, options)
    result = analyze_event_logs(
        contract,
        topic0=topic0 or ERC20_TRANSFER_TOPIC,
        start_block=start,
        end_block=end,
        options=event_options,
    )

    summary = result.get("summary", {})
    lines = [
        "Contract Event Findings:",
        f"• Contract: {contract}",
        f"• Blocks scanned: {start} → {end}",
        f"• Verdict: {summary.get('verdict', 'unknown')} (severity {summary.get('severity', 'n/a')})",
        f"• Logs analysed: {_human(summary.get('total_logs'))}",
    ]

    alerts = result.get("alerts", []) or []
    lines.extend(_format_alerts(alerts))
    metrics_payload = result.get("metrics", {}) or {}
    metric_lines = _format_event_metrics(metrics_payload)
    if metric_lines:
        lines.append("")
        lines.extend(metric_lines)

    method_lines = _format_methods(PERSONA_METHODS_EVENT)
    if method_lines:
        lines.append("")
        lines.extend(method_lines)

    lines.append("")
    lines.append(
        "Investigator guidance: inspect the most severe alerts, compare against historical baselines, "
        "and determine whether anomalies repeat across contiguous block ranges."
    )

    charts: list[Dict[str, Any]] = []
    baselines = metrics_payload.get("baselines") or []
    baselines = metrics_payload.get("baselines") or []
    baseline_chart_data: list[Dict[str, Any]] = []
    for item in _safe_top(baselines):
        address = item.get("address") or "n/a"
        transfers = _coerce_int(item.get("transfer_count"))
        total_volume = _coerce_float(item.get("total_volume"))
        if transfers is None or total_volume is None:
            continue
        baseline_chart_data.append(
            {
                "address": address,
                "transfers": transfers,
                "volume_eth": total_volume / WEI_PER_ETH,
            }
        )
    transfer_chart = _build_bar_chart(
        key="event_transfer_counts",
        title="Event Transfer Counts",
        description="Decoded transfers per address during the scan.",
        label_field="address",
        value_field="transfers",
        label_title="Address",
        value_title="Transfers",
        data=_safe_top(baseline_chart_data, MAX_METRIC_PREVIEW),
    )
    if transfer_chart:
        charts.append(transfer_chart)

    volume_chart = _build_bar_chart(
        key="event_volume_eth",
        title="Event Volume (ETH)",
        description="Total transfer volume converted from wei to ETH per address.",
        label_field="address",
        value_field="volume_eth",
        label_title="Address",
        value_title="Volume (ETH)",
        data=_safe_top(baseline_chart_data, MAX_METRIC_PREVIEW),
    )
    if volume_chart:
        charts.append(volume_chart)

    payload = {
        "narrative": "\n".join(lines),
        "charts": charts,
        "summary": summary,
        "alerts": _summarize_alerts(alerts),
        "metrics": _limit_metrics(metrics_payload, MAX_METRIC_PREVIEW),
    }
    return _finalize_response(payload)


def swap_events(
    *,
    pool_address: str,
    topic0: str,
    start_block: int | str,
    end_block: int | str,
    options: Mapping[str, Any] | None = None,
) -> str:
    if not pool_address:
        raise ValueError("'pool_address' is required")
    if not topic0:
        raise ValueError("'topic0' is required for swap event analysis")

    start = _maybe_int(start_block)
    end = _maybe_int(end_block)
    if end < start:
        raise ValueError("'end_block' must be greater than or equal to 'start_block'")

    swap_options = _options_from_payload(SwapAnalysisOptions, options)
    result = analyze_swap_events(
        pool_address,
        topic0=topic0,
        start_block=start,
        end_block=end,
        options=swap_options,
    )

    summary = result.get("summary", {})
    alerts = result.get("alerts", []) or []

    lines = [
        "Swap Surveillance Report:",
        f"• Pool: {pool_address}",
        f"• Blocks scanned: {start} → {end}",
        f"• Verdict: {summary.get('verdict', 'unknown')} (severity {summary.get('severity', 'n/a')})",
        f"• Logs analysed: {_human(summary.get('total_logs'))}",
    ]

    lines.extend(_format_alerts(alerts))
    method_lines = _format_methods(PERSONA_METHODS_SWAP)
    if method_lines:
        lines.append("")
        lines.extend(method_lines)

    lines.append("")
    lines.append(
        "Investigator guidance: focus on large price-impact moves and repeated counterparty loops, "
        "then cross-reference implicated wallets with broader risk scores."
    )

    charts: list[Dict[str, Any]] = []

    price_alerts = [alert for alert in alerts if alert.get("type") == "price_impact"]
    price_chart_data: list[Dict[str, Any]] = []
    for alert in _safe_top(price_alerts):
        details = alert.get("details") or {}
        delta = _coerce_float(details.get("delta_bps"))
        if delta is None:
            continue
        participants = details.get("participants") or []
        if isinstance(participants, str):
            label = participants
        elif isinstance(participants, Sequence):
            label = ", ".join(str(item) for item in participants[:2])
        else:
            label = None
        if not label:
            label = alert.get("address") or details.get("pool") or "n/a"
        price_chart_data.append(
            {
                "label": label,
                "delta_bps": delta,
            }
        )
    chart = _build_chart(
        key="swap_price_impact",
        title="Swap Price Impact Alerts",
        description="Magnitude of detected price swings (basis points).",
        mark={"type": "bar", "tooltip": True},
        encoding={
            "x": {
                "field": "label",
                "type": "nominal",
                "title": "Participants",
            },
            "y": {
                "field": "delta_bps",
                "type": "quantitative",
                "title": "Δ price (bps)",
            },
            "tooltip": [
                {"field": "label", "type": "nominal", "title": "Participants"},
                {
                    "field": "delta_bps",
                    "type": "quantitative",
                    "title": "Δ price (bps)",
                },
            ],
        },
        data=price_chart_data,
    )
    if chart:
        charts.append(chart)

    wash_alerts = [alert for alert in alerts if alert.get("type") == "wash_trade"]
    wash_chart_data: list[Dict[str, Any]] = []
    for alert in _safe_top(wash_alerts):
        details = alert.get("details") or {}
        swaps = _coerce_int(details.get("swaps"))
        if swaps is None:
            continue
        participants = details.get("participants") or []
        if isinstance(participants, str):
            label = participants
        elif isinstance(participants, Sequence):
            label = ", ".join(str(item) for item in participants[:2])
        else:
            label = None
        if not label:
            label = alert.get("address") or "n/a"
        wash_chart_data.append(
            {
                "label": label,
                "swaps": swaps,
            }
        )
    chart = _build_chart(
        key="swap_wash_trades",
        title="Suspected Wash Trades",
        description="Number of rapid swaps between the same counterparties.",
        mark={"type": "bar", "tooltip": True},
        encoding={
            "x": {
                "field": "label",
                "type": "nominal",
                "title": "Participants",
            },
            "y": {
                "field": "swaps",
                "type": "quantitative",
                "title": "Swap count",
            },
            "tooltip": [
                {"field": "label", "type": "nominal", "title": "Participants"},
                {
                    "field": "swaps",
                    "type": "quantitative",
                    "title": "Swaps",
                },
            ],
        },
        data=wash_chart_data,
    )
    if chart:
        charts.append(chart)

    payload: Dict[str, Any] = {
        "narrative": "\n".join(lines),
        "charts": charts,
        "summary": summary,
        "alerts": _summarize_alerts(alerts),
    }
    raw_payload = result.get("raw")
    if raw_payload:
        payload["raw"] = raw_payload

    return _finalize_response(payload)


def transaction_analysis(
    *,
    tx_hash: str,
    from_block: int | str = 0,
    options: Mapping[str, Any] | None = None,
) -> str:
    normalized_hash = _normalize_tx_hash(tx_hash)
    start_block = _maybe_int(from_block)
    tx_options = _options_from_payload(TransactionAnalysisOptions, options)
    result = analyze_transaction(
        normalized_hash,
        from_block=start_block,
        options=tx_options,
    )

    summary = result.get("summary", {})
    lines = [
        "Transaction Risk Summary:",
        f"• Hash: {normalized_hash}",
        f"• Verdict: {summary.get('verdict', 'unknown')} (severity {summary.get('severity', 'n/a')})",
        f"• Transactions inspected: {_human(summary.get('total_transactions'))}",
    ]

    alerts = result.get("alerts", []) or []
    lines.extend(_format_alerts(alerts))
    data_payload = result.get("data", []) or []
    data_lines = _format_transaction_data(data_payload)
    if data_lines:
        lines.append("")
        lines.extend(data_lines)

    method_lines = _format_methods(PERSONA_METHODS_TX)
    if method_lines:
        lines.append("")
        lines.extend(method_lines)

    lines.append("")
    lines.append(
        "Investigator guidance: verify the flagged selectors, confirm counterparties against watchlists, "
        "and trace related transfers for wider exposure."
    )

    charts: list[Dict[str, Any]] = []
    flagged_records = [
        item for item in _safe_top(data_payload) if item.get("risk_flags")
    ]
    tx_chart_data: list[Dict[str, Any]] = []
    for item in flagged_records:
        value = _coerce_float(item.get("value"))
        if value is None:
            continue
        tx_chart_data.append(
            {
                "hash": item.get("hash") or item.get("transaction_hash") or "n/a",
                "value": value,
                "method": item.get("method") or item.get("selector") or "n/a",
            }
        )
    chart = _build_chart(
        key="transaction_values",
        title="Flagged Transaction Values",
        description="Value of risk-flagged transactions (wei).",
        mark={"type": "bar", "tooltip": True},
        encoding={
            "x": {
                "field": "hash",
                "type": "nominal",
                "title": "Transaction",
                "sort": "-y",
            },
            "y": {
                "field": "value",
                "type": "quantitative",
                "title": "Value (wei)",
                "scale": {"type": "symlog"},
            },
            "tooltip": [
                {"field": "hash", "type": "nominal", "title": "Transaction"},
                {
                    "field": "value",
                    "type": "quantitative",
                    "title": "Value (wei)",
                },
                {"field": "method", "type": "nominal", "title": "Method"},
            ],
        },
        data=tx_chart_data,
    )
    if chart:
        charts.append(chart)

    payload = {
        "narrative": "\n".join(lines),
        "charts": charts,
        "summary": summary,
        "alerts": _summarize_alerts(alerts),
        "data": _limit_records(data_payload, MAX_DATA_PREVIEW),
    }
    return _finalize_response(payload)


__all__ = [
    "wallet_activity",
    "event_logs",
    "swap_events",
    "transaction_analysis",
]
