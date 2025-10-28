# 🐕 Sniffer - AI-Powered Blockchain Fraud Detection

<div align="center">

![Sniffer Logo](src/sniffer_logo.png)

**An intelligent blockchain investigation platform combining AI analysis with real-time Ethereum data to detect fraudulent activities.**

Made with ❤️ by **Abdul**, **Junaid**, and **Walid** for Encode Hackathon (November 2024)

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-FF4B4B.svg)](https://streamlit.io)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

</div>

---

## 🎯 Overview

**Sniffer** is your K9 detective for blockchain fraud 🐶🔍. It combines cutting-edge AI (OpenAI GPT) with powerful blockchain analytics to help investigators identify suspicious wallet activity, contract exploits, swap manipulation, and transaction fraud—all through a simple chat interface.

### Key Highlights

- 🤖 **AI-Powered Analysis**: Natural language queries powered by OpenAI GPT models
- ⚡ **Real-Time Data**: Direct integration with Envio HyperSync for fast Ethereum data access
- 📊 **Statistical Fraud Detection**: Z-score anomalies, network centrality, CUSUM trends
- 💬 **Chat Interface**: Conversational investigation workflow—just ask Sniffer!
- 📈 **Live Market Data**: Track BTC, ETH, SOL, SPY, and USD/GBP prices
- 🎨 **Polished UI**: Custom stage bubbles, mascot animations, and interactive charts

---

## 🚀 Quick Start

### Prerequisites

- Python 3.12 or higher
- pip package manager
- OpenAI API access
- Git

### Installation

```bash
# Clone the repository
git clone https://github.com/Junaid2005/encode-hack-nov.git
cd encode-hack-nov

# Create and activate virtual environment
python3 -m venv venv

# On macOS/Linux:
source venv/bin/activate

# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Configuration

Create a `.streamlit/secrets.toml` file in the project root:

```toml
# OpenAI Configuration
OPENAI_API_KEY = "your-openai-api-key"
OPENAI_MODEL = "gpt-4o-mini"
```

> **Note**: Replace the placeholder values with your actual OpenAI credentials.

### Run the Application

```bash
streamlit run src/frontend/app.py
```

The app will open in your browser at `http://localhost:8501`

---

## 🎮 Usage

### 1. Home Page
- Project overview and feature highlights
- Live cryptocurrency market data dashboard
- BTC, ETH, SOL price tracking with interactive charts

### 2. Sniffer AI (Main Chat Interface)
Ask Sniffer to investigate blockchain activity using natural language:

**Example Queries:**
```
"Analyze wallet 0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb from block 18000000"

"Check Uniswap pool 0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640 for wash trades"

"Scan contract 0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984 for suspicious events"

"Explain transaction hash 0x123abc..."
```

**What You'll Get:**
- 🔍 Plain-language narrative explaining findings
- ⚠️ Severity-ranked alerts (Low/Medium/High)
- 📊 Interactive charts showing anomalies
- 🎯 Actionable next steps for investigation

### 3. Sniffer MCP Tools
Browse available analysis tools:
- `wallet_activity` - Multi-wallet baseline & anomaly detection
- `event_logs` - Contract event monitoring
- `swap_events` - DEX swap surveillance (Uniswap V3)
- `transaction_analysis` - Single transaction deep-dive

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────┐
│          Frontend (Streamlit)                    │
│  • Multi-page dashboard                          │
│  • AI chat interface (ChatWidget)                │
│  • Live crypto market widgets                    │
└──────────────────┬──────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────┐
│       MCP Tools Layer (Function Bridge)          │
│  • OpenAI function calling schemas               │
│  • Input validation & formatting                 │
│  • Response transformation & narratives          │
└──────────────────┬──────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────┐
│      Backend Analytics Engine                    │
│  • Envio HyperSync data fetching                 │
│  • Statistical fraud detection algorithms        │
│  • Network graph analysis                        │
│  • Event decoding (ERC-20, Uniswap V3)           │
└──────────────────────────────────────────────────┘
```

### Technology Stack

**Frontend**
- **Streamlit** - Python web framework
- **Altair** - Declarative visualizations
- **Pandas** - Data manipulation

**AI/LLM**
- **OpenAI GPT** - Natural language understanding
- **Function Calling** - AI → Blockchain tool invocation

**Blockchain**
- **Envio HyperSync** - High-performance Ethereum indexing
- **Custom Decoders** - ERC-20 transfers, Uniswap swaps

**Analytics**
- **NumPy/SciPy** - Statistical computations
- **NetworkX** - Graph centrality analysis

---

## 🔬 Fraud Detection Algorithms

### 1. **Z-Score Anomaly Detection**
Identifies transfers significantly larger/smaller than a wallet's typical activity:
```python
z_score = (value - baseline_mean) / baseline_std
if |z_score| > threshold: → Flag anomaly
```

### 2. **CUSUM Trend Analysis**
Detects sustained behavioral changes (not just one-off spikes):
```python
cusum += max(0, |z_score| - threshold)
if cusum > limit: → Persistent anomaly
```

### 3. **Network Centrality**
Finds "hub" addresses interacting with many counterparties (mixers, exchanges):
```python
centrality = degree_centrality(transfer_graph)
if degree > min_threshold: → High-risk hub
```

### 4. **Price Impact Analysis**
Spots market manipulation or MEV opportunities on Uniswap:
```python
price_delta_bps = (price_after - price_before) / price_before * 10000
if |price_delta_bps| > 50: → High-impact swap
```

### 5. **Wash Trade Detection**
Identifies fake trading volume between colluding addresses:
```python
if (sender == prev_recipient and recipient == prev_sender and
    time_diff < max_interval): → Potential wash trade
```

---

## 📁 Project Structure

```
encode-hack-nov/
├── src/
│   ├── backend/
│   │   ├── fraud_detection.py      # Core detection algorithms
│   │   ├── tools.py                 # High-level analysis wrappers
│   │   ├── yfinance_crypto.py       # Market data fetcher
│   │   └── scripts/                 # Standalone utility scripts
│   │
│   ├── frontend/
│   │   ├── app.py                   # Streamlit entry point
│   │   ├── sniffer_core.py          # Main AI chat page
│   │   ├── sniffer_home.py          # Landing page
│   │   ├── sniffer_client.py        # Tool documentation
│   │   ├── crypto_widgets.py        # Market data widgets
│   │   └── mcp/
│   │       ├── chat_widget.py       # AI chat interface
│   │       ├── mcp_schema.py        # Function calling schemas
│   │       └── mcp_funcs/
│   │           └── mcp_fraud.py     # MCP tool implementations
│   │
│   └── *.png                        # Sniffer mascot images
│
├── requirements.txt                 # Python dependencies
├── pyrightconfig.json              # Type checking config
├── CODE_SUMMARY.txt                # Technical overview
├── NON_TECH_OVERVIEW.txt           # Plain-language guide
└── README.md                       # You are here!
```

---

## 🔧 Development

### Code Overview

**Key Files:**
- `chat_widget.py` - AI chat loop, stage bubbles, tool invocation
- `mcp_schema.py` - OpenAI function schemas (4 main tools)
- `mcp_fraud.py` - Tool wrappers (validation → backend → response formatting)
- `fraud_detection.py` - Statistical algorithms & HyperSync queries
- `tools.py` - High-level analysis orchestration

### Adding New Detection Algorithms

1. **Add algorithm to `fraud_detection.py`**:
```python
def detect_my_pattern(transfers: List[Dict], threshold: float) -> List[Dict]:
    findings = []
    # Your detection logic here
    return findings
```

2. **Integrate in `tools.py`**:
```python
def analyze_wallet_activity(...):
    # ... existing code ...
    my_alerts = detect_my_pattern(transfers, options.my_threshold)
    alerts.extend(my_alerts)
```

3. **Add to MCP schema in `mcp_schema.py`** (if exposing to AI):
```python
{
    "type": "function",
    "function": {
        "name": "my_new_analysis",
        "description": "...",
        "parameters": {...}
    }
}
```

### Running Tests

```bash
# (Add when tests are implemented)
pytest tests/
```

---

## 🎨 UI Features

### Stage Bubbles
Custom HTML/CSS speech bubbles show live analysis progress:

- 🔵 **Fetching Stage**: "Sniffer is getting data from Envio HyperSync..."
- 🟣 **Reviewing Stage**: "Sniffer is reviewing the evidence..."
- ✅ **Complete Stage**: "Sniffer fetched the findings — report ready"

### Mascot States
Different dog images for each stage:
- `happy_sniffer.png` - Normal/success
- `thinking_sniffer.png` - Analyzing
- `fraud_detected_sniffer.png` - Active investigation
- `fraud_sniffer.png` - Fraud alert

---

## 📊 Example Output

```
🐕 Sniffer Analysis Report

Narrative:
"Analysis of wallet 0x123abc revealed 5 suspicious transfers totaling 
150 ETH from blocks 18000000-18005000. Three transfers exceeded 3σ 
from the baseline, and the address shows high network centrality 
(degree=45), suggesting it may be a mixer or exchange."

Alerts:
⚠️ [HIGH] Large transfer: 50 ETH → 0xabc (block 18000123)
⚠️ [MEDIUM] Value anomaly: z-score 3.2 (block 18000456)
⚠️ [MEDIUM] High centrality: degree 45

Next Steps:
• Investigate counterparty 0xabc for known fraud patterns
• Review transaction methods for risky calls
• Check if address is a known mixer service
```

---

## 🤝 Contributing

We welcome contributions! Here's how:

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/amazing-feature`
3. **Make your changes**: Follow existing code style
4. **Commit**: `git commit -m "Add amazing feature"`
5. **Push**: `git push origin feature/amazing-feature`
6. **Open a Pull Request**

### Contribution Guidelines
- Write clear commit messages
- Add docstrings to new functions
- Update README if adding features
- Test thoroughly before submitting

---

## 📝 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **Envio HyperSync** - Lightning-fast Ethereum data indexing
- **OpenAI** - Powering the AI analysis
- **Streamlit** - Making web apps delightfully simple
- **Encode Hackathon** - For the amazing opportunity
- **Open Source Community** - For the incredible tools and libraries

---

## 📚 Additional Resources

- [CODE_SUMMARY.txt](CODE_SUMMARY.txt) - Detailed technical walkthrough
- [NON_TECH_OVERVIEW.txt](NON_TECH_OVERVIEW.txt) - Plain-language explanation
- [Envio HyperSync Docs](https://docs.envio.dev/)
- [Streamlit Docs](https://docs.streamlit.io/)
- [OpenAI Docs](https://platform.openai.com/docs)

---

## 📧 Contact

**Project Team:**
- Abdul
- Junaid
- Walid

**Repository**: [github.com/Junaid2005/encode-hack-nov](https://github.com/Junaid2005/encode-hack-nov)

---

<div align="center">

**🐕 Happy Sniffing! 🔍**

If you find Sniffer useful, please ⭐ star the repository!

</div>
