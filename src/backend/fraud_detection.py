from __future__ import annotations

import asyncio
import math
import statistics
from collections import defaultdict
from typing import Any, Dict, List, Mapping, Sequence, Tuple, cast

import hypersync
from hypersync import (
    BlockField,
    ClientConfig,
    FieldSelection,
    HexOutput,
    LogField,
    LogSelection,
    StreamConfig,
    TransactionField,
    TransactionSelection,
)

ERC20_TRANSFER_TOPIC = (
    "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
)
TRANSFER_EVENT_SIGNATURE = (
    "Transfer(address indexed from, address indexed to, uint256 value)"
)


def _address_to_topic(address: str) -> str:
    checksum = address.lower()
    return "0x000000000000000000000000" + checksum[2:]


def _transaction_to_dict(tx: Any) -> Dict[str, Any]:
    return {
        "block_number": getattr(tx, "block_number", None),
        "transaction_index": getattr(tx, "transaction_index", None),
        "hash": getattr(tx, "hash", None),
        "from": getattr(tx, "from_", None),
        "to": getattr(tx, "to", None),
        "value": getattr(tx, "value", None),
        "input": getattr(tx, "input", None),
    }


def _log_to_dict(log: Any) -> Dict[str, Any]:
    return {
        "block_number": getattr(log, "block_number", None),
        "log_index": getattr(log, "log_index", None),
        "transaction_hash": getattr(log, "transaction_hash", None),
        "transaction_index": getattr(log, "transaction_index", None),
        "address": getattr(log, "address", None),
        "data": getattr(log, "data", None),
        "topic0": getattr(log, "topic0", None),
        "topic1": getattr(log, "topic1", None),
        "topic2": getattr(log, "topic2", None),
        "topic3": getattr(log, "topic3", None),
    }


def _decoded_event_to_dict(event: Any) -> Dict[str, Any]:
    indexed = getattr(event, "indexed", []) or []
    body = getattr(event, "body", []) or []

    def _value(item: Any) -> Any:
        return getattr(item, "val", item)

    return {
        "indexed": [_value(item) for item in indexed],
        "body": [_value(item) for item in body],
    }


def _z_scores(values: Sequence[float]) -> List[float]:
    if not values:
        return []
    if len(values) == 1:
        return [0.0]
    mean = statistics.fmean(values)
    std_dev = statistics.pstdev(values)
    if math.isclose(std_dev, 0.0):
        return [0.0 for _ in values]
    return [(value - mean) / std_dev for value in values]


def _maybe_hex_to_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value, 16) if value.startswith("0x") else int(value)
        except ValueError:
            return None
    return None


def _extract_transfer(
    event: Mapping[str, Any],
) -> tuple[str | None, str | None, int | None]:
    indexed = event.get("indexed", []) or []
    body = event.get("body", []) or []
    from_addr = indexed[0] if len(indexed) > 0 else None
    to_addr = indexed[1] if len(indexed) > 1 else None
    value = None
    if body:
        raw_value = body[0]
        value = (
            _maybe_hex_to_int(raw_value)
            if isinstance(raw_value, str)
            else (int(raw_value) if raw_value is not None else None)
        )
    return from_addr, to_addr, value


def analyze_swap_price_impact(
    decoded_logs: Sequence[Mapping[str, Any]],
    *,
    min_price_delta_bps: float = 50.0,
    min_notional: int | None = None,
) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    prev_price: float | None = None
    for event in decoded_logs:
        body = event.get("body", []) or []
        indexed = event.get("indexed", []) or []
        if len(body) < 4 or len(indexed) < 3:
            continue
        amount0_any = body[0]
        amount1_any = body[1]
        sqrt_price_any = body[2]
        liquidity_any = body[3]

        amount0_val = (
            _maybe_hex_to_int(amount0_any)
            if isinstance(amount0_any, str)
            else amount0_any
        )
        amount1_val = (
            _maybe_hex_to_int(amount1_any)
            if isinstance(amount1_any, str)
            else amount1_any
        )
        sqrt_price_val = (
            _maybe_hex_to_int(sqrt_price_any)
            if isinstance(sqrt_price_any, str)
            else sqrt_price_any
        )
        liquidity_val = (
            _maybe_hex_to_int(liquidity_any)
            if isinstance(liquidity_any, str)
            else liquidity_any
        )

        if None in (amount0_val, amount1_val, sqrt_price_val, liquidity_val):
            continue

        amount0 = cast(int, amount0_val)
        amount1 = cast(int, amount1_val)
        sqrt_price_x96 = cast(int, sqrt_price_val)
        liquidity = cast(int, liquidity_val)

        if min_notional is not None and max(abs(amount0), abs(amount1)) < min_notional:
            continue
        if liquidity == 0:
            continue
        price = (sqrt_price_x96 / (1 << 96)) ** 2
        if prev_price is None:
            prev_price = price
            continue
        delta = abs(price - prev_price)
        if prev_price == 0:
            prev_price = price
            continue
        bps_delta = (delta / prev_price) * 10_000
        if bps_delta >= min_price_delta_bps:
            findings.append(
                {
                    "type": "price_impact",
                    "price": price,
                    "previous_price": prev_price,
                    "delta_bps": bps_delta,
                    "amount0": amount0,
                    "amount1": amount1,
                    "liquidity": liquidity,
                    "recipient": indexed[1],
                }
            )
        prev_price = price
    return findings


def detect_swap_wash_trades(
    decoded_logs: Sequence[Mapping[str, Any]],
    *,
    max_swaps: int = 3,
) -> List[Dict[str, Any]]:
    edges: Dict[Tuple[str, str], int] = {}
    for event in decoded_logs:
        indexed_any = event.get("indexed", []) or []
        if len(indexed_any) < 3:
            continue
        sender = indexed_any[0]
        recipient = indexed_any[1]
        if not sender or not recipient:
            continue
        sender_str = cast(str, sender)
        recipient_str = cast(str, recipient)
        pair = (sender_str.lower(), recipient_str.lower())
        key = tuple(sorted(pair))
        if len(key) != 2:
            continue
        key_pair = cast(Tuple[str, str], key)
        edges[key_pair] = edges.get(key_pair, 0) + 1
    findings: List[Dict[str, Any]] = []
    for (addr_a, addr_b), count in edges.items():
        if count >= max_swaps:
            findings.append(
                {
                    "type": "wash_trade_pair",
                    "participants": [addr_a, addr_b],
                    "swaps": count,
                }
            )
    return findings


def _run(coro):
    try:
        return asyncio.run(coro)
    except RuntimeError as exc:  # pragma: no cover
        if "asyncio.run() cannot be called" not in str(exc):
            raise
        loop = asyncio.get_event_loop()
        if loop.is_running():  # pragma: no cover
            raise RuntimeError(
                "An event loop is already running; await the coroutine directly instead."
            ) from exc
        return loop.run_until_complete(coro)


def collect_wallet_activity(
    addresses: Sequence[str],
    *,
    from_block: int = 0,
    transfer_topic: str = ERC20_TRANSFER_TOPIC,
) -> Dict[str, Any]:
    async def _collect() -> Dict[str, Any]:
        if not addresses:
            raise ValueError("Provide at least one wallet address")

        client = hypersync.HypersyncClient(ClientConfig())
        lowered_addresses = [addr.lower() for addr in addresses]
        address_topic_filter = list(map(_address_to_topic, lowered_addresses))
        transfer_topic_normalized = transfer_topic.lower()

        query = hypersync.Query(
            from_block=from_block,
            logs=[
                LogSelection(
                    topics=[
                        [transfer_topic_normalized],
                        [],
                        address_topic_filter,
                        [],
                    ]
                ),
                LogSelection(
                    topics=[
                        [transfer_topic_normalized],
                        address_topic_filter,
                        [],
                        [],
                    ]
                ),
            ],
            transactions=[
                TransactionSelection(from_=lowered_addresses),
                TransactionSelection(to=lowered_addresses),
            ],
            field_selection=FieldSelection(
                block=[
                    BlockField.NUMBER,
                    BlockField.TIMESTAMP,
                    BlockField.HASH,
                ],
                log=[
                    LogField.BLOCK_NUMBER,
                    LogField.LOG_INDEX,
                    LogField.TRANSACTION_INDEX,
                    LogField.TRANSACTION_HASH,
                    LogField.DATA,
                    LogField.ADDRESS,
                    LogField.TOPIC0,
                    LogField.TOPIC1,
                    LogField.TOPIC2,
                    LogField.TOPIC3,
                ],
                transaction=[
                    TransactionField.BLOCK_NUMBER,
                    TransactionField.TRANSACTION_INDEX,
                    TransactionField.HASH,
                    TransactionField.FROM,
                    TransactionField.TO,
                    TransactionField.VALUE,
                    TransactionField.INPUT,
                ],
            ),
        )

        result = await client.collect(query, StreamConfig())
        decoder = hypersync.Decoder([TRANSFER_EVENT_SIGNATURE])
        decoded_logs = await decoder.decode_logs(result.data.logs)

        erc20_volume: Dict[str, int] = {}
        for entry in decoded_logs:
            if entry is None:
                continue
            sender = entry.indexed[0].val
            receiver = entry.indexed[1].val
            value = entry.body[0].val
            erc20_volume[sender] = erc20_volume.get(sender, 0) + value
            erc20_volume[receiver] = erc20_volume.get(receiver, 0) + value

        wei_volume: Dict[str, int] = {}
        for tx in result.data.transactions:
            wei_volume[tx.from_] = wei_volume.get(tx.from_, 0) + int(tx.value, 16)
            if tx.to:
                wei_volume[tx.to] = wei_volume.get(tx.to, 0) + int(tx.value, 16)

        logs = [_log_to_dict(log) for log in result.data.logs]
        transactions = [_transaction_to_dict(tx) for tx in result.data.transactions]
        blocks = [
            {
                "number": getattr(block, "number", None),
                "hash": getattr(block, "hash", None),
                "timestamp": getattr(block, "timestamp", None),
            }
            for block in result.data.blocks
        ]
        decoded_serialized = [
            _decoded_event_to_dict(entry) for entry in decoded_logs if entry is not None
        ]

        return {
            "next_block": result.next_block,
            "archive_height": result.archive_height,
            "logs": logs,
            "transactions": transactions,
            "blocks": blocks,
            "erc20_volume": erc20_volume,
            "wei_volume": wei_volume,
            "decoded_logs": decoded_serialized,
        }

    return _run(_collect())


def fetch_contract_logs(
    contract: str,
    *,
    start_block: int,
    end_block: int,
) -> Mapping[str, Any]:
    async def _collect() -> Mapping[str, Any]:
        client = hypersync.HypersyncClient(ClientConfig())
        query = hypersync.preset_query_logs(contract, start_block, end_block)
        result = await client.get(query)
        logs = [_log_to_dict(log) for log in result.data.logs]
        return {
            "next_block": result.next_block,
            "archive_height": result.archive_height,
            "logs": logs,
        }

    return _run(_collect())


def fetch_event_logs(
    contract: str,
    *,
    topic0: str,
    start_block: int,
    end_block: int,
) -> Mapping[str, Any]:
    async def _collect() -> Mapping[str, Any]:
        client = hypersync.HypersyncClient(ClientConfig())
        query = hypersync.preset_query_logs_of_event(
            contract, topic0, start_block, end_block
        )
        result = await client.get(query)
        decoded_logs = None
        if topic0.lower() == ERC20_TRANSFER_TOPIC:
            decoder = hypersync.Decoder([TRANSFER_EVENT_SIGNATURE])
            decoded = await decoder.decode_logs(result.data.logs)
            decoded_logs = [
                _decoded_event_to_dict(ev) for ev in decoded if ev is not None
            ]
        logs = [_log_to_dict(log) for log in result.data.logs]
        return {
            "next_block": result.next_block,
            "archive_height": result.archive_height,
            "logs": logs,
            "decoded_logs": decoded_logs,
        }

    return _run(_collect())


def fetch_swap_events(
    pool_address: str,
    *,
    topic0: str,
    start_block: int,
    end_block: int,
) -> Mapping[str, Any]:
    async def _collect() -> Mapping[str, Any]:
        client = hypersync.HypersyncClient(ClientConfig())
        query = hypersync.preset_query_logs_of_event(
            pool_address,
            topic0,
            start_block,
            end_block,
        )
        result = await client.get(query)
        logs = [_log_to_dict(log) for log in result.data.logs]
        decoder = hypersync.Decoder([TRANSFER_EVENT_SIGNATURE])
        decoded = await decoder.decode_logs(result.data.logs)
        decoded_logs = [_decoded_event_to_dict(ev) for ev in decoded if ev is not None]
        return {
            "next_block": result.next_block,
            "archive_height": result.archive_height,
            "logs": logs,
            "decoded_logs": decoded_logs,
        }

    return _run(_collect())


def fetch_transaction_by_hash(
    tx_hash: str,
    *,
    from_block: int = 0,
) -> Mapping[str, Any]:
    async def _collect() -> Mapping[str, Any]:
        client = hypersync.HypersyncClient(ClientConfig())
        query = hypersync.Query(
            from_block=from_block,
            join_mode=hypersync.JoinMode.JOIN_NOTHING,
            field_selection=hypersync.FieldSelection(
                transaction=[
                    TransactionField.BLOCK_NUMBER,
                    TransactionField.TRANSACTION_INDEX,
                    TransactionField.HASH,
                    TransactionField.FROM,
                    TransactionField.TO,
                    TransactionField.VALUE,
                    TransactionField.INPUT,
                ]
            ),
            transactions=[
                TransactionSelection(hash=[tx_hash]),
            ],
        )
        result = await client.get(query)
        transactions = [_transaction_to_dict(tx) for tx in result.data.transactions]
        return {
            "next_block": result.next_block,
            "archive_height": result.archive_height,
            "transactions": transactions,
        }

    return _run(_collect())


def top_token_senders(
    contract: str,
    *,
    window_blocks: int = int(1e4),
    topic0: str = ERC20_TRANSFER_TOPIC,
    top_n: int = 10,
) -> Mapping[str, Any]:
    async def _collect() -> Mapping[str, Any]:
        client = hypersync.HypersyncClient(ClientConfig())
        height = await client.get_height()
        query = hypersync.Query(
            from_block=height - window_blocks,
            logs=[
                LogSelection(
                    address=[contract],
                    topics=[[topic0]],
                )
            ],
            field_selection=FieldSelection(
                log=[
                    LogField.TOPIC0,
                    LogField.TOPIC1,
                    LogField.TOPIC2,
                    LogField.DATA,
                    LogField.TRANSACTION_HASH,
                ],
                transaction=[
                    TransactionField.HASH,
                    TransactionField.GAS_USED,
                ],
            ),
        )
        stream_config = StreamConfig(
            hex_output=HexOutput.PREFIXED,
        )
        result = await client.collect(query, stream_config)
        decoder = hypersync.Decoder([TRANSFER_EVENT_SIGNATURE])
        decoded_logs = await decoder.decode_logs(result.data.logs)

        totals: Dict[str, float] = {}
        for entry in decoded_logs:
            if entry is None:
                continue
            sender = entry.indexed[0].val
            value = entry.body[0].val
            totals[sender] = totals.get(sender, 0.0) + float(value)

        leaders = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:top_n]
        return {
            "next_block": result.next_block,
            "archive_height": result.archive_height,
            "leaders": [
                {"address": address, "total_value": total_value}
                for address, total_value in leaders
            ],
        }

    return _run(_collect())


def detect_value_anomalies(
    decoded_logs: Sequence[Mapping[str, Any]],
    *,
    z_threshold: float = 2.0,
) -> List[Dict[str, Any]]:
    values = []
    for entry in decoded_logs:
        body = entry.get("body", [])
        if not body:
            continue
        maybe_value = (
            _maybe_hex_to_int(body[0]) if isinstance(body[0], str) else body[0]
        )
        if maybe_value is None:
            continue
        values.append(float(maybe_value))

    scores = _z_scores(values)
    anomalies: List[Dict[str, Any]] = []
    for decoded, score in zip(decoded_logs, scores):
        if abs(score) >= z_threshold:
            anomalies.append({"event": decoded, "z_score": score})
    return anomalies


def detect_large_transfers(
    decoded_logs: Sequence[Mapping[str, Any]],
    *,
    min_value: int,
) -> List[Dict[str, Any]]:
    flagged: List[Dict[str, Any]] = []
    for entry in decoded_logs:
        body = entry.get("body", [])
        if not body:
            continue
        raw_value = body[0]
        integer_value = (
            _maybe_hex_to_int(raw_value)
            if isinstance(raw_value, str)
            else int(raw_value)
        )
        if integer_value is None:
            continue
        if integer_value >= min_value:
            flagged.append({"event": entry, "value": integer_value})
    return flagged


def compute_address_centrality(
    decoded_logs: Sequence[Mapping[str, Any]],
    *,
    min_degree: int = 1,
) -> List[Dict[str, Any]]:
    edges: Dict[str, set[str]] = defaultdict(set)
    for entry in decoded_logs:
        sender, receiver, _ = _extract_transfer(entry)
        if not sender or not receiver:
            continue
        edges[sender].add(receiver)
        edges[receiver].add(sender)

    centrality: List[Dict[str, Any]] = []
    for address, neighbors in edges.items():
        degree = len(neighbors)
        if degree >= min_degree:
            centrality.append({"address": address, "degree": degree})
    return sorted(centrality, key=lambda item: item["degree"], reverse=True)


def score_wallet_activity(
    watched_addresses: Sequence[str],
    anomalies: Sequence[Mapping[str, Any]],
    large_transfers: Sequence[Mapping[str, Any]],
    centrality: Sequence[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    watched = [addr.lower() for addr in watched_addresses]
    scores: Dict[str, Dict[str, Any]] = {
        addr: {"address": addr, "score": 0, "factors": []} for addr in watched
    }

    for anomaly in anomalies:
        event = anomaly.get("event", {})
        sender, receiver, value = _extract_transfer(event)
        for addr in (sender, receiver):
            if addr and addr.lower() in scores:
                scores[addr.lower()]["score"] += 20
                scores[addr.lower()]["factors"].append(
                    {
                        "type": "z_score_anomaly",
                        "z_score": anomaly.get("z_score"),
                        "value": value,
                    }
                )

    for entry in large_transfers:
        event = entry.get("event", {})
        sender, receiver, value = _extract_transfer(event)
        for addr in (sender, receiver):
            if addr and addr.lower() in scores:
                scores[addr.lower()]["score"] += 15
                scores[addr.lower()]["factors"].append(
                    {
                        "type": "large_transfer",
                        "value": entry.get("value"),
                    }
                )

    central_map = {
        item["address"].lower(): item for item in centrality if item.get("address")
    }
    for addr, record in scores.items():
        central_record = central_map.get(addr)
        if central_record:
            degree = central_record.get("degree", 0)
            record["score"] += min(25, degree * 5)
            record["factors"].append(
                {
                    "type": "centrality",
                    "degree": degree,
                }
            )
        record["score"] = min(100, record["score"])

    return sorted(scores.values(), key=lambda item: item["score"], reverse=True)


def summarize_counterparties(
    decoded_logs: Sequence[Mapping[str, Any]],
    watched_addresses: Sequence[str],
) -> Dict[str, List[Dict[str, Any]]]:
    watched = {addr.lower() for addr in watched_addresses}
    watched_summary: Dict[str, Dict[str, Any]] = {
        addr: {
            "address": addr,
            "incoming_count": 0,
            "incoming_value": 0,
            "outgoing_count": 0,
            "outgoing_value": 0,
        }
        for addr in watched
    }
    counterparties: Dict[str, Dict[str, Any]] = {}

    for event in decoded_logs:
        sender, receiver, value = _extract_transfer(event)
        if value is None:
            value = 0
        sender_l = sender.lower() if isinstance(sender, str) else sender
        receiver_l = receiver.lower() if isinstance(receiver, str) else receiver

        if sender_l in watched_summary:
            watched_summary[sender_l]["outgoing_count"] += 1
            watched_summary[sender_l]["outgoing_value"] += value
            if receiver_l and receiver_l not in watched:
                counter = counterparties.setdefault(
                    receiver_l,
                    {
                        "address": receiver_l,
                        "interactions": 0,
                        "total_value": 0,
                    },
                )
                counter["interactions"] += 1
                counter["total_value"] += value

        if receiver_l in watched_summary:
            watched_summary[receiver_l]["incoming_count"] += 1
            watched_summary[receiver_l]["incoming_value"] += value
            if sender_l and sender_l not in watched:
                counter = counterparties.setdefault(
                    sender_l,
                    {
                        "address": sender_l,
                        "interactions": 0,
                        "total_value": 0,
                    },
                )
                counter["interactions"] += 1
                counter["total_value"] += value

    watched_list = list(watched_summary.values())
    counterparties_list = sorted(
        counterparties.values(), key=lambda item: item["total_value"], reverse=True
    )

    return {
        "watched": watched_list,
        "counterparties": counterparties_list,
    }


def detect_suspicious_patterns(
    decoded_logs: Sequence[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for event in decoded_logs:
        sender, receiver, value = _extract_transfer(event)
        if sender and receiver and sender.lower() == receiver.lower():
            findings.append(
                {
                    "type": "self_transfer",
                    "address": sender,
                    "value": value,
                }
            )
        if value == 0:
            findings.append(
                {
                    "type": "zero_value",
                    "from": sender,
                    "to": receiver,
                }
            )
    return findings


def decode_transaction_methods(
    transactions: Sequence[Mapping[str, Any]],
    known_selectors: Mapping[str, str] | None = None,
) -> List[Dict[str, Any]]:
    known_selectors = known_selectors or {}
    decoded: List[Dict[str, Any]] = []
    for tx in transactions:
        input_data = tx.get("input")
        if not input_data or not isinstance(input_data, str) or len(input_data) < 10:
            decoded.append({**tx, "method": None})
            continue
        selector = input_data[:10].lower()
        method = known_selectors.get(selector)
        decoded.append({**tx, "method": method, "selector": selector})
    return decoded


def label_transaction_risk(
    transactions: Sequence[Mapping[str, Any]],
    watchlist: Sequence[str] | None = None,
    large_value_threshold: int = int(1e20),
) -> List[Dict[str, Any]]:
    watch = {addr.lower() for addr in (watchlist or [])}
    enriched: List[Dict[str, Any]] = []
    for tx in transactions:
        value = _maybe_hex_to_int(tx.get("value"))
        risk_flags: List[str] = []
        sender = tx.get("from") or tx.get("from_")
        recipient = tx.get("to")
        if sender and sender.lower() in watch:
            risk_flags.append("sender_watchlist")
        if recipient and recipient.lower() in watch:
            risk_flags.append("recipient_watchlist")
        if value is not None and value >= large_value_threshold:
            risk_flags.append("large_value")
        enriched.append({**tx, "risk_flags": risk_flags})
    return enriched
