"""
HTTP file download + local PDF text extraction for agent tools.

Files are stored under a dedicated temp directory; read_pdf only accepts paths inside that tree.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import tempfile
import uuid
from pathlib import Path
from typing import Optional
from urllib.parse import unquote, urlparse

import aiohttp
from agents import function_tool

from ..llm_config import LLMConfig
from .pdf_tools import extract_text_from_pdf

DEFAULT_MAX_DOWNLOAD_BYTES = 35 * 1024 * 1024
MAX_PDF_TEXT_CHARS = 120_000

DOWNLOAD_ROOT = Path(tempfile.gettempdir()) / "agents-deep-research-downloads"


def _max_download_bytes() -> int:
    raw = os.getenv("AGENTS_MAX_DOWNLOAD_BYTES")
    if raw:
        try:
            return max(1_000_000, int(raw))
        except ValueError:
            pass
    return DEFAULT_MAX_DOWNLOAD_BYTES


def _is_allowed_url(url: str) -> bool:
    try:
        p = urlparse(url.strip())
        return p.scheme in ("http", "https") and bool(p.netloc)
    except Exception:
        return False


def _guess_suffix(url: str, content_type: Optional[str]) -> str:
    path = unquote(urlparse(url).path or "")
    for ext in (".pdf", ".docx", ".doc", ".html", ".htm", ".txt", ".json", ".xml"):
        if path.lower().endswith(ext):
            return ext
    if content_type:
        ct = content_type.split(";")[0].strip().lower()
        if ct == "application/pdf":
            return ".pdf"
        if ct in ("application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"):
            return ".docx"
    return ""


def _is_path_under_download_root(path: Path) -> bool:
    try:
        path.resolve().relative_to(DOWNLOAD_ROOT.resolve())
        return True
    except ValueError:
        return False


def create_download_file_tool(config: Optional[LLMConfig] = None):
    """Bright Data / SERP-agnostic HTTP download tool for WebSearchAgent and CourtSearchAgent."""

    max_bytes = _max_download_bytes()

    @function_tool
    async def download_file(url: str) -> str:
        """Download a file from an HTTP or HTTPS URL to a secure temporary directory.

        Use for judgment PDFs, court orders, or other documents linked from search results.
        Returns the absolute local path, size, and content type — then call read_pdf with that path for PDFs.

        Args:
            url: Full http(s) URL to the file.

        Returns:
            Human-readable result with local_file_path on success, or an error message.
        """
        _ = config  # reserved for future limits per LLMConfig
        url = (url or "").strip()
        if not _is_allowed_url(url):
            return "ERROR: Only http/https URLs with a host are allowed."

        DOWNLOAD_ROOT.mkdir(parents=True, exist_ok=True)
        suffix = ""
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
        }

        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(
                    url,
                    allow_redirects=True,
                    timeout=aiohttp.ClientTimeout(total=120),
                ) as resp:
                    if resp.status != 200:
                        body = (await resp.text())[:500]
                        return f"ERROR: HTTP {resp.status} from server. Body preview: {body}"

                    ctype = resp.headers.get("Content-Type", "")
                    clen = resp.headers.get("Content-Length")
                    if clen:
                        try:
                            if int(clen) > max_bytes:
                                return f"ERROR: Remote file too large ({clen} bytes); max {max_bytes}."
                        except ValueError:
                            pass

                    suffix = _guess_suffix(url, ctype)
                    out_name = f"{uuid.uuid4().hex}{suffix or '.bin'}"
                    out_path = DOWNLOAD_ROOT / out_name

                    hasher = hashlib.sha256()
                    total = 0
                    with open(out_path, "wb") as f:
                        async for chunk in resp.content.iter_chunked(64 * 1024):
                            if not chunk:
                                continue
                            total += len(chunk)
                            if total > max_bytes:
                                out_path.unlink(missing_ok=True)
                                return f"ERROR: Download exceeded max size ({max_bytes} bytes)."
                            hasher.update(chunk)
                            f.write(chunk)

            digest = hasher.hexdigest()
            return (
                f"SUCCESS\n"
                f"local_file_path: {out_path.resolve()}\n"
                f"size_bytes: {total}\n"
                f"content_type: {ctype or 'unknown'}\n"
                f"sha256: {digest}\n"
                f"For PDFs, call read_pdf with the exact local_file_path above."
            )
        except asyncio.TimeoutError:
            return "ERROR: Download timed out."
        except aiohttp.ClientError as e:
            return f"ERROR: Network failure: {e!s}"
        except OSError as e:
            return f"ERROR: Could not write file: {e!s}"

    return download_file


def create_read_pdf_tool(config: Optional[LLMConfig] = None):
    """Extract text from a PDF on disk (path must be under the agent download directory)."""

    @function_tool
    async def read_pdf(local_file_path: str) -> str:
        """Extract text from a PDF file on this machine.

        Args:
            local_file_path: Absolute path exactly as returned in download_file output (local_file_path: ...).

        Returns:
            Extracted text (truncated if extremely long), or an error message.
        """
        _ = config
        raw = (local_file_path or "").strip()
        if "local_file_path:" in raw:
            for line in raw.splitlines():
                line = line.strip()
                if line.startswith("local_file_path:"):
                    raw = line.split(":", 1)[1].strip()
                    break

        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = (DOWNLOAD_ROOT / raw).resolve()
        else:
            path = path.resolve()

        if not _is_path_under_download_root(path):
            return (
                "ERROR: Path must be inside the agent download directory. "
                "Use only the path printed by download_file (local_file_path)."
            )
        if not path.is_file():
            return f"ERROR: File not found: {path}"
        if path.suffix.lower() != ".pdf":
            return f"ERROR: read_pdf only supports .pdf files; got suffix {path.suffix!r}."

        try:

            def _read() -> str:
                return extract_text_from_pdf(str(path))

            text = await asyncio.to_thread(_read)
        except Exception as e:
            return f"ERROR: PDF extraction failed: {e!s}"

        if not (text or "").strip():
            return "ERROR: No extractable text (may be scanned image PDF)."

        if len(text) > MAX_PDF_TEXT_CHARS:
            return (
                text[:MAX_PDF_TEXT_CHARS]
                + f"\n\n[TRUNCATED — showing first {MAX_PDF_TEXT_CHARS} characters of PDF text]"
            )
        return text

    return read_pdf
