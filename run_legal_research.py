#!/usr/bin/env python3
"""
Run the legal research pipeline on judgments from PDF, URL, DOCX, or raw text.
Single run or batch over a directory of files. Outputs CaseRecord as JSON.
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

# Project root
_project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(_project_root))

from deep_researcher.llm_config import create_default_config, LLMConfig
from deep_researcher.legal.pipeline import LegalPipeline
from deep_researcher.legal.storage import LegalDB
from deep_researcher.legal.models import CaseRecord


def _parse_args():
    p = argparse.ArgumentParser(description="Run legal pipeline on judgment(s).")
    p.add_argument("--pdf", type=str, help="Path to a PDF file (or directory in batch mode).")
    p.add_argument("--url", type=str, help="URL of a judgment to fetch.")
    p.add_argument("--text", type=str, help="Raw judgment text or path to a .txt file.")
    p.add_argument("--docx", type=str, help="Path to a DOCX file (or directory in batch mode).")
    p.add_argument(
        "--batch",
        nargs="?",
        const=".",
        default=None,
        metavar="DIR",
        help="Batch mode: process all PDF/DOCX/txt in DIR (default: current dir).",
    )
    p.add_argument(
        "--output",
        type=str,
        default=None,
        help="Single run: output JSON path. Batch: output directory (default: outputs/legal).",
    )
    p.add_argument(
        "--no-mongo",
        action="store_true",
        help="Do not use MongoDB (skip LegalDB).",
    )
    p.add_argument("--model", type=str, default=None, help="Override main/fast model name.")
    return p.parse_args()


def _get_config(args):
    if args.model:
        return LLMConfig(
            search_provider=os.getenv("SEARCH_PROVIDER", "jina"),
            reasoning_model_provider=os.getenv("REASONING_MODEL_PROVIDER", "openai"),
            reasoning_model=os.getenv("REASONING_MODEL", "o3-mini"),
            main_model_provider=os.getenv("MAIN_MODEL_PROVIDER", "openai"),
            main_model=args.model,
            fast_model_provider=os.getenv("FAST_MODEL_PROVIDER", "openai"),
            fast_model=args.model,
        )
    return create_default_config()


def _collect_batch_files(directory: Path):
    exts = {".pdf", ".docx", ".txt"}
    files = []
    for p in directory.iterdir():
        if p.is_file() and p.suffix.lower() in exts:
            files.append(p)
    return sorted(files)


async def _run_single(pipeline: LegalPipeline, args) -> CaseRecord:
    pdf_path = args.pdf
    url = args.url
    text = args.text
    docx_path = args.docx

    if sum(1 for x in (pdf_path, url, text, docx_path) if x) != 1:
        raise SystemExit("Exactly one of --pdf, --url, --text, or --docx is required.")

    if text and os.path.isfile(text):
        with open(text, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()

    return await pipeline.process_judgment(
        text=text if text else None,
        pdf_path=pdf_path,
        url=url,
        docx_path=docx_path,
    )


async def _run_batch(pipeline: LegalPipeline, args):
    directory = Path(args.batch)
    if not directory.is_dir():
        raise SystemExit(f"Batch directory does not exist: {directory}")

    out_dir = Path(args.output or "outputs/legal")
    out_dir.mkdir(parents=True, exist_ok=True)

    files = _collect_batch_files(directory)
    if not files:
        raise SystemExit(f"No PDF/DOCX/txt files found in {directory}")

    for fp in files:
        stem = fp.stem
        out_path = out_dir / f"{stem}_case.json"
        try:
            if fp.suffix.lower() == ".pdf":
                record = await pipeline.process_judgment(pdf_path=str(fp))
            elif fp.suffix.lower() == ".docx":
                record = await pipeline.process_judgment(docx_path=str(fp))
            else:
                with open(fp, "r", encoding="utf-8", errors="replace") as f:
                    record = await pipeline.process_judgment(text=f.read())
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(record.model_dump(mode="json"), f, indent=2, ensure_ascii=False)
            print(f"Wrote {out_path}")
        except Exception as e:
            print(f"Error processing {fp}: {e}", file=sys.stderr)


async def main():
    args = _parse_args()
    config = _get_config(args)
    db = None if args.no_mongo else LegalDB()
    pipeline = LegalPipeline(config, db)

    if args.batch is not None:
        await _run_batch(pipeline, args)
        return

    record = await _run_single(pipeline, args)
    out_path = args.output or "output_case.json"
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(record.model_dump(mode="json"), f, indent=2, ensure_ascii=False)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
