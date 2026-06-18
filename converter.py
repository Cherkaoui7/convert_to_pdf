"""
Office files → PDF converter with maximum format fidelity.
Uses LibreOffice headless for DOC/DOCX/PPT/PPTX/XLS/XLSX/ODT/ODP/ODS/RTF.
Uses ReportLab for TXT/LOG/CSV/IMG (plain text and images).
Uses PyPDF2 for merging and watermarking.
"""

import os
import sys
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Optional, List

# ---------- Configuration ----------
SUPPORTED_OFFICE = {
    ".doc", ".docx", ".odt", ".rtf",
    ".ppt", ".pptx", ".odp",
    ".xls", ".xlsx", ".ods",
}
SUPPORTED_TEXT = {".txt", ".log", ".csv", ".tsv"}
SUPPORTED_IMAGES = {".jpg", ".jpeg", ".png", ".bmp", ".gif"}

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


def convert_with_libreoffice(input_path: str, output_dir: str, timeout: int = 180) -> str:
    soffice = find_soffice()
    profile_dir = tempfile.mkdtemp(prefix="lo_profile_")
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

    expected_pdf = os.path.join(output_dir, Path(input_path).stem + ".pdf")
    if not os.path.exists(expected_pdf):
        raise RuntimeError(f"PDF not produced. Expected: {expected_pdf}")
    return expected_pdf


def convert_text_to_pdf(input_path: str, output_path: str) -> str:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    pw, ph = A4
    margin = 2 * 28.3464567
    font_name = "Courier"
    font_size = 10

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


def convert_image_to_pdf(input_path: str, output_path: str) -> str:
    from PIL import Image
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    img = Image.open(input_path)
    if img.mode == "RGBA":
        img = img.convert("RGB")

    pw, ph = A4
    c = canvas.Canvas(output_path, pagesize=(pw, ph))
    
    # Scale image to fit page while maintaining aspect ratio
    img_w, img_h = img.size
    aspect = img_w / img_h
    page_aspect = pw / ph

    if aspect > page_aspect:
        new_w = pw
        new_h = pw / aspect
    else:
        new_h = ph
        new_w = ph * aspect

    x = (pw - new_w) / 2
    y = (ph - new_h) / 2

    c.drawImage(input_path, x, y, width=new_w, height=new_h, preserveAspectRatio=True)
    c.save()
    return output_path


def convert(input_path: str, output_path: Optional[str] = None, timeout: int = 180) -> str:
    input_path = os.path.abspath(input_path)
    if not os.path.isfile(input_path):
        raise FileNotFoundError(f"Input not found: {input_path}")

    ext = Path(input_path).suffix.lower()
    if ext not in SUPPORTED_OFFICE and ext not in SUPPORTED_TEXT and ext not in SUPPORTED_IMAGES:
        raise ValueError(f"Unsupported format: {ext}")

    if output_path is None:
        output_path = os.path.splitext(input_path)[0] + ".pdf"
    output_path = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    if ext in SUPPORTED_TEXT:
        return convert_text_to_pdf(input_path, output_path)
    elif ext in SUPPORTED_IMAGES:
        return convert_image_to_pdf(input_path, output_path)
    else:
        with tempfile.TemporaryDirectory(prefix="lo_out_") as tmp_out:
            produced = convert_with_libreoffice(input_path, tmp_out, timeout=timeout)
            shutil.move(produced, output_path)
        return output_path


# ---------- NEW FEATURES: Watermark & Merge ----------

def watermark_pdf(input_pdf: str, output_pdf: str, text: str):
    """Adds a diagonal text watermark to every page of the PDF."""
    from PyPDF2 import PdfReader, PdfWriter
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.colors import Color

    # Create a temporary watermark PDF
    wm_tmp = output_pdf.replace(".pdf", "_wm_tmp.pdf")
    c = canvas.Canvas(wm_tmp, pagesize=A4)
    c.saveState()
    c.setFont("Helvetica-Bold", 40)
    c.setFillColor(Color(0.5, 0.5, 0.5, alpha=0.3)) # Gray, transparent
    c.translate(A4[0] / 2, A4[1] / 2)
    c.rotate(45)
    c.drawCentredString(0, 0, text)
    c.restoreState()
    c.save()

    # Overlay watermark on original PDF
    reader = PdfReader(input_pdf)
    writer = PdfWriter()
    wm_reader = PdfReader(wm_tmp)

    for page in reader.pages:
        page.merge_page(wm_reader.pages[0])
        writer.add_page(page)

    with open(output_pdf, "wb") as f:
        writer.write(f)

    os.remove(wm_tmp)
    return output_pdf


def merge_pdfs(pdf_list: List[str], output_pdf: str):
    """Merges multiple PDF files into one."""
    from PyPDF2 import PdfWriter, PdfReader

    writer = PdfWriter()
    for pdf_path in pdf_list:
        reader = PdfReader(pdf_path)
        for page in reader.pages:
            writer.add_page(page)

    with open(output_pdf, "wb") as f:
        writer.write(f)
    return output_pdf


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python converter.py <input_file> [output_pdf]")
        sys.exit(1)
    out = convert(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    print(f"✓ Created: {out}")