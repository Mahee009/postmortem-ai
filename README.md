# ⚰️ PostMortemAI

> Describe your startup. Find out which failure patterns from 5,000+ real postmortems are most likely to kill it.

**[Live Demo](https://postmortem-ai.railway.app)** · **[HN Discussion](#)** · **[Star to support ⭐](#)**

---

## What it does

You describe your startup in plain English. PostMortemAI:

1. Classifies your startup (type, stage, model, team)
2. Retrieves the 15 most similar startup failures from a database of 5,000+ indexed postmortems
3. Synthesizes a **personalized failure risk report** — ranked risks, specific evidence, warning signs you might already have, and a 30-day survival checklist

**Not generic advice. Pattern matching against real failures.**

```
Input:  "I'm building B2B SaaS for freelancers, 6 months in, 50 free users, 3 paying..."

Output: Your Top 5 Failure Risks — ranked, evidenced, actionable
        The pattern most likely to kill you
        Your 30-day survival checklist
        The thing you're probably lying to yourself about
```

---

## Architecture

```
User Description
      ↓
[Classifier Agent]     ← Claude Sonnet — extracts structured startup profile
      ↓
[Retrieval Agent]      ← Qdrant semantic search over 5,000+ postmortems
      ↓
[Synthesis Agent]      ← Claude Sonnet — generates personalized risk report
      ↓
Risk Report (Markdown)
```

**Tech stack:** Claude Sonnet · LangGraph · Qdrant · FastAPI · Streamlit · Firecrawl · sentence-transformers

---

## Quickstart (5 minutes)

### Prerequisites
- Python 3.11+
- Docker (for Qdrant)
- API keys: [Anthropic](https://console.anthropic.com) · [Firecrawl](https://firecrawl.dev) (free tier)

```bash
# 1. Clone
git clone https://github.com/yourusername/postmortem-ai
cd postmortem-ai

# 2. Install
pip install -r requirements.txt

# 3. Configure
cp .env.example .env
# Edit .env with your API keys

# 4. Start Qdrant
docker run -d -p 6333:6333 qdrant/qdrant

# 5. Health check
python scripts/health_check.py

# 6. Ingest postmortems (30-40 min, first time only)
python scripts/ingest_all.py

# 7. Run
uvicorn api.main:app --reload &
streamlit run frontend/app.py
```

Open http://localhost:8501

---

## Deploy (no laptop required)

### Railway (recommended — free tier works)
```bash
npm install -g @railway/cli
railway login
railway init
railway up
```
Set env vars in Railway dashboard. Add Qdrant Cloud free tier for the vector DB.

### Qdrant Cloud (free 1GB tier)
1. Sign up at cloud.qdrant.io
2. Create a cluster → copy the URL + API key
3. Set `QDRANT_URL` and `QDRANT_API_KEY` in Railway

---

## Data Sources
Postmortems are scraped and structured from:
- [Failory](https://failory.com) startup cemetery
- Hacker News "Tell HN: We're shutting down" posts
- [Indie Hackers](https://indiehackers.com) failure stories
- CB Insights startup failure database
- Medium/Substack postmortem posts

All sources are public. No proprietary data.

---

## Contributing
- Add postmortem sources → edit `data/sources.json`
- Improve extraction → edit `ingestion/extractor.py`
- Improve the risk report → edit the prompt in `agents/synthesizer.py`
- PRs welcome. If you add 500+ new postmortems, you get a shoutout in the README.

---

## Why I built this

I kept reading startup postmortems and thinking "someone should build a way to query all of this." The knowledge exists. It's just scattered and unsearchable. This is the tool I wished existed when I started my first company.

---

*Built by [you] · MIT License · Not financial advice*
