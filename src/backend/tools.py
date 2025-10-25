from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence

from .fraud_detection import (
    ERC20_TRANSFER_TOPIC,
    analyze_swap_price_impact,
    collect_wallet_activity,
    compute_address_centrality,
    compute_rolling_trends,
    compute_wallet_baselines,
    decode_transaction_methods,
    detect_large_transfers,
    detect_suspicious_patterns,
    detect_swap_wash_trades,
    detect_value_anomalies,
    fetch_event_logs,
    fetch_swap_events,
    fetch_transaction_by_hash,
    label_transaction_risk,
    score_wallet_activity,
    summarize_counterparties,
)

SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2}
SEVERITY_DEFAULTS = {
    "value_anomaly": "medium",
    "large_transfer": "high",
    "centrality": "medium",
    "trend": "high",
    "heuristic": "medium",
    "price_impact": "high",
    "wash_trade": "high",
    "transaction_risk": "medium",
}


def _sanitize_large_ints(obj: Any) -> Any:
    limit = 2**63 - 1
    if isinstance(obj, dict):
        return {key: _sanitize_large_ints(value) for key, value in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_large_ints(item) for item in obj]
    if isinstance(obj, int) and abs(obj) > limit:
        return str(obj)
    return obj


def _generate_alert_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _filter_suspicious_patterns(
    patterns: Sequence[Mapping[str, Any]],
    *,
    include_self_transfers: bool,
    include_zero_value: bool,
) -> List[Dict[str, Any]]:
    filtered: List[Dict[str, Any]] = []
    for finding in patterns:
        finding_type = finding.get("type")
        if finding_type == "self_transfer" and include_self_transfers:
            filtered.append(dict(finding))
        elif finding_type == "zero_value" and include_zero_value:
            filtered.append(dict(finding))
    return filtered


@dataclass
class WalletAnalysisOptions:
    z_threshold: float = 2.0
    large_transfer_threshold: int = int(1e18)
    min_centrality_degree: int = 3
    include_self_transfers: bool = True
    include_zero_value: bool = True
    baseline_window: int = 20
    trend_window: int = 30
    trend_z_threshold: float = 3.0
    trend_cusum_limit: float = 5.0


@dataclass
class EventAnalysisOptions:
    z_threshold: float = 2.0
    large_transfer_threshold: int = int(1e18)
    min_centrality_degree: int = 3
    baseline_window: int = 20
    trend_window: int = 30
    trend_z_threshold: float = 3.0
    trend_cusum_limit: float = 5.0
    include_self_transfers: bool = True
    include_zero_value: bool = True


@dataclass
class SwapAnalysisOptions:
    min_price_delta_bps: float = 50.0
    min_notional: Optional[int] = None
    wash_trade_threshold: int = 3


@dataclass
class TransactionAnalysisOptions:
    decode_methods: bool = True
    large_value_threshold: int = int(1e20)
    watchlist: Sequence[str] = field(default_factory=list)


def analyze_wallet_activity(
    addresses: Sequence[str],
    *,
    from_block: int = 0,
    transfer_topic: str = ERC20_TRANSFER_TOPIC,
    options: Optional[WalletAnalysisOptions] = None,
) -> Dict[str, Any]:
    opts = options or WalletAnalysisOptions()
    result = collect_wallet_activity(
        addresses,
        from_block=from_block,
        transfer_topic=transfer_topic,
    )

    decoded_events = result.get("decoded_logs", []) or []
    normalized_addresses = [addr.lower() for addr in addresses]

    anomalies = detect_value_anomalies(
        decoded_events, z_threshold=float(opts.z_threshold)
    )
    large_transfers = detect_large_transfers(
        decoded_events, min_value=int(opts.large_transfer_threshold)
    )
    centrality = compute_address_centrality(
        decoded_events, min_degree=int(opts.min_centrality_degree)
    )
    suspicious_patterns = detect_suspicious_patterns(decoded_events)
    filtered_patterns = _filter_suspicious_patterns(
        suspicious_patterns,
        include_self_transfers=opts.include_self_transfers,
        include_zero_value=opts.include_zero_value,
    )
    baselines = compute_wallet_baselines(
        decoded_events,
        normalized_addresses,
        window_size=int(opts.baseline_window),
    )
    trend_alerts = compute_rolling_trends(
        decoded_events,
        window=int(opts.trend_window),
        z_threshold=float(opts.trend_z_threshold),
        cusum_limit=float(opts.trend_cusum_limit),
        include_addresses=normalized_addresses,
    )
    risk_scores = score_wallet_activity(
        addresses,
        anomalies,
        large_transfers,
        centrality,
    )
    counterparties = summarize_counterparties(decoded_events, addresses)

    alerts = []
    for category, payload in [
        ("value_anomaly", anomalies),
        ("large_transfer", large_transfers),
        ("centrality", centrality),
        ("trend", trend_alerts),
        ("heuristic", filtered_patterns),
    ]:
        for item in payload:
            alerts.append(
                {
                    "id": _generate_alert_id(category),
                    "type": category,
                    "address": (
                        item.get("address")
                        if isinstance(item, Mapping)
                        else item.get("event", {}).get("indexed", [None])[0]
                    ),
                    "severity": item.get(
                        "severity", SEVERITY_DEFAULTS.get(category, "medium")
                    ),
                    "verdict": item.get("verdict", "suspected_fraud"),
                    "details": _sanitize_large_ints(item),
                }
            )

    max_severity = max(
        [SEVERITY_RANK.get(alert.get("severity", "low"), 0) for alert in alerts] or [0]
    )
    severity_label = [k for k, v in SEVERITY_RANK.items() if v == max_severity]
    severity_label = severity_label[0] if severity_label else "low"
    verdict = "clear" if not alerts else "suspected_fraud"

    response = {
        "summary": {
            "addresses": list(addresses),
            "next_block": result.get("next_block"),
            "archive_height": result.get("archive_height"),
            "total_logs": len(result.get("logs", [])),
            "total_transactions": len(result.get("transactions", [])),
            "verdict": verdict,
            "severity": severity_label,
        },
        "alerts": alerts,
        "metrics": {
            "baselines": _sanitize_large_ints(baselines),
            "risk_scores": _sanitize_large_ints(risk_scores),
            "counterparties": _sanitize_large_ints(counterparties),
        },
        "raw": _sanitize_large_ints(result),
    }
    return response


def analyze_event_logs(
    contract: str,
    *,
    topic0: str = ERC20_TRANSFER_TOPIC,
    start_block: int,
    end_block: int,
    options: Optional[EventAnalysisOptions] = None,
) -> Dict[str, Any]:
    opts = options or EventAnalysisOptions()
    result = fetch_event_logs(
        contract,
        topic0=topic0,
        start_block=start_block,
        end_block=end_block,
    )

    decoded_events = result.get("decoded_logs") or []
    anomalies = detect_value_anomalies(
        decoded_events, z_threshold=float(opts.z_threshold)
    )
    large_transfers = detect_large_transfers(
        decoded_events, min_value=int(opts.large_transfer_threshold)
    )
    centrality = compute_address_centrality(
        decoded_events, min_degree=int(opts.min_centrality_degree)
    )
    suspicious_patterns = detect_suspicious_patterns(decoded_events)
    filtered_patterns = _filter_suspicious_patterns(
        suspicious_patterns,
        include_self_transfers=opts.include_self_transfers,
        include_zero_value=opts.include_zero_value,
    )
    baselines = compute_wallet_baselines(
        decoded_events,
        window_size=int(opts.baseline_window),
    )
    trend_alerts = compute_rolling_trends(
        decoded_events,
        window=int(opts.trend_window),
        z_threshold=float(opts.trend_z_threshold),
        cusum_limit=float(opts.trend_cusum_limit),
    )

    alerts = []
    for category, payload in [
        ("value_anomaly", anomalies),
        ("large_transfer", large_transfers),
        ("centrality", centrality),
        ("trend", trend_alerts),
        ("heuristic", filtered_patterns),
    ]:
        for item in payload:
            alerts.append(
                {
                    "id": _generate_alert_id(category),
                    "type": category,
                    "address": (
                        item.get("address") if isinstance(item, Mapping) else None
                    ),
                    "severity": item.get(
                        "severity", SEVERITY_DEFAULTS.get(category, "medium")
                    ),
                    "verdict": item.get("verdict", "suspected_fraud"),
                    "details": _sanitize_large_ints(item),
                }
            )

    max_severity = max(
        [SEVERITY_RANK.get(alert.get("severity", "low"), 0) for alert in alerts] or [0]
    )
    severity_label = [k for k, v in SEVERITY_RANK.items() if v == max_severity]
    severity_label = severity_label[0] if severity_label else "low"
    verdict = "clear" if not alerts else "suspected_fraud"

    response = {
        "summary": {
            "contract": contract,
            "topic0": topic0,
            "next_block": result.get("next_block"),
            "archive_height": result.get("archive_height"),
            "total_logs": len(result.get("logs", [])),
            "verdict": verdict,
            "severity": severity_label,
        },
        "alerts": alerts,
        "metrics": {
            "baselines": _sanitize_large_ints(baselines),
        },
        "raw": _sanitize_large_ints(result),
    }
    return response


def analyze_swap_events(
    pool_address: str,
    *,
    topic0: str,
    start_block: int,
    end_block: int,
    options: Optional[SwapAnalysisOptions] = None,
) -> Dict[str, Any]:
    opts = options or SwapAnalysisOptions()
    result = fetch_swap_events(
        pool_address,
        topic0=topic0,
        start_block=start_block,
        end_block=end_block,
    )
    decoded_logs = result.get("decoded_logs") or []

    price_impacts = analyze_swap_price_impact(
        decoded_logs,
        min_price_delta_bps=float(opts.min_price_delta_bps),
        min_notional=opts.min_notional,
    )
    wash_trades = detect_swap_wash_trades(
        decoded_logs,
        max_swaps=int(opts.wash_trade_threshold),
    )

    alerts = []
    for category, payload in [
        ("price_impact", price_impacts),
        ("wash_trade", wash_trades),
    ]:
        for item in payload:
            alerts.append(
                {
                    "id": _generate_alert_id(category),
                    "type": category,
                    "address": (
                        item.get("participants", [None])[0]
                        if isinstance(item, Mapping)
                        else None
                    ),
                    "severity": item.get(
                        "severity", SEVERITY_DEFAULTS.get(category, "high")
                    ),
                    "verdict": item.get("verdict", "suspected_fraud"),
                    "details": _sanitize_large_ints(item),
                }
            )

    max_severity = max(
        [SEVERITY_RANK.get(alert.get("severity", "low"), 0) for alert in alerts] or [0]
    )
    severity_label = [k for k, v in SEVERITY_RANK.items() if v == max_severity]
    severity_label = severity_label[0] if severity_label else "low"
    verdict = "clear" if not alerts else "suspected_fraud"

    response = {
        "summary": {
            "pool_address": pool_address,
            "topic0": topic0,
            "next_block": result.get("next_block"),
            "archive_height": result.get("archive_height"),
            "total_logs": len(result.get("logs", [])),
            "verdict": verdict,
            "severity": severity_label,
        },
        "alerts": alerts,
        "raw": _sanitize_large_ints(result),
    }
    return response


def analyze_transaction(
    tx_hash: str,
    *,
    from_block: int = 0,
    options: Optional[TransactionAnalysisOptions] = None,
) -> Dict[str, Any]:
    opts = options or TransactionAnalysisOptions()
    result = fetch_transaction_by_hash(tx_hash, from_block=from_block)
    transactions = result.get("transactions", []) or []

    decoded = (
        decode_transaction_methods(transactions)
        if opts.decode_methods
        else transactions
    )
    enriched = label_transaction_risk(
        decoded,
        watchlist=opts.watchlist,
        large_value_threshold=int(opts.large_value_threshold),
    )

    alerts = []
    for item in enriched:
        if not item.get("risk_flags"):
            continue
        severity = "high" if "large_value" in item.get("risk_flags", []) else "medium"
        alerts.append(
            {
                "id": _generate_alert_id("transaction_risk"),
                "type": "transaction_risk",
                "address": item.get("from") or item.get("from_"),
                "severity": severity,
                "verdict": "suspected_fraud",
                "details": _sanitize_large_ints(item),
            }
        )

    max_severity = max(
        [SEVERITY_RANK.get(alert.get("severity", "low"), 0) for alert in alerts] or [0]
    )
    severity_label = [k for k, v in SEVERITY_RANK.items() if v == max_severity]
    severity_label = severity_label[0] if severity_label else "low"
    verdict = "clear" if not alerts else "suspected_fraud"

    response = {
        "summary": {
            "tx_hash": tx_hash,
            "next_block": result.get("next_block"),
            "archive_height": result.get("archive_height"),
            "total_transactions": len(transactions),
            "verdict": verdict,
            "severity": severity_label,
        },
        "alerts": alerts,
        "data": _sanitize_large_ints(enriched),
        "raw": _sanitize_large_ints(result),
    }
    return response
