Office → PDF Converter
Converts DOC, DOCX, PPT, PPTX, XLS, XLSX, ODT, ODP, ODS, RTF, TXT, CSV to PDFwith high fidelity (preserves fonts, layouts, images, tables, formulas).

Why This Preserves Formatting
Format	Engine used	Why high fidelity
Office files	LibreOffice headless	Uses the actual rendering engine that opens the file, exports the result directly to PDF (no re-encoding of layout)
Plain text	ReportLab	Monospace font + line-wrap preservation
This is the same engine used by online services like Smallpdf / ILovePDF (LibreOffice backend).

Quick Start (Local)
1. Install LibreOffice
macOS: brew install --cask libreoffice
Ubuntu: sudo apt install libreoffice
Windows: Download from libreoffice.org
2. Install Python deps
pip install -r requirements.txt
3. Run web app
python app.py# Open http://localhost:5000
4. Or use CLI
# Single filepython convert_cli.py "report.docx"# Whole directorypython convert_cli.py ./docs ./pdfs
Docker (Recommended)
docker build -t office2pdf .docker run -p 5000:5000 office2pdf# Open http://localhost:5000
API Usage
curl -X POST http://localhost:5000/convert \  -F "files=@presentation.pptx" \  -o presentation.pdf
Limitations
Very large PPTX/XLSX with complex charts may take 30–60 s.
Embedded fonts not present on the system will be substituted (install fonts-noto-cjk for Asian text — already in the Docker image).
Conversions are serialized (LibreOffice limitation) — for high concurrency, run multiple containers.
Why This Approach Preserves Original Format
No intermediate re-encoding — LibreOffice opens the document using the same engine that renders it for display, then exports directly to PDF via its native PDF filter (writer_pdf_Export, impress_pdf_Export, calc_pdf_Export).
Same fonts, same layout engine — fonts installed on the system (DejaVu, Liberation, Noto CJK in Docker) match Microsoft's metric-compatible fonts (Calibri → Carlito, Arial → Liberation Sans, Times → Liberation Serif).
Native format support — handles binary .doc, .ppt, .xls (not just the XML-based versions).
Text files use monospace rendering to preserve alignment of code/logs/CSV columns.
Run It Now
bash

# Fastest path
git clone <your-repo> office2pdf && cd office2pdf
docker build -t office2pdf .
docker run -p 5000:5000 office2pdf
# → http://localhost:5000
Drag-drop a .docx, .pptx, .xlsx, or .txt and download a faithful PDF.