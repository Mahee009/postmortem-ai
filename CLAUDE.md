# PostMortemAI — CLAUDE.md

## What This Project Is
PostMortemAI is an open-source AI agent that indexes 5,000+ startup failure postmortems and tells founders which failure patterns are most likely to kill their specific startup right now.

**The core loop:**
1. Ingest + structure postmortems from HN, Indie Hackers, Failory, CB Insights
2. User describes their startup in plain English
3. Agent classifies the startup, retrieves the 15 most similar failures
4. Synthesizes a personalized "failure risk report" with ranked risks + countermeasures

---

## Project Structure
```
postmortem-ai/
├── CLAUDE.md                  ← You are here
├── .env                       ← API keys (never commit)
├── requirements.txt
├── ingestion/
│   ├── scraper.py             ← Firecrawl-based scraper for postmortem sources
│   ├── extractor.py           ← LLM-based structured extraction from raw text
│   └── embedder.py            ← Chunk + embed + upsert to Qdrant
├── agents/
│   ├── classifier.py          ← Startup classifier agent (multi-turn)
│   ├── matcher.py             ← Semantic retrieval from Qdrant
│   ├── synthesizer.py         ← Risk synthesis agent (core reasoning)
│   └── orchestrator.py        ← LangGraph orchestration of all agents
├── api/
│   └── main.py                ← FastAPI server
├── frontend/
│   └── app.py                 ← Streamlit UI
├── scripts/
│   ├── ingest_all.py          ← Run full ingestion pipeline
│   └── health_check.py        ← Verify Qdrant + API keys work
└── data/
    └── sources.json           ← List of postmortem URLs to scrape
```

---

## Tech Stack
- **LLM:** Claude Sonnet via Anthropic API (`claude-sonnet-4-20250514`)
- **Orchestration:** LangGraph (stateful agent graphs)
- **Vector DB:** Qdrant (local Docker or Qdrant Cloud free tier)
- **Scraping:** Firecrawl API
- **Web framework:** FastAPI
- **UI:** Streamlit
- **Deployment:** Railway (API + Streamlit), Qdrant Cloud

---

## Environment Variables (.env)
```
ANTHROPIC_API_KEY=sk-ant-...
FIRECRAWL_API_KEY=fc-...
QDRANT_URL=http://localhost:6333        # or your Qdrant Cloud URL
QDRANT_API_KEY=                         # only needed for Qdrant Cloud
QDRANT_COLLECTION=postmortems
```

---

## Key Architectural Decisions

### 1. Postmortem Schema (what we extract from every failure story)
Every postmortem gets structured into this exact shape:
```json
{
  "id": "uuid",
  "source_url": "https://...",
  "startup_name": "Acme Inc",
  "startup_type": "B2B SaaS | B2C | Marketplace | Hardware | ...",
  "stage_at_failure": "pre-product | pre-revenue | early-revenue | growth | Series A+",
  "team_size": 3,
  "months_alive": 18,
  "funding": "bootstrapped | pre-seed | seed | Series A",
  "primary_failure_cause": "no market need | ran out of cash | team issues | competition | pricing | ...",
  "secondary_causes": ["cause1", "cause2"],
  "warning_signs_missed": ["sign1", "sign2"],
  "decision_point": "The specific moment where a different decision would have changed the outcome",
  "what_they_would_do_differently": "Free text",
  "raw_summary": "2-3 sentence plain English summary"
}
```

### 2. The Startup Profile (what we ask the user)
```json
{
  "description": "What we're building in plain English",
  "type": "B2B SaaS | B2C | Marketplace | ...",
  "stage": "idea | pre-product | pre-revenue | early-revenue | growth",
  "months_in": 6,
  "team_size": 2,
  "funding": "bootstrapped | pre-seed | seed",
  "biggest_worry": "Free text — what keeps you up at night",
  "revenue": "$0 | <$1K | $1K-$10K | $10K+ MRR"
}
```

### 3. Similarity Search
We embed a combined string per postmortem:
`"{startup_type} {stage_at_failure} {primary_failure_cause} {raw_summary}"`

And query with:
`"{user.type} {user.stage} {user.description} {user.biggest_worry}"`

This gives us semantic similarity over *business context*, not just keywords.

### 4. Risk Report Structure
The synthesizer outputs exactly this:
```
## Your Top 5 Failure Risks

### Risk 1: [Name] — Severity: CRITICAL
Evidence from X similar failures: [specific examples]
Warning signs to watch RIGHT NOW: [list]
What to do this week: [specific action]

[repeat for risks 2-5]

## The Failure Pattern Most Likely To Kill You
[Single paragraph, direct, no fluff]

## Your 30-Day Survival Checklist
[ ] Action 1
[ ] Action 2
...
```

---

## Agent Flow (LangGraph)
```
START
  ↓
[classifier_node] — asks 5 clarifying questions, builds startup profile
  ↓
[retrieval_node] — queries Qdrant, gets top 15 similar postmortems
  ↓
[pattern_node] — extracts failure patterns from retrieved postmortems
  ↓
[synthesis_node] — generates personalized risk report
  ↓
END → returns risk report + source postmortems
```

---

## Claude Code Conventions
- Always use `async/await` for all LLM and Qdrant calls
- All LLM calls go through `agents/base.py` — never call Anthropic API directly in agent files
- Each agent file has ONE public function: `async def run(input: dict) -> dict`
- Errors are never swallowed — always re-raise with context
- No print statements — use Python `logging` module everywhere
- Type hints on every function signature

---

## Running Locally
```bash
# 1. Start Qdrant
docker run -p 6333:6333 qdrant/qdrant

# 2. Install deps
pip install -r requirements.txt

# 3. Run ingestion (first time only, takes ~30 min)
python scripts/ingest_all.py

# 4. Start API
uvicorn api.main:app --reload --port 8000

# 5. Start UI (separate terminal)
streamlit run frontend/app.py
```

---

## Common Tasks for Claude Code
- "Add a new postmortem source" → edit `data/sources.json` + test with `ingestion/scraper.py`
- "The classifier is asking too many questions" → edit `agents/classifier.py`, reduce `MAX_CLARIFICATION_TURNS`
- "Risk report feels generic" → edit the system prompt in `agents/synthesizer.py`
- "Add a new failure taxonomy category" → edit `FAILURE_TAXONOMY` in `ingestion/extractor.py`
- "Deploy to Railway" → see `scripts/deploy.sh`
