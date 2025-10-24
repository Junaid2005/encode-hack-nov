from typing import Any, Dict, List, Tuple
from collections import defaultdict

from .schemas import ProcessedResponse, Aggregates, AnalyzeResponse, AnalysisFindings
from .config import Settings


def _extract_input_fields(rec: Dict[str, Any]) -> Tuple[str | None, float, str | None]:
    """Extract (asset_id, amount, address) from a HyperSync record.

    Defensive conversions ensure robustness to missing or malformed fields.
    """
    input_obj = rec.get("input", {}) if isinstance(rec, dict) else {}
    asset_id = None
    address = None
    amount_val = 0.0

    if isinstance(input_obj, dict):
        asset_id = input_obj.get("asset_id")
        address = input_obj.get("address")
        amount = input_obj.get("amount", 0)
        try:
            amount_val = float(amount)
        except (TypeError, ValueError):
            amount_val = 0.0
    return asset_id, amount_val, address


def process_data(data: List[Dict[str, Any]], sample_size: int = 10) -> ProcessedResponse:
    by_asset: Dict[str, float] = defaultdict(float)
    by_address: Dict[str, float] = defaultdict(float)
    tx_count_by_address: Dict[str, int] = defaultdict(int)
    total_amount: float = 0.0

    for rec in data:
        asset_id, amount, address = _extract_input_fields(rec)
        total_amount += amount
        if asset_id:
            by_asset[asset_id] += amount
        if address:
            by_address[address] += amount
            tx_count_by_address[address] += 1

    aggregates = Aggregates(
        total_amount=total_amount,
        by_asset=dict(by_asset),
        by_address=dict(by_address),
        tx_count_by_address=dict(tx_count_by_address),
    )
    sample = data[: max(0, min(sample_size, len(data)))]
    return ProcessedResponse(
        total_records=len(data),
        aggregates=aggregates,
        sample=sample,
    )


def analyze_data(
    data: List[Dict[str, Any]],
    processed: ProcessedResponse,
    settings: Settings,
) -> AnalyzeResponse:
    findings = AnalysisFindings()

    # 1) Large transfers
    for rec in data:
        asset_id, amount, address = _extract_input_fields(rec)
        if amount >= settings.large_transfer_threshold:
            findings.large_transfers.append(
                {
                    "tx_id": rec.get("tx_id"),
                    "asset_id": asset_id,
                    "address": address,
                    "amount": amount,
                    "block_height": rec.get("block_height"),
                }
            )

    # 2) High-frequency addresses
    for addr, count in processed.aggregates.tx_count_by_address.items():
        if count >= settings.high_frequency_threshold:
            findings.high_frequency_addresses.append(
                {
                    "address": addr,
                    "tx_count": count,
                }
            )

    # 3) Concentration risks
    total_amount = processed.aggregates.total_amount or 0.0
    if total_amount > 0:
        for addr, amt in processed.aggregates.by_address.items():
            share = amt / total_amount
            if share >= settings.concentration_share_threshold:
                findings.concentration_risks.append(
                    {
                        "address": addr,
                        "amount": amt,
                        "share": round(share, 4),
                    }
                )

    summary_parts: List[str] = []
    if findings.large_transfers:
        summary_parts.append(f"{len(findings.large_transfers)} large transfer(s)")
    if findings.high_frequency_addresses:
        summary_parts.append(
            f"{len(findings.high_frequency_addresses)} high-frequency address(es)"
        )
    if findings.concentration_risks:
        summary_parts.append(
            f"{len(findings.concentration_risks)} concentration risk(s)"
        )
    summary = (
        "Detected: " + "; ".join(summary_parts) + "."
        if summary_parts
        else "No notable anomalies detected by heuristic rules."
    )

    return AnalyzeResponse(findings=findings, summary=summary)

