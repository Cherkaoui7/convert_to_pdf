"""
Office files → PDF converter with maximum format fidelity.
Uses LibreOffice headless for DOC/DOCX/PPT/PPTX/XLS/XLSX/ODT/ODP/ODS/RTF.
Uses ReportLab for TXT/LOG/CSV (plain text).
"""

import os
import sys
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Optional

# ---------- Configuration ----------
SUPPORTED_OFFICE = {
    ".doc", ".docx", ".odt", ".rtf",
    ".ppt", ".pptx", ".odp",
    ".xls", ".xlsx", ".ods",
}
SUPPORTED_TEXT = {".txt", ".log", ".csv", ".tsv"}

# LibreOffice binary candidates
SOFFICE_CANDIDATES = [
    "soffice",
    "libreoffice",
    "/usr/bin/soffice",
    "/usr/bin/libreoffice",
    "/opt/libreoffice*/program/soffice",
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
]

# Serialize LibreOffice calls (it doesn't like concurrent invocations)
_lo_lock = threading.Lock()


def find_soffice() -> str:
    for path in SOFFICE_CANDIDATES:
        if "*" in path:
            import glob
            for match in glob.glob(path):
                if os.path.isfile(match) or shutil.which(match):
                    return match
            continue
        if os.path.isfile(path) or shutil.which(path):
            return path
    raise EnvironmentError(
        "LibreOffice not found. Install it:\n"
        "  Ubuntu/Debian: apt-get install -y libreoffice\n"
        "  macOS: brew install --cask libreoffice\n"
        "  Windows: https://www.libreoffice.org/download/"
    )


def convert_with_libreoffice(
    input_path: str,
    output_dir: str,
    timeout: int = 180,
) -> str:
    """Convert any Office file to PDF using LibreOffice headless."""
    soffice = find_soffice()

    # Use a dedicated user profile (avoids root/Home issues and corrupt ini files)
    profile_dir = tempfile.mkdtemp(prefix="lo_profile_")
    
    # FIX: Ensure the path is absolute and properly formatted for Windows (file:///C:/...)
    profile_uri = Path(profile_dir).resolve().as_uri()

    cmd = [
        soffice,
        "--headless",
        "--nologo",
        "--nofirststartwizard",
        "--norestore",
        f"-env:UserInstallation={profile_uri}",
        "--convert-to", "pdf:writer_pdf_Export",
        "--outdir", output_dir,
        input_path,
    ]

    with _lo_lock:
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                check=False,
            )
            if result.returncode != 0:
                raise RuntimeError(
                    f"LibreOffice failed: "
                    f"{result.stderr.decode('utf-8', errors='ignore').strip()}"
                )
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"LibreOffice timed out after {timeout}s")
        finally:
            try:
                shutil.rmtree(profile_dir, ignore_errors=True)
            except Exception:
                pass

    expected_pdf = os.path.join(
        output_dir,
        Path(input_path).stem + ".pdf",
    )
    if not os.path.exists(expected_pdf):
        raise RuntimeError(
            f"PDF not produced. Expected: {expected_pdf}"
        )
    return expected_pdf


def convert_text_to_pdf(
    input_path: str,
    output_path: str,
    font_name: str = "Courier",
    font_size: int = 10,
    page_size: str = "A4",
    margin: float = 2 * 28.3464567,  # 2 cm in points
) -> str:
    """Convert plain text file to PDF preserving monospace layout."""
    from reportlab.lib.pagesizes import A4, LETTER, legal, landscape
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import cm

    sizes = {"A4": A4, "LETTER": LETTER, "LEGAL": legal}
    pw, ph = sizes.get(page_size.upper(), A4)

    # Try to read with multiple encodings
    text = None
    for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252", "utf-16"):
        try:
            with open(input_path, "r", encoding=enc) as f:
                text = f.read()
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise RuntimeError("Unable to decode text file")

    c = canvas.Canvas(output_path, pagesize=(pw, ph))
    line_height = font_size * 1.2
    y = ph - margin
    x = margin

    c.setFont(font_name, font_size)

    for line in text.splitlines():
        # Handle form-feed (page break) character
        if "\f" in line:
            parts = line.split("\f")
            for i, part in enumerate(parts):
                if y < margin + line_height:
                    c.showPage()
                    c.setFont(font_name, font_size)
                    y = ph - margin
                c.drawString(x, y, part)
                y -= line_height
                if i < len(parts) - 1:
                    c.showPage()
                    c.setFont(font_name, font_size)
                    y = ph - margin
            continue

        if y < margin + line_height:
            c.showPage()
            c.setFont(font_name, font_size)
            y = ph - margin

        # Wrap long lines (preserve content, just break visually)
        max_chars = max(1, int((pw - 2 * margin) / (font_size * 0.6)))
        while len(line) > max_chars:
            c.drawString(x, y, line[:max_chars])
            line = line[max_chars:]
            y -= line_height
            if y < margin + line_height:
                c.showPage()
                c.setFont(font_name, font_size)
                y = ph - margin

        c.drawString(x, y, line)
        y -= line_height

    c.save()
    return output_path


def convert(
    input_path: str,
    output_path: Optional[str] = None,
    timeout: int = 180,
) -> str:
    """
    Convert a single Office/text file to PDF.
    Returns the path to the generated PDF.
    """
    input_path = os.path.abspath(input_path)
    if not os.path.isfile(input_path):
        raise FileNotFoundError(f"Input not found: {input_path}")

    ext = Path(input_path).suffix.lower()
    if ext not in SUPPORTED_OFFICE and ext not in SUPPORTED_TEXT:
        raise ValueError(
            f"Unsupported format: {ext}. "
            f"Supported: {sorted(SUPPORTED_OFFICE | SUPPORTED_TEXT)}"
        )

    if output_path is None:
        output_path = os.path.splitext(input_path)[0] + ".pdf"
    output_path = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    if ext in SUPPORTED_TEXT:
        return convert_text_to_pdf(input_path, output_path)
    else:
        # LibreOffice writes to a temp dir, then we move the file
        with tempfile.TemporaryDirectory(prefix="lo_out_") as tmp_out:
            produced = convert_with_libreoffice(
                input_path, tmp_out, timeout=timeout
            )
            shutil.move(produced, output_path)
        return output_path


def convert_batch(
    input_paths,
    output_dir: str,
    timeout: int = 180,
    on_progress=None,
):
    """Convert multiple files. Returns dict {input: (ok, pdf_or_error)}."""
    os.makedirs(output_dir, exist_ok=True)
    results = {}
    total = len(input_paths)
    for i, p in enumerate(input_paths, 1):
        try:
            out = os.path.join(
                output_dir,
                Path(p).stem + ".pdf",
            )
            # Avoid overwriting on duplicate stems
            counter = 1
            while os.path.exists(out):
                out = os.path.join(
                    output_dir,
                    f"{Path(p).stem}_{counter}.pdf",
                )
                counter += 1
            pdf = convert(p, out, timeout=timeout)
            results[p] = (True, pdf)
        except Exception as e:
            results[p] = (False, str(e))
        if on_progress:
            on_progress(i, total, p)
    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python converter.py <input_file> [output_pdf]")
        sys.exit(1)
    out = convert(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    print(f"✓ Created: {out}")