from mcp_funcs.mcp_hi import say_hi
from mcp_funcs.mcp_num import get_random_number
from mcp_funcs.mcp_char import get_random_chars

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
]


MCP_FUNCTION_MAP = {
    "say_hi": say_hi,
    "get_random_number": get_random_number,
    "get_random_chars": get_random_chars,
}
