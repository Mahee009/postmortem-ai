"""
synthesizer.py — the core reasoning agent
Takes a startup profile + 15 similar failures → personalized risk report
This is where PostMortemAI earns its value
"""

import logging
from dotenv import load_dotenv
from agents.llm import call_llm

load_dotenv()
logger = logging.getLogger(__name__)

SYNTHESIS_SYSTEM = """You are a partner-level VC writing an internal investment memo about a NEW startup that a founder just pitched to you.

CRITICAL DISTINCTION: The founder's startup is described under "The Founder's Startup". The companies listed under "Evidence" are DEAD companies used only as reference. The founder's startup is NOT one of those dead companies. Do not mix them up.

You follow the output format exactly. You do not add text outside the format."""

SYNTHESIS_PROMPT = """A founder just pitched their startup to you. You have {n_failures} real failure postmortems from similar dead companies as evidence.

## ⚠️ The Startup Being Analyzed (this is NOT one of the dead companies below)
{profile_summary}

## Evidence — Dead Companies Used As Reference Only
{failures_text}

---

Write a partner-level VC investment memo about THE FOUNDER'S STARTUP above. The dead companies are evidence, not the subject.

RULES — read before writing, enforce while writing:
1. The 3 Killers must name something the founder EXPLICITLY said or a pattern directly visible in the evidence. No invented risks.
2. BANNED PHRASES — if you write any of these, start over: "pricing strategy", "single revenue stream", "failure to adapt to market conditions", "customer acquisition may be challenging", "what makes this unique", "product-market fit" (say something specific instead).
3. Each Killer must cite ONE specific named dead company from the evidence — what they built, what killed them.
4. The One Question must contain a specific detail from the founder's description — it cannot apply to every startup.
5. The 30-Day Tests must have hard numbers in the pass/fail conditions (e.g. "3 users pay", "churn drops below 20%", "$500 revenue") — not vague outcomes.
6. Stop writing after the last line. No closing paragraph.

Use EXACTLY this format:

---

# Verdict: [ONE brutal sentence. Would you fund this? Why not?]

## The Core Problem Nobody Is Saying Out Loud
[2-3 sentences. The single structural reason this probably fails. Not a risk — the reason. The thing a good investor sees in minute 3 of the pitch.]

---

## The 3 Actual Killers (not the generic ones)

### ☠️ Killer 1: [Name it precisely]
**Why this kills you specifically:** [Not generically. Based on THEIR description and the failure evidence.]
**The failure pattern:** [1-2 specific postmortems that died this exact way. Name the startup, what they said, what happened.]
**The question you can't answer right now:** [One specific question a VC would ask that would expose this.]
**What survival looks like:** [One concrete thing to do in the next 30 days that would change this. If nothing changes it — say that.]

### ☠️ Killer 2: [Name it precisely]
[Same structure]

### ☠️ Killer 3: [Name it precisely]
[Same structure]

---

## What You Got Right
[2-3 sentences max. Genuine strengths only. If there are none worth mentioning, say "Nothing structural yet — only execution points."]

---

## The One Question That Decides Everything
[One specific, uncomfortable question. The answer to this question determines whether this startup lives or dies. A real investor would ask this in the first 5 minutes. Not "do you have product-market fit" — something specific to THIS startup.]

---

## 30-Day Survival Test
[3 specific experiments they can run in 30 days that will tell them whether to keep going or stop. Each one has a pass/fail condition. Not tasks — tests with measurable outcomes.]

1. **Test:** [What to do] → **Pass if:** [Specific measurable outcome] → **Fail if:** [Specific measurable outcome]
2. [Same]
3. [Same]

---
*Analysis based on {n_failures} real startup failure postmortems*
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

    report = await call_llm(prompt, system=SYNTHESIS_SYSTEM, max_tokens=3000)

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
