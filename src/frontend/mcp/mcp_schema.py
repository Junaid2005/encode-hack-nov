from .mcp_funcs.mcp_hi import say_hi
from .mcp_funcs.mcp_num import get_random_number
from .mcp_funcs.mcp_char import get_random_chars
from .mcp_funcs.mcp_fraud import (
    event_logs,
    swap_events,
    transaction_analysis,
    wallet_activity,
)

# MCP Tools schema
MCP_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "say_hi",
            "description": "Say hello",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_random_number",
            "description": "Get a random number between 1 and 100",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_random_chars",
            "description": "Generate random characters",
            "parameters": {
                "type": "object",
                "properties": {
                    "length": {
                        "type": "integer",
                        "description": "Number of characters to generate",
                        "default": 5,
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "wallet_activity",
            "description": "Analyze wallet activity and fraud indicators for specified addresses.",
            "parameters": {
                "type": "object",
                "properties": {
                    "addresses": {
                        "type": "array",
                        "description": "List of wallet addresses to analyze.",
                        "items": {"type": "string"},
                    },
                    "from_block": {
                        "type": "integer",
                        "description": "Starting block number for the analysis (must be greater than 0).",
                        "minimum": 1,
                    },
                    "transfer_topic": {
                        "type": "string",
                        "description": "Event topic to monitor (defaults to ERC-20 transfer).",
                        "default": "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",
                    },
                    "options": {
                        "type": "object",
                        "description": "Advanced wallet analysis options overriding defaults.",
                        "properties": {
                            "z_threshold": {"type": "number"},
                            "large_transfer_threshold": {"type": "integer"},
                            "min_centrality_degree": {"type": "integer"},
                            "include_self_transfers": {"type": "boolean"},
                            "include_zero_value": {"type": "boolean"},
                            "baseline_window": {"type": "integer"},
                            "trend_window": {"type": "integer"},
                            "trend_z_threshold": {"type": "number"},
                            "trend_cusum_limit": {"type": "number"},
                        },
                        "additionalProperties": False,
                    },
                },
                "required": ["addresses", "from_block"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "event_logs",
            "description": "Fetch and analyze contract event logs for anomalies.",
            "parameters": {
                "type": "object",
                "properties": {
                    "contract": {
                        "type": "string",
                        "description": "Contract address to query logs from.",
                    },
                    "topic0": {
                        "type": "string",
                        "description": "Event topic to filter by.",
                        "default": "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",
                    },
                    "start_block": {
                        "type": "integer",
                        "description": "Inclusive start block number.",
                    },
                    "end_block": {
                        "type": "integer",
                        "description": "Inclusive end block number.",
                    },
                    "options": {
                        "type": "object",
                        "description": "Event analysis options overriding defaults.",
                        "properties": {
                            "z_threshold": {"type": "number"},
                            "large_transfer_threshold": {"type": "integer"},
                            "min_centrality_degree": {"type": "integer"},
                            "baseline_window": {"type": "integer"},
                            "trend_window": {"type": "integer"},
                            "trend_z_threshold": {"type": "number"},
                            "trend_cusum_limit": {"type": "number"},
                            "include_self_transfers": {"type": "boolean"},
                            "include_zero_value": {"type": "boolean"},
                        },
                        "additionalProperties": False,
                    },
                },
                "required": ["contract", "start_block", "end_block"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "swap_events",
            "description": "Inspect swap pool events for price impact and wash trading.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pool_address": {
                        "type": "string",
                        "description": "Pool contract address to analyze.",
                    },
                    "topic0": {
                        "type": "string",
                        "description": "Swap event topic signature.",
                    },
                    "start_block": {
                        "type": "integer",
                        "description": "Inclusive start block number.",
                    },
                    "end_block": {
                        "type": "integer",
                        "description": "Inclusive end block number.",
                    },
                    "options": {
                        "type": "object",
                        "description": "Swap analysis options overriding defaults.",
                        "properties": {
                            "min_price_delta_bps": {"type": "number"},
                            "min_notional": {"type": "integer"},
                            "wash_trade_threshold": {"type": "integer"},
                        },
                        "additionalProperties": False,
                    },
                },
                "required": ["pool_address", "topic0", "start_block", "end_block"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "transaction_analysis",
            "description": "Analyze a transaction for risk indicators and decoded methods.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tx_hash": {
                        "type": "string",
                        "description": "Transaction hash to inspect.",
                    },
                    "from_block": {
                        "type": "integer",
                        "description": "Starting block for historical context.",
                        "default": 0,
                    },
                    "options": {
                        "type": "object",
                        "description": "Transaction analysis options overriding defaults.",
                        "properties": {
                            "decode_methods": {"type": "boolean"},
                            "large_value_threshold": {"type": "integer"},
                            "watchlist": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                        "additionalProperties": False,
                    },
                },
                "required": ["tx_hash"],
            },
        },
    },
]


MCP_FUNCTION_MAP = {
    "say_hi": say_hi,
    "get_random_number": get_random_number,
    "get_random_chars": get_random_chars,
    "wallet_activity": wallet_activity,
    "event_logs": event_logs,
    "swap_events": swap_events,
    "transaction_analysis": transaction_analysis,
}
