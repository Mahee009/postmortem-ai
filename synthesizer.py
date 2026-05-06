"""
synthesizer.py — the core reasoning agent
Takes a startup profile + 15 similar failures → personalized risk report
This is where PostMortemAI earns its value
"""

import os
import json
import logging
from anthropic import AsyncAnthropic
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)
client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

SYNTHESIS_PROMPT = """You are a ruthlessly honest startup advisor with deep knowledge of why startups fail.

You have access to {n_failures} real startup failure stories that are similar to this founder's situation.

## The Founder's Startup

{profile_summary}

## Similar Startup Failures (Evidence Base)

{failures_text}

---

## Your Task

Write a personalized failure risk report for this founder. Be direct, specific, and actionable.
Do NOT be generic. Every point must be grounded in the actual failure stories above.

Use EXACTLY this format:

---

# Your Startup Failure Risk Report
*Based on analysis of {n_failures} similar startup failures*

## Your Situation
[2-3 sentences summarizing their startup and what makes their situation interesting/risky. No fluff.]

---

## Top 5 Failure Risks — Ranked by Likelihood

### 🔴 Risk 1: [Short name] — CRITICAL
**What it is:** [One sentence defining this risk precisely]
**Evidence from similar failures:** [2-3 specific examples from the postmortems, with startup names/descriptions]
**Warning signs you may already have:** [2-3 specific observable indicators for THIS founder's situation]
**What to do this week:** [One specific, concrete action. Not "think about it." An actual task.]

### 🟠 Risk 2: [Short name] — HIGH
[Same structure]

### 🟡 Risk 3: [Short name] — MEDIUM
[Same structure]

### 🟡 Risk 4: [Short name] — MEDIUM
[Same structure]

### 🟢 Risk 5: [Short name] — WATCH
[Same structure]

---

## The Pattern Most Likely to Kill You

[One paragraph, 4-6 sentences. Be direct. Name the specific failure mode that has killed the most similar startups at their exact stage. Reference specific postmortems. This should feel like a cold shower — honest and clarifying, not devastating.]

---

## Your 30-Day Survival Checklist

[7-10 specific, actionable items. Each starts with a verb. Numbered list. These should be things they can literally do in the next 30 days to validate or invalidate their biggest risks.]

1. [ ] [Action]
2. [ ] [Action]
...

---

## One Thing You're Probably Lying to Yourself About

[2-3 sentences. The single most common self-deception that kills startups at this exact stage and type. Delivered with empathy but no softening.]

---
*Sources: {n_failures} startup failure postmortems analyzed*
"""

def build_profile_summary(profile: dict) -> str:
    return f"""
- **Type:** {profile.get('type', 'Unknown')}
- **Stage:** {profile.get('stage', 'Unknown')}
- **Description:** {profile.get('description', 'Not provided')}
- **Team:** {profile.get('team_size', '?')} people
- **Funding:** {profile.get('funding', 'Unknown')}
- **Revenue:** {profile.get('revenue', '$0')}
- **Time building:** {profile.get('months_in', '?')} months
- **Biggest worry:** {profile.get('biggest_worry', 'Not stated')}
- **Target customer:** {profile.get('target_customer', 'Unknown')}
- **Business model:** {profile.get('business_model', 'Unknown')}
""".strip()


def build_failures_text(failures: list[dict], max_failures: int = 12) -> str:
    """Format the retrieved failures for the prompt."""
    lines = []
    for i, f in enumerate(failures[:max_failures]):
        score = f.get("similarity_score", 0)
        lines.append(f"""
**Failure #{i+1}** (similarity: {score:.0%})
- Startup: {f.get('startup_name', 'Unknown')} | Type: {f.get('startup_type', '?')}
- Stage at failure: {f.get('stage_at_failure', '?')} | Alive for: {f.get('months_alive', '?')} months
- Primary cause: {f.get('primary_failure_cause', '?')}
- Secondary causes: {', '.join(f.get('secondary_causes', []))}
- Warning signs missed: {', '.join(f.get('warning_signs_missed', []))}
- Decision point: {f.get('decision_point', 'Not recorded')}
- What they'd do differently: {f.get('what_they_would_do_differently', 'Not recorded')}
- Summary: {f.get('raw_summary', 'No summary')}
""".strip())
    return "\n\n".join(lines)


async def synthesize_risk_report(
    startup_profile: dict,
    similar_failures: list[dict],
) -> tuple[str, list[dict]]:
    """
    Generate the personalized risk report.

    Returns:
        (risk_report_markdown, source_postmortems_used)
    """
    if not similar_failures:
        return (
            "⚠️ Not enough similar startup failures found in the database yet. "
            "Try running the ingestion pipeline to add more postmortems.",
            []
        )

    profile_summary = build_profile_summary(startup_profile)
    failures_text = build_failures_text(similar_failures)
    n = len(similar_failures)

    prompt = SYNTHESIS_PROMPT.format(
        n_failures=n,
        profile_summary=profile_summary,
        failures_text=failures_text,
    )

    logger.info(f"Synthesizing risk report from {n} failures...")

    response = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}],
        system="You are a startup failure analyst. You give honest, specific, evidence-based risk assessments. You never give generic advice. Every point must reference specific patterns from the failure data provided."
    )

    report = response.content[0].text.strip()

    # Return the top sources used
    sources = [
        {
            "startup_name": f.get("startup_name", "Unknown"),
            "primary_failure_cause": f.get("primary_failure_cause", ""),
            "raw_summary": f.get("raw_summary", ""),
            "source_url": f.get("source_url", ""),
            "similarity_score": f.get("similarity_score", 0),
        }
        for f in similar_failures[:8]
    ]

    return report, sources


if __name__ == "__main__":
    import asyncio

    # Test with mock data
    profile = {
        "type": "B2B SaaS",
        "stage": "early-revenue",
        "description": "Time tracking and invoicing tool for freelancers",
        "team_size": 2,
        "funding": "bootstrapped",
        "revenue": "<$1K MRR",
        "months_in": 6,
        "biggest_worry": "Can't convert free users to paid",
        "target_customer": "Freelance designers and developers",
        "business_model": "$15/month subscription",
    }

    failures = [
        {
            "startup_name": "InvoicePro",
            "startup_type": "B2B SaaS",
            "stage_at_failure": "early-revenue",
            "months_alive": 14,
            "primary_failure_cause": "no_market_need",
            "secondary_causes": ["wrong_pricing", "customer_acquisition"],
            "warning_signs_missed": ["users loved the free tier but refused to pay", "support tickets were all about features that existed in free tools"],
            "decision_point": "They built the product for 8 months before talking to paying customers",
            "what_they_would_do_differently": "Charge from day one with no free tier",
            "raw_summary": "B2B SaaS for freelance invoicing. Had 400 free users, 4 paying after 6 months. Shut down when founder ran out of savings. The free tier attracted users who had no budget.",
            "similarity_score": 0.87,
            "source_url": "https://example.com/invoicepro-postmortem",
        }
    ]

    report, sources = asyncio.run(synthesize_risk_report(profile, failures))
    print(report)
