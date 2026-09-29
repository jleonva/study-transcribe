from __future__ import annotations
import json, os, re, sys
from pathlib import Path
from flask import Flask, Response, jsonify, render_template, request, send_file

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = Path.home() / "Documents" / "StudyTranscriptions"
sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(Path(__file__).resolve().parent))
from jobs import JobManager  # noqa: E402

app = Flask(__name__, template_folder="templates", static_folder="static")
try:
    manager = JobManager(ROOT, DEFAULT_OUTPUT)
except PermissionError:
    # Keep the documented default where possible, but allow restricted Windows
    # profiles and service accounts to start the UI.
    manager = JobManager(ROOT, ROOT / "outputs")
    DEFAULT_OUTPUT = ROOT / "outputs"

def body() -> dict:
    data = request.get_json(silent=True)
    if not isinstance(data, dict): raise ValueError("JSON object required")
    return data

@app.errorhandler(ValueError)
def value_error(exc): return jsonify(error=str(exc)), 400

@app.get("/")
def index(): return render_template("index.html", default_output=str(DEFAULT_OUTPUT))

@app.post("/api/scan-folder")
def scan_folder():
    folder = Path(body().get("folder", "")).expanduser().resolve()
    if not folder.is_dir(): raise ValueError("folder does not exist")
    files = [{"name": p.name, "path": str(p), "size": p.stat().st_size} for p in sorted(folder.iterdir(), key=lambda x: x.name.lower()) if p.is_file() and p.suffix.lower() == ".pdf"]
    return jsonify(folder=str(folder), files=files)

@app.get("/api/pdf/toc")
def pdf_toc():
    pdf, folder = Path(request.args.get("path", "")).resolve(), Path(request.args.get("folder", "")).resolve()
    try: pdf.relative_to(folder)
    except ValueError as exc: raise ValueError("PDF is outside the selected folder") from exc
    import pymupdf
    doc = pymupdf.open(pdf)
    return jsonify(path=str(pdf), page_count=doc.page_count, toc=[{"level": l, "title": t, "page": p} for l, t, p in doc.get_toc()])

@app.post("/api/jobs")
def create_job():
    data = body(); return jsonify(manager.create(data, Path(data.get("input_root", "")).resolve(), Path(data.get("output_root") or DEFAULT_OUTPUT).expanduser().resolve())), 201

@app.get("/api/jobs")
def list_jobs(): return jsonify(list(manager.jobs.values()))

@app.post("/api/jobs/start")
def start_jobs(): manager.start(); return jsonify(started=True)

@app.get("/api/jobs/<job_id>/events")
def events(job_id: str):
    if job_id not in manager.jobs: raise ValueError("unknown job")
    history, q = manager.subscribe(job_id)
    def stream():
        try:
            for event in history: yield f"data: {json.dumps(event)}\n\n"
            while True:
                event = q.get(); yield f"data: {json.dumps(event)}\n\n"
                if event["kind"] in {"completed", "failed"}: break
        finally: manager.unsubscribe(job_id, q)
    return Response(stream(), mimetype="text/event-stream")

def result_dir(job: dict) -> Path:
    # Discover the exact output from the manifest rather than reimplementing
    # run.py's Unicode slugification rules.
    for manifest in Path(job["output_root"]).rglob("manifest.json"):
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            if data.get("source_pdf") == job["source_pdf"]:
                return manifest.parent
        except (OSError, json.JSONDecodeError):
            continue
    raise ValueError("job output is not available yet")

@app.get("/api/jobs/<job_id>/manifest")
def manifest(job_id: str):
    job = manager.jobs.get(job_id)
    if not job: raise ValueError("unknown job")
    files = list(result_dir(job).glob("manifest.json")); return jsonify(json.loads(files[0].read_text(encoding="utf-8")) if files else {})

@app.get("/api/jobs/<job_id>/markdown")
def markdown(job_id: str):
    job = manager.jobs.get(job_id)
    if not job: raise ValueError("unknown job")
    files = list(result_dir(job).glob("*.md")); return jsonify(markdown=files[0].read_text(encoding="utf-8") if files else "")

def safe_output(job: dict, path: Path) -> Path:
    root, candidate = Path(job["output_root"]).resolve(), path.resolve()
    try: candidate.relative_to(root)
    except ValueError as exc: raise ValueError("asset is outside the job output") from exc
    return candidate

@app.get("/api/jobs/<job_id>/assets/<path:name>")
def asset(job_id: str, name: str):
    job = manager.jobs.get(job_id)
    if not job: raise ValueError("unknown job")
    return send_file(safe_output(job, Path(job["output_root"]) / name))

@app.post("/api/jobs/<job_id>/placeholder")
def placeholder(job_id: str):
    job = manager.jobs.get(job_id)
    if not job: raise ValueError("unknown job")
    data = body(); old, replacement = str(data.get("image_ref", "")), str(data.get("replacement", "")).strip()
    if not old or not replacement: raise ValueError("image_ref and replacement are required")
    md_path = next(result_dir(job).glob("*.md"), None)
    if not md_path: raise ValueError("Markdown output is not available")
    text = md_path.read_text(encoding="utf-8")
    actual = old
    if text.count(actual) != 1:
        # The manifest stores absolute staging paths while Markdown stores a
        # relative image URL. Resolve that difference by matching the basename.
        basename = re.escape(Path(old).name)
        matches = re.findall(r"!\[[^\]]*\]\([^)]*" + basename + r"\)", text)
        if len(matches) == 1: actual = matches[0]
    if text.count(actual) != 1: raise ValueError("image reference must occur exactly once")
    md_path.write_text(text.replace(actual, replacement), encoding="utf-8"); return jsonify(saved=True)

@app.post("/api/jobs/<job_id>/finalize")
def finalize(job_id: str):
    job = manager.jobs.get(job_id)
    if not job: raise ValueError("unknown job")
    import subprocess
    subprocess.run([sys.executable, str(ROOT / "scripts" / "finalize.py"), str(result_dir(job))], check=True, capture_output=True, text=True)
    return jsonify(finalized=True)

if __name__ == "__main__": app.run(host="127.0.0.1", port=int(os.environ.get("STUDY_TRANSCRIBE_PORT", "5000")), debug=False)
