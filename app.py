"""
Web UI for converting Office files to PDF.
"""
import os
import tempfile
import shutil
from pathlib import Path
from flask import Flask, request, jsonify, send_file, render_template, after_this_request
from converter import (
    convert, SUPPORTED_OFFICE, SUPPORTED_TEXT, SUPPORTED_IMAGES, 
    watermark_pdf, merge_pdfs
)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100 MB

ALLOWED = SUPPORTED_OFFICE | SUPPORTED_TEXT | SUPPORTED_IMAGES

def allowed_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/convert", methods=["POST"])
def convert_route():
    if "files" not in request.files:
        return jsonify({"error": "No files uploaded"}), 400

    files = request.files.getlist("files")
    if not files or files[0].filename == "":
        return jsonify({"error": "No files selected"}), 400

    # Get options from frontend
    merge_option = request.form.get("merge") == "true"
    watermark_text = request.form.get("watermark", "").strip()

    workdir = tempfile.mkdtemp(prefix="o2pdf_")
    results = []

    @after_this_request
    def cleanup(response):
        try:
            shutil.rmtree(workdir, ignore_errors=True)
        except Exception:
            pass
        return response

    try:
        for f in files:
            if not allowed_file(f.filename):
                results.append({"name": f.filename, "status": "error", "message": "Unsupported file type"})
                continue

            src = os.path.join(workdir, f.filename)
            os.makedirs(os.path.dirname(src), exist_ok=True)
            f.save(src)

            try:
                pdf_path = convert(src)
                # Apply watermark if provided
                if watermark_text:
                    wm_path = pdf_path.replace(".pdf", "_wm.pdf")
                    watermark_pdf(pdf_path, wm_path, watermark_text)
                    pdf_path = wm_path

                results.append({"name": f.filename, "status": "ok", "pdf_path": pdf_path})
            except Exception as e:
                results.append({"name": f.filename, "status": "error", "message": str(e)})

        ok = [r for r in results if r["status"] == "ok"]
        
        if len(ok) == 0:
            err_msg = results[0]["message"] if results else "Unknown error"
            return jsonify({"error": err_msg}), 500
            
        elif len(ok) == 1:
            return send_file(
                ok[0]["pdf_path"],
                as_attachment=True,
                download_name=Path(ok[0]["name"]).stem + ".pdf",
                mimetype="application/pdf",
            )
        else:
            # Multiple files
            if merge_option:
                # Merge into one PDF
                merged_path = os.path.join(workdir, "merged.pdf")
                pdf_paths = [r["pdf_path"] for r in ok]
                merge_pdfs(pdf_paths, merged_path)
                return send_file(
                    merged_path,
                    as_attachment=True,
                    download_name="converted_merged.pdf",
                    mimetype="application/pdf",
                )
            else:
                # Zip them up
                import zipfile
                zip_path = os.path.join(workdir, "converted.zip")
                with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
                    for r in ok:
                        arcname = Path(r["name"]).stem + ".pdf"
                        z.write(r["pdf_path"], arcname)
                return send_file(
                    zip_path,
                    as_attachment=True,
                    download_name="converted_pdfs.zip",
                    mimetype="application/zip",
                )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)