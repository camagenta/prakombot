"""Tests for notifier/schemas.py — payload parsing and validation."""
import os
import sys
import unittest
from datetime import datetime


REPO = "/Volumes/Pusdiklat BPS 4/Antigravity/prakombot"
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from notifier.tests.conftest import _make_module


class TestFormSubmitPayload(unittest.TestCase):
    def setUp(self):
        import notifier.schemas
        import importlib
        importlib.reload(notifier.schemas)
        self.schemas = notifier.schemas

    def _valid_payload(self, **overrides):
        data = {
            "form_id": "1AbCxyz",
            "submitted_at": "2026-06-02T22:00:00Z",
            "responses": [
                {"index": 0, "title": "Nama", "answer": "Budi"},
                {"index": 1, "title": "NIP", "answer": "123456789012345678"},
            ],
        }
        data.update(overrides)
        return data

    def test_parses_valid_payload(self):
        p = self.schemas.FormSubmitPayload(**self._valid_payload())
        self.assertEqual(p.form_id, "1AbCxyz")
        self.assertEqual(len(p.responses), 2)
        self.assertEqual(p.responses[0].answer, "Budi")

    def test_rejects_empty_responses(self):
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            self.schemas.FormSubmitPayload(
                form_id="x", submitted_at="2026-06-02T22:00:00Z", responses=[]
            )

    def test_rejects_missing_form_id(self):
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            self.schemas.FormSubmitPayload(
                submitted_at="2026-06-02T22:00:00Z",
                responses=[{"index": 0, "title": "Nama", "answer": "Budi"}],
            )

    def test_parses_from_json(self):
        import json
        body = json.dumps(self._valid_payload()).encode()
        p = self.schemas.FormSubmitPayload.model_validate_json(body)
        self.assertEqual(p.responses[1].title, "NIP")

    def test_find_by_title_case_insensitive(self):
        p = self.schemas.FormSubmitPayload(**self._valid_payload())
        self.assertEqual(p.find("nama"), "Budi")
        self.assertEqual(p.find("NIP"), "123456789012345678")
        self.assertIsNone(p.find("Alamat"))

    def test_format_message_includes_all_responses(self):
        p = self.schemas.FormSubmitPayload(**self._valid_payload())
        text = p.format_message()
        self.assertIn("Nama: Budi", text)
        self.assertIn("NIP: 123456789012345678", text)
        self.assertIn("Ada isian form baru", text)


if __name__ == "__main__":
    unittest.main()
