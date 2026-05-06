"""
frontend/app.py — Streamlit UI for PostMortemAI
Clean, founder-focused interface
"""

import streamlit as st
import httpx
import asyncio
import os

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(
    page_title="PostMortemAI — Know Before You Fail",
    page_icon="⚰️",
    layout="wide",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main { max-width: 900px; }
    .stTextArea textarea { font-size: 16px; }
    .risk-card { 
        background: #1a1a2e; 
        border-radius: 8px; 
        padding: 16px; 
        margin: 8px 0;
    }
    h1 { font-size: 2.2rem !important; }
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.title("⚰️ PostMortemAI")
st.caption("Describe your startup. We'll tell you which failure patterns from 5,000+ postmortems are most likely to kill it.")

col1, col2, col3 = st.columns(3)
try:
    resp = httpx.get(f"{API_URL}/stats", timeout=3)
    stats = resp.json()
    with col1:
        st.metric("Postmortems Indexed", f"{stats.get('total_postmortems', 0):,}")
    with col2:
        st.metric("Failure Patterns", "14")
    with col3:
        st.metric("Startup Types", "12")
except:
    with col1:
        st.metric("Postmortems Indexed", "Loading...")

st.divider()

# ── Input ─────────────────────────────────────────────────────────────────────
st.subheader("Tell us about your startup")

examples = [
    "Custom",
    "B2B SaaS, 6 months in, no revenue yet",
    "Marketplace, 1 year old, 200 users, 3 paying",
    "Consumer app, Series A funded, growth stalled",
]

example = st.selectbox("Load an example (or type your own below):", examples)

if example != "Custom":
    prefill = example
else:
    prefill = ""

description = st.text_area(
    "Describe your startup in plain English",
    value=prefill,
    height=160,
    placeholder="""Example: I'm building a B2B SaaS for restaurant inventory management. 
8 months in, team of 2, bootstrapped. We have 30 beta users but only 2 paying customers.
My biggest worry is that restaurants tell us they love it but won't pay for it...""",
    label_visibility="collapsed",
)

st.caption("The more specific you are, the more accurate your risk report. Include: what you build, for whom, your stage, revenue, team size, and what worries you most.")

analyze_btn = st.button("⚡ Analyze My Startup", type="primary", use_container_width=True)

# ── Analysis ──────────────────────────────────────────────────────────────────
if analyze_btn and description.strip():
    with st.spinner("Analyzing against 5,000+ startup failures... (~15 seconds)"):
        try:
            response = httpx.post(
                f"{API_URL}/analyze",
                json={"description": description},
                timeout=120,
            )
            response.raise_for_status()
            result = response.json()

            if result.get("error"):
                st.error(f"Error: {result['error']}")
            else:
                # Profile summary
                profile = result.get("startup_profile", {})
                if profile:
                    with st.expander("📋 How we classified your startup", expanded=False):
                        col1, col2, col3, col4 = st.columns(4)
                        col1.metric("Type", profile.get("type", "?"))
                        col2.metric("Stage", profile.get("stage", "?"))
                        col3.metric("Revenue", profile.get("revenue", "?"))
                        col4.metric("Similar Failures Found", result.get("similar_failures_count", 0))

                # Main report
                st.divider()
                st.markdown(result["risk_report"])

                # Sources
                sources = result.get("source_postmortems", [])
                if sources:
                    st.divider()
                    with st.expander(f"📚 {len(sources)} Postmortems Used as Evidence", expanded=False):
                        for s in sources:
                            score_pct = int(s.get("similarity_score", 0) * 100)
                            st.markdown(f"""
**{s.get('startup_name', 'Unknown')}** — {s.get('primary_failure_cause', '?').replace('_', ' ').title()} `{score_pct}% similar`

{s.get('raw_summary', '')}

[Read full postmortem]({s.get('source_url', '#')}) 
---""")

        except httpx.HTTPStatusError as e:
            st.error(f"API error: {e.response.text}")
        except Exception as e:
            st.error(f"Something went wrong: {str(e)}")

elif analyze_btn:
    st.warning("Please describe your startup first.")

# ── Footer ────────────────────────────────────────────────────────────────────
st.divider()
st.caption(
    "PostMortemAI is open source. "
    "[View on GitHub](https://github.com/yourusername/postmortem-ai) · "
    "Built with Claude, LangGraph, and Qdrant · "
    "Not financial advice — this is pattern matching from public failure stories."
)
