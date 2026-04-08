#!/usr/bin/env python3
"""
Chained / infinite MRO research runner with a file-backed queue.

How it works
============
1. Seed the queue with one or more aircraft/part/make configurations.
2. For each pending item: run full IterativeResearcher MRO research.
3. On completion the KnowledgeGapAgent returns `related_mro_targets` — related
   aircraft/engine configurations worth investigating next.
4. Those targets are written as "<slug>-search-targets.json" (the "search file")
   and pushed onto the queue as new pending items (deduplicated, depth-limited).
5. Loop continues until the queue is empty or --max-total / --max-depth is reached.

Queue file: outputs/mro_queue.json  (or override with --queue-file)
Resume: re-run the same command — already-done items are skipped automatically.

Usage examples
==============
  # Seed with one config
  python run_mro_research_chain.py --aircraft "Boeing 737-800" --part engine --make "CFM56-7B"

  # Seed with multiple configs from a JSON seed file
  python run_mro_research_chain.py --seed seeds/mro_seed.json

  # Resume an interrupted run
  python run_mro_research_chain.py --queue-file outputs/mro_queue.json

  # Limit depth and total items
  python run_mro_research_chain.py --aircraft "A320" --part engine \\
      --max-depth 2 --max-total 15 --max-iterations 5

Seed file format (seeds/mro_seed.json)
=======================================
[
  {"aircraft": "Boeing 737-800", "part": "engine", "make": "CFM56-7B"},
  {"aircraft": "Airbus A320ceo", "part": "engine", "make": "CFM56-5B"}
]
"""

import argparse
import asyncio
import json
import os
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path

_project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(_project_root))

from dotenv import load_dotenv
load_dotenv(_project_root / ".env")

from agents import set_tracing_disabled
from run_mro_research import run_research, _slug, _timestamped_basename

if not os.getenv("OPENAI_API_KEY") or "your-" in str(os.getenv("OPENAI_API_KEY", "")):
    set_tracing_disabled(True)

# ---------------------------------------------------------------------------
# Queue data model
# ---------------------------------------------------------------------------

QUEUE_VERSION = 1


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _make_item(
    aircraft: str,
    part: str,
    make: str | None = None,
    context: str | None = None,
    source_id: str | None = None,
    relationship: str = "initial",
    depth: int = 0,
    priority: str = "medium",
    reason: str = "",
) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "aircraft": aircraft,
        "part": part,
        "make": make,
        "context": context,
        "source_id": source_id,
        "relationship": relationship,
        "depth": depth,
        "priority": priority,
        "reason": reason,
        "status": "pending",      # pending | running | done | failed | skipped
        "report_path": None,
        "json_path": None,
        "targets_path": None,
        "error": None,
        "added_at": _now(),
        "started_at": None,
        "completed_at": None,
    }


def _item_key(aircraft: str, part: str, make: str | None) -> str:
    """Normalised key for deduplication."""
    return f"{aircraft.lower().strip()}|{part.lower().strip()}|{(make or '').lower().strip()}"


# ---------------------------------------------------------------------------
# Queue persistence
# ---------------------------------------------------------------------------

def load_queue(queue_path: Path) -> dict:
    if queue_path.exists():
        with queue_path.open(encoding="utf-8") as f:
            return json.load(f)
    return {
        "version": QUEUE_VERSION,
        "created_at": _now(),
        "updated_at": _now(),
        "config": {},
        "items": [],
    }


def save_queue(queue: dict, queue_path: Path) -> None:
    queue["updated_at"] = _now()
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    queue_path.write_text(json.dumps(queue, indent=2, ensure_ascii=False), encoding="utf-8")


def queue_done_keys(queue: dict) -> set[str]:
    """Return normalised keys for all non-pending items (done/failed/running/skipped)."""
    return {
        _item_key(i["aircraft"], i["part"], i.get("make"))
        for i in queue["items"]
        if i["status"] != "pending"
    }


def enqueue_targets(
    queue: dict,
    targets: list[dict],
    source_id: str,
    max_depth: int,
    current_depth: int,
) -> int:
    """Add new targets to the queue. Returns count of newly added items."""
    done_keys = queue_done_keys(queue)
    # Also track pending keys to avoid adding duplicates there too
    pending_keys = {
        _item_key(i["aircraft"], i["part"], i.get("make"))
        for i in queue["items"]
        if i["status"] == "pending"
    }
    existing_keys = done_keys | pending_keys

    next_depth = current_depth + 1
    if next_depth > max_depth:
        return 0

    added = 0
    for t in targets:
        aircraft = t.get("aircraft", "").strip()
        part = t.get("part", "engine").strip()
        make = (t.get("make") or "").strip() or None
        key = _item_key(aircraft, part, make)
        if not aircraft or not part:
            continue
        if key in existing_keys:
            continue
        item = _make_item(
            aircraft=aircraft,
            part=part,
            make=make,
            source_id=source_id,
            relationship=t.get("relationship", "RELATED"),
            depth=next_depth,
            priority=t.get("priority", "medium"),
            reason=t.get("reason", ""),
        )
        queue["items"].append(item)
        existing_keys.add(key)
        added += 1

    return added


# ---------------------------------------------------------------------------
# Main chain runner
# ---------------------------------------------------------------------------

async def run_chain(
    queue_path: Path,
    max_depth: int,
    max_total: int,
    max_iterations: int,
    max_time: int,
    model: str | None,
    out_dir: Path,
    verbose: bool = True,
) -> None:
    queue = load_queue(queue_path)
    out_dir.mkdir(parents=True, exist_ok=True)

    total_done = sum(1 for i in queue["items"] if i["status"] == "done")
    total_failed = sum(1 for i in queue["items"] if i["status"] == "failed")

    def _log(msg: str) -> None:
        if verbose:
            print(msg)

    _log(f"\n{'='*70}")
    _log(f"MRO Chain Research — queue: {queue_path}")
    _log(f"Limits: max_depth={max_depth}  max_total={max_total}  "
         f"max_iterations={max_iterations}  max_time={max_time}m")
    _log(f"Queue: {len(queue['items'])} items total  "
         f"({total_done} done, {total_failed} failed)")
    _log(f"{'='*70}\n")

    while True:
        # Re-load queue state to pick up any changes
        queue = load_queue(queue_path)

        # Count total processed so far
        processed = sum(1 for i in queue["items"] if i["status"] in ("done", "failed"))
        if processed >= max_total:
            _log(f"\n[CHAIN] Reached max_total={max_total}. Stopping.")
            break

        # Find next pending item (respect priority: high > medium > low)
        pending = [i for i in queue["items"] if i["status"] == "pending"]
        if not pending:
            _log("\n[CHAIN] Queue is empty. All done.")
            break

        priority_order = {"high": 0, "medium": 1, "low": 2}
        pending.sort(key=lambda x: (x["depth"], priority_order.get(x.get("priority", "medium"), 1)))
        item = pending[0]

        aircraft = item["aircraft"]
        part = item["part"]
        make = item.get("make")
        depth = item["depth"]
        relationship = item.get("relationship", "initial")

        _log(f"\n[CHAIN] Processing item {item['id'][:8]}…")
        _log(f"  Aircraft : {aircraft}")
        _log(f"  Part     : {part}")
        _log(f"  Make     : {make or '(unknown)'}")
        _log(f"  Depth    : {depth}  Relationship: {relationship}")
        _log(f"  Progress : {processed + 1}/{max_total}")

        # Mark as running and save
        item["status"] = "running"
        item["started_at"] = _now()
        save_queue(queue, queue_path)

        base = _timestamped_basename(aircraft, part, make)

        try:
            report, extracted, related_targets = await run_research(
                aircraft=aircraft,
                part=part,
                make=make,
                context=item.get("context"),
                max_iterations=max_iterations,
                max_time=max_time,
                model=model,
            )

            # --- Write report ---
            report_path = out_dir / f"{base}.md"
            report_path.write_text(report, encoding="utf-8")
            _log(f"\n[CHAIN] Report saved: {report_path}")

            # --- Write JSON ---
            json_path = None
            if extracted:
                json_path = out_dir / f"{base}.json"
                json_path.write_text(json.dumps(extracted, indent=2, ensure_ascii=False), encoding="utf-8")

            # --- Write search-targets file ---
            targets_path = None
            if related_targets:
                targets_payload = {
                    "generated_at": _now(),
                    "source_item_id": item["id"],
                    "aircraft": aircraft,
                    "part": part,
                    "make": make,
                    "depth": depth,
                    "targets": related_targets,
                }
                targets_path = out_dir / f"{base}-search-targets.json"
                targets_path.write_text(
                    json.dumps(targets_payload, indent=2, ensure_ascii=False),
                    encoding="utf-8"
                )
                _log(f"[CHAIN] Search targets saved: {targets_path}")
                _log(f"  → {len(related_targets)} follow-up target(s) identified")

                # --- Enqueue new targets ---
                added = enqueue_targets(
                    queue=queue,
                    targets=related_targets,
                    source_id=item["id"],
                    max_depth=max_depth,
                    current_depth=depth,
                )
                if added:
                    _log(f"[CHAIN] {added} new item(s) added to the queue (depth {depth + 1})")
                else:
                    _log(f"[CHAIN] No new items added (all targets already in queue or max_depth reached)")

            # --- Update item status ---
            item["status"] = "done"
            item["completed_at"] = _now()
            item["report_path"] = str(report_path)
            item["json_path"] = str(json_path) if json_path else None
            item["targets_path"] = str(targets_path) if targets_path else None

        except Exception as exc:
            _log(f"\n[CHAIN] ERROR processing item {item['id'][:8]}: {exc}")
            item["status"] = "failed"
            item["error"] = str(exc)
            item["completed_at"] = _now()

        finally:
            save_queue(queue, queue_path)

    # --- Summary ---
    queue = load_queue(queue_path)
    done = [i for i in queue["items"] if i["status"] == "done"]
    failed = [i for i in queue["items"] if i["status"] == "failed"]
    pending = [i for i in queue["items"] if i["status"] == "pending"]
    _log(f"\n{'='*70}")
    _log(f"[CHAIN] Run complete.")
    _log(f"  Done    : {len(done)}")
    _log(f"  Failed  : {len(failed)}")
    _log(f"  Pending : {len(pending)} (will resume on next run)")
    _log(f"  Queue   : {queue_path}")
    _log(f"{'='*70}\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Chained MRO research with file-backed queue. "
                    "Runs research → identifies related configs → queues them → repeats."
    )

    # Seed options (mutually exclusive)
    seed_group = parser.add_mutually_exclusive_group()
    seed_group.add_argument("--aircraft", "-a", help="Seed aircraft (e.g. 'Boeing 737-800')")
    seed_group.add_argument("--seed", "-s", help="Path to JSON seed file (list of {aircraft,part,make?})")

    parser.add_argument("--part", "-p", default="engine", help="Seed part type (default: engine)")
    parser.add_argument("--make", "-k", default=None, help="Seed make/model (e.g. CFM56-7B)")
    parser.add_argument("--context", "-c", default=None, help="Optional research context")

    # Queue options
    parser.add_argument(
        "--queue-file", "-q",
        default="outputs/mro_queue.json",
        help="Path to queue JSON file (default: outputs/mro_queue.json)"
    )

    # Depth / limit options
    parser.add_argument("--max-depth", type=int, default=2,
                        help="Max hop depth from seed (default: 2)")
    parser.add_argument("--max-total", type=int, default=20,
                        help="Max total items to process before stopping (default: 20)")

    # Research options
    parser.add_argument("--max-iterations", type=int, default=5,
                        help="Max research iterations per item (default: 5)")
    parser.add_argument("--max-time", type=int, default=60,
                        help="Max time per item in minutes (default: 60)")
    parser.add_argument(
        "--model",
        "-m",
        default=None,
        help="Override reasoning/main/fast model ids (default: from .env)",
    )

    # Output
    parser.add_argument("--out-dir", default="outputs",
                        help="Output directory for reports and JSON (default: outputs/)")
    parser.add_argument("--quiet", action="store_true", help="Suppress verbose output")

    args = parser.parse_args()

    # Validate env
    if not (os.getenv("EXA_API_KEY") or os.getenv("DR_EXA_API_KEY")):
        print("Error: Set EXA_API_KEY in .env", file=sys.stderr)
        sys.exit(1)
    if not (os.getenv("OPENROUTER_API_KEY") or os.getenv("DR_OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")):
        print("Error: Set OPENROUTER_API_KEY in .env", file=sys.stderr)
        sys.exit(1)

    queue_path = Path(args.queue_file)
    out_dir = Path(args.out_dir)

    # Load or create queue
    queue = load_queue(queue_path)

    # Add seeds if provided
    if args.aircraft:
        seeds = [{"aircraft": args.aircraft, "part": args.part, "make": args.make, "context": args.context}]
    elif args.seed:
        seed_file = Path(args.seed)
        if not seed_file.exists():
            print(f"Error: seed file not found: {seed_file}", file=sys.stderr)
            sys.exit(1)
        seeds = json.loads(seed_file.read_text(encoding="utf-8"))
    else:
        # No seeds supplied — just resume the existing queue
        seeds = []

    existing_keys = {
        _item_key(i["aircraft"], i["part"], i.get("make"))
        for i in queue["items"]
    }

    newly_seeded = 0
    for s in seeds:
        aircraft = s.get("aircraft", "").strip()
        part = s.get("part", "engine").strip()
        make = (s.get("make") or "").strip() or None
        context = s.get("context") or args.context
        key = _item_key(aircraft, part, make)
        if not aircraft:
            continue
        if key in existing_keys:
            print(f"[SEED] Already in queue: {aircraft} / {part} / {make or 'unknown'} — skipping")
            continue
        item = _make_item(aircraft=aircraft, part=part, make=make, context=context)
        queue["items"].append(item)
        existing_keys.add(key)
        newly_seeded += 1
        print(f"[SEED] Added: {aircraft} / {part} / {make or 'unknown'}")

    if newly_seeded:
        save_queue(queue, queue_path)

    pending_count = sum(1 for i in queue["items"] if i["status"] == "pending")
    if pending_count == 0:
        print("\nNo pending items in queue. Use --aircraft / --seed to add new seeds.")
        sys.exit(0)

    asyncio.run(run_chain(
        queue_path=queue_path,
        max_depth=args.max_depth,
        max_total=args.max_total,
        max_iterations=args.max_iterations,
        max_time=args.max_time,
        model=args.model,
        out_dir=out_dir,
        verbose=not args.quiet,
    ))


if __name__ == "__main__":
    main()
