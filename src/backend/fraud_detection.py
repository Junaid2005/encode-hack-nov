from __future__ import annotations

import asyncio
from typing import Any, Dict, Iterable, List, Mapping, Sequence

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

ERC20_TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
TRANSFER_EVENT_SIGNATURE = "Transfer(address indexed from, address indexed to, uint256 value)"


def _address_to_topic(address: str) -> str:
    checksum = address.lower()
    return "0x000000000000000000000000" + checksum[2:]


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

        return {
            "next_block": result.next_block,
            "archive_height": result.archive_height,
            "logs": result.data.logs,
            "transactions": result.data.transactions,
            "blocks": result.data.blocks,
            "erc20_volume": erc20_volume,
            "wei_volume": wei_volume,
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
        return {
            "next_block": result.next_block,
            "archive_height": result.archive_height,
            "logs": result.data.logs,
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
        query = hypersync.preset_query_logs_of_event(contract, topic0, start_block, end_block)
        result = await client.get(query)
        decoder = hypersync.Decoder([TRANSFER_EVENT_SIGNATURE]) if topic0.lower() == ERC20_TRANSFER_TOPIC else None
        decoded = None
        if decoder:
            decoded = await decoder.decode_logs(result.data.logs)
        return {
            "next_block": result.next_block,
            "archive_height": result.archive_height,
            "logs": result.data.logs,
            "decoded_logs": decoded,
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
        return {
            "next_block": result.next_block,
            "archive_height": result.archive_height,
            "logs": result.data.logs,
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
        return {
            "next_block": result.next_block,
            "archive_height": result.archive_height,
            "transactions": result.data.transactions,
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
