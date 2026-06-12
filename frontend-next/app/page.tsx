"use client";

/**
 * PostMortemAI — single-file Next.js 14 App Router page
 *
 * Drop-in: app/page.tsx
 * Tailwind CSS required.
 * Install: npm i react-markdown remark-gfm
 *
 * API contract:
 *   POST http://localhost:8000/analyze
 *     body: { description: string }
 *     returns: {
 *       risk_report: string (markdown),
 *       startup_profile: { type, stage, revenue, funding },
 *       source_postmortems: Array<{
 *         startup_name, primary_failure_cause, raw_summary,
 *         source_url, similarity_score (0..1)
 *       }>,
 *       similar_failures_count: number,
 *       competitors: Array<{
 *         name, domain, description, why_relevant, funding_stage
 *       }>
 *     }
 */

import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// ───────────────────────────────────────────────────────────────────────────
// Types
// ───────────────────────────────────────────────────────────────────────────

type StartupProfile = {
  type: string;
  stage: string;
  revenue: string;
  funding: string;
};

type SourcePostmortem = {
  startup_name: string;
  primary_failure_cause: string;
  raw_summary: string;
  source_url: string;
  similarity_score: number;
};

type Competitor = {
  name: string;
  domain: string;
  description: string;
  funding_stage: string;
  why_relevant: string;
};

type AnalyzeResponse = {
  risk_report: string;
  startup_profile: StartupProfile;
  source_postmortems: SourcePostmortem[];
  similar_failures_count: number;
  competitors: Competitor[];
};

// ───────────────────────────────────────────────────────────────────────────
// Failure-cause palette
// ───────────────────────────────────────────────────────────────────────────

const CAUSE_STYLES: Record<string, { bg: string; text: string; ring: string; label: string }> = {
  no_market_need:        { bg: "bg-rose-500/10",     text: "text-rose-300",     ring: "ring-rose-500/30",     label: "No market need" },
  ran_out_of_cash:       { bg: "bg-amber-500/10",    text: "text-amber-300",    ring: "ring-amber-500/30",    label: "Ran out of cash" },
  not_the_right_team:    { bg: "bg-orange-500/10",   text: "text-orange-300",   ring: "ring-orange-500/30",   label: "Wrong team" },
  got_outcompeted:       { bg: "bg-fuchsia-500/10",  text: "text-fuchsia-300",  ring: "ring-fuchsia-500/30",  label: "Outcompeted" },
  pricing_cost_issues:   { bg: "bg-yellow-500/10",   text: "text-yellow-300",   ring: "ring-yellow-500/30",   label: "Pricing / cost" },
  poor_product:          { bg: "bg-red-500/10",      text: "text-red-300",      ring: "ring-red-500/30",      label: "Poor product" },
  need_disconnect:       { bg: "bg-pink-500/10",     text: "text-pink-300",     ring: "ring-pink-500/30",     label: "User disconnect" },
  failed_pivot:          { bg: "bg-violet-500/10",   text: "text-violet-300",   ring: "ring-violet-500/30",   label: "Failed pivot" },
  poor_marketing:        { bg: "bg-sky-500/10",      text: "text-sky-300",      ring: "ring-sky-500/30",      label: "Poor marketing" },
  ignore_customers:      { bg: "bg-teal-500/10",     text: "text-teal-300",     ring: "ring-teal-500/30",     label: "Ignored customers" },
  product_mistimed:      { bg: "bg-indigo-500/10",   text: "text-indigo-300",   ring: "ring-indigo-500/30",   label: "Mistimed" },
  legal_challenges:      { bg: "bg-stone-500/10",    text: "text-stone-300",    ring: "ring-stone-500/30",    label: "Legal" },
  burn_out:              { bg: "bg-emerald-500/10",  text: "text-emerald-300",  ring: "ring-emerald-500/30",  label: "Burnout" },
  pivot_gone_bad:        { bg: "bg-purple-500/10",   text: "text-purple-300",   ring: "ring-purple-500/30",   label: "Pivot gone bad" },
};

function causeStyle(cause: string) {
  return (
    CAUSE_STYLES[cause] ?? {
      bg: "bg-zinc-500/10",
      text: "text-zinc-300",
      ring: "ring-zinc-500/30",
      label: cause.replace(/_/g, " "),
    }
  );
}

// ───────────────────────────────────────────────────────────────────────────
// Loading status messages
// ───────────────────────────────────────────────────────────────────────────

const STATUS_MESSAGES = [
  "Scanning 5,247 postmortems…",
  "Identifying failure patterns…",
  "Cross-referencing similar startups…",
  "Mapping risk vectors…",
  "Generating your report…",
];

// ───────────────────────────────────────────────────────────────────────────
// Page
// ───────────────────────────────────────────────────────────────────────────

export default function Page() {
  const [description, setDescription] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [statusIdx, setStatusIdx] = useState(0);
  const [scanCount, setScanCount] = useState(0);

  const resultsRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!loading) return;
    setStatusIdx(0);
    const id = setInterval(() => {
      setStatusIdx((i) => (i + 1) % STATUS_MESSAGES.length);
    }, 1600);
    return () => clearInterval(id);
  }, [loading]);

  useEffect(() => {
    if (!loading) { setScanCount(0); return; }
    let raf = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min((now - start) / 1000, 30);
      setScanCount(Math.floor(5247 * (1 - Math.exp(-t / 1.4))));
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [loading]);

  useEffect(() => {
    if (!result || !resultsRef.current) return;
    window.scrollTo({ top: resultsRef.current.getBoundingClientRect().top + window.scrollY - 24, behavior: "smooth" });
  }, [result]);

  async function analyze() {
    if (!description.trim() || loading) return;
    setLoading(true); setError(null); setResult(null);
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ description }),
      });
      if (!res.ok) throw new Error(`Request failed: ${res.status}`);
      setResult(await res.json());
    } catch (e: unknown) {
      setError((e as Error)?.message ?? "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  function reset() {
    setResult(null); setError(null); setDescription("");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  const canSubmit = description.trim().length >= 20 && !loading;

  return (
    <main className="relative min-h-screen overflow-x-hidden bg-[#0a0a0f] text-zinc-200 antialiased selection:bg-violet-500/30 selection:text-white">
      <BackgroundFX />

      <header className="relative z-10 border-b border-white/[0.06] bg-black/20 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-3 text-[11px] sm:text-xs">
          <div className="flex items-center gap-2 font-mono tracking-tight text-zinc-500">
            <span className="relative inline-flex h-1.5 w-1.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400/70" />
              <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-emerald-400" />
            </span>
            <span className="text-zinc-400">postmortem.ai</span>
            <span className="text-zinc-700">/</span>
            <span className="text-zinc-500">v0.3</span>
          </div>
          <div className="hidden items-center gap-3 font-mono text-zinc-500 sm:flex">
            <Stat label="postmortems indexed" value="5,247" />
            <span className="text-zinc-700">·</span>
            <Stat label="failure patterns" value="14" />
            <span className="text-zinc-700">·</span>
            <Stat label="startup types" value="12" />
          </div>
        </div>
      </header>

      <section className="relative z-10 mx-auto max-w-3xl px-5 pb-10 pt-20 sm:pt-28">
        <div className="mb-7 flex justify-center">
          <div className="inline-flex items-center gap-2 rounded-full border border-white/[0.08] bg-white/[0.02] px-3 py-1 font-mono text-[10px] uppercase tracking-[0.2em] text-zinc-400 backdrop-blur-sm">
            <svg viewBox="0 0 24 24" className="h-3 w-3 text-violet-400" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
            </svg>
            Forensic intelligence for founders
          </div>
        </div>

        <h1 className="text-balance text-center text-[42px] font-medium leading-[1.05] tracking-tight text-white sm:text-[64px]">
          Find out{" "}
          <span className="relative inline-block">
            <span className="bg-gradient-to-br from-rose-300 via-rose-400 to-red-600 bg-clip-text text-transparent">
              how you&apos;ll fail
            </span>
            <span className="absolute -bottom-1 left-0 right-0 h-px bg-gradient-to-r from-transparent via-rose-500/60 to-transparent" />
          </span>
          <br />before you do.
        </h1>

        <p className="mx-auto mt-5 max-w-xl text-balance text-center text-[15px] leading-relaxed text-zinc-400 sm:text-base">
          Describe your startup. We pattern-match it against{" "}
          <span className="text-zinc-200">5,247 documented failures</span> and tell you, unsentimentally, where the cracks are.
        </p>

        <div className="group relative mt-12">
          <div aria-hidden className="pointer-events-none absolute -inset-px rounded-2xl opacity-0 blur-xl transition-opacity duration-500 group-focus-within:opacity-100 group-focus-within:bg-gradient-to-br group-focus-within:from-violet-500/40 group-focus-within:via-violet-500/20 group-focus-within:to-fuchsia-500/30" />
          <div className="relative rounded-2xl border border-white/[0.08] bg-[#0e0e16]/80 backdrop-blur-md transition-all duration-300 group-focus-within:border-violet-500/50 group-focus-within:shadow-[0_0_0_1px_rgba(139,92,246,0.4),0_30px_80px_-20px_rgba(139,92,246,0.25)]">
            <div className="flex items-center justify-between border-b border-white/[0.05] px-4 py-2.5 font-mono text-[10px] uppercase tracking-[0.18em] text-zinc-500">
              <div className="flex items-center gap-2">
                <span className="h-1.5 w-1.5 rounded-full bg-rose-500/80" />
                <span>describe_startup.txt</span>
              </div>
              <span className={description.length > 0 ? "text-zinc-400" : "text-zinc-600"}>{description.length} chars</span>
            </div>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              onKeyDown={(e) => { if ((e.metaKey || e.ctrlKey) && e.key === "Enter") analyze(); }}
              disabled={loading}
              placeholder="We're building an AI tool that helps small e-commerce shops auto-generate product descriptions. We have 12 paying customers at $29/mo, mostly Shopify stores. Solo founder, technical, 8 months in, $4K MRR. Considering raising a pre-seed…"
              className="block h-44 w-full resize-none bg-transparent px-5 py-4 text-[15px] leading-relaxed text-zinc-100 placeholder:text-zinc-600 focus:outline-none disabled:opacity-60 sm:h-52"
            />
            <div className="flex flex-col items-stretch justify-between gap-3 border-t border-white/[0.05] px-4 py-3 sm:flex-row sm:items-center">
              <div className="flex items-center gap-2 font-mono text-[10.5px] text-zinc-500">
                <kbd className="rounded border border-white/10 bg-white/[0.04] px-1.5 py-0.5 text-[10px] text-zinc-400">⌘</kbd>
                <kbd className="rounded border border-white/10 bg-white/[0.04] px-1.5 py-0.5 text-[10px] text-zinc-400">↵</kbd>
                <span>to analyze · be specific, name numbers</span>
              </div>
              <button
                onClick={analyze}
                disabled={!canSubmit}
                className="group/btn relative inline-flex items-center justify-center gap-2 overflow-hidden rounded-lg border border-red-900/60 bg-gradient-to-b from-red-700 to-red-900 px-5 py-2.5 text-[13px] font-medium text-red-50 shadow-[0_1px_0_0_rgba(255,255,255,0.08)_inset,0_8px_24px_-8px_rgba(185,28,28,0.5)] transition-all hover:from-red-600 hover:to-red-800 active:translate-y-px disabled:cursor-not-allowed disabled:opacity-40"
              >
                <span aria-hidden className="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/15 to-transparent transition-transform duration-700 group-hover/btn:translate-x-full" />
                {loading ? (<><Spinner /><span>Analyzing…</span></>) : (<><span>Analyze My Startup</span><svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M5 12h14M13 5l7 7-7 7" /></svg></>)}
              </button>
            </div>
          </div>
        </div>

        <div className="mt-5 flex flex-wrap items-center justify-center gap-x-5 gap-y-2 font-mono text-[11px] text-zinc-500">
          {[["bg-violet-400","what you do"],["bg-rose-400","who pays"],["bg-amber-400","stage & traction"],["bg-emerald-400","what scares you"]].map(([c, l]) => (
            <span key={l} className="inline-flex items-center gap-1.5"><span className={`h-1 w-1 rounded-full ${c}`} />{l}</span>
          ))}
        </div>
      </section>

      {loading && (
        <section className="relative z-10 mx-auto max-w-3xl px-5 pb-24">
          <LoadingPanel scanCount={scanCount} statusIdx={statusIdx} />
        </section>
      )}

      {error && !loading && (
        <section className="relative z-10 mx-auto max-w-3xl px-5 pb-24">
          <div className="rounded-xl border border-red-900/40 bg-red-950/20 p-5 text-sm text-red-200">
            <div className="mb-1 font-mono text-[11px] uppercase tracking-wider text-red-400">error</div>
            <div>{error}</div>
            <div className="mt-2 text-[12px] text-red-300/70">Make sure the API is running at <span className="font-mono">http://localhost:8000/analyze</span>.</div>
          </div>
        </section>
      )}

      {result && !loading && (
        <>
          <section ref={resultsRef} className="relative z-10 mx-auto max-w-6xl px-5 pb-12">
            <div className="mb-6 flex flex-col items-start justify-between gap-4 sm:flex-row sm:items-center">
              <div className="flex flex-wrap items-center gap-2">
                {(["type","stage","revenue","funding"] as const).map((k) => (
                  <ProfileChip key={k} label={k} value={result.startup_profile[k]} />
                ))}
              </div>
              <button onClick={reset} className="inline-flex items-center gap-1.5 rounded-md border border-white/10 bg-white/[0.02] px-3 py-1.5 font-mono text-[11px] text-zinc-400 transition-colors hover:border-white/20 hover:bg-white/[0.04] hover:text-zinc-200">
                <svg viewBox="0 0 24 24" className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth="2.2"><path d="M3 12a9 9 0 1 0 3-6.7M3 4v5h5" /></svg>
                new analysis
              </button>
            </div>

            <div className="grid gap-5 lg:grid-cols-[1.4fr_1fr]">
              <article className="relative overflow-hidden rounded-2xl border border-white/[0.07] bg-gradient-to-b from-[#0e0e16] to-[#0b0b12] p-1">
                <div className="rounded-[14px] border border-white/[0.04] bg-[#0a0a11]">
                  <div className="flex items-center justify-between border-b border-white/[0.05] px-5 py-3">
                    <div className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.2em] text-zinc-500">
                      <span className="h-1.5 w-1.5 rounded-full bg-violet-400" />risk report
                    </div>
                    <div className="font-mono text-[10px] text-zinc-600">confidential · founder-only</div>
                  </div>
                  <div className="px-5 py-6 sm:px-7 sm:py-8">
                    <MarkdownReport markdown={result.risk_report} />
                  </div>
                </div>
              </article>

              <aside className="space-y-4">
                <div className="flex items-baseline justify-between">
                  <h2 className="font-mono text-[11px] uppercase tracking-[0.2em] text-zinc-500">similar failed startups</h2>
                  <span className="font-mono text-[11px] text-zinc-600">{result.similar_failures_count} matched</span>
                </div>
                <div className="space-y-3">
                  {result.source_postmortems.map((pm, i) => <PostmortemCard key={i} pm={pm} index={i} />)}
                </div>
                {result.source_postmortems.length === 0 && (
                  <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] px-4 py-8 text-center text-sm text-zinc-500">No similar postmortems found.</div>
                )}
              </aside>
            </div>
          </section>

          <section className="relative z-10 mx-auto max-w-6xl px-5 pb-24">
            <div className="mb-5 flex items-end justify-between gap-4">
              <div>
                <h2 className="flex items-center gap-2 text-[20px] font-medium tracking-tight text-white sm:text-[22px]">
                  <span className="relative inline-flex h-5 w-5 items-center justify-center">
                    <span className="absolute inset-0 animate-ping rounded-full bg-red-500/30" />
                    <svg viewBox="0 0 24 24" className="relative h-4 w-4 text-red-400" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M12 9v4M12 17h.01M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z" />
                    </svg>
                  </span>
                  Who You&apos;re Up Against
                </h2>
                <p className="mt-1 text-[13.5px] text-zinc-400">Competitors operating in your exact space at your stage</p>
              </div>
              <div className="hidden font-mono text-[10.5px] uppercase tracking-[0.18em] text-zinc-600 sm:block">scroll →</div>
            </div>

            {result.competitors.length > 0 && (
              <div className="-mx-5 flex snap-x snap-mandatory gap-4 overflow-x-auto px-5 pb-4 [scrollbar-width:thin]" style={{ scrollbarColor: "rgba(255,255,255,0.08) transparent" }}>
                {result.competitors.map((c: Competitor, i: number) => <CompetitorCard key={c.domain + i} competitor={c} index={i} />)}
                <div className="w-1 flex-shrink-0" aria-hidden />
              </div>
            )}

            {result.competitors.length === 0 && (
              <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] px-4 py-8 text-center text-sm text-zinc-500">Competitor analysis coming soon.</div>
            )}
          </section>
        </>
      )}

      <footer className="relative z-10 border-t border-white/[0.06] bg-black/20 backdrop-blur-sm">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-2 px-5 py-6 text-center font-mono text-[11px] text-zinc-500 sm:flex-row sm:text-left">
          <div>Pattern matching from public failure stories. Not advice.</div>
          <div className="text-zinc-600">built for founders who&apos;d rather know · postmortem.ai</div>
        </div>
      </footer>
    </main>
  );
}

// ───────────────────────────────────────────────────────────────────────────
// Subcomponents
// ───────────────────────────────────────────────────────────────────────────

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <span className="inline-flex items-baseline gap-1.5">
      <span className="text-zinc-300">{value}</span>
      <span className="text-zinc-600">{label}</span>
    </span>
  );
}

function Spinner() {
  return (
    <svg viewBox="0 0 24 24" className="h-3.5 w-3.5 animate-spin" fill="none">
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeOpacity="0.25" strokeWidth="2.5" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
    </svg>
  );
}

function ProfileChip({ label, value }: { label: string; value: string }) {
  return (
    <div className="inline-flex items-center gap-2 rounded-md border border-white/[0.08] bg-white/[0.02] px-2.5 py-1.5 backdrop-blur-sm">
      <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-zinc-500">{label}</span>
      <span className="text-[12.5px] text-zinc-200">{value}</span>
    </div>
  );
}

function LoadingPanel({ scanCount, statusIdx }: { scanCount: number; statusIdx: number }) {
  return (
    <div className="relative overflow-hidden rounded-2xl border border-white/[0.07] bg-[#0e0e16]/80 p-8 backdrop-blur-md sm:p-12">
      <style>{`
        @keyframes pmai-sweep { 0%,100%{transform:translateY(0);opacity:.6} 50%{transform:translateY(160px);opacity:1} }
        @keyframes pmai-fade-in { from{opacity:0;transform:translateY(4px)} to{opacity:1;transform:translateY(0)} }
        @keyframes pmai-progress { 0%{transform:translateX(-100%)} 100%{transform:translateX(350%)} }
      `}</style>
      <div aria-hidden className="pointer-events-none absolute inset-x-0 top-0 h-32 bg-gradient-to-b from-violet-500/10 via-violet-500/[0.03] to-transparent" style={{ animation: "pmai-sweep 2.4s ease-in-out infinite" }} />
      <div className="relative flex flex-col items-center text-center">
        <div className="relative mb-7 h-16 w-16">
          <div className="absolute inset-0 animate-ping rounded-full bg-violet-500/30" />
          <div className="absolute inset-2 animate-ping rounded-full bg-violet-500/40" style={{ animationDelay: "0.4s" }} />
          <div className="absolute inset-4 rounded-full bg-gradient-to-br from-violet-400 to-fuchsia-600 shadow-[0_0_30px_rgba(139,92,246,0.6)]" />
          <div className="absolute inset-[26px] rounded-full bg-white/90" />
        </div>
        <div className="font-mono text-[11px] uppercase tracking-[0.22em] text-zinc-500">analyzing</div>
        <div className="mt-2 font-mono text-4xl font-medium tabular-nums text-white sm:text-5xl">
          {scanCount.toLocaleString()}<span className="text-zinc-600"> / 5,247</span>
        </div>
        <div className="mt-6 h-6 overflow-hidden">
          <div key={statusIdx} className="text-[14px] text-zinc-300" style={{ animation: "pmai-fade-in 0.4s ease-out" }}>{STATUS_MESSAGES[statusIdx]}</div>
        </div>
        <div className="mt-6 h-px w-full max-w-md overflow-hidden bg-white/5">
          <div className="h-full bg-gradient-to-r from-transparent via-violet-400 to-transparent" style={{ width: "40%", animation: "pmai-progress 1.6s ease-in-out infinite" }} />
        </div>
      </div>
    </div>
  );
}

function PostmortemCard({ pm, index }: { pm: SourcePostmortem; index: number }) {
  const cs = causeStyle(pm.primary_failure_cause);
  const pct = Math.round(pm.similarity_score * 100);
  const [shown, setShown] = useState(0);
  useEffect(() => {
    const t = setTimeout(() => setShown(pct), 80 + index * 90);
    return () => clearTimeout(t);
  }, [pct, index]);

  return (
    <a href={pm.source_url} target="_blank" rel="noopener noreferrer"
      className="group relative block overflow-hidden rounded-xl border border-white/[0.07] bg-gradient-to-b from-[#0e0e16] to-[#0a0a11] p-4 transition-all hover:border-white/[0.14] hover:bg-[#11111a]"
      style={{ animation: `pmai-card-in 0.5s ${index * 60}ms ease-out backwards` }}>
      <style>{`@keyframes pmai-card-in{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}`}</style>
      <div aria-hidden className="pointer-events-none absolute -inset-px rounded-xl opacity-0 transition-opacity duration-500 group-hover:opacity-100" style={{ background: "radial-gradient(400px circle at 50% 0%,rgba(139,92,246,0.08),transparent 40%)" }} />
      <div className="relative">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h3 className="truncate text-[15px] font-medium text-white">{pm.startup_name}</h3>
              <svg viewBox="0 0 24 24" className="h-3 w-3 flex-shrink-0 text-zinc-600 transition-colors group-hover:text-zinc-300" fill="none" stroke="currentColor" strokeWidth="2"><path d="M7 17L17 7M9 7h8v8" /></svg>
            </div>
            <div className={`mt-1.5 inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-[10.5px] font-medium ring-1 ring-inset ${cs.bg} ${cs.text} ${cs.ring}`}>
              <span className={`h-1 w-1 rounded-full ${cs.text.replace("text-", "bg-")}`} />{cs.label}
            </div>
          </div>
          <div className="flex flex-col items-end">
            <div className="font-mono text-[11px] tabular-nums text-zinc-300">{pct}<span className="text-zinc-600">%</span></div>
            <div className="font-mono text-[9px] uppercase tracking-wider text-zinc-600">match</div>
          </div>
        </div>
        <div className="mt-3 h-1 overflow-hidden rounded-full bg-white/[0.04]">
          <div className="relative h-full rounded-full bg-gradient-to-r from-violet-500 via-fuchsia-500 to-rose-500 transition-[width] duration-1000 ease-out" style={{ width: `${shown}%` }}>
            <div aria-hidden className="absolute inset-y-0 right-0 w-8 bg-gradient-to-r from-transparent to-white/40 blur-sm" />
          </div>
        </div>
        <p className="mt-3 line-clamp-2 text-[13px] leading-relaxed text-zinc-400">{pm.raw_summary}</p>
      </div>
    </a>
  );
}

function CompetitorCard({ competitor, index }: { competitor: Competitor; index: number }) {
  const [logoFailed, setLogoFailed] = useState(false);
  return (
    <div className="group relative flex w-[300px] flex-shrink-0 snap-start flex-col overflow-hidden rounded-xl border border-white/[0.07] bg-gradient-to-b from-[#0e0e16] to-[#0a0a11] p-4 transition-all duration-300 hover:-translate-y-1 hover:border-white/[0.14] hover:shadow-[0_20px_50px_-15px_rgba(139,92,246,0.35)]"
      style={{ animation: `pmai-card-in 0.5s ${index * 70}ms ease-out backwards` }}>
      <style>{`@keyframes pmai-card-in{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}`}</style>
      <div aria-hidden className="pointer-events-none absolute -inset-px rounded-xl opacity-0 transition-opacity duration-500 group-hover:opacity-100" style={{ background: "radial-gradient(420px circle at 50% 0%,rgba(139,92,246,0.10),transparent 45%)" }} />
      <div className="relative flex items-start justify-between gap-3">
        <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center overflow-hidden rounded-lg border border-white/[0.08] bg-white/[0.04]">
          {!logoFailed ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={`https://logo.clearbit.com/${competitor.domain}`} alt="" width={40} height={40} onError={() => setLogoFailed(true)} className="h-full w-full object-contain" loading="lazy" />
          ) : (
            <span className="font-mono text-[15px] font-medium text-zinc-300">{competitor.name.charAt(0).toUpperCase()}</span>
          )}
        </div>
        <div className="inline-flex items-center gap-1 rounded-md border border-white/[0.08] bg-white/[0.03] px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-zinc-400">
          <span className="h-1 w-1 rounded-full bg-emerald-400/80" />{competitor.funding_stage}
        </div>
      </div>
      <div className="relative mt-3">
        <h3 className="text-[15px] font-medium text-white">{competitor.name}</h3>
        <p className="mt-1 line-clamp-2 text-[12.5px] leading-relaxed text-zinc-400">{competitor.description}</p>
      </div>
      <div className="relative mt-3 border-t border-white/[0.05] pt-3">
        <div className="font-mono text-[9.5px] uppercase tracking-[0.16em] text-zinc-500">why they&apos;re relevant</div>
        <p className="mt-1 text-[12.5px] leading-snug text-zinc-300">{competitor.why_relevant}</p>
      </div>
    </div>
  );
}

function MarkdownReport({ markdown }: { markdown: string }) {
  return (
    <div>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: (p) => <h1 className="mb-4 mt-2 text-[26px] font-medium leading-tight tracking-tight text-white" {...p} />,
          h2: (p) => <h2 className="mb-3 mt-7 text-[18px] font-medium tracking-tight text-white" {...p} />,
          h3: (p) => <h3 className="mb-2 mt-5 font-mono text-[14px] uppercase tracking-[0.16em] text-violet-300" {...p} />,
          p: (p) => <p className="mb-4 text-[14.5px] leading-relaxed text-zinc-300" {...p} />,
          ul: (p) => <ul className="mb-4 ml-1 space-y-1.5" {...p} />,
          ol: (p) => <ol className="mb-4 ml-5 list-decimal space-y-1.5" {...p} />,
          li: ({ children, ...p }) => (
            <li className="relative pl-5 text-[14px] leading-relaxed text-zinc-300" {...p}>
              <span className="absolute left-0 top-[10px] h-1 w-1 rounded-full bg-violet-400/70" />{children}
            </li>
          ),
          strong: (p) => <strong className="font-medium text-white" {...p} />,
          em: (p) => <em className="text-zinc-200" {...p} />,
          a: (p) => <a className="text-violet-300 underline decoration-violet-500/40 underline-offset-2 transition-colors hover:text-violet-200" target="_blank" rel="noopener noreferrer" {...p} />,
          blockquote: ({ children, ...p }) => (
            <blockquote className="my-4 border-l-2 border-rose-500/40 bg-rose-500/[0.04] px-4 py-2 text-[14px] italic text-zinc-300" {...p}>{children}</blockquote>
          ),
          code: ({ className, children }: { className?: string; children?: React.ReactNode }) => {
            if (className?.includes("language-")) {
              return <pre className="my-4 overflow-x-auto rounded-lg border border-white/[0.06] bg-black/40 p-4 font-mono text-[12.5px] leading-relaxed text-zinc-300"><code>{children}</code></pre>;
            }
            return <code className="rounded border border-white/10 bg-white/[0.04] px-1.5 py-0.5 font-mono text-[12.5px] text-violet-200">{children}</code>;
          },
          hr: () => <hr className="my-6 border-0 bg-gradient-to-r from-transparent via-white/10 to-transparent" style={{ height: 1 }} />,
          table: (p) => <div className="my-4 overflow-x-auto rounded-lg border border-white/[0.06]"><table className="w-full border-collapse text-[13px]" {...p} /></div>,
          th: (p) => <th className="border-b border-white/[0.08] bg-white/[0.03] px-3 py-2 text-left font-mono text-[11px] uppercase tracking-wider text-zinc-400" {...p} />,
          td: (p) => <td className="border-b border-white/[0.04] px-3 py-2 text-zinc-300" {...p} />,
        }}
      >{markdown}</ReactMarkdown>
    </div>
  );
}

function BackgroundFX() {
  return (
    <>
      <style>{`
        @keyframes pmai-orb { 0%{transform:translate(-50%,0) scale(1)} 100%{transform:translate(-50%,40px) scale(1.1)} }
        @keyframes pmai-orb-2 { 0%{transform:translate(0,0) scale(1)} 100%{transform:translate(-60px,-40px) scale(1.15)} }
      `}</style>
      <div aria-hidden className="pointer-events-none fixed inset-0 z-0 opacity-[0.35]" style={{ backgroundImage: "linear-gradient(to right,rgba(255,255,255,0.04) 1px,transparent 1px),linear-gradient(to bottom,rgba(255,255,255,0.04) 1px,transparent 1px)", backgroundSize: "56px 56px", maskImage: "radial-gradient(ellipse 80% 60% at 50% 0%,black 30%,transparent 80%)", WebkitMaskImage: "radial-gradient(ellipse 80% 60% at 50% 0%,black 30%,transparent 80%)" }} />
      <div aria-hidden className="pointer-events-none fixed left-1/2 top-[-200px] z-0 h-[500px] w-[900px] -translate-x-1/2 rounded-full opacity-50 blur-[120px]" style={{ background: "radial-gradient(closest-side,rgba(139,92,246,0.35),rgba(168,85,247,0.18) 40%,transparent 70%)", animation: "pmai-orb 14s ease-in-out infinite alternate" }} />
      <div aria-hidden className="pointer-events-none fixed bottom-[-300px] right-[-200px] z-0 h-[600px] w-[600px] rounded-full opacity-30 blur-[140px]" style={{ background: "radial-gradient(closest-side,rgba(220,38,38,0.4),rgba(127,29,29,0.2) 40%,transparent 70%)", animation: "pmai-orb-2 18s ease-in-out infinite alternate" }} />
    </>
  );
}
