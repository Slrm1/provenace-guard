"""Generate real API evidence locally: python demo.py (after pip install -r requirements.txt)."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from app import create_app
from tests.test_app import AI, HUMAN


def main():
    with tempfile.TemporaryDirectory() as temp:
        app = create_app({"TESTING": True, "DATABASE": str(Path(temp) / "demo.db")})
        client = app.test_client()
        with patch("app.groq_signal", return_value=(None, "not_configured")):
            submissions = [client.post("/submit", json={"text": text, "creator_id": "demo-writer"})
                           for text in (AI, HUMAN, "A tiny poem about rain.")]
        responses = [r.json for r in submissions]
        appeal = client.post("/appeal", json={
            "content_id": responses[0]["content_id"], "creator_id": "demo-writer",
            "creator_reasoning": "I drafted and revised this myself; please review the attribution.",
        })
        print(json.dumps({"submissions": responses, "appeal": appeal.json,
                          "audit_log": client.get("/log").json}, indent=2))
        codes = []
        with patch("app.groq_signal", return_value=(None, "not_configured")):
            for _ in range(9):
                codes.append(client.post("/submit", json={"text": HUMAN, "creator_id": "demo-writer"}).status_code)
        print("Rate limit after initial three submissions:", codes)


if __name__ == "__main__":
    main()
