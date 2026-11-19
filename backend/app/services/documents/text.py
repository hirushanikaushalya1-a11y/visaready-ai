"""Text extraction: embedded PDF text first, OCR (Tesseract) for scanned pages and images.
All subprocesses run with timeouts on temporary copies; input is never interpreted as a command."""
from __future__ import annotations

import io
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

ALLOWED_TYPES = {"application/pdf": ".pdf", "image/jpeg": ".jpg", "image/png": ".png"}
MAX_PAGES = 60


def sniff_content_type(data: bytes) -> str | None:
    """Identify the file from magic bytes — the client-supplied MIME type is ignored."""
    if data[:5] == b"%PDF-":
        return "application/pdf"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    return None


def pdf_is_encrypted_or_active(data: bytes) -> str | None:
    """Reject PDFs we cannot safely process. Returns a reason or None."""
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception:  # noqa: BLE001
        return "The PDF could not be read. It may be damaged."
    if reader.is_encrypted:
        return "Password-protected PDFs cannot be processed. Please upload an unlocked copy."
    root = reader.trailer.get("/Root", {})
    try:
        if "/JavaScript" in str(root.get("/Names", {})) or "/OpenAction" in root and "/JS" in str(root.get("/OpenAction")):
            return "This PDF contains embedded scripts and was rejected for security reasons."
    except Exception:  # noqa: BLE001
        pass
    if len(reader.pages) > MAX_PAGES:
        return f"PDFs are limited to {MAX_PAGES} pages. Please split the document."
    return None


@dataclass
class PageText:
    page_number: int
    text: str
    method: str
    ocr_confidence: float | None = None


def ocr_available() -> bool:
    return shutil.which("tesseract") is not None


def _ocr_image(path: Path) -> tuple[str, float | None]:
    out = subprocess.run(
        ["tesseract", str(path), "stdout", "-l", "eng", "--psm", "3", "tsv"],
        capture_output=True, timeout=120, check=False,
    )
    lines = out.stdout.decode("utf-8", "replace").splitlines()
    words, confs, last_line = [], [], None
    text_parts: list[str] = []
    for row in lines[1:]:
        cols = row.split("\t")
        if len(cols) < 12:
            continue
        try:
            conf = float(cols[10])
        except ValueError:
            continue
        line_id = (cols[2], cols[3], cols[4])
        word = cols[11]
        if conf < 0:
            continue
        if last_line is not None and line_id != last_line:
            text_parts.append("\n")
        elif text_parts:
            text_parts.append(" ")
        text_parts.append(word)
        last_line = line_id
        if word.strip():
            words.append(word)
            confs.append(conf)
    conf_avg = round(sum(confs) / len(confs), 1) if confs else None
    return "".join(text_parts).strip(), conf_avg


def extract_pages(data: bytes, content_type: str) -> list[PageText]:
    with tempfile.TemporaryDirectory(prefix="vr-doc-") as tmp:
        tmpdir = Path(tmp)
        if content_type == "application/pdf":
            src = tmpdir / "in.pdf"
            src.write_bytes(data)
            from pypdf import PdfReader

            n = len(PdfReader(io.BytesIO(data)).pages)
            pages: list[PageText] = []
            for i in range(1, n + 1):
                res = subprocess.run(["pdftotext", "-layout", "-f", str(i), "-l", str(i), str(src), "-"],
                                     capture_output=True, timeout=60, check=False)
                text = res.stdout.decode("utf-8", "replace").strip()
                if len(text) >= 25 or not ocr_available():
                    pages.append(PageText(i, text, "pdf_text"))
                    continue
                # Scanned page: rasterise and OCR.
                prefix = tmpdir / f"p{i}"
                subprocess.run(["pdftoppm", "-r", "200", "-gray", "-png", "-f", str(i), "-l", str(i), str(src), str(prefix)],
                               capture_output=True, timeout=120, check=False)
                imgs = sorted(tmpdir.glob(f"p{i}*.png"))
                if imgs:
                    t, conf = _ocr_image(imgs[0])
                    pages.append(PageText(i, t, "ocr", conf))
                else:
                    pages.append(PageText(i, text, "pdf_text"))
            return pages
        # images
        if not ocr_available():
            return [PageText(1, "", "unavailable")]
        src = tmpdir / ("in" + ALLOWED_TYPES[content_type])
        src.write_bytes(data)
        t, conf = _ocr_image(src)
        return [PageText(1, t, "ocr", conf)]


def detect_scripts(text: str) -> set[str]:
    """Detect non-Latin scripts relevant to our source markets (for translation flags)."""
    found = set()
    for ch in text:
        o = ord(ch)
        if 0x0D80 <= o <= 0x0DFF:
            found.add("sinhala")
        elif 0x0B80 <= o <= 0x0BFF:
            found.add("tamil")
        elif 0x0900 <= o <= 0x097F:
            found.add("devanagari")
        elif 0x0980 <= o <= 0x09FF:
            found.add("bengali")
    return found
