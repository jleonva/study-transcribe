from __future__ import annotations

import json
import queue
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobManager:
    """Persistent, sequential job queue around scripts/run.py."""
    def __init__(self, repo_root: Path, state_root: Path):
        self.repo_root = repo_root.resolve(); self.state_root = state_root.resolve()
        self.state_root.mkdir(parents=True, exist_ok=True)
        self.state_path = self.state_root / ".study-transcribe-jobs.json"
        self._lock = threading.RLock(); self._running = False
        self._events: dict[str, list[dict]] = {}; self._event_queues: dict[str, list[queue.Queue]] = {}
        self.jobs: dict[str, dict] = self._load()

    def _load(self) -> dict[str, dict]:
        if not self.state_path.exists(): return {}
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            for job in data.values():
                if job.get("status") == "running":
                    job["status"] = "failed"; job["error"] = "The server stopped while this job was running."
            return data
        except (OSError, json.JSONDecodeError): return {}

    def _save(self) -> None:
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.jobs, ensure_ascii=False, indent=2), encoding="utf-8"); tmp.replace(self.state_path)

    def _emit(self, job_id: str, kind: str, message: str) -> None:
        event = {"kind": kind, "message": message, "at": now()}; self._events.setdefault(job_id, []).append(event)
        for q in self._event_queues.get(job_id, []): q.put(event)

    def subscribe(self, job_id: str):
        q: queue.Queue = queue.Queue()
        with self._lock:
            history = list(self._events.get(job_id, [])); self._event_queues.setdefault(job_id, []).append(q)
        return history, q

    def unsubscribe(self, job_id: str, q: queue.Queue) -> None:
        with self._lock:
            if q in self._event_queues.get(job_id, []): self._event_queues[job_id].remove(q)

    @staticmethod
    def _inside(path: Path, root: Path) -> Path:
        candidate = path.resolve()
        try: candidate.relative_to(root.resolve())
        except ValueError as exc: raise ValueError("path is outside the selected folder") from exc
        return candidate

    def create(self, payload: dict, input_root: Path, output_root: Path) -> dict:
        source = self._inside(Path(payload.get("source_pdf", "")), input_root)
        if source.suffix.lower() != ".pdf" or not source.is_file(): raise ValueError("source_pdf must be an existing PDF inside the selected folder")
        selection = payload.get("selection_type", "pages")
        if selection not in {"pages", "chapter"}: raise ValueError("selection_type must be pages or chapter")
        if selection == "pages":
            start, end = int(payload.get("page_start", 0)), int(payload.get("page_end", 0))
            if start < 1 or end < start: raise ValueError("page_start/page_end must be a valid inclusive range")
        elif not str(payload.get("chapter_query", "")).strip(): raise ValueError("chapter_query is required for chapter selection")
        out = output_root.resolve(); out.mkdir(parents=True, exist_ok=True); job_id = uuid.uuid4().hex[:12]
        job = {"id": job_id, "source_pdf": str(source), "output_root": str(out), "selection_type": selection,
               "chapter_query": payload.get("chapter_query", ""), "page_start": payload.get("page_start"), "page_end": payload.get("page_end"),
               "options": {k: bool(payload.get(k, False)) for k in ("no_formula_ocr", "force_scanned", "allow_scanned", "prose")},
               "status": "queued", "created_at": now(), "error": None}
        with self._lock: self.jobs[job_id] = job; self._save()
        return job

    def start(self) -> None:
        with self._lock:
            if self._running: return
            self._running = True
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self) -> None:
        try:
            while True:
                with self._lock:
                    job = next((j for j in self.jobs.values() if j["status"] == "queued"), None)
                    if not job: return
                    job["status"] = "running"; job["started_at"] = now(); self._save()
                self._run_one(job)
        finally:
            with self._lock: self._running = False

    def _run_one(self, job: dict) -> None:
        args = [sys.executable, str(self.repo_root / "scripts" / "run.py"), job["source_pdf"], "-o", job["output_root"]]
        args += (["--chapter", job["chapter_query"]] if job["selection_type"] == "chapter" else ["--pages", f"{job['page_start']}-{job['page_end']}"])
        for option, enabled in job["options"].items():
            if enabled: args.append("--" + option.replace("_", "-"))
        self._emit(job["id"], "started", "Running transcription pipeline")
        try:
            proc = subprocess.Popen(args, cwd=self.repo_root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", bufsize=1)
            assert proc.stdout is not None
            for line in proc.stdout: self._emit(job["id"], "log", line.rstrip())
            code = proc.wait()
            with self._lock:
                job["status"] = "completed" if code == 0 else "failed"; job["finished_at"] = now()
                if code: job["error"] = f"Transcription exited with code {code}."
                self._save()
            self._emit(job["id"], job["status"], job.get("error") or "Job completed")
        except Exception as exc:
            with self._lock:
                job["status"] = "failed"; job["finished_at"] = now(); job["error"] = str(exc); self._save()
            self._emit(job["id"], "failed", str(exc))
