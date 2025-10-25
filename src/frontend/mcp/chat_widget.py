import base64
import json
import os
import sys
from pathlib import Path

import altair as alt
import streamlit as st
from openai import AzureOpenAI
import json
import sys
import os
import logging

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
        self.client = AzureOpenAI(
            api_key=api_key or st.secrets["OPENAI_ENDPOINT"],
            azure_endpoint=st.secrets["OPENAI_ENDPOINT"],
            api_version=st.secrets["OPENAI_VERSION"],
        )

        self.tools = tools

        self.function_map = function_map

        self.system_prompt = (
            "You are Sniffer, the AI K9 detective for this Streamlit investigation desk—an ever-alert fraud hound who speaks in a professional but friendly tone and occasionally references your canine instincts. "
            "Before answering, call the appropriate MCP tool to collect evidence. The toolkit includes: "
            "wallet_activity (multi-wallet baselines, anomaly scores, and counterparty overlays), "
            "event_logs (contract event anomaly detection), swap_events (price-impact and wash-trade surveillance), "
            "and transaction_analysis (single-transaction decoding and risk scoring). "
            "For every response after running a tool, deliver:\n"
            "1) a plain-language narrative describing the suspicious behaviour and who is impacted,\n"
            "2) a breakdown of detection methods used (z-score baselines, centrality, price impact, wash-trade counts, etc.) and what each reveals,\n"
            "3) the key indicators or risk factors with severity and why they matter, and\n"
            "4) specific next steps or clarifying questions to advance the investigation. "
            "Explain technical metrics in everyday language so non-technical investigators understand the implications. "
            "Always confirm the block scope: if the user does not provide a starting block or block range, ask for it before invoking a tool. "
            "If any other required parameters are missing, ask concise clarification questions before proceeding."
        )

        # Initialize session state
        if "messages" not in st.session_state:
            st.session_state.messages = [
                {
                    "role": "system",
                    "content": self.system_prompt,
                }
            ]
        elif (
            not st.session_state.messages
            or st.session_state.messages[0].get("role") != "system"
        ):
            st.session_state.messages.insert(
                0,
                {
                    "role": "system",
                    "content": self.system_prompt,
                },
            )

        asset_root = Path(__file__).resolve().parents[2] / "src"
        if not asset_root.exists():
            asset_root = Path(__file__).resolve().parents[2]
        self.image_ready_b64 = self._encode_image(
            asset_root / "fraud_detected_sniffer.png"
        )
        self.image_thinking_b64 = self._encode_image(
            asset_root / "thinking_sniffer.png"
        )
        self.image_happy_b64 = self._encode_image(asset_root / "happy_sniffer.png")
        fraud_image_path = asset_root / "fraud_sniffer.png"
        self.image_fraud_b64 = (
            self._encode_image(fraud_image_path) if fraud_image_path.exists() else ""
        )
        self.image_display_width = 180
        self.model_history_limit = 14
        self.pending_hypersync_banner = False

        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)

        if not st.session_state.get("sniffer_intro_inserted"):
            intro_text = (
                "**Sniffer reporting for duty!**\n"
                "Share a wallet, contract, pool, or transaction hash and I'll fetch the data, sniff for anomalies, and chart anything suspicious."
            )
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": intro_text,
                    "image_b64": self.image_happy_b64,
                    "image_caption": "Sniffer is ready to investigate!",
                    "image_width": self.image_display_width,
                }
            )
            st.session_state["sniffer_intro_inserted"] = True

        self.spinner_css = f"""
        <style>
        .sniffer-visual {{
            display: flex;
            flex-direction: column;
            justify-content: flex-end;
            align-items: center;
            min-height: 300px;
            gap: 12px;
            text-align: center;
        }}
        .sniffer-visual img {{
            width: {self.image_display_width}px;
            max-width: 100%;
            height: auto;
            filter: drop-shadow(0 12px 32px rgba(0, 0, 0, 0.45));
        }}
        .sniffer-visual .sniffer-stage-caption {{
            margin-top: 16px;
            padding: 12px 20px;
            display: inline-block;
            border-radius: 999px;
            font-size: 1rem;
            font-weight: 600;
            letter-spacing: 0.4px;
            background: linear-gradient(135deg, #1f3b65, #0f1b2e);
            color: #f5f7fb;
            border: 1px solid rgba(255, 255, 255, 0.1);
            box-shadow: 0 8px 24px rgba(15, 27, 46, 0.45);
        }}
        .sniffer-visual .sniffer-stage-caption span {{
            background: linear-gradient(135deg, #2f6bff, #8b47ff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}
        .sniffer-intro-caption {{
            margin-top: 0.6rem;
            font-size: 0.92rem;
            letter-spacing: 0.2px;
            color: rgba(236, 241, 255, 0.75);
        }}
        .sniffer-thinking-loader {{
            margin-top: 14px;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }}
        .sniffer-thinking-loader span {{
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: linear-gradient(135deg, #2f6bff, #8b47ff);
            box-shadow: 0 0 12px rgba(143, 71, 255, 0.6);
            animation: snifferPulse 1.2s ease-in-out infinite;
        }}
        .sniffer-thinking-loader span:nth-child(2) {{
            animation-delay: 0.15s;
        }}
        .sniffer-thinking-loader span:nth-child(3) {{
            animation-delay: 0.3s;
        }}
        .sniffer-thinking-loader + .sniffer-thinking-loader {{
            margin-top: 0.4rem;
        }}
        .sniffer-thinking-wall {{
            display: flex;
            justify-content: center;
            margin-top: 0.35rem;
        }}
        .sniffer-thinking-text {{
            margin: 0;
            text-align: center;
            color: rgba(236, 241, 255, 0.9);
            font-size: 0.95rem;
            letter-spacing: 0.25px;
        }}
        .sniffer-hypersync-banner {{
            display: flex;
            justify-content: center;
            margin-bottom: 1rem;
        }}
        .sniffer-hypersync-card {{
            display: inline-flex;
            align-items: center;
            gap: 14px;
            padding: 12px 22px;
            border-radius: 999px;
            background: linear-gradient(135deg, #1f3b65, #0f1b2e);
            color: #f5f7fb;
            box-shadow: 0 8px 24px rgba(15, 27, 46, 0.45);
            border: 1px solid rgba(255, 255, 255, 0.08);
        }}
        .sniffer-hypersync-card img {{
            width: 44px;
            height: auto;
            filter: drop-shadow(0 12px 24px rgba(0, 0, 0, 0.35));
        }}
        .sniffer-hypersync-card-text {{
            font-size: 0.98rem;
            font-weight: 600;
            letter-spacing: 0.35px;
        }}
        .sniffer-hypersync-card-text span {{
            background: linear-gradient(135deg, #2f6bff, #8b47ff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}
        #sniffer-chat-wrapper {{
            max-height: 70vh;
            overflow-y: auto;
            padding-right: 4px;
            scroll-behavior: smooth;
        }}
        </style>
        <script>
        const scrollSnifferChat = () => {{
            try {{
                const doc = window.parent && window.parent.document ? window.parent.document : document;
                const log = doc.querySelector('#sniffer-chat-log');
                if (log) {{
                    log.scrollTo({{ top: log.scrollHeight, behavior: 'smooth' }});
                }}
            }} catch (err) {{
                // ignore cross-origin issues
            }}
        }};
        window.setTimeout(scrollSnifferChat, 200);
        </script>
        """

    @staticmethod
    def _encode_image(path: Path) -> str:
        with path.open("rb") as handle:
            return base64.b64encode(handle.read()).decode("ascii")

    def _build_chart(self, chart_payload):
        data = chart_payload.get("data")
        spec = chart_payload.get("spec") or {}
        if not data or not spec:
            return None

        chart_spec = {
            "data": {"values": data},
            "mark": spec.get("mark", {"type": "bar"}),
            "encoding": spec.get("encoding", {}),
        }
        title = chart_payload.get("title")
        if title:
            chart_spec["title"] = title
        return alt.Chart.from_dict(chart_spec)

    def _render_chart(self, target, chart_obj):
        try:
            target.altair_chart(chart_obj, width="stretch")
        except TypeError:
            target.altair_chart(chart_obj, use_container_width=True)

    def _render_tool_output(self, content: str, container=None):
        target = container or st
        try:
            payload = json.loads(content)
        except (TypeError, json.JSONDecodeError):
            target.markdown(content)
            return

        if self.pending_hypersync_banner:
            target.markdown(
                f"""
                <div class="sniffer-hypersync-banner">
                    <div class="sniffer-hypersync-card">
                        <img src="data:image/png;base64,{self.image_ready_b64}" alt="Sniffer fetching data" />
                        <div class="sniffer-hypersync-card-text"><span>Sniffer</span> is getting data from Envio Hypersync — fetching on-chain evidence.</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            self.pending_hypersync_banner = False

        summary = payload.get("summary")
        if summary:
            summary_expander = target.expander("Summary", expanded=False)
            summary_expander.json(summary)

        alerts = payload.get("alerts") or []
        if alerts:
            alerts_expander = target.expander("Alerts", expanded=False)
            alerts_expander.table(alerts)

        metrics = payload.get("metrics")
        if metrics:
            metrics_expander = target.expander("Metrics", expanded=False)
            metrics_expander.json(metrics)

        data_records = payload.get("data")
        if data_records:
            data_expander = target.expander("Records", expanded=False)
            data_expander.dataframe(data_records)

        suspected_fraud = False
        if summary:
            verdict = str(summary.get("verdict", "")).lower()
            severity = str(summary.get("severity", "")).lower()
            suspected_fraud = verdict not in {"", "clear"} or severity in {
                "medium",
                "high",
            }

        if suspected_fraud and self.image_fraud_b64:
            try:
                image_bytes = base64.b64decode(self.image_fraud_b64)
                target.image(
                    image_bytes,
                    caption="Sniffer raised a fraud alert.",
                    width=self.image_display_width,
                )
            except Exception:
                target.warning("Fraud visual unavailable, but alerts were triggered.")

        narrative = payload.get("narrative")
        if narrative:
            target.markdown(narrative)

        charts = payload.get("charts") or []
        chart_count = payload.get("chart_count", 0)
        chart_rendered = False
        for chart_payload in charts:
            chart_obj = self._build_chart(chart_payload)
            if not chart_obj:
                continue
            self._render_chart(target, chart_obj)
            description = chart_payload.get("description")
            if description:
                target.caption(description)
            chart_rendered = True
        if charts and not chart_rendered and chart_count:
            target.info(
                "Charts were requested but no datapoints were returned by the tool."
            )
        elif chart_count == 0:
            target.caption("No chartable datapoints were returned for this response.")

    def _prune_history(self, history):
        if len(history) <= self.model_history_limit:
            return history
        trimmed = [history[0]]
        trimmed.extend(history[-(self.model_history_limit - 1) :])
        return trimmed

    def display_messages(self):
        """Display chat messages"""
        if not st.session_state.get("sniffer_spinner_css_injected"):
            st.markdown(self.spinner_css, unsafe_allow_html=True)
            st.session_state["sniffer_spinner_css_injected"] = True
        chat_container = st.container()
        with chat_container:
            st.markdown(
                "<div id='sniffer-chat-wrapper'><div id='sniffer-chat-log'>",
                unsafe_allow_html=True,
            )
            for message in st.session_state.messages:
                if isinstance(message, dict):
                    role = message["role"]
                    if role == "system":
                        continue
                    display_role = "assistant" if role == "tool" else role

                    with st.chat_message(display_role):
                        if role == "tool":
                            st.markdown("**🐶 Sniffer**")
                            self._render_tool_output(message["content"])
                        else:
                            image_b64 = message.get("image_b64")
                            if image_b64:
                                try:
                                    image_width = message.get("image_width")
                                    if image_width is None:
                                        st.markdown(
                                            f"""
                                            <div class="sniffer-visual">
                                                <img style="width: {self.image_display_width}px; max-width: 100%; height: auto;" src="data:image/png;base64,{image_b64}" alt="Sniffer ready" />
                                                <div class="sniffer-stage-caption"><span>Sniffer</span> is ready to investigate!</div>
                                                <div class="sniffer-intro-caption">Share a wallet, contract, pool, or transaction hash and I’ll fetch the data, sniff for anomalies, and chart anything suspicious.</div>
                                            </div>
                                            """,
                                            unsafe_allow_html=True,
                                        )
                                    else:
                                        st.image(
                                            base64.b64decode(image_b64),
                                            caption=message.get("image_caption"),
                                            width=image_width,
                                        )
                                except Exception:
                                    st.warning("Unable to display Sniffer visual.")
                            st.markdown(message["content"])
            st.markdown(
                "<div id='sniffer-chat-sentinel'></div></div></div>",
                unsafe_allow_html=True,
            )

    def chat_with_tools(self):
        """Handle chat with tool calling"""
        user_prompt = st.chat_input(
            "Try: 'Analyze wallet activity for 0x...', 'Scan swap events for pool ...', or 'Review tx hash ...'"
        )
        if user_prompt:
            # Add user message
            st.session_state.messages.append({"role": "user", "content": user_prompt})

            # Display user message
            with st.chat_message("user"):
                st.markdown(user_prompt)

            # Get AI response with tool calling
            with st.chat_message("assistant", avatar="🐶"):
                st.markdown(self.spinner_css, unsafe_allow_html=True)
                tool_output_container = st.container()
                stage_placeholder = st.empty()
                trimmed_messages = self._prune_history(st.session_state.messages)

                response = self.client.chat.completions.create(
                    model=st.secrets["OPENAI_DEPLOYMENT"],
                    messages=trimmed_messages,
                    tools=self.tools,
                    tool_choice="auto",
                )

                while True:
                    message = response.choices[0].message

                    if message.tool_calls:
                        stage_placeholder.markdown(
                            f"""
                            <div class="sniffer-visual">
                                <img style="width: {self.image_display_width}px; max-width: 100%; height: auto;" src="data:image/png;base64,{self.image_ready_b64}" alt="Sniffer querying Envio Hypersync" />
                                <div class="sniffer-stage-caption"><span>Sniffer</span> is getting data from Envio Hypersync — fetching on-chain evidence.</div>
                                <div class='sniffer-thinking-wall'>
                                    <div class='sniffer-thinking-loader'><span></span><span></span><span></span></div>
                                </div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                        self.pending_hypersync_banner = True
                        st.session_state.messages.append(message)

                        trimmed_messages = self._prune_history(
                            st.session_state.messages
                        )

                        for tool_call in message.tool_calls:
                            function_name = tool_call.function.name
                            function_args = json.loads(tool_call.function.arguments)

                            function_result = self.function_map[function_name](
                                **function_args
                            )

                            tool_message = {
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": function_result,
                            }
                            st.session_state.messages.append(tool_message)
                            self._render_tool_output(
                                function_result, tool_output_container
                            )

                        trimmed_messages = self._prune_history(
                            st.session_state.messages
                        )

                        response = self.client.chat.completions.create(
                            model=st.secrets["OPENAI_DEPLOYMENT"],
                            messages=trimmed_messages,
                            tools=self.tools,
                            tool_choice="auto",
                        )
                        continue

                    if message.content:
                        stage_placeholder.empty()
                        visual_markup = f"""
                            <div class="sniffer-visual">
                                <img style="width: {self.image_display_width}px; max-width: 100%; height: auto;" src="data:image/png;base64,{self.image_happy_b64}" alt="Sniffer reports ready" />
                                <div class="sniffer-stage-caption">📬 <span>Sniffer</span> fetched the findings — report ready for review.</div>
                            </div>
                            """
                        st.markdown(visual_markup, unsafe_allow_html=True)
                        st.markdown(message.content)
                        st.session_state.messages.append(
                            {
                                "role": "assistant",
                                "content": message.content,
                            }
                        )
                    break

    def render(self):
        """Render the complete chat widget"""
        self.display_messages()
        self.chat_with_tools()
