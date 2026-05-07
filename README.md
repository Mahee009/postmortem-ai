<div align="center">

# ⚰️ PostMortemAI

### *Find out how you'll fail — before you do.*

[![Live Demo](https://img.shields.io/badge/Live_Demo-postmortem--ai.vercel.app-black?style=for-the-badge&logo=vercel)](https://postmortem-ai-1pa9.vercel.app)
[![GitHub Stars](https://img.shields.io/github/stars/Mahee009/postmortem-ai?style=for-the-badge&logo=github&color=yellow)](https://github.com/Mahee009/postmortem-ai)
[![Python](https://img.shields.io/badge/Python-3.11+-blue?style=for-the-badge&logo=python)](https://python.org)
[![LangGraph](https://img.shields.io/badge/LangGraph-Orchestration-purple?style=for-the-badge)](https://langchain-ai.github.io/langgraph/)

<br/>

**Describe your startup in plain English.**
**We pattern-match it against 5,000+ documented failures and tell you, unsentimentally, where the cracks are.**

<br/>

> *"The kind of analysis a good investor gives you in minute 3 of a pitch — before you waste 2 years of your life."*

<br/>

![PostMortemAI Demo](https://raw.githubusercontent.com/Mahee009/postmortem-ai/main/assets/demo.gif)

</div>

---

## What This Actually Does

Most AI tools summarize. This one **diagnoses**.

You describe your startup. PostMortemAI:

1. **Classifies** your startup — type, stage, model, team, market
2. **Retrieves** the 15 most similar startup failures from a live vector database of 5,000+ indexed postmortems
3. **Reasons** across failure patterns using a VC-style analysis framework
4. **Outputs** a personalized failure risk report — ranked killers, specific evidence from real failures, 30-day survival tests with pass/fail conditions

```
Input:  "B2B SaaS for freelancers, 6 months in, 50 free users, 3 paying,
         competing with Notion and Linear, no growth channel yet..."

Output: ☠️ Killer 1: You're building a feature, not a product
        ☠️ Killer 2: Zero switching cost — users leave in 5 seconds
        ☠️ Killer 3: Distribution is the real problem, not the product
        
        → 30-Day Survival Tests with measurable pass/fail conditions
        → 15 similar failed startups as evidence
        → The one question a VC would ask that exposes everything
```

---

## Architecture

This is not a chatbot. It's a **4-stage multi-agent reasoning system**.

```
┌─────────────────────────────────────────────────────────────┐
│                      User Description                        │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────┐
│  STAGE 1 — Classifier Agent                                  │
│  Claude extracts: startup type, stage, model, team,          │
│  revenue, target customer, biggest worry                     │
└──────────────────────────┬───────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────┐
│  STAGE 2 — Retrieval Agent                                   │
│  Semantic search over 5,000+ postmortems via Qdrant          │
│  sentence-transformers embeddings (all-MiniLM-L6-v2)        │
│  Returns top 15 by cosine similarity                         │
└──────────────────────────┬───────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────┐
│  STAGE 3 — Synthesis Agent                                   │
│  VC-memo style reasoning across retrieved failures           │
│  Identifies 3 specific killers with evidence chains          │
│  Generates 30-day survival tests with pass/fail conditions   │
└──────────────────────────┬───────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────┐
│  STAGE 4 — Competitor Agent                                  │
│  Live competitor lookup via Serper.dev                       │
│  Returns real companies competing in your exact space        │
└──────────────────────────┬───────────────────────────────────┘
                           ▼
                    Risk Report + Sources
```

**Orchestrated by LangGraph** — stateful, resumable, production-grade agent graph with typed state, conditional routing, and human-in-the-loop ready architecture.

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| **LLM** | HuggingFace Router (auto-failover) | Free, reliable, no hardcoded model names |
| **Orchestration** | LangGraph | Stateful multi-agent graph |
| **Vector DB** | Qdrant Cloud | Semantic postmortem retrieval |
| **Embeddings** | sentence-transformers (local) | Zero API dependency |
| **Scraping** | Firecrawl + Jina.ai | Postmortem ingestion pipeline |
| **Competitor Intel** | Serper.dev | Live Google search results |
| **API** | FastAPI + Pydantic | Typed, async, production-ready |
| **Frontend** | Next.js 14 + Tailwind | Premium dark UI |
| **Deployment** | Render (API) + Vercel (UI) | Free tier, auto-deploy on push |

---

## What Makes This Non-Trivial

Most LLM projects are API wrappers. This isn't.

**The hard parts:**

- **Cross-session semantic retrieval** — not keyword search. Finds failures by business similarity, not word overlap.
- **LLM-as-judge synthesis** — the agent doesn't just summarize. It reasons about *which* failure patterns apply to *this* startup specifically and *why*.
- **Auto-discovery LLM routing** — fetches live free model list from HuggingFace at runtime. Never breaks on deprecated model names.
- **VC-constraint prompting** — explicit rules that ban generic outputs ("pricing strategy", "single revenue stream"). Forces specific, evidence-grounded reasoning.
- **Multi-source data fusion** — postmortem database + live competitor search + LLM reasoning, unified in one response.

---

## Running Locally

```bash
# Clone
git clone https://github.com/Mahee009/postmortem-ai
cd postmortem-ai

# Install
pip install -r requirements.txt

# Configure
cp .env.example .env
# Fill in: OPENROUTER_API_KEY, QDRANT_URL, QDRANT_API_KEY, SERPER_API_KEY

# Start Qdrant
docker run -d -p 6333:6333 qdrant/qdrant

# Health check
python scripts/health_check.py

# Ingest postmortems (first time only, ~30 min)
python scripts/ingest_all.py

# Run
uvicorn api.main:app --reload --port 8000 &
cd frontend-next && npm install && npm run dev
```

Open `http://localhost:3000`

---

## Data Sources

5,000+ postmortems indexed from:

- [Failory](https://failory.com) — curated startup cemetery
- Hacker News "Tell HN: We're shutting down" posts
- [Indie Hackers](https://indiehackers.com) failure stories
- CB Insights startup failure database
- Medium/Substack postmortem posts

All public. No proprietary data. Structured via LLM extraction into 14 failure taxonomy categories.

---

## Project Structure

```
postmortem-ai/
├── agents/
│   ├── orchestrator.py      # LangGraph agent graph
│   ├── classifier.py        # Startup profile extraction
│   ├── matcher.py           # Semantic retrieval
│   ├── synthesizer.py       # VC-style risk synthesis
│   ├── competitors.py       # Live competitor lookup
│   └── llm.py               # Auto-discovery LLM router
├── ingestion/
│   ├── scraper.py           # Firecrawl-based ingestion
│   ├── extractor.py         # LLM structured extraction
│   └── embedder.py          # Embeddings + Qdrant ops
├── api/
│   └── main.py              # FastAPI server
├── frontend-next/           # Next.js 14 frontend
├── scripts/
│   ├── ingest_all.py        # Full ingestion pipeline
│   └── health_check.py      # Service verification
└── CLAUDE.md                # AI agent context file
```

---

## Failure Taxonomy

The agent classifies every failure into 14 categories:

`no_market_need` · `ran_out_of_cash` · `team_issues` · `competition` · `wrong_pricing` · `poor_product` · `bad_timing` · `regulatory` · `pivot_failed` · `scaling_too_fast` · `customer_acquisition` · `founder_burnout` · `monetization_failed` · `distribution_failed`

---

## Why I Built This

I kept reading startup postmortems thinking: *someone should make this queryable.*

The knowledge exists. 5,000+ founders wrote down exactly why they failed. It's just scattered across blog posts, HN threads, and Medium articles — unsearchable and unstructured.

PostMortemAI is the query layer over collective startup failure knowledge.

---

## Contributing

- Add postmortem sources → edit `data/sources.json`
- Improve extraction quality → edit `ingestion/extractor.py`  
- Sharpen the risk report → edit the synthesis prompt in `agents/synthesizer.py`
- Add 500+ new postmortems → you get a shoutout in the README

---

<div align="center">

**Built by [Mahee Tibrewal](https://github.com/Mahee009)**

*Pattern matching from public failure stories. Not advice.*

⭐ Star this if you think every founder should know their failure patterns before they fail

</div>
