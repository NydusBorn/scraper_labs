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
import sqlite3
import re
from collections import Counter
import plotly.graph_objects as go
import plotly.io as pio

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

# Last organized DB path cached for reuse (charts)
_last_db_path: Optional[Path] = None


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
        if not env.__contains__("INTERMEDIATE_DATASET_DIR") or env["INTERMEDIATE_DATASET_DIR"] is None:
            env["INTERMEDIATE_DATASET_DIR"] = str(intermediate_dir)
            _append_log(f"[server] using INTERMEDIATE_DATASET_DIR={intermediate_dir} for scraper")

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
    
    env = os.environ.copy()
    
    if env.__contains__("INTERMEDIATE_DATASET_DIR") and env["INTERMEDIATE_DATASET_DIR"] is not None:
        payload.input_dir = env["INTERMEDIATE_DATASET_DIR"]
        _append_log(f"[server] using INTERMEDIATE_DATASET_DIR={payload.input_dir} from environment")
    if env.__contains__("REVIEWS_DB") and env["REVIEWS_DB"] is not None:
        payload.output_db = env["REVIEWS_DB"]
        _append_log(f"[server] using REVIEWS_DB={payload.output_db} from environment")
    
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

    global _last_db_path
    _last_db_path = output_db
    return OrganizeResponse(status="ok", output_db=str(output_db))


def _resolve_db_path(db_param: Optional[str]) -> Path:
    env = os.environ.copy()
    if db_param:
        return Path(db_param).expanduser().resolve()
    if _last_db_path is not None:
        return _last_db_path
    if env.get("REVIEWS_DB"):
        return Path(env["REVIEWS_DB"]).expanduser().resolve()
    # Fallback default next to project root
    return Path(__file__).resolve().parents[1] / "data" / "out" / "scraper.db"


def _open_conn(db_path: Path) -> sqlite3.Connection:
    if not db_path.exists():
        raise HTTPException(status_code=400, detail=f"DB not found: {db_path}")
    return sqlite3.connect(str(db_path))


def _tokenize(text: str) -> list[str]:
    if not text:
        return []
    tokens = re.findall(r"[\w\-]+", text.lower(), flags=re.UNICODE)
    # simple filter: drop short tokens
    return [t for t in tokens if len(t) > 2 and not t.isdigit()]


_RU_STOP = {
    # minimal RU stopword set; not exhaustive
    "и","в","во","не","что","он","на","я","с","со","как","а","то","все","она","так","его","но","да","ты","к","у","же","вы","за","бы","по","только","ее","мне","было","вот","от","меня","еще","нет","о","из","ему","теперь","когда","даже","ну","вдруг","ли","если","уже","или","ни","быть","был","него","до","вас","нибудь","опять","уж","вам","ведь","там","потом","себя","ничего","ей","может","они","тут","где","есть","надо","ней","для","мы","тебя","их","чем","была","сам","чтоб","без","будто","чего","раз","тоже","себе","под","будет","ж","тогда","кто","этот","того","потому","этого","какой","совсем","ним","здесь","этом","один","почти","мой","тем","чтобы","нее","кажется","сейчас","были","куда","зачем","всех","никогда","можно","при","наконец","два","об","другой","хоть","после","над","больше","тот","через","эти","нас","про","всего","них","какая","много","разве","три","эту","моя","впрочем","хорошо","свою","этой","перед","иногда","лучше","чуть","том","нельзя","такой","им","более","всегда","конечно","всю","между"
}

# Lazy NLP components
_nlp_loaded = False
_segmenter = None
_morph_vocab = None
_morph_tagger = None
_ru_stopwords = None


def _ensure_nlp():
    global _nlp_loaded, _segmenter, _morph_vocab, _morph_tagger, _ru_stopwords
    if _nlp_loaded:
        return
    try:
        import natasha as nlp
        _segmenter = nlp.Segmenter()
        _morph_vocab = nlp.MorphVocab()
        emb = nlp.NewsEmbedding()
        _morph_tagger = nlp.NewsMorphTagger(emb)
    except Exception as e:
        _append_log(f"[server] natasha load failed: {e}")
        _segmenter = _morph_vocab = _morph_tagger = None
    # Stopwords via NLTK with fallback
    try:
        import nltk
        from nltk.corpus import stopwords
        try:
            _ru_stopwords = set(stopwords.words('russian'))
        except LookupError:
            nltk.download('stopwords', quiet=True)
            _ru_stopwords = set(stopwords.words('russian'))
    except Exception as e:
        _append_log(f"[server] nltk stopwords failed: {e}")
        _ru_stopwords = set(_RU_STOP)
    _nlp_loaded = True


def _preprocess_text_natasha(text: str) -> list[str]:
    """Lemmatize Russian text using natasha, filter stopwords/punct/numbers.
    Falls back to simple regex tokenization if natasha unavailable.
    """
    if not text:
        return []
    _ensure_nlp()
    import string
    tokens = re.findall(r"[\w\-]+", text.lower(), flags=re.UNICODE)
    if _segmenter is not None and _morph_tagger is not None and _morph_vocab is not None:
        try:
            import natasha as nlp
            doc = nlp.Doc(" ".join(tokens))
            doc.segment(_segmenter)
            doc.tag_morph(_morph_tagger)
            for t in list(getattr(doc, 'tokens', []) or []):
                t.lemmatize(_morph_vocab)
            lemmas = [t.lemma for t in list(getattr(doc, 'tokens', []) or [])]
        except Exception as e:
            _append_log(f"[server] natasha processing failed, fallback: {e}")
            lemmas = tokens
    else:
        lemmas = tokens
    # Filters
    punct = set(string.punctuation).union({"«","»","—","–","...","``","''","`","'","„","“","”"})
    sw = _ru_stopwords or set(_RU_STOP)
    result = []
    for lemma in lemmas:
        if not lemma or lemma in sw:
            continue
        if lemma.isdigit() or len(lemma) <= 2:
            continue
        if lemma in punct:
            continue
        result.append(lemma)
    return result


def _build_bar_figure(labels: list[str], values: list[float], title: str = "Histogram", orientation: str = "v"):
    if orientation == "h":
        bar = go.Bar(x=values, y=labels, orientation='h')
        layout = go.Layout(title=title, xaxis_title="Count", yaxis_title="")
    else:
        bar = go.Bar(x=labels, y=values)
        layout = go.Layout(title=title, xaxis_title="", yaxis_title="Count")
    fig = go.Figure(data=[bar], layout=layout)
    return fig


@app.get("/charts/histogram")
def get_histogram(kind: str, db: Optional[str] = None, text_field: str = "review_descr", bins: int = 20, top_n: int = 30, fmt: str = "json"): 
    """
    Return histogram data for the specified kind.
    kind: one of [token_count, stars, likes, comments, year_usage, word_freq]
    Returns: { labels: [..], values: [..], kind: str, field?: str }
    """
    db_path = _resolve_db_path(db)
    try:
        conn = _open_conn(db_path)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    try:
        cur = conn.cursor()
        if kind in ("stars", "likes", "comments", "year_usage"):
            # numeric histogram with simple binning
            cur.execute(f"SELECT {kind} FROM reviews WHERE {kind} IS NOT NULL")
            vals = [row[0] for row in cur.fetchall() if isinstance(row[0], (int, float))]
            if not vals:
                return {"labels": [], "values": [], "kind": kind}
            mn, mx = min(vals), max(vals)
            if bins < 1:
                bins = 10
            if mn == mx:
                labels = [str(mn)]
                return {"labels": labels, "values": [len(vals)], "kind": kind}
            width = (mx - mn) / bins
            # Avoid zero width
            width = width or 1
            edges = [mn + i * width for i in range(bins)] + [mx]
            counts = [0] * bins
            for v in vals:
                # find bin index
                idx = int((v - mn) / width)
                if idx >= bins:
                    idx = bins - 1
                counts[idx] += 1
            labels = [f"{round(edges[i],2)}–{round(edges[i+1],2)}" for i in range(bins)]
            if fmt == "plotly":
                fig = _build_bar_figure(labels, counts, title=kind.replace('_',' ').title())
                return {"figure": fig.to_plotly_json(), "kind": kind}
            return {"labels": labels, "values": counts, "kind": kind}
        elif kind == "token_count": 
            # per-row token count of selected text field
            if text_field not in ("review_descr", "title"):
                text_field = "review_descr"
            cur.execute(f"SELECT {text_field} FROM reviews WHERE {text_field} IS NOT NULL")
            counts = Counter()
            for (txt,) in cur.fetchall():
                n = len(_tokenize(txt))
                counts[n] += 1
            # Sort by token count ascending
            items = sorted(counts.items(), key=lambda x: x[0])
            labels = [str(k) for k, _ in items]
            values = [v for _, v in items]
            if fmt == "plotly":
                fig = _build_bar_figure(labels, values, title=f"Token Count ({text_field})")
                return {"figure": fig.to_plotly_json(), "kind": kind, "field": text_field}
            return {"labels": labels, "values": values, "kind": kind, "field": text_field}
        elif kind == "word_freq":
            if text_field not in ("review_descr", "title"):
                text_field = "review_descr"
            cur.execute(f"SELECT {text_field} FROM reviews WHERE {text_field} IS NOT NULL")
            freq = Counter()
            for (txt,) in cur.fetchall():
                for lemma in _preprocess_text_natasha(txt):
                    freq[lemma] += 1
            items = freq.most_common(max(1, min(200, top_n)))
            labels = [k for k, _ in items]
            values = [v for _, v in items]
            if fmt == "plotly":
                fig = _build_bar_figure(labels, values, title=f"Word Frequency ({text_field})", orientation="h")
                return {"figure": fig.to_plotly_json(), "kind": kind, "field": text_field}
            return {"labels": labels, "values": values, "kind": kind, "field": text_field}
        else:
            raise HTTPException(status_code=400, detail=f"Unknown histogram kind: {kind}")
    finally:
        try:
            conn.close()
        except Exception:
            pass


@app.get("/")
def root():
    return {"status": "ok", "message": "Scraper server is running"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, port=11001, host="0.0.0.0", reload=False, log_level="warning")
