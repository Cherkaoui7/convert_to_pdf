"""
Web UI for converting Office files to PDF.
"""
import os
import tempfile
import shutil
from pathlib import Path
from flask import Flask, request, jsonify, send_file, render_template, after_this_request
from converter import convert, SUPPORTED_OFFICE, SUPPORTED_TEXT

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100 MB

ALLOWED = SUPPORTED_OFFICE | SUPPORTED_TEXT


def allowed_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/convert", methods=["POST"])
def convert_route():
    if "files" not in request.files:
        return jsonify({"error": "No files uploaded"}), 400

    # FIX: request.files.getlist instead of request.getlist
    files = request.files.getlist("files")
    if not files or files[0].filename == "":
        return jsonify({"error": "No files selected"}), 400

    workdir = tempfile.mkdtemp(prefix="o2pdf_")
    results = []

    # Register cleanup to happen after the response is sent
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
                results.append({
                    "name": f.filename,
                    "status": "error",
                    "message": "Unsupported file type",
                })
                continue

            # Securely save the file to our temp dir
            src = os.path.join(workdir, f.filename)
            os.makedirs(os.path.dirname(src), exist_ok=True)
            f.save(src)

            try:
                pdf_path = convert(src)
                results.append({
                    "name": f.filename,
                    "status": "ok",
                    "pdf": os.path.basename(pdf_path),
                    "pdf_path": pdf_path,
                })
            except Exception as e:
                results.append({
                    "name": f.filename,
                    "status": "error",
                    "message": str(e),
                })

        ok = [r for r in results if r["status"] == "ok"]
        
        if len(ok) == 0:
            # If everything failed, return the error message
            err_msg = results[0]["message"] if results else "Unknown error"
            return jsonify({"error": err_msg}), 500
            
        elif len(ok) == 1:
            # Single file: send the PDF directly
            return send_file(
                ok[0]["pdf_path"],
                as_attachment=True,
                download_name=Path(ok[0]["name"]).stem + ".pdf",
                mimetype="application/pdf",
            )
        else:
            # Multiple files: zip them up
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