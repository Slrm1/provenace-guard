import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import LABELS, classify, create_app


HUMAN = ("ok so i tried the ramen place downtown and honestly? underwhelming. "
         "the broth was fine, but way too salty! i was thirsty all afternoon. "
         "my friend got the spicy version; she liked it. maybe i'll try that next time. ") * 3
AI = ("It is important to note that artificial intelligence represents a transformative paradigm shift. "
      "Furthermore, stakeholders must consider a comprehensive approach to responsible deployment. "
      "Moreover, this multifaceted challenge is crucial for every organization. ") * 4


class ProvenanceGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = create_app({"TESTING": True, "DATABASE": str(Path(self.tmp.name) / "test.db")})
        self.client = self.app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def submit(self, text=HUMAN):
        return self.client.post("/submit", json={"text": text, "creator_id": "writer-1"})

    def test_labels_and_scores(self):
        ai = classify(AI, semantic=0.99)
        human = classify(HUMAN, semantic=0.01)
        short = classify("A short poem.")
        self.assertEqual(ai["attribution"], "likely_ai")
        self.assertEqual(human["attribution"], "likely_human")
        self.assertEqual(short["attribution"], "uncertain")
        for item in (ai, human, short):
            self.assertEqual(item["label"], LABELS[item["attribution"]])
        self.assertGreater(ai["ai_likeness_score"], human["ai_likeness_score"])

    def test_submission_appeal_and_audit(self):
        with patch("app.groq_signal", return_value=(None, "not_configured")):
            response = self.submit()
        self.assertEqual(response.status_code, 201)
        content_id = response.json["content_id"]
        self.assertEqual(set(response.json["signals"]), {"structural", "formulaic"})
        appeal = self.client.post("/appeal", json={
            "content_id": content_id, "creator_id": "writer-1",
            "creator_reasoning": "I wrote this from my own experience.",
        })
        self.assertEqual(appeal.status_code, 201)
        self.assertEqual(self.client.get(f"/content/{content_id}").json["status"], "under_review")
        entries = self.client.get("/log").json["entries"]
        self.assertEqual([e["event_type"] for e in entries], ["appeal", "decision"])
        self.assertEqual(entries[0]["content_id"], content_id)
        self.assertEqual(self.client.post("/appeal", json={
            "content_id": content_id, "creator_id": "writer-1",
            "creator_reasoning": "I wrote this from my own experience.",
        }).status_code, 409)

    def test_creator_mismatch_and_rate_limit(self):
        with patch("app.groq_signal", return_value=(None, "not_configured")):
            first = self.submit()
            for _ in range(9):
                self.assertEqual(self.submit().status_code, 201)
            self.assertEqual(self.submit().status_code, 429)
        mismatch = self.client.post("/appeal", json={
            "content_id": first.json["content_id"], "creator_id": "someone-else",
            "creator_reasoning": "I claim this writing is mine.",
        })
        self.assertEqual(mismatch.status_code, 403)


if __name__ == "__main__":
    unittest.main()
