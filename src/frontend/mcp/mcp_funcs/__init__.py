"""Expose MCP fraud utility functions."""

from .mcp_char import get_random_chars
from .mcp_fraud import event_logs, swap_events, transaction_analysis, wallet_activity
from .mcp_hi import say_hi
from .mcp_num import get_random_number

__all__ = [
    "say_hi",
    "get_random_number",
    "get_random_chars",
    "wallet_activity",
    "event_logs",
    "swap_events",
    "transaction_analysis",
]
