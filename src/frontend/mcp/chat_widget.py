import streamlit as st
from openai import OpenAI
import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from .mcp_schema import MCP_TOOLS, MCP_FUNCTION_MAP


class ChatWidget:
    def __init__(
        self,
        api_key: str,
        tools: list = MCP_TOOLS,
        function_map: dict = MCP_FUNCTION_MAP,
    ):
        self.api_key = api_key
        self.client = OpenAI(api_key=api_key)

        self.tools = tools

        self.function_map = function_map

        # Initialize session state
        if "messages" not in st.session_state:
            st.session_state.messages = []

    def display_messages(self):
        """Display chat messages"""
        for message in st.session_state.messages:
            if isinstance(message, dict):
                role = message["role"]
                display_role = "assistant" if role == "tool" else role
                avatar = "🐶" if role in ["assistant", "tool"] else None

                with st.chat_message(display_role, avatar=avatar):
                    st.markdown(message["content"])

    def chat_with_tools(self):
        """Handle chat with tool calling"""
        if prompt := st.chat_input(
            "Try: 'say hi', 'give me a random number', or 'generate random chars'"
        ):
            # Add user message
            st.session_state.messages.append({"role": "user", "content": prompt})

            # Display user message
            with st.chat_message("user"):
                st.markdown(prompt)

            # Get AI response with tool calling
            with st.chat_message("assistant", avatar="🐶"):
                response = self.client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=st.session_state.messages,
                    tools=self.tools,
                    tool_choice="auto",
                )

                # Handle tool calls
                if response.choices[0].message.tool_calls:
                    # Add assistant message with tool calls
                    st.session_state.messages.append(response.choices[0].message)

                    # Execute tool calls
                    for tool_call in response.choices[0].message.tool_calls:
                        function_name = tool_call.function.name
                        function_args = json.loads(tool_call.function.arguments)

                        # Call the function
                        function_result = self.function_map[function_name](
                            **function_args
                        )

                        # Add tool result to messages
                        st.session_state.messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": function_result,
                            }
                        )

                        st.markdown(function_result)
                else:
                    # No tool calls, just display response
                    st.markdown(response.choices[0].message.content)
                    st.session_state.messages.append(
                        {
                            "role": "assistant",
                            "content": response.choices[0].message.content,
                        }
                    )

    def render(self):
        """Render the complete chat widget"""
        self.display_messages()
        self.chat_with_tools()
