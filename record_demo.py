"""Run a real local HTTP walkthrough and save the observed responses for the video."""

import json
import tempfile
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

from werkzeug.serving import make_server

from app import create_app
from tests.test_app import AI, HUMAN


def main():
    with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporary:
        app = create_app({"TESTING": True, "DATABASE": str(Path(temporary) / "capture.db")})
        server = make_server("127.0.0.1", 0, app)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"

        def call(method, route, payload=None):
            body = json.dumps(payload).encode() if payload is not None else None
            request = Request(base + route, data=body, method=method,
                              headers={"Content-Type": "application/json"} if body else {})
            try:
                with urlopen(request, timeout=10) as response:
                    return response.status, json.load(response)
            except HTTPError as error:
                return error.code, {"error": error.read().decode()[:120]}

        try:
            with patch("app.groq_signal", return_value=(None, "not_configured")):
                health = call("GET", "/health")
                submissions = [call("POST", "/submit", {"text": text, "creator_id": "demo-writer"})
                               for text in (AI, HUMAN, "A tiny poem about rain.")]
                first_id = submissions[0][1]["content_id"]
                appeal = call("POST", "/appeal", {
                    "content_id": first_id, "creator_id": "demo-writer",
                    "creator_reasoning": "I drafted and revised this myself; please review the attribution.",
                })
                content = call("GET", f"/content/{first_id}")
                log = call("GET", "/log")
                rate_statuses = [call("POST", "/submit", {"text": HUMAN, "creator_id": "demo-writer"})[0]
                                 for _ in range(9)]
            capture = {
                "base_url": "http://127.0.0.1:<ephemeral-port>",
                "health": {"http_status": health[0], "body": health[1]},
                "submissions": [{"http_status": status, "body": body} for status, body in submissions],
                "appeal": {"http_status": appeal[0], "body": appeal[1]},
                "content_after_appeal": {"http_status": content[0], "body": content[1]},
                "audit_log": {"http_status": log[0], "body": log[1]},
                "rate_limit_statuses_after_first_three": rate_statuses,
            }
            output = Path(__file__).parent / "demo_capture.json"
            output.write_text(json.dumps(capture, indent=2), encoding="utf-8")
            print(f"Saved live HTTP evidence to {output}")
            print("Submissions:", [(x["http_status"], x["body"]["attribution"],
                                    x["body"]["confidence"]) for x in capture["submissions"]])
            print("Appeal:", appeal[0], appeal[1]["status"])
            print("Rate limit:", rate_statuses)
        finally:
            server.shutdown()
            thread.join(timeout=5)


if __name__ == "__main__":
    main()
