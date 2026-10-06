# Provenance Guard — implementation plan

## Architecture

```text
POST /submit (text, creator_id)
  -> validate input -> structural signal + lexical signal
  -> optional Groq assessment -> weighted score and disagreement check
  -> attribution + exact transparency label -> SQLite decision and audit event
  -> response (content_id, scores, confidence, label)

POST /appeal (content_id, creator_id, creator_reasoning)
  -> verify creator and current status -> SQLite status = under_review
  -> linked appeal and audit event -> confirmation
GET /log -> recent structured events; GET /content/<id> -> current record
```

Each submission is validated, scored by distinct structural and lexical signals, optionally assessed by Groq, and turned into a cautious label. The decision and signal values are saved together with an audit event before the response. An appeal checks the creator ID, changes the stored status, and adds an audit event linked to the original decision.

## Detection signals and combination

Every run uses two independent local signals in `[0, 1]`, where higher means more AI-like. **Structural regularity** measures sentence-length uniformity, repeated sentence openings, and low punctuation variety. It can over-score formal writing or short poetry and under-score edited AI text. **Formulaic language** measures a small list of generic connective and promotional phrases, normalized by text length. It can over-score technical or academic prose and miss AI text without those phrases. An optional **Groq semantic assessment** measures holistic style using `meta-llama/llama-4-scout-17b-16e-instruct`; it may reflect model bias and must never be treated as proof.

Without Groq, score = `0.55 × structural + 0.45 × formulaic`. With Groq, score = `0.25 × structural + 0.20 × formulaic + 0.55 × Groq`. The application returns each signal and weights. If the signals disagree by more than 0.55, the outcome is uncertain. On an unavailable or malformed Groq response, the system uses the two local signals and records the error class, never the API key or raw submitted text.

## Uncertainty and labels

The score is an **AI-likeness index**, not a statistically calibrated probability that an author used AI. A value of 0.60 means the combined indicators lean somewhat AI-like, but still yields `uncertain`. It is deliberately harder to label someone likely AI (`>= 0.85`) than likely human (`<= 0.30`), reflecting the cost of a false accusation. Text under 80 words is always uncertain because the evidence is too thin. Signal disagreement also forces uncertainty. The returned `confidence` is the strength of the chosen decision: `score` for likely AI, `1-score` for likely human, and `1-2*abs(score-0.5)` for uncertain, clipped to `[0,1]`. It is an index rather than a calibrated probability. The exact labels are:

| Variant | Exact text |
| --- | --- |
| High-confidence AI | "This writing shows strong indicators of AI generation. This assessment is not proof of authorship. The creator can appeal." |
| High-confidence human | "This writing shows strong indicators of human authorship. This assessment is not proof of authorship." |
| Uncertain | "We cannot reliably determine how this writing was created. No authorship claim is made." |

## Appeals and edge cases

The submitting creator supplies `content_id`, matching `creator_id`, and a 10–2000 character `creator_reasoning`. The first valid appeal changes `classified` to `under_review`; duplicates get a conflict response. A reviewer would see the original score, component signals, decision timestamp, appeal reasoning and timestamp. Authentication and reviewer resolution are outside this classroom API; a production system needs verified identity and restricted audit access.

Short poems with repetition can look structurally uniform despite being human. Polished academic prose may contain formulaic transitions. Lightly edited AI writing can evade both local indicators. These cases should generally receive an uncertain label, and appeals preserve a route for correcting mistakes.

## API and safety

`POST /submit` accepts JSON `text` (1–20,000 characters) and `creator_id` (1–100 characters), returning content ID, attribution, confidence, AI-likeness score, signal details, label and status. `POST /appeal` accepts the three fields above. `GET /content/<id>` and `GET /log?limit=20` support review and demo. Submission is limited to 10 requests per minute and 100 per day per IP. SQLite stores records and append-only audit events; raw text is not stored, only its SHA-256 hash. `/log` is deliberately public for grading and must be protected in deployment.

## AI Tool Plan

- **M3:** Give the detection section and architecture diagram to the AI tool; request the Flask route skeleton and structural-signal function. Verify the function's `[0,1]` output on varied prose before integration.
- **M4:** Give detection and uncertainty sections plus the diagram; request the lexical signal and weighted combination. Verify score ranges, four different sample texts, and the short-text and disagreement rules.
- **M5:** Give labels, appeals, and architecture sections; request label mapping, SQLite persistence, appeal endpoint, audit logging and rate limits. Verify exact label strings, creator match, duplicate appeals, 429 behavior, and linked audit events.

No stretch feature is claimed; the optional Groq assessment is a third signal when configured, but the required system works with the two local signals.
