from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import time
from collections import deque
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# --- Logging buffer capturing ---
# We maintain a global ring buffer with recent stdout/stderr lines from both the
# server and any background scraper subprocess we start.
LOG_BUFFER_MAX_LINES = 2000
_log_buffer = deque(maxlen=LOG_BUFFER_MAX_LINES)
_log_lock = threading.Lock()


def _append_log(line: str) -> None:
    with _log_lock:
        _log_buffer.append(line.rstrip("\n"))


# Mirror the server's own stdout prints into the buffer
class _StdoutInterceptor:
    def __init__(self, original_stream):
        self.original_stream = original_stream
        self.lock = threading.Lock()

    def write(self, data):
        with self.lock:
            try:
                text = str(data)
            except Exception:
                text = repr(data)
            if text:
                for line in text.splitlines():
                    _append_log(line)
            return self.original_stream.write(data)

    def flush(self):
        with self.lock:
            return self.original_stream.flush()

    def isatty(self):
        """Check if the stream is a TTY."""
        return self.original_stream.isatty() if hasattr(self.original_stream, 'isatty') else False

    def fileno(self):
        """Return the file descriptor if available."""
        return self.original_stream.fileno() if hasattr(self.original_stream, 'fileno') else -1

    def __getattr__(self, name):
        """Proxy any other attributes to the original stream."""
        return getattr(self.original_stream, name)


# Install interceptors once on import
if not isinstance(sys.stdout, _StdoutInterceptor):
    sys.stdout = _StdoutInterceptor(sys.stdout)  # type: ignore
if not isinstance(sys.stderr, _StdoutInterceptor):
    sys.stderr = _StdoutInterceptor(sys.stderr)  # type: ignore


# --- Scraper process management ---
_scraper_proc: Optional[subprocess.Popen] = None
_scraper_reader_thread: Optional[threading.Thread] = None
_scraper_lock = threading.Lock()


def _reader_target(pipe, proc_desc: str):
    try:
        for raw in iter(pipe.readline, ""):
            if not raw:
                break
            _append_log(f"[{proc_desc}] {raw.rstrip()}" )
    except Exception as e:
        _append_log(f"[server] log reader error: {e}")
    finally:
        try:
            pipe.close()
        except Exception:
            pass


# --- FastAPI app ---
app = FastAPI(title="Scraper Server", version="1.0.0")

app.add_middleware(
CORSMiddleware,
allow_origins=["http://localhost:3000"], # Specify allowed origins
allow_credentials=True,
allow_methods=["*"], # Allow all HTTP methods, including OPTIONS
allow_headers=["*"], # Allow all headers
)


class StartScrapingRequest(BaseModel):
    intermediate_dir: str = Field(..., description="Directory path for intermediate dataset (JSON files will be written here)")


class StartScrapingResponse(BaseModel):
    status: str
    pid: Optional[int] = None
    message: Optional[str] = None


class StopScrapingResponse(BaseModel):
    status: str
    message: Optional[str] = None


class OrganizeRequest(BaseModel):
    input_dir: str = Field(..., description="Path to intermediate dataset directory (with JSON files)")
    output_db: str = Field(..., description="Path to output SQLite database file to create")


class OrganizeResponse(BaseModel):
    status: str
    output_db: Optional[str] = None
    message: Optional[str] = None


@app.get("/stdout")
def get_stdout(lines: int = 30):
    """Return the last N lines from the combined stdout/stderr buffer.

    Query params:
    - lines: number of lines to return (default 30, max 2000)
    """
    n = max(0, min(lines, LOG_BUFFER_MAX_LINES))
    with _log_lock:
        data = list(_log_buffer)[-n:]
    return {"stdout": data}


@app.post("/start-scraping", response_model=StartScrapingResponse)
def start_scraping(payload: StartScrapingRequest):
    global _scraper_proc, _scraper_reader_thread

    intermediate_dir = Path(payload.intermediate_dir).expanduser().resolve()
    intermediate_dir.mkdir(parents=True, exist_ok=True)

    with _scraper_lock:
        if _scraper_proc and _scraper_proc.poll() is None:
            return StartScrapingResponse(status="already_running", pid=_scraper_proc.pid)

        # Build environment with target dataset directory for the spider
        env = os.environ.copy()
        env["INTERMEDIATE_DATASET_DIR"] = str(intermediate_dir)

        # Launch the downloader as a subprocess, capturing stdout+stderr
        cmd = [sys.executable, str(Path(__file__).resolve().parents[1] / "L1" / "download_reviews.py")]
        _append_log(f"[server] starting scraper: {' '.join(cmd)} with INTERMEDIATE_DATASET_DIR={intermediate_dir}")
        proc = subprocess.Popen(
            cmd,
            cwd=str(Path(__file__).resolve().parents[1]),  # project root
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        _scraper_proc = proc

        # Start reader thread
        if proc.stdout is not None:
            t = threading.Thread(target=_reader_target, args=(proc.stdout, "scraper"), daemon=True)
            t.start()
            _scraper_reader_thread = t
        else:
            _scraper_reader_thread = None

        return StartScrapingResponse(status="started", pid=proc.pid)


@app.post("/stop-scraping", response_model=StopScrapingResponse)
def stop_scraping():
    global _scraper_proc

    with _scraper_lock:
        if _scraper_proc is None or _scraper_proc.poll() is not None:
            return StopScrapingResponse(status="not_running", message="No active scraper process")

        proc = _scraper_proc
        _append_log(f"[server] stopping scraper pid={proc.pid}")
        try:
            proc.terminate()
        except Exception as e:
            _append_log(f"[server] terminate error: {e}")
        
        # Wait up to 10 seconds, then kill
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            _append_log(f"[server] scraper did not exit, sending SIGKILL")
            try:
                proc.kill()
            except Exception as e:
                _append_log(f"[server] kill error: {e}")
            try:
                proc.wait(timeout=5)
            except Exception:
                pass

        status = "stopped"
        if proc.poll() is None:
            status = "failed_to_stop"
        _scraper_proc = None
        return StopScrapingResponse(status=status)


@app.post("/organize", response_model=OrganizeResponse)
def organize(payload: OrganizeRequest):
    # Defer import to avoid loading scraper deps for this endpoint
    try:
        from L2.organize_dataset import organize as organize_fn
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to import organizer: {e}")

    input_dir = Path(payload.input_dir).expanduser().resolve()
    output_db = Path(payload.output_db).expanduser().resolve()

    if not input_dir.exists() or not input_dir.is_dir():
        raise HTTPException(status_code=400, detail=f"input_dir does not exist or is not a directory: {input_dir}")

    # Ensure parent dir for DB exists
    output_db.parent.mkdir(parents=True, exist_ok=True)

    # Run organize synchronously; it creates/replaces the DB
    _append_log(f"[server] organizing dataset from {input_dir} into {output_db}")
    try:
        organize_fn(str(input_dir), str(output_db))
    except Exception as e:
        _append_log(f"[server] organize failed: {e}")
        raise HTTPException(status_code=500, detail=f"organize failed: {e}")

    return OrganizeResponse(status="ok", output_db=str(output_db))


@app.get("/")
def root():
    return {"status": "ok", "message": "Scraper server is running"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, port=11001, reload=False, log_level="debug")
