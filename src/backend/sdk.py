"""SDK-style facade for using the backend from Streamlit (no web server required).

Usage in Streamlit (example):

    from src.backend.sdk import fetch_data, process_data, analyze_data, query_and_analyze

    query = {
        "from_block": 0,
        "to_block": 1300000,
        "inputs": [{"asset_id": ["0x..."]}],
        "field_selection": {"input": [
            "block_height", "tx_id", "input.asset_id", "input.amount", "input.address"
        ]},
    }

    data = fetch_data(query)
    processed = process_data(data)
    analysis = analyze_data(data)
    combined = query_and_analyze(query)

Environment variables: see src.backend.config.Settings for all available options.
"""
from typing import Any, Dict, Iterable, List, Optional

from .config import Settings, get_settings
from .dal import HyperSyncClient
from .schemas import CombinedResponse, ProcessedResponse, AnalyzeResponse
from .service import process_data as _process_data_impl, analyze_data as _analyze_data_impl
from .models import Transaction, Address, Case
from .case_management import (
    create_case as _create_case,
    list_cases as _list_cases,
    get_case as _get_case,
    add_addresses as _add_addresses,
    add_transactions as _add_transactions,
)

__all__ = [
    "fetch_data",
    "process_data",
    "analyze_data",
    "query_and_analyze",
    "build_query_for_address",
    # convenience fetchers
    "fetch_transactions",
    "fetch_addresses",
    "fetch_blocks",
    "fetch_logs",
    "fetch_token_transfers",
    "fetch_traces",
    "fetch_internal_transactions",
    "fetch_receipts",
    "fetch_deployments",
    # case mgmt
    "create_case",
    "list_cases",
    "get_case",
    "add_case_addresses",
    "add_case_transactions",
]


def _get_client(settings: Optional[Settings] = None) -> HyperSyncClient:
    settings = settings or get_settings()
    return HyperSyncClient(settings)


def fetch_data(query: Dict[str, Any], *, settings: Optional[Settings] = None) -> List[Dict[str, Any]]:
    """Fetch raw records from HyperSync using the provided query dict."""
    client = _get_client(settings)
    return client.query(query)


def process_data(data: List[Dict[str, Any]], *, sample_size: int = 10) -> ProcessedResponse:
    """Aggregate and summarize raw records (format-independent heuristics)."""
    return _process_data_impl(data, sample_size=sample_size)


def analyze_data(
    data: List[Dict[str, Any]], *, settings: Optional[Settings] = None, sample_size: int = 10
) -> AnalyzeResponse:
    """Run heuristic analysis on records. Internally uses process_data first."""
    settings = settings or get_settings()
    processed = _process_data_impl(data, sample_size=sample_size)
    return _analyze_data_impl(data, processed, settings)


def query_and_analyze(
    query: Dict[str, Any], *, settings: Optional[Settings] = None, sample_size: int = 10
) -> CombinedResponse:
    """End-to-end: fetch -> process -> analyze.

    Returns a CombinedResponse containing both processed aggregates and analysis findings.
    """
    settings = settings or get_settings()
    data = fetch_data(query, settings=settings)
    processed = _process_data_impl(data, sample_size=sample_size)
    analysis = _analyze_data_impl(data, processed, settings)
    return CombinedResponse(processed=processed, analysis=analysis)


def build_query_for_address(
    address: str,
    *,
    from_block: int = 0,
    to_block: int = 1_300_000,
) -> Dict[str, Any]:
    """Helper to create a HyperSync query focused on an address.

    Note: Adjust field_selection based on the network schema you target.
    """
    return {
        "from_block": from_block,
        "to_block": to_block,
        "inputs": [{"address": [address]}],
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


# --- Convenience fetchers mapped to common selections ---

def fetch_transactions(address: str, start_block: int, end_block: int) -> List[Dict[str, Any]]:
    """Fetch transactions involving the address either as sender or recipient.

    Uses two transaction selections (OR): one for 'from', one for 'to'.
    """
    query: Dict[str, Any] = {
        "from_block": start_block,
        "to_block": end_block,
        "transactions": [
            {"from": [address]},
            {"to": [address]},
        ],
        "field_selection": {
            "transaction": [
                "hash",
                "block_number",
                "from",
                "to",
                "value",
                "status",
                "gas",
                "gas_price",
                "max_fee_per_gas",
                "max_priority_fee_per_gas",
                "type",
                "contract_address",
            ],
            "block": ["timestamp"],
        },
    }
    return fetch_data(query)


def fetch_addresses(transaction_hash: str) -> List[Dict[str, Any]]:
    """Fetch transaction summary (hash, from, to) for a specific transaction.

    Note: Assumes the backend supports selecting transactions by hash. If not,
    this should be adapted with an appropriate narrowing strategy.
    """
    query: Dict[str, Any] = {
        "transactions": [
            {"hash": [transaction_hash]}
        ],
        "field_selection": {
            "transaction": ["hash", "from", "to", "value", "status", "gas_used"],
            "block": ["number", "timestamp"],
        },
    }
    return fetch_data(query)


def fetch_blocks(block_number: int) -> List[Dict[str, Any]]:
    """Fetch a single block by number using include_all_blocks over a 1-block range."""
    query: Dict[str, Any] = {
        "from_block": block_number,
        "to_block": block_number + 1,
        "include_all_blocks": True,
        "field_selection": {
            "block": [
                "number",
                "hash",
                "parent_hash",
                "timestamp",
                "miner",
                "gas_limit",
                "gas_used",
                "base_fee_per_gas",
            ]
        },
    }
    return fetch_data(query)


def fetch_logs(contract_address: str, from_block: int, to_block: int, topic0: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetch logs for a contract, optionally filtering by the first topic (event signature)."""
    topics = [[topic0]] if topic0 else []
    query: Dict[str, Any] = {
        "from_block": from_block,
        "to_block": to_block,
        "logs": [
            {
                "address": [contract_address],
                "topics": topics,
            }
        ],
        "field_selection": {
            "log": [
                "address",
                "data",
                "topic0",
                "topic1",
                "topic2",
                "topic3",
                "log_index",
            ],
            "transaction": ["hash", "from", "to"],
            "block": ["number", "timestamp"],
        },
    }
    return fetch_data(query)


# --- Additional helpers ---

_TRANSFER_TOPIC0 = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"


def _topic_from_address(address: str) -> str:
    """Pad an EVM address to a 32-byte topic value (0x + 64 hex chars)."""
    if not address:
        return ""
    a = address.lower().removeprefix("0x")
    a = a.strip()
    # ensure only hex chars
    try:
        int(a, 16)
    except ValueError:
        raise ValueError("Address must be hex string")
    padded = "0x" + ("0" * (64 - len(a))) + a
    return padded


def fetch_token_transfers(
    *,
    contract_address: Optional[str] = None,
    from_holder: Optional[str] = None,
    to_holder: Optional[str] = None,
    start_block: int,
    end_block: int,
) -> List[Dict[str, Any]]:
    """Fetch ERC-20/721 Transfer events, optionally filtered by holder(s)/contract.

    Uses logs with topic0=Transfer and optional topic1/2 address filters.
    """
    topics: List[List[str]] = [[_TRANSFER_TOPIC0]]
    # topic1 = from, topic2 = to
    if from_holder:
        topics.append([_topic_from_address(from_holder)])
    else:
        topics.append([])
    if to_holder:
        topics.append([_topic_from_address(to_holder)])
    else:
        topics.append([])

    logs_sel: Dict[str, Any] = {"topics": topics}
    if contract_address:
        logs_sel["address"] = [contract_address]

    query: Dict[str, Any] = {
        "from_block": start_block,
        "to_block": end_block,
        "logs": [logs_sel],
        "field_selection": {
            "log": [
                "address",
                "data",
                "topic0",
                "topic1",
                "topic2",
                "log_index",
            ],
            "transaction": ["hash", "from", "to"],
            "block": ["number", "timestamp"],
        },
    }
    return fetch_data(query)


def fetch_traces(
    *,
    from_addr: Optional[str] = None,
    to_addr: Optional[str] = None,
    call_types: Optional[List[str]] = None,
    start_block: int,
    end_block: int,
) -> List[Dict[str, Any]]:
    """Fetch internal transaction traces (call/create/suicide/reward).

    Filters by from/to/call_type if provided.
    """
    trace_sel: Dict[str, Any] = {}
    if from_addr:
        trace_sel["from"] = [from_addr]
    if to_addr:
        trace_sel["to"] = [to_addr]
    if call_types:
        trace_sel["call_type"] = call_types

    query: Dict[str, Any] = {
        "from_block": start_block,
        "to_block": end_block,
        "traces": [trace_sel or {}],
        "field_selection": {
            "trace": [
                "type",
                "call_type",
                "from",
                "to",
                "value",
                "gas",
                "gas_used",
                "input",
                "output",
            ],
            "transaction": ["hash"],
            "block": ["number", "timestamp"],
        },
    }
    return fetch_data(query)


def fetch_internal_transactions(
    *, from_addr: Optional[str] = None, to_addr: Optional[str] = None, start_block: int, end_block: int
) -> List[Dict[str, Any]]:
    """Fetch internal txs (trace type 'call')."""
    return fetch_traces(
        from_addr=from_addr,
        to_addr=to_addr,
        call_types=["call"],
        start_block=start_block,
        end_block=end_block,
    )


def fetch_receipts(
    *, tx_hash: Optional[str] = None, start_block: Optional[int] = None, end_block: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Fetch receipt-like data.

    If tx_hash is provided, query by hash. Otherwise, use block range (requires both start_block and end_block).
    """
    tx_sel: List[Dict[str, Any]]
    if tx_hash:
        tx_sel = [{"hash": [tx_hash]}]
    else:
        if start_block is None or end_block is None:
            raise ValueError("start_block and end_block required if tx_hash is not provided")
        # No specific filter; return receipts for range
        tx_sel = [{}]

    query: Dict[str, Any] = {
        "from_block": start_block or 0,
        "to_block": end_block or (start_block or 0) + 1,
        "transactions": tx_sel,
        "field_selection": {
            "transaction": [
                "hash",
                "status",
                "gas_used",
                "logs_bloom",
                "type",
                "block_number",
                "from",
                "to",
            ],
            "block": ["timestamp"],
        },
    }
    return fetch_data(query)


def fetch_deployments(
    *, start_block: int, end_block: int, sender: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Fetch contract deployments by scanning transactions where contract_address is set.

    Filters by sender (from) if provided; additional client-side filter ensures contract_address is not null.
    """
    tx_sel: Dict[str, Any] = {}
    if sender:
        tx_sel["from"] = [sender]

    query: Dict[str, Any] = {
        "from_block": start_block,
        "to_block": end_block,
        "transactions": [tx_sel or {}],
        "field_selection": {
            "transaction": [
                "hash",
                "from",
                "to",
                "contract_address",
                "type",
            ],
            "block": ["number", "timestamp"],
        },
    }
    results = fetch_data(query)
    # Client-side filter to only keep deployments
    return [r for r in results if (r.get("contract_address") or (r.get("transaction") or {}).get("contract_address"))]


# --- Case management (SQLite-backed) ---

def create_case(name: str, description: Optional[str] = None) -> Case:
    return _create_case(name, description)


def list_cases() -> List[Case]:
    return _list_cases()


def get_case(case_id: str) -> Optional[Case]:
    return _get_case(case_id)


def add_case_addresses(case_id: str, addresses: Iterable[str | Address]) -> int:
    """Add addresses to a case. Accepts raw strings or Address models."""
    addr_models: List[Address] = []
    for a in addresses:
        if isinstance(a, Address):
            addr_models.append(a)
        else:
            addr_models.append(Address(address=str(a)))
    return _add_addresses(case_id, addr_models)


def add_case_transactions(case_id: str, txs: Iterable[Dict[str, Any] | Transaction]) -> int:
    """Add transactions to a case. Accepts dicts or Transaction models."""
    tx_models: List[Transaction] = []
    for t in txs:
        if isinstance(t, Transaction):
            tx_models.append(t)
        else:
            # best-effort mapping from dict keys
            tx_models.append(
                Transaction(
                    tx_id=str(t.get("tx_id")),
                    block_height=t.get("block_height"),
                    asset_id=t.get("asset_id") or (t.get("input") or {}).get("asset_id"),
                    amount=float(t.get("amount", (t.get("input") or {}).get("amount", 0.0))),
                    address=(t.get("address") or (t.get("input") or {}).get("address")),
                )
            )
    return _add_transactions(case_id, tx_models)
