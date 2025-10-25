import streamlit as st
from openai import OpenAI
import numpy as np
import pandas as pd


class ChatWidget:
    def __init__(self, api_key: str):
        """Initialize the chat widget with OpenAI client"""
        self.client = OpenAI(api_key=api_key)
        self._initialize_session_state()

    def _initialize_session_state(self):
        """Initialize session state variables"""
        if "openai_model" not in st.session_state:
            st.session_state["openai_model"] = "gpt-3.5-turbo"

        if "messages" not in st.session_state:
            st.session_state.messages = []

    def display_messages(self):
        """Display all chat messages"""
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

    def handle_user_input(self, prompt: str):
        """Handle user input and generate AI response"""
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})

        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)

        # Generate and display AI response
        with st.chat_message("assistant"):
            stream = self.client.chat.completions.create(
                model=st.session_state["openai_model"],
                messages=[
                    {"role": m["role"], "content": m["content"]}
                    for m in st.session_state.messages
                ],
                stream=True,
            )
            response = st.write_stream(stream)

        # Add AI response to messages
        st.session_state.messages.append({"role": "assistant", "content": response})

    def render(self):
        """Render the complete chat widget"""
        self.display_messages()

        col1, col2 = st.columns([0.7, 0.3])

        with col1:
            st.subheader("Fraud in the Market")
            detect_button = st.button("Sniff Fraud 🔎")
            if detect_button:
                # Generate new data when button is pressed
                scatter_data = self.generate_scatter_data(
                    button_pressed=True, random_seed=np.random.randint(0, 10000)
                )
                st.scatter_chart(scatter_data)
            else:
                scatter_data = self.generate_scatter_data(
                    button_pressed=False, random_seed=42
                )
                st.scatter_chart(scatter_data)

        with col2:
            if prompt := st.chat_input("How can I help you today?"):
                self.handle_user_input(prompt)

    # @st.cache_data
    def generate_scatter_data(self, button_pressed: bool, random_seed: int):
        """Generate scatter data - cached but refreshes when button is pressed"""
        np.random.seed(random_seed)
        return pd.DataFrame(
            {
                "X": np.random.normal(0, 1, 100),
                "Y": np.random.normal(0, 1, 100),
                "Size": np.random.randint(10, 100, 100),
            }
        )
