#!/usr/bin/env python3
"""
Non-stop India legal article workflow (daily run).

Flow
====
1) Optional discovery: **all court tiers** (within `--max-discovery-searches`) → **direct**
   SERP queries for **listed / running / pending** matters → compile topics into the queue.
2) For each pending item with run_date == RUN_DATE: iterative research (Web + crawl + CourtSearch)
   then writer produces a formal legal article (India jurisdiction).
3) On completion, follow-on topics from the knowledge-gap agent are enqueued for the same run_date.

Usage
=====
  # Discover topics + process all pending items for that calendar day
  python run_india_legal_daily.py --date 2026-04-04

  # Skip discovery (only drain queue for that date)
  python run_india_legal_daily.py --date 2026-04-04 --skip-discovery

  # Discovery only (seed queue, no articles yet)
  python run_india_legal_daily.py --date 2026-04-04 --discover-only

  # Resume a previous run (same queue + output folder)
  python run_india_legal_daily.py --date 2026-04-04 \\
      --queue-file outputs/india_legal_2026-04-08_12-00-00_ab12cd34/queue.json \\
      --out-dir outputs/india_legal_2026-04-08_12-00-00_ab12cd34

By default each invocation creates a new run folder ``outputs/india_legal_<UTC-timestamp>_<id>/`` with a fresh
``queue.json`` there; all ``.md`` files are written to that same folder.

Requires .env: BRIGHTDATA_API_KEY, BRIGHTDATA_SERP_ZONE (or BRIGHTDATA_ZONE), OPENROUTER_API_KEY (or DR_OPENROUTER_API_KEY).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(_project_root))

from dotenv import load_dotenv

load_dotenv(_project_root / ".env")

from agents import set_tracing_disabled

from deep_researcher.india_legal_discovery import (
    DiscoveredTopic,
    discover_topics_for_date,
    topic_title_key,
)
from deep_researcher.iterative_research_legal_india import IterativeResearcherIndiaLegal
from deep_researcher.llm_config import create_default_config

if not os.getenv("OPENAI_API_KEY") or "your-" in str(os.getenv("OPENAI_API_KEY", "")):
    set_tracing_disabled(True)

QUEUE_VERSION = 1


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _new_run_id() -> str:
    """UTC timestamp + short hex so each run has a unique folder/queue name."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
    return f"{ts}_{uuid.uuid4().hex[:8]}"


def create_config(model: str | None = None):
    """LLM stack from .env; optional CLI ``--model`` overrides all three model ids."""
    return create_default_config(search_provider="brightdata", model_override=model)


def _slug(s: str, max_len: int = 40) -> str:
    x = re.sub(r"[^\w\-]+", "_", (s or "").lower()).strip("_")
    return (x[:max_len] or "topic").rstrip("_")


def _timestamped_basename(title: str) -> str:
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    return f"{_slug(title)}_india_legal_{ts}"


def article_output_instructions(run_date: str) -> str:
    return f"""
Publication working date (India): {run_date}
Jurisdiction: India only (courts, tribunals, agencies, statutes as reported).

Write a legal analytical article suitable for an Indian legal news desk (formal legal English).

Structure (use markdown headings **in this order**):

1. **Headline** — precise, neutral, legally informative (single line, then blank line).

2. **Citations and case numbers** — **Immediately after the headline, before judges and counsel.** Use labelled lines or a small table. **Exact text as in sources**—do not invent reporter lines.

   Include every line your materials support; otherwise `Not stated in sources`:
   - **Case title** (short citation form of parties, if not already obvious from the headline)
   - **AIR** — All India Reporter citation(s) if reported (e.g. `AIR YYYY SC …`)
   - **SCC** — Supreme Court Cases citation in standard form, e.g. `(YYYY) Vol SCC Page`, if reported
   - **Other journal / neutral cites** — **SCALE**, **SCR**, tribunal reporters such as **`SCC OnLine NCLAT`**, **`SCC OnLine CCI`**, **`SCC OnLine NCLT`**, etc., if reported
   - **Official case numbers** — as printed on the order: e.g. Civil Appeal / SLP / Writ Petition / Review / Curative numbers, **Company Appeal (AT) No.**, **Case No.** before CCI or other regulators, **Diary No.**, **IA** numbers if given as the formal identifier

3. **Judges and counsel** — **After §2.** This is the **authoritative** place for **full names** of judges and lawyers, spelled **exactly** as in the **judgment header, official court PDF, Indian Kanoon, or SCC Online / reporter text**—cross-check at least one primary source before finalising. Do not guess or normalise spelling.

   Use clear subheadings:
   - **Court / Tribunal** and **Bench** (e.g. Single Judge, Division Bench of two judges, Full Bench).
   - **Coram** — each judge’s **full name** with title (e.g. Hon’ble Mr Justice …, Hon’ble Dr Justice …, Hon’ble Ms Justice …) and **seniormost / presiding** indicated if your source states it (e.g. "Presiding: …"). For tribunals: **Member(s) / Chairperson** as named in the order.
   - **Counsel / Advocates** — for **each side** (appellant(s), respondent(s), applicant(s), CCI / Union / State, intervenors, amicus if any): **full names** with **designation** if given (Sr. Adv., Adv., AAG, ASG, etc.) and **who they appeared for**. Use `Not stated in sources` for any role not named in materials.

   If the story is **not** court-led (no bench yet), state that; still give **§2** citations/numbers if any apply, and list counsel **only if** sources name them.

4. **Case record (reporter-style)** — Technical metadata (SCC Online / headnote style). **Citations and official numbers** must **match §2**; **coram and counsel** must **match §3** (you may write "As §2" / "As §3" where already complete). **Only include fields supported by your sources**; for anything not found, write `Not stated in sources`.

   Cover (skip lines wholly unavailable):
   - **Case title** (party names in citation form)
   - **Citations & official numbers** — same as **§2** (must not contradict)
   - **Coram** — same names as **Judges and counsel** (must not contradict §3)
   - **Counsel** — same as **Judges and counsel** (must not contradict §3)
   - **Date of decision / order**
   - **Subject / catchwords / headnote topics** (if sources quote them)
   - **Statutes & provisions** referred or interpreted
   - **Result / disposal**
   - **Procedural history** — courts or bodies below, if stated
   - **Cases referred / relied on / distinguished** — only if listed in sources
   - **Source note** — SCC Online, Indian Kanoon, official PDF URL, etc.

5. **Introduction** — lede with what is at stake legally and institutionally.
6. **Chronology (by date)** — A dedicated timeline **sorted strictly by date** (earliest → latest, or latest → earliest; state which you use once). Use a **markdown table** with columns such as: **Date** | **Event / order / filing** | **Forum or actor** | **Citation / identifier (if any)** | **Source ref [n]**. Every row must be tied to a source; use `Approx. / month only` or `Not stated in sources` when a day is not reported. Include orders, appeals filed, hearings, transfers, key regulator steps, and final disposal as reported.

7. **Precedents** — Legal and decisional backdrop **as actually cited or discussed in your sources** (do not invent a treatise). Use subheadings as appropriate:
   - **Cases relied on / followed** — citation, court, ratio or use as stated in sources
   - **Cases distinguished / overruled / referred** — only if your materials mention them
   - **Statutory / regulatory lineage** — prior amendments, rules, or guidelines if sources tie them to the dispute
   For each authority, one short neutral line on **why it matters** for the instant topic (holding, analogy, or contrast), with inline [n] citations.

8. **Factual matrix** — Narrative of parties, institutions, and the fact pattern; cross-reference the **Chronology** where helpful. Do not repeat the full date table here—expand context, actors, and relationships that sources support.
9. **Issues and legal framework** — issues presented; statutes/rules/constitutional provisions *as cited in sources*.
10. **Analysis** — structured reasoning; distinguish holding/obiter where cases are discussed; note limitations of sources.
11. **Outlook** — what remains open procedurally or substantively, without speculation dressed as fact.

Citation style: inline [1], [2] mapping to a **References** list with URLs at the end.
Do not fabricate citations, docket numbers, or quotes. Mark uncertainty explicitly.

End with a short **Disclaimer**: not legal advice; based on public sources as of the research run.
"""


def build_article_query(
    *,
    run_date: str,
    title: str,
    angle: str,
    branch: str,
    seed_phrases: List[str],
) -> str:
    seeds = ", ".join(seed_phrases) if seed_phrases else "(none — infer from title and angle)"
    return f"""
India legal research task for an analytical article. Working date: {run_date}.

TOPIC TITLE: {title}
EDITORIAL ANGLE: {angle}
BRANCH (taxonomy): {branch}
SEED PHRASES: {seeds}

Mandate:
- Research only India-relevant public materials (newsrooms, court portals, regulators, government releases).
- For **case-led topics**, actively seek **reporter-grade metadata**: query **SCC Online** (`site:scconline.com`), **Indian Kanoon** (`site:indiankanoon.org`), **Supreme Court** (`site:sci.gov.in`), and official tribunal/court sites. SCC Online blog digests and case summaries often list citations, coram, and headnote-style subject lines even when the full judgment is paywalled — use what is publicly visible.
- For the article opening: gather **AIR**, **SCC** (and **SCC OnLine** tribunal cites), **SCALE**/**SCR** if reported, and **official case numbers** (appeal/SLP/WP/company appeal/regulator case no., diary no., etc.) for **Citations and case numbers** (right after the headline).
- Extract **exact spellings** of **judges’ and counsel’s full names** from judgment headers, official PDFs, Indian Kanoon, or SCC-style digests—for **Judges and counsel** (after citations).
- Extract party names, bench, dates, statutes cited, and disposal for the **Case record** section.
- Build material for **Chronology (by date)**: every dated procedural step you find (orders, appeals, hearings, filings) with forum and citation where reported.
- Build material for **Precedents**: prior cases and statutes your sources **actually** cite, follow, distinguish, or discuss in relation to this story.
- Collect related matters and authorities *as actually reported* — do not invent case names or citations.
- Cover criminal/civil/tax/constitutional/administrative angles only to the extent sources support them for this story.
"""


def load_queue(path: Path) -> dict:
    if path.exists():
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    return {
        "version": QUEUE_VERSION,
        "created_at": _now(),
        "updated_at": _now(),
        "items": [],
    }


def save_queue(q: dict, path: Path) -> None:
    q["updated_at"] = _now()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(q, indent=2, ensure_ascii=False), encoding="utf-8")


def _item_key(run_date: str, title: str) -> str:
    return f"{run_date}|{topic_title_key(title)}"


def _make_item(
    *,
    run_date: str,
    title: str,
    provisional_angle: str,
    branch: str,
    priority: str = "medium",
    seed_phrases: Optional[List[str]] = None,
    source: str = "discovery",
    parent_id: Optional[str] = None,
) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "run_date": run_date,
        "title": title.strip(),
        "provisional_angle": (provisional_angle or "").strip(),
        "branch": (branch or "other").strip(),
        "priority": priority,
        "seed_phrases": seed_phrases or [],
        "source": source,
        "parent_id": parent_id,
        "status": "pending",
        "article_path": None,
        "followups_path": None,
        "error": None,
        "added_at": _now(),
        "started_at": None,
        "completed_at": None,
    }


def existing_keys_for_date(queue: dict, run_date: str) -> set[str]:
    keys: set[str] = set()
    for it in queue.get("items", []):
        if it.get("run_date") != run_date:
            continue
        if it.get("status") == "pending":
            keys.add(_item_key(run_date, it.get("title", "")))
        if it.get("status") in ("running", "done", "failed"):
            keys.add(_item_key(run_date, it.get("title", "")))
    return keys


def enqueue_discovered_topics(queue: dict, run_date: str, topics: List[DiscoveredTopic]) -> int:
    existing = existing_keys_for_date(queue, run_date)
    added = 0
    for t in topics:
        title = (t.title or "").strip()
        if not title:
            continue
        k = _item_key(run_date, title)
        if k in existing:
            continue
        queue["items"].append(
            _make_item(
                run_date=run_date,
                title=title,
                provisional_angle=t.provisional_angle,
                branch=t.branch,
                priority=t.priority,
                seed_phrases=t.seed_phrases,
                source="discovery",
            )
        )
        existing.add(k)
        added += 1
    return added


def enqueue_followups(
    queue: dict,
    run_date: str,
    followups: List[Dict[str, Any]],
    parent_id: str,
) -> int:
    existing = existing_keys_for_date(queue, run_date)
    added = 0
    for raw in followups:
        title = (raw.get("title") or "").strip()
        if not title:
            continue
        k = _item_key(run_date, title)
        if k in existing:
            continue
        queue["items"].append(
            _make_item(
                run_date=run_date,
                title=title,
                provisional_angle=raw.get("headline_angle") or raw.get("reason") or "",
                branch=raw.get("branch") or "other",
                priority=raw.get("priority") or "medium",
                seed_phrases=[title, raw.get("relationship", "")],
                source="follow_on",
                parent_id=parent_id,
            )
        )
        existing.add(k)
        added += 1
    return added


async def run_article_for_item(
    item: dict,
    *,
    run_date: str,
    max_iterations: int,
    max_time: int,
    model: str | None,
    out_dir: Path,
) -> tuple[str, List[Dict[str, Any]]]:
    config = create_config(model=model)
    researcher = IterativeResearcherIndiaLegal(
        max_iterations=max_iterations,
        max_time_minutes=max_time,
        verbose=True,
        tracing=False,
        config=config,
    )
    query = build_article_query(
        run_date=run_date,
        title=item["title"],
        angle=item.get("provisional_angle", ""),
        branch=item.get("branch", "other"),
        seed_phrases=list(item.get("seed_phrases") or []),
    )
    report = await researcher.run(
        query,
        output_length="2,500–5,000 words unless sources are thin",
        output_instructions=article_output_instructions(run_date),
        background_context=f"Queued item id={item['id']} source={item.get('source')}",
    )
    return report, researcher.last_related_legal_topics


async def run_daily(
    *,
    run_date: str,
    queue_path: Path,
    out_dir: Path,
    discover: bool,
    discover_only: bool,
    max_discovery_searches: int,
    max_concurrent_discovery: int,
    max_articles: int,
    max_iterations: int,
    max_time: int,
    model: str | None,
    verbose: bool = True,
) -> None:
    def log(msg: str) -> None:
        if verbose:
            print(msg)

    queue = load_queue(queue_path)

    # Any prior crash leaves items stuck as "running"; clear at every run start (all dates).
    reset_running_n = 0
    for it in queue.get("items", []):
        if it.get("status") == "running":
            it["status"] = "pending"
            it["started_at"] = None
            reset_running_n += 1
    if reset_running_n:
        save_queue(queue, queue_path)
        log(f"[QUEUE] Reset {reset_running_n} stale 'running' item(s) to pending at run start.")

    if discover:
        log(f"\n[DISCOVERY] Running-matters SERP (all court tiers within budget) + topic compilation for {run_date} …")
        compilation = await discover_topics_for_date(
            run_date,
            config=create_config(model=model),
            max_discovery_searches=max_discovery_searches,
            max_concurrent_searches=max_concurrent_discovery,
        )
        n = enqueue_discovered_topics(queue, run_date, compilation.topics)
        save_queue(queue, queue_path)
        log(f"[DISCOVERY] Enqueued {n} new topic(s). Total items in queue: {len(queue['items'])}")

    if discover_only:
        log("[DISCOVERY] --discover-only set; exiting before writing articles.")
        return

    queue = load_queue(queue_path)

    out_dir.mkdir(parents=True, exist_ok=True)

    pending = [
        it
        for it in queue["items"]
        if it.get("run_date") == run_date and it.get("status") == "pending"
    ]
    priority_order = {"high": 0, "medium": 1, "low": 2}
    pending.sort(key=lambda x: priority_order.get(x.get("priority", "medium"), 1))

    done_count = 0
    for item in pending:
        if done_count >= max_articles:
            log(f"\n[LIMIT] max_articles={max_articles} reached for this run.")
            break

        log(f"\n{'='*70}\n[ARTICLE] {item['title']}\n{'='*70}")
        item["status"] = "running"
        item["started_at"] = _now()
        save_queue(queue, queue_path)

        base = _timestamped_basename(item["title"])
        article_path = out_dir / f"{base}.md"
        follow_path = out_dir / f"{base}-followups.json"

        try:
            report, followups = await run_article_for_item(
                item,
                run_date=run_date,
                max_iterations=max_iterations,
                max_time=max_time,
                model=model,
                out_dir=out_dir,
            )
            article_path.write_text(report, encoding="utf-8")
            item["status"] = "done"
            item["article_path"] = str(article_path)
            item["completed_at"] = _now()

            if followups:
                follow_path.write_text(
                    json.dumps(
                        {
                            "run_date": run_date,
                            "source_item_id": item["id"],
                            "followups": followups,
                        },
                        indent=2,
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
                item["followups_path"] = str(follow_path)
                added = enqueue_followups(queue, run_date, followups, parent_id=item["id"])
                log(f"[QUEUE] Enqueued {added} follow-on topic(s) for {run_date}.")
            else:
                item["followups_path"] = None

            done_count += 1
        except Exception as exc:
            log(f"\n[ERROR] {exc}")
            item["status"] = "failed"
            item["error"] = str(exc)
            item["completed_at"] = _now()
        finally:
            save_queue(queue, queue_path)

    queue = load_queue(queue_path)
    rem = len([i for i in queue["items"] if i.get("run_date") == run_date and i.get("status") == "pending"])
    log(f"\n[DONE] Finished {done_count} article(s) this run. Pending for {run_date}: {rem}. Queue file: {queue_path}")


def main() -> None:
    p = argparse.ArgumentParser(
        description="India legal daily article workflow: direct legal-news discovery, queue, research, write."
    )
    p.add_argument(
        "--date",
        "-d",
        required=True,
        help="Run date YYYY-MM-DD (all queued topics for this calendar day are processed).",
    )
    p.add_argument(
        "--queue-file",
        "-q",
        default=None,
        help="Queue JSON path (default: outputs/india_legal_<run_id>/queue.json for a new run)",
    )
    p.add_argument(
        "--out-dir",
        "-o",
        default=None,
        help="Directory for .md / followups JSON (default: same folder as the queue for a new run)",
    )
    p.add_argument(
        "--model",
        "-m",
        default=None,
        help="Override reasoning/main/fast model ids (default: REASONING_MODEL, MAIN_MODEL, FAST_MODEL from .env)",
    )
    p.add_argument("--max-articles", type=int, default=50, help="Max articles to write this run (default: 50)")
    p.add_argument("--max-iterations", type=int, default=10, help="Research iterations per article (default: 10)")
    p.add_argument("--max-time", type=int, default=45, help="Max minutes per article")
    p.add_argument("--skip-discovery", action="store_true", help="Do not run SERP legal-news discovery")
    p.add_argument("--discover-only", action="store_true", help="Only enqueue topics from discovery, then exit")
    p.add_argument("--no-discover", action="store_true", help="Alias for --skip-discovery")
    p.add_argument(
        "--max-discovery-searches",
        type=int,
        default=18,
        help=(
            "Max SERP calls per discovery run. Schedules one distinct query per court tier first, "
            "then round-robin until this cap (default: 18). Use >= 14 to reach every tier at least once."
        ),
    )
    p.add_argument(
        "--max-concurrent-discovery",
        type=int,
        default=2,
        help="Max parallel SERP requests during discovery (default: 2).",
    )
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args()

    try:
        datetime.strptime(args.date, "%Y-%m-%d")
    except ValueError:
        print("Error: --date must be YYYY-MM-DD", file=sys.stderr)
        sys.exit(1)

    if not os.getenv("BRIGHTDATA_API_KEY"):
        print("Error: Set BRIGHTDATA_API_KEY in .env", file=sys.stderr)
        sys.exit(1)
    if not (os.getenv("BRIGHTDATA_SERP_ZONE") or os.getenv("BRIGHTDATA_ZONE")):
        print("Error: Set BRIGHTDATA_SERP_ZONE or BRIGHTDATA_ZONE in .env", file=sys.stderr)
        sys.exit(1)
    if not (os.getenv("OPENROUTER_API_KEY") or os.getenv("DR_OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")):
        print("Error: Set OPENROUTER_API_KEY (or DR_OPENROUTER_API_KEY) in .env", file=sys.stderr)
        sys.exit(1)

    skip_discovery = args.skip_discovery or args.no_discover
    if args.discover_only and skip_discovery:
        print("Error: --discover-only cannot be combined with --skip-discovery / --no-discover", file=sys.stderr)
        sys.exit(1)

    discover = not skip_discovery

    # Default: new timestamped run directory under outputs/ with queue.json + articles together.
    if args.queue_file is None and args.out_dir is None:
        run_root = Path("outputs") / f"india_legal_{_new_run_id()}"
        run_root.mkdir(parents=True, exist_ok=True)
        queue_path = run_root / "queue.json"
        out_dir = run_root
    elif args.queue_file is not None and args.out_dir is None:
        queue_path = Path(args.queue_file)
        out_dir = queue_path.parent
    elif args.queue_file is None and args.out_dir is not None:
        out_dir = Path(args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        queue_path = out_dir / "queue.json"
    else:
        queue_path = Path(args.queue_file)
        out_dir = Path(args.out_dir)

    if not args.quiet:
        print(f"[RUN] Queue file: {queue_path.resolve()}")
        print(f"[RUN] Article output directory: {out_dir.resolve()}")

    asyncio.run(
        run_daily(
            run_date=args.date,
            queue_path=queue_path,
            out_dir=out_dir,
            discover=discover,
            discover_only=args.discover_only,
            max_discovery_searches=args.max_discovery_searches,
            max_concurrent_discovery=args.max_concurrent_discovery,
            max_articles=args.max_articles,
            max_iterations=args.max_iterations,
            max_time=args.max_time,
            model=args.model,
            verbose=not args.quiet,
        )
    )


if __name__ == "__main__":
    main()
