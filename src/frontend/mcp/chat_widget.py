import base64
import json
import os
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import altair as alt
import pandas as pd
import streamlit as st
from openai import OpenAI

from .mcp_schema import MCP_FUNCTION_MAP, MCP_TOOLS


@dataclass
class SnifferVisuals:
    root: Path
    ready: str = field(init=False)
    thinking: str = field(init=False)
    happy: str = field(init=False)
    fraud: Optional[str] = field(init=False)

    def __post_init__(self) -> None:
        self.ready = self._encode_asset("fraud_detected_sniffer.png")
        self.thinking = self._encode_asset("thinking_sniffer.png")
        self.happy = self._encode_asset("happy_sniffer.png")
        self.fraud = self._encode_asset("fraud_sniffer.png", required=False)

    def _encode_asset(self, asset_name: str, *, required: bool = True) -> str:
        asset_path = self.root / asset_name
        if not asset_path.exists():
            if required:
                raise FileNotFoundError(asset_path)
            return ""
        with asset_path.open("rb") as handle:
            return base64.b64encode(handle.read()).decode("ascii")


@dataclass
class SnifferMessage:
    role: str
    content: str

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"role": self.role, "content": self.content}
        return payload


class ChatWidget:
    MODEL_HISTORY_LIMIT = 14
    IMAGE_WIDTH = 120

    def __init__(
        self,
        api_key: Optional[str],
        *,
        tools: Iterable[Dict[str, Any]] = MCP_TOOLS,
        function_map: Dict[str, Any] = MCP_FUNCTION_MAP,
    ) -> None:
        self.function_map = function_map
        self.tools = list(tools)
        # self.client = AzureOpenAI(
        #     api_key=api_key or st.secrets["OPENAI_API_KEY"],
        #     azure_endpoint=st.secrets["OPENAI_ENDPOINT"],
        #     api_version=st.secrets["OPENAI_VERSION"],
        # )
        api_key_value = api_key or st.secrets.get("OPENAI_API_KEY")
        if not api_key_value:
            api_key_value = os.environ.get("OPENAI_API_KEY")
        if not api_key_value:
            raise RuntimeError(
                "OPENAI_API_KEY is not configured. Set it in Streamlit secrets or as an environment variable."
            )
        self.client = OpenAI(api_key=api_key_value)
        self.model_name = (
            st.secrets.get("OPENAI_MODEL"))
        if not self.model_name:
            raise RuntimeError(
                "OPENAI_MODEL/OPENAI_DEPLOYMENT is not configured. Define it in Streamlit secrets or environment variables."
            )
        asset_root = Path(__file__).resolve().parents[2] / "src"
        if not asset_root.exists():
            asset_root = Path(__file__).resolve().parents[2]
        self.visuals = SnifferVisuals(root=asset_root)
        self.image_display_width = 110
        self.system_prompt = (
            "You are Sniffer, the AI K9 detective for this Streamlit investigation desk—an ever-alert fraud hound who speaks in a professional but friendly tone and occasionally references your canine instincts. "
            "Before answering, call the appropriate MCP tool to collect evidence. The toolkit includes: "
            "wallet_activity (multi-wallet baselines, anomaly scores, and counterparty overlays), event_logs (contract event anomaly detection), swap_events (price-impact and wash-trade surveillance), and transaction_analysis (single-transaction decoding and risk scoring). "
            "For every response after running a tool, deliver: 1) a plain-language narrative describing the suspicious behaviour and who is impacted, 2) a breakdown of detection methods used (z-score baselines, centrality, price impact, wash-trade counts, etc.) and what each reveals, 3) the key indicators or risk factors with severity and why they matter, and 4) specific next steps or clarifying questions to advance the investigation. "
            "Explain technical metrics in everyday language so non-technical investigators understand the implications. Always confirm the block scope: if the user does not provide a starting block or block range, ask for it before invoking a tool. If any other required parameters are missing, ask concise clarification questions before proceeding."
        )
        self._ensure_state()

    # ------------------------------------------------------------------
    # Session state helpers
    # ------------------------------------------------------------------
    def _ensure_state(self) -> None:
        messages = st.session_state.setdefault("sniffer_messages", [])
        if not messages:
            messages.append(SnifferMessage("system", self.system_prompt).to_dict())
        elif messages[0].get("role") != "system":
            messages.insert(0, SnifferMessage("system", self.system_prompt).to_dict())
        st.session_state.setdefault("sniffer_history", [])

    # ------------------------------------------------------------------
    # UI helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _encode_chart(chart_payload: Dict[str, Any]) -> Optional[alt.Chart]:
        data = chart_payload.get("data")
        spec = chart_payload.get("spec")
        if not data or not spec:
            return None
        df = pd.DataFrame(data)
        mark = spec.get("mark", {"type": "bar"})
        encoding_spec = spec.get("encoding", {})
        chart = (
            alt.Chart(df).mark_bar()
            if str(mark.get("type", "")).lower() == "bar"
            else alt.Chart(df).mark_point()
        )

        def _to_channel(key: str, value: Any) -> Any:
            if key == "tooltip" and isinstance(value, list):
                tooltips = []
                for item in value:
                    if isinstance(item, dict) and "field" in item:
                        kwargs = {k: v for k, v in item.items() if k != "field"}
                        tooltips.append(alt.Tooltip(item["field"], **kwargs))
                    else:
                        tooltips.append(item)
                return tooltips
            if not isinstance(value, dict) or "field" not in value:
                return value
            kwargs = {k: v for k, v in value.items() if k != "field"}
            channel_map = {
                "x": alt.X,
                "y": alt.Y,
                "color": alt.Color,
                "size": alt.Size,
                "shape": alt.Shape,
                "column": alt.Column,
                "row": alt.Row,
                "tooltip": alt.Tooltip,
            }
            factory = channel_map.get(key)
            if factory is None:
                return value
            return factory(value["field"], **kwargs)

        encoded = {key: _to_channel(key, value) for key, value in encoding_spec.items()}
        if encoded:
            chart = chart.encode(**encoded)

        width = spec.get("width", "container")
        height = spec.get("height", 400)
        chart = chart.properties(width=width, height=height)
        title = chart_payload.get("title")
        if title:
            chart = chart.properties(title=title)
        return chart

    def _render_chart(self, chart_payload: Dict[str, Any]) -> None:
        chart_obj = self._encode_chart(chart_payload)
        if not chart_obj:
            st.info("Chart requested, but no data returned.")
            return
        try:
            st.altair_chart(chart_obj, use_container_width=True)
        except Exception as exc:  # pragma: no cover - UI fails safe
            st.error(f"Unable to render chart: {exc}")

    def _render_tool_response(self, tool_content: str) -> None:
        try:
            payload = json.loads(tool_content)
        except (TypeError, json.JSONDecodeError):
            st.markdown(tool_content)
            return

        summary = payload.get("summary")
        if summary:
            with st.expander("Summary", expanded=False):
                st.json(summary)

        alerts = payload.get("alerts") or []
        if alerts:
            with st.expander("Alerts", expanded=False):
                st.table(alerts)

        metrics = payload.get("metrics")
        if metrics:
            with st.expander("Metrics", expanded=False):
                st.json(metrics)

        records = payload.get("data")
        if records:
            with st.expander("Records", expanded=False):
                st.dataframe(records)

        narrative = payload.get("narrative")
        if narrative:
            st.markdown(narrative)

        charts = payload.get("charts") or []
        for chart_payload in charts:
            self._render_chart(chart_payload)
            description = chart_payload.get("description")
            if description:
                st.caption(description)

        suspected_fraud = False
        if summary:
            verdict = str(summary.get("verdict", "")).lower()
            severity = str(summary.get("severity", "")).lower()
            suspected_fraud = verdict not in {"", "clear"} or severity in {"medium", "high"}
        if suspected_fraud and self.visuals.fraud:
            st.image(
                base64.b64decode(self.visuals.fraud),
                caption="Sniffer raised a fraud alert.",
                width=self.IMAGE_WIDTH,
            )

        chart_count = payload.get("chart_count")
        if chart_count == 0:
            st.caption("No chartable datapoints returned.")

    # ------------------------------------------------------------------
    # History helpers
    # ------------------------------------------------------------------
    def _append_history(self, message: Dict[str, Any]) -> None:
        history = st.session_state["sniffer_messages"]
        history.append(message)

    def _trimmed_history(self) -> List[Dict[str, Any]]:
        history = st.session_state["sniffer_messages"]
        if len(history) <= self.MODEL_HISTORY_LIMIT:
            return history
        trimmed = [history[0]]
        trimmed.extend(history[-(self.MODEL_HISTORY_LIMIT - 1) :])
        return trimmed

    # ------------------------------------------------------------------
    # Core chat loop
    # ------------------------------------------------------------------
    def _handle_tool_calls(self, message: Any) -> Any:
        # Show fetching stage bubble
        stage_placeholder = st.empty()
        stage_placeholder.markdown(
            self._stage_markup(
                self.visuals.ready,
                "Sniffer is getting data from Envio Hypersync — fetching on-chain evidence.",
                show_loader=True,
                stage="fetch",
            ),
            unsafe_allow_html=True,
        )
        
        # Execute tools
        tool_calls = getattr(message, "tool_calls", None) or []
        for tool_call in tool_calls:
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)
            tool_result = self.function_map[function_name](**function_args)
            self._append_history(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": function_name,
                    "content": tool_result,
                }
            )
            # Show tool results in expanders
            with st.expander("📊 Data Retrieved", expanded=False):
                self._render_tool_response(tool_result)
        
        # Update to reviewing stage bubble
        stage_placeholder.markdown(
            self._stage_markup(
                self.visuals.thinking,
                "Sniffer is reviewing the evidence — drafting your investigation brief.",
                show_loader=True,
                stage="draft",
            ),
            unsafe_allow_html=True,
        )
        
        return stage_placeholder

    def _stage_markup(
        self,
        image_b64: str,
        caption: str,
        *,
        show_loader: bool = False,
        stage: str | None = None,
    ) -> str:
        stage_class = f" stage--{stage}" if stage else ""
        caption_html = caption.replace(
            "Sniffer", "<span class='sniffer-stage-highlight'>Sniffer</span>", 1
        )
        loader_html = (
            "<div class='sniffer-stage-loader'><span></span><span></span><span></span></div>"
            if show_loader
            else ""
        )
        return (
            "<div class='sniffer-visual'>"
            f"<div class='sniffer-stage-bubble{stage_class}'>"
            f"<img class='sniffer-stage-icon' src='data:image/png;base64,{image_b64}' alt='Sniffer stage icon' />"
            f"<div class='sniffer-stage-text'>{caption_html}</div>"
            f"{loader_html}"
            "</div>"
            "</div>"
        )

    def _inject_spinner_css(self) -> None:
        spinner_css = textwrap.dedent(
            f"""
            <style>
            .sniffer-visual {{
                display: flex;
                flex-direction: column;
                justify-content: flex-end;
                align-items: center;
                min-height: 120px;
                gap: 10px;
                text-align: center;
            }}
            .sniffer-stage-bubble {{
                display: inline-flex;
                align-items: center;
                gap: 12px;
                padding: 8px 18px;
                border-radius: 999px;
                background: linear-gradient(135deg, #192e4c, #0f1d33);
                border: 1px solid rgba(255, 255, 255, 0.08);
                box-shadow: 0 8px 24px rgba(15, 27, 46, 0.45);
            }}
            .sniffer-stage-bubble.stage--fetch {{
                background: linear-gradient(135deg, #1c3156, #0f1d33);
            }}
            .sniffer-stage-bubble.stage--draft {{
                background: linear-gradient(135deg, #221c49, #121c3a);
            }}
            .sniffer-stage-bubble.stage--deliver {{
                background: linear-gradient(135deg, #1f3b65, #142b49);
            }}
            .sniffer-stage-icon {{
                width: 28px;
                height: 28px;
                border-radius: 8px;
                filter: drop-shadow(0 6px 12px rgba(0, 0, 0, 0.35));
            }}
            .sniffer-stage-text {{
                font-size: 0.92rem;
                font-weight: 600;
                letter-spacing: 0.3px;
                color: #f5f7fb;
            }}
            .sniffer-stage-highlight {{
                background: linear-gradient(135deg, #2f6bff, #8b47ff);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
            }}
            .sniffer-stage-loader {{
                display: inline-flex;
                align-items: center;
                gap: 6px;
            }}
            .sniffer-stage-loader span {{
                width: 9px;
                height: 9px;
                border-radius: 50%;
                background: linear-gradient(135deg, #2f6bff, #8b47ff);
                box-shadow: 0 0 10px rgba(143, 71, 255, 0.6);
                animation: snifferPulse 1.2s ease-in-out infinite;
            }}
            .sniffer-stage-loader span:nth-child(2) {{
                animation-delay: 0.15s;
            }}
            .sniffer-stage-loader span:nth-child(3) {{
                animation-delay: 0.3s;
            }}
            .sniffer-thinking-loader,
            .sniffer-thinking-loader span,
            .sniffer-thinking-wall {{
                display: none !important;
            }}
            .sniffer-intro-caption {{
                margin-top: 0.6rem;
                font-size: 0.92rem;
                letter-spacing: 0.2px;
                color: rgba(236, 241, 255, 0.75);
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
        )
        st.markdown(spinner_css, unsafe_allow_html=True)

    def _render_intro(self) -> None:
        history = st.session_state["sniffer_messages"]
        if st.session_state.get("sniffer_intro_shown"):
            return
        intro_message = SnifferMessage(
            "assistant",
            "**Sniffer reporting for duty!**\nShare a wallet, contract, pool, or transaction hash and I'll fetch the data, sniff for anomalies, and chart anything suspicious.",
        )
        history.append({
            "role": "assistant",
            "content": intro_message.content,
            "image_b64": self.visuals.happy,
        })
        st.session_state["sniffer_intro_shown"] = True

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def render(self) -> None:
        self._inject_spinner_css()
        self._render_intro()
        self._display_history()
        self._chat_loop()

    def _display_history(self) -> None:
        for message in st.session_state["sniffer_messages"]:
            role = message.get("role")
            if role in {"system", "tool"}:
                continue
            with st.chat_message(role or "assistant"):
                stage_caption = message.get("stage_caption")
                stage_image_b64 = message.get("stage_image_b64") or message.get("image_b64")
                stage_name = message.get("stage")
                show_stage_loader = bool(message.get("stage_show_loader"))

                if stage_caption and stage_image_b64:
                    st.markdown(
                        self._stage_markup(
                            stage_image_b64,
                            stage_caption,
                            show_loader=show_stage_loader,
                            stage=stage_name,
                        ),
                        unsafe_allow_html=True,
                    )
                else:
                    image_b64 = message.get("image_b64")
                    if image_b64:
                        st.image(base64.b64decode(image_b64), width=self.IMAGE_WIDTH)
                content = message.get("content")
                if content:
                    st.markdown(content)

    def _chat_loop(self) -> None:
        user_prompt = st.chat_input(
            "Try: 'Analyze wallet activity for 0x...', 'Scan swap events for pool ...', or 'Review tx hash ...'"
        )
        if not user_prompt:
            return

        user_message = SnifferMessage("user", user_prompt).to_dict()
        self._append_history(user_message)

        with st.chat_message("user"):
            st.markdown(user_prompt)

        with st.chat_message("assistant", avatar=None):
            stage_placeholder = None
            pending = self.client.chat.completions.create(
                model=self.model_name,
                messages=self._trimmed_history(),
                tools=self.tools,
                tool_choice="auto",
                )

            while True:
                message = pending.choices[0].message
                tool_calls = getattr(message, "tool_calls", None) or []

                if tool_calls:
                    self._append_history(message.model_dump())
                    stage_placeholder = self._handle_tool_calls(message)
                    pending = self.client.chat.completions.create(
                        model=self.model_name,
                        messages=self._trimmed_history(),
                        tools=self.tools,
                        tool_choice="auto",
                        )
                    continue

                content = getattr(message, "content", None)
                if content:
                    assistant_record = message.model_dump()
                    assistant_record["stage_caption"] = (
                        "Sniffer is getting data from Envio Hypersync — fetching on-chain evidence."
                    )
                    assistant_record["stage_image_b64"] = self.visuals.ready
                    assistant_record["stage"] = "fetch"
                    assistant_record["stage_show_loader"] = False
                    assistant_record["image_b64"] = self.visuals.ready
                    self._append_history(assistant_record)
                    
                    # Clear the reviewing bubble and show final stage
                    if stage_placeholder:
                        stage_placeholder.empty()
                    
                    st.markdown(
                        self._stage_markup(
                            self.visuals.ready,
                            "Sniffer is getting data from Envio Hypersync — fetching on-chain evidence.",
                            stage="fetch",
                        ),
                        unsafe_allow_html=True,
                    )
                    st.markdown(content)
                    break
