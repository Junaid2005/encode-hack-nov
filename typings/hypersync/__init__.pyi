from typing import Any, Optional, Sequence

class ClientConfig:
    url: Optional[str]
    bearer_token: Optional[str]

class HypersyncClient:
    def __init__(self, config: ClientConfig) -> None: ...
    async def get_height(self) -> int: ...
    async def get_chain_id(self) -> int: ...
    async def collect(
        self, query: "Query", config: "StreamConfig"
    ) -> "QueryResponse": ...
    async def get(self, query: "Query") -> "QueryResponse": ...

class Decoder:
    def __init__(self, signatures: Sequence[str]) -> None: ...
    async def decode_logs(self, logs: Sequence[Any]) -> Sequence[Any]: ...

class ColumnMapping: ...

class StreamConfig:
    def __init__(self, **kwargs: Any) -> None: ...

class QueryResponse:
    data: Any
    next_block: int
    archive_height: Optional[int]

class Query:
    def __init__(self, **kwargs: Any) -> None: ...

def preset_query_logs(
    address: str, from_block: int, to_block: Optional[int] | None = None
) -> Query: ...
def preset_query_logs_of_event(
    address: str, topic0: str, from_block: int, to_block: Optional[int] | None = None
) -> Query: ...

class LogSelection:
    def __init__(self, **kwargs: Any) -> None: ...

class TransactionSelection:
    def __init__(self, **kwargs: Any) -> None: ...

class FieldSelection:
    def __init__(self, **kwargs: Any) -> None: ...

class JoinMode:
    JOIN_NOTHING: Any

class HexOutput:
    PREFIXED: Any

class BlockField:
    NUMBER: Any
    TIMESTAMP: Any
    HASH: Any

class LogField:
    BLOCK_NUMBER: Any
    LOG_INDEX: Any
    TRANSACTION_INDEX: Any
    TRANSACTION_HASH: Any
    DATA: Any
    ADDRESS: Any
    TOPIC0: Any
    TOPIC1: Any
    TOPIC2: Any
    TOPIC3: Any

class TransactionField:
    BLOCK_NUMBER: Any
    TRANSACTION_INDEX: Any
    HASH: Any
    FROM: Any
    TO: Any
    VALUE: Any
    INPUT: Any
    GAS_USED: Any
