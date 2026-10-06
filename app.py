"""Provenance Guard classroom API. Scores are indicators, not proof of authorship."""

import hashlib
import json
import os
import re
import sqlite3
import statistics
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_file
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

load_dotenv()

LABELS = {
    "likely_ai": "This writing shows strong indicators of AI generation. This assessment is not proof of authorship. The creator can appeal.",
    "likely_human": "This writing shows strong indicators of human authorship. This assessment is not proof of authorship.",
    "uncertain": "We cannot reliably determine how this writing was created. No authorship claim is made.",
}
PHRASES = (
    "it is important to note", "furthermore", "moreover", "in conclusion",
    "transformative", "paradigm shift", "stakeholders", "in today's world",
    "delve into", "multifaceted", "crucial", "comprehensive",
)
WORD_RE = re.compile(r"\b[\w']+\b", re.UNICODE)


def clamp(value):
    return max(0.0, min(1.0, value))


def structural_signal(text):
    sentences = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
    lengths = [len(WORD_RE.findall(s)) for s in sentences]
    if len(lengths) < 3:
        return 0.5
    mean = statistics.mean(lengths)
    cv = statistics.pstdev(lengths) / mean if mean else 0
    uniformity = 1 - clamp(cv / 0.8)
    starts = [WORD_RE.findall(s.lower())[0] for s in sentences if WORD_RE.findall(s)]
    repeated_starts = 1 - len(set(starts)) / len(starts) if starts else 0
    punctuation = len(set(c for c in text if c in ",;:!?—-()"))
    low_variety = 1 - clamp(punctuation / 6)
    return round(clamp(0.65 * uniformity + 0.2 * repeated_starts + 0.15 * low_variety), 4)


def formulaic_signal(text):
    lower = text.lower()
    words = WORD_RE.findall(lower)
    if not words:
        return 0.0
    hits = sum(lower.count(phrase) for phrase in PHRASES)
    return round(clamp(hits / max(1, len(words) / 70) / 3), 4)


def groq_signal(text):
    if not os.getenv("GROQ_API_KEY"):
        return None, "not_configured"
    try:
        from groq import Groq

        response = Groq().chat.completions.create(
            model=os.getenv("GROQ_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct"),
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "Assess AI-like writing style only. This cannot establish authorship. Return only JSON with numeric ai_likeness between 0 and 1."},
                {"role": "user", "content": text},
            ],
        )
        score = float(json.loads(response.choices[0].message.content)["ai_likeness"])
        if not 0 <= score <= 1:
            raise ValueError("score outside range")
        return round(score, 4), None
    except Exception as exc:
        return None, type(exc).__name__


def classify(text, semantic=None, semantic_error=None):
    words = WORD_RE.findall(text)
    structural = structural_signal(text)
    formulaic = formulaic_signal(text)
    signals = {"structural": structural, "formulaic": formulaic}
    if semantic is None:
        weights = {"structural": 0.55, "formulaic": 0.45}
    else:
        signals["groq_semantic"] = semantic
        weights = {"structural": 0.25, "formulaic": 0.20, "groq_semantic": 0.55}
    score = round(sum(signals[k] * weights[k] for k in weights), 4)
    disagreement = max(signals.values()) - min(signals.values()) > 0.55
    if len(words) < 80 or disagreement:
        attribution = "uncertain"
    elif score >= 0.85:
        attribution = "likely_ai"
    elif score <= 0.30:
        attribution = "likely_human"
    else:
        attribution = "uncertain"
    confidence = (score if attribution == "likely_ai" else
                  1 - score if attribution == "likely_human" else
                  1 - 2 * abs(score - 0.5))
    return {
        "attribution": attribution,
        "confidence": round(clamp(confidence), 4),
        "ai_likeness_score": score,
        "label": LABELS[attribution],
        "signals": signals,
        "weights": weights,
        "word_count": len(words),
        "uncertainty_reasons": (["short_text"] if len(words) < 80 else []) + (["signal_disagreement"] if disagreement else []),
        "semantic_signal_status": semantic_error or "available",
    }


def now():
    return datetime.now(timezone.utc).isoformat()


def create_app(config=None):
    app = Flask(__name__)
    app.config.update(DATABASE=os.getenv("DATABASE_PATH", "provenance.db"), TESTING=False)
    if config:
        app.config.update(config)
    limiter = Limiter(get_remote_address, app=app, default_limits=[], storage_uri="memory://")

    def connection():
        db = sqlite3.connect(app.config["DATABASE"])
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        return db

    with closing(connection()) as db, db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS content (
              content_id TEXT PRIMARY KEY, creator_id TEXT NOT NULL, text_sha256 TEXT NOT NULL,
              created_at TEXT NOT NULL, status TEXT NOT NULL, attribution TEXT NOT NULL,
              confidence REAL NOT NULL, ai_likeness_score REAL NOT NULL,
              label TEXT NOT NULL, signals_json TEXT NOT NULL, weights_json TEXT NOT NULL,
              word_count INTEGER NOT NULL, uncertainty_reasons_json TEXT NOT NULL,
              semantic_signal_status TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS appeals (
              appeal_id TEXT PRIMARY KEY, content_id TEXT NOT NULL UNIQUE REFERENCES content(content_id),
              creator_reasoning TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audit (
              event_id TEXT PRIMARY KEY, content_id TEXT NOT NULL REFERENCES content(content_id),
              event_type TEXT NOT NULL, timestamp TEXT NOT NULL, details_json TEXT NOT NULL
            );
        """)

    @app.post("/submit")
    @limiter.limit("10 per minute;100 per day")
    def submit():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify(error="Expected a JSON object."), 400
        text = payload.get("text")
        creator = payload.get("creator_id")
        if not isinstance(text, str) or not 1 <= len(text.strip()) <= 20000:
            return jsonify(error="text must contain 1–20,000 characters."), 400
        if not isinstance(creator, str) or not 1 <= len(creator.strip()) <= 100:
            return jsonify(error="creator_id must contain 1–100 characters."), 400
        text, creator = text.strip(), creator.strip()
        semantic, error = groq_signal(text)
        result = classify(text, semantic, error)
        content_id, timestamp = str(uuid.uuid4()), now()
        with closing(connection()) as db, db:
            db.execute("""INSERT INTO content VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
                content_id, creator, hashlib.sha256(text.encode()).hexdigest(), timestamp,
                "classified", result["attribution"], result["confidence"], result["ai_likeness_score"],
                result["label"], json.dumps(result["signals"]), json.dumps(result["weights"]),
                result["word_count"], json.dumps(result["uncertainty_reasons"]), result["semantic_signal_status"],
            ))
            db.execute("INSERT INTO audit VALUES (?,?,?,?,?)", (
                str(uuid.uuid4()), content_id, "decision", timestamp,
                json.dumps({"creator_id": creator, "attribution": result["attribution"],
                            "confidence": result["confidence"], "ai_likeness_score": result["ai_likeness_score"],
                            "signals": result["signals"], "status": "classified"}),
            ))
        return jsonify(content_id=content_id, creator_id=creator, timestamp=timestamp,
                       status="classified", **result), 201

    @app.post("/appeal")
    def appeal():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify(error="Expected a JSON object."), 400
        content_id, creator, reasoning = (payload.get(k) for k in
                                          ("content_id", "creator_id", "creator_reasoning"))
        if not isinstance(content_id, str) or not isinstance(creator, str) or not isinstance(reasoning, str) or not 10 <= len(reasoning.strip()) <= 2000:
            return jsonify(error="Provide content_id, creator_id, and creator_reasoning of 10–2,000 characters."), 400
        with closing(connection()) as db, db:
            row = db.execute("SELECT creator_id,status FROM content WHERE content_id=?", (content_id,)).fetchone()
            if row is None:
                return jsonify(error="Content not found."), 404
            if row["creator_id"] != creator:
                return jsonify(error="creator_id does not match the submission."), 403
            if row["status"] != "classified":
                return jsonify(error="An appeal is already under review."), 409
            appeal_id, timestamp = str(uuid.uuid4()), now()
            db.execute("UPDATE content SET status='under_review' WHERE content_id=?", (content_id,))
            db.execute("INSERT INTO appeals VALUES (?,?,?,?)", (appeal_id, content_id, reasoning.strip(), timestamp))
            db.execute("INSERT INTO audit VALUES (?,?,?,?,?)", (
                str(uuid.uuid4()), content_id, "appeal", timestamp,
                json.dumps({"creator_id": creator, "appeal_id": appeal_id,
                            "appeal_reasoning": reasoning.strip(), "status": "under_review"}),
            ))
        return jsonify(appeal_id=appeal_id, content_id=content_id, status="under_review", timestamp=timestamp), 201

    @app.get("/content/<content_id>")
    def content(content_id):
        with closing(connection()) as db, db:
            row = db.execute("SELECT * FROM content WHERE content_id=?", (content_id,)).fetchone()
            if row is None:
                return jsonify(error="Content not found."), 404
            data = dict(row)
            data["signals"] = json.loads(data.pop("signals_json"))
            data["weights"] = json.loads(data.pop("weights_json"))
            data["uncertainty_reasons"] = json.loads(data.pop("uncertainty_reasons_json"))
            return jsonify(data)

    @app.get("/log")
    def log():
        try:
            limit = int(request.args.get("limit", 20))
        except ValueError:
            return jsonify(error="limit must be an integer."), 400
        if not 1 <= limit <= 100:
            return jsonify(error="limit must be between 1 and 100."), 400
        with closing(connection()) as db, db:
            rows = db.execute("SELECT * FROM audit ORDER BY timestamp DESC, rowid DESC LIMIT ?", (limit,)).fetchall()
        return jsonify(entries=[{k: row[k] for k in ("event_id", "content_id", "event_type", "timestamp")}
                                | {"details": json.loads(row["details_json"])} for row in rows])

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    @app.get("/demo")
    def demo_page():
        return send_file(Path(__file__).with_name("demo_ui.html"))

    return app


if __name__ == "__main__":
    create_app().run(debug=False)
