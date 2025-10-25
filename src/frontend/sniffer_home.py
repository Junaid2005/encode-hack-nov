import streamlit as st
import time
from pathlib import Path


def stream_data(text):
    for letter in text:
        yield letter
        time.sleep(0.05)


st.set_page_config(
    page_title="Sniffer Home",
    page_icon="🏠",
    layout="wide",
)

st.title("🏠 Sniffer Home")
image_path = Path(__file__).resolve().parents[1] / "happy_sniffer.png"

if not st.session_state.get("sniffer_home_visited", False):
    st.session_state["sniffer_home_visited"] = True
    st.write_stream(stream_data("Welcome to the Sniffer..... 🔎"))
    st.image(str(image_path), width=360)
    st.balloons()
else:
    st.image(str(image_path), width=360)
    st.caption("Welcome back to the Sniffer!")

st.subheader("What we do")
st.write(
    """
We're a pack of developers who are *paws-itively* passionate about blockchain and data analysis. 
We've built Sniffer to help you sniff out suspicious activity on the blockchain—no bones about it!

**Our Tools:**  
- 🐶 **Sniffer Core**: An AI-powered assistant that doesn't just sit and stay—it actively helps you 
  query blockchain data verbally, generates insightful graphs, and lets you have a proper conversation 
  about your findings. Ask questions, get answers, and visualise patterns without lifting a paw.

- 🐕‍🦺 **Sniffer Client**: An MCP UI client for HyperSync that lets you dig deep into blockchain data 
  with powerful fraud detection analytics. It's the ultimate fetch tool for blockchain forensics.

Whether you're tracking down dodgy transactions or analysing market trends, Sniffer has got your back. 
We're not barking up the wrong tree—we're leading the pack in blockchain fraud detection! 🦴
"""
)
st.subheader("The pack behind Sniffer 🐕")

col1, col2, col3 = st.columns(3, vertical_alignment="top")

with col1:
    with st.container(border=True, height=300):
        st.subheader("Abdul 🐕")
        st.markdown("**Chief Sniffer Officer**")
        st.write(
            "Leads the pack with expertise in backend development and data analysis. Sniffs out fraud patterns in blockchain data with unmatched precision."
        )
        st.markdown(
            "🔗 [GitHub](https://github.com/AbdulAaqib) | 💼 [LinkedIn](https://www.linkedin.com/in/abdulaaqib/)"
        )

with col2:
    with st.container(border=True, height=300):
        st.subheader("Junaid 🐕‍🦺")
        st.markdown("**Lead Paw-grammer**")
        st.write(
            "Crafts the frontend experience with Streamlit wizardry. Transforms complex data into beautiful, intuitive interfaces that even a puppy could navigate."
        )
        st.markdown(
            "🔗 [GitHub](https://github.com/Junaid2005) | 💼 [LinkedIn](https://www.linkedin.com/in/junaid-mohammad-4a4091260/)"
        )

with col3:
    with st.container(border=True, height=300):
        st.subheader("Walid 🦮")
        st.markdown("**Chief Strategy Officer**")
        st.write(
            "Guides the pack's vision and brand identity. Ensures Sniffer remains the top dog in blockchain fraud detection through strategic planning and market positioning."
        )
        st.markdown("💼 [LinkedIn](https://www.linkedin.com/in/walid-m-155819267/)")
