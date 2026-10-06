# Provenance Guard

Provenance Guard is a Flask API for giving readers cautious context about the apparent origin of submitted writing. It combines independent writing signals, returns a confidence index and a plain-language label, and lets the submitting creator appeal. It does **not** prove authorship.

The design decisions and flow diagram were written first in [planning.md](planning.md). A submission passes through validation, structural and formulaic signals, optional Groq assessment, weighted scoring, label selection, SQLite storage, and an audit event before a JSON response. An appeal links to that content, marks it `under_review`, and records a second event.

## Run

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Set `GROQ_API_KEY` in an untracked `.env` to enable the optional semantic signal. The two local signals work without a key. `DATABASE_PATH` can override the default `provenance.db`. Run `python -m unittest discover -s tests -v` for tests and `python demo.py` for a reproducible API walkthrough and audit output.

```powershell
Invoke-RestMethod http://localhost:5000/submit -Method Post -ContentType 'application/json' -Body '{"creator_id":"writer-1","text":"Paste a passage of at least 80 words for stronger evidence..."}'
Invoke-RestMethod http://localhost:5000/log
```

`POST /submit` requires `text` (1–20,000 characters) and `creator_id` (1–100 characters). It returns `content_id`, `attribution`, `confidence`, `ai_likeness_score`, `signals`, `weights`, `label`, `status`, and `timestamp`. `POST /appeal` requires that `content_id`, the same `creator_id`, and `creator_reasoning` (10–2,000 characters). `GET /content/<content_id>` shows current status. `GET /log?limit=20` shows recent events. `GET /health` checks service availability.

## Signals and confidence

The structural signal looks at sentence-length regularity, repeated sentence starts, and punctuation variety. The formulaic signal counts generic transition and promotional phrases per word count. These measure different properties: patterns of sentence construction versus specific vocabulary. Groq, when configured, adds a holistic semantic assessment. Each may fail: polished human prose can be uniform or formulaic, while edited AI text can avoid both local patterns; a language model can bring its own bias.

The local weighted AI-likeness score is `0.55 × structural + 0.45 × formulaic`. With Groq it is `0.25 × structural + 0.20 × formulaic + 0.55 × semantic`. Groq errors fall back to the local signals and appear as an error class in `semantic_signal_status`. This score is **not a calibrated probability of AI authorship**. The response's `confidence` expresses strength of the assigned category: the AI-likeness score for `likely_ai`, its complement for `likely_human`, and proximity to the middle for `uncertain`. Text under 80 words and signals differing by more than 0.55 are always `uncertain`. Otherwise `>= 0.85` means `likely_ai`, `<= 0.30` means `likely_human`, and the middle remains `uncertain`. The high threshold for an AI label reflects the cost of falsely accusing a human writer.

An actual local `python demo.py` run without Groq produced these examples. The formal, intentionally AI-style passage scored **0.8875** AI-likeness and returned `likely_ai` with **0.8875** confidence. The casual ramen review scored **0.2531** AI-likeness and returned `likely_human` with **0.7469** confidence. The five-word poem scored **0.2750** AI-likeness but returned `uncertain` because it was too short. This shows meaningful score variation and how the short-text guard changes the label. The test suite checks all three categories. Without a validated corpus of known authorship, these values should not be interpreted as calibrated probabilities. A real deployment would measure false positives on diverse human writing, tune thresholds on held-out examples, and review appeals.

## Exact transparency labels

| Variant | Text shown to a reader |
| --- | --- |
| High-confidence AI | "This writing shows strong indicators of AI generation. This assessment is not proof of authorship. The creator can appeal." |
| High-confidence human | "This writing shows strong indicators of human authorship. This assessment is not proof of authorship." |
| Uncertain | "We cannot reliably determine how this writing was created. No authorship claim is made." |

## Appeals, rate limits, and audit

An appeal verifies that the supplied `creator_id` matches the submission, stores the creator's reasoning, and changes status to `under_review`. Duplicate appeals return HTTP 409. This classroom identity check is only a string match; deployment requires authentication. A human reviewer would need the original decision, signal values, and appeal reason together.

`/submit` allows **10 requests per minute and 100 per day per IP**. A creator is unlikely to submit more than ten substantial works in a minute, while these limits slow a flood of automated requests and protect optional paid API usage. Flask-Limiter uses `memory://` for local demonstration, so counters reset on restart and are not shared between workers. Use shared storage such as Redis in deployment. The eleventh rapid request should return HTTP 429; `tests/test_app.py` asserts that behavior.

SQLite stores the decision and append-only structured events. Raw submitted text is not persisted; its SHA-256 digest is. `GET /log` returns an array of event objects. Each decision event has a UTC `timestamp`, `content_id`, `attribution`, `confidence`, `ai_likeness_score`, both local signal scores, and `status`. An appeal event shares its `content_id` and contains `appeal_reasoning` and `under_review`. The following is a condensed sample from an actual `python demo.py` run on October 5, 2026 EDT (UTC timestamps). Run the script to see the full JSON, including event IDs and creator IDs:

```json
[
  {"event_type":"decision","timestamp":"2026-10-06T02:50:57.549118+00:00","content_id":"1fe0ab27-1c85-414d-98d2-c75a2a4983f7","details":{"attribution":"likely_ai","confidence":0.8875,"ai_likeness_score":0.8875,"signals":{"structural":0.7955,"formulaic":1.0},"status":"classified"}},
  {"event_type":"decision","timestamp":"2026-10-06T02:50:57.560075+00:00","content_id":"1180732b-0906-4b3c-a98f-bbf9d385c90a","details":{"attribution":"likely_human","confidence":0.7469,"ai_likeness_score":0.2531,"signals":{"structural":0.4601,"formulaic":0.0},"status":"classified"}},
  {"event_type":"decision","timestamp":"2026-10-06T02:50:57.569391+00:00","content_id":"9439797a-db8c-420e-a7a0-4f8ab2a2da1f","details":{"attribution":"uncertain","confidence":0.55,"ai_likeness_score":0.275,"signals":{"structural":0.5,"formulaic":0.0},"status":"classified"}},
  {"event_type":"appeal","timestamp":"2026-10-06T02:50:57.583130+00:00","content_id":"1fe0ab27-1c85-414d-98d2-c75a2a4983f7","details":{"appeal_reasoning":"I drafted and revised this myself; please review the attribution.","status":"under_review"}}
]
```

The decision event stays unchanged as history; `GET /content/<id>` reports the current `under_review` status. In that same demo, seven further submissions returned HTTP 201, followed by **429, 429** once the per-minute limit was reached. The public log endpoint is for grading and needs access control in deployment.

## Limitations and reflection

A human poet who repeats a short line is likely to receive `uncertain`: the sample is short and repetition resembles the structural pattern. Formal academic writing may trigger formulaic phrases even when human. The system intentionally avoids strong claims from short or conflicting evidence. A determined user can rephrase text to evade lexical rules, and the local signals are not validated detectors.

The specification fixed the cautious AI threshold, labels, and appeal status before route code, making the response contract straightforward to implement. Implementation added an optional Groq signal with a local fallback so the required pipeline could still run without credentials; the plan documents the resulting weights. For AI assistance, I asked Codex to design the signal boundaries and API from the spec, then revised the result to force uncertain outcomes for short text and signal disagreement. I also asked Codex to implement appeals and audit persistence, then revised the flow to require a matching creator ID, reject duplicate appeals, and avoid persisting raw text.

## Walkthrough video

`demo_walkthrough.avi` is a captioned video showing the results of a real Flask server running on loopback HTTP: submissions, their signal scores and labels, an appeal, the audit log, and HTTP 429 rate limiting. The exact HTTP responses are saved in [demo_capture.json](demo_capture.json). The video has no spoken audio. To reproduce it on Windows, run `python record_demo.py` followed by `node make_video.js`; `python demo.py` is a shorter test-client walkthrough.
