import os
from pathlib import Path
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")
CONFIG = {
    "SUPABASE_URL": "https://example.supabase.co",
    "SUPABASE_KEY": "test-key",
    "DB_HOST": "example.pooler.supabase.com",
    "POSTGRES_USER": "quiz_reader.example",
    "POSTGRES_PASSWORD": "test-only",
    "OPENAI_API_KEY": "test-only",
}


class AppTests(unittest.TestCase):
    def test_signed_out_buttons_are_disabled(self):
        with patch.dict(os.environ, CONFIG):
            app = AppTest.from_file(APP, default_timeout=15).run()
            self.assertFalse(app.exception)
            buttons = {button.label: button for button in app.button}
            for label in ["Run SQL", "Save answer", "Load my saved answer"]:
                self.assertTrue(buttons[label].disabled)

    def test_signed_in_query_displays_rows(self):
        with patch.dict(os.environ, CONFIG), patch("services.run_query", return_value=(["name"], [("Campus Tacos",)])) as run:
            app = AppTest.from_file(APP, default_timeout=15)
            app.session_state["token"] = "test-session"
            app.run()
            next(t for t in app.text_area if t.label == "Your SQL").input("SELECT name FROM restaurants;")
            next(b for b in app.button if b.label == "Run SQL").click().run()
            self.assertFalse(app.exception)
            run.assert_called_once_with("test-session", "SELECT name FROM restaurants;")
            self.assertEqual(app.dataframe[-1].value.iloc[0, 0], "Campus Tacos")

    def test_ai_generation_executes_and_validates_without_login(self):
        from unittest.mock import Mock
        from rag import QUESTIONS
        q = QUESTIONS[0]
        hits = [{"id": "schema", "kind": "schema", "text": "restaurants(name, avg_cost)", "distance": 0.1}]
        with patch.dict(os.environ, CONFIG), \
             patch("rag.get_collection", return_value=Mock(count=lambda: 9)), \
             patch("rag.retrieve", return_value=hits), \
             patch("rag.generate_sql", return_value=q["sql"]), \
             patch("services.read_query", return_value=(q["columns"], q["rows"])) as run:
            app = AppTest.from_file(APP, default_timeout=15).run()
            next(b for b in app.button if b.label == "Generate SQL").click().run()
            self.assertFalse(app.exception)
            self.assertTrue(any("Correct!" in s.value for s in app.success))
            self.assertEqual(run.call_count, 2)
            self.assertTrue(any(q["sql"] == block.value for block in app.code))

    def test_execution_failure_keeps_generated_sql(self):
        from unittest.mock import Mock
        with patch.dict(os.environ, CONFIG), \
             patch("rag.get_collection", return_value=Mock(count=lambda: 9)), \
             patch("rag.retrieve", return_value=[]), \
             patch("rag.generate_sql", return_value="DELETE FROM restaurants;"), \
             patch("services.read_query", side_effect=ValueError("Use one SELECT statement.")):
            app = AppTest.from_file(APP, default_timeout=15).run()
            next(b for b in app.button if b.label == "Generate SQL").click().run()
            self.assertFalse(app.exception)
            self.assertTrue(any("DELETE FROM" in block.value for block in app.code))
            self.assertTrue(any("SELECT" in w.value for w in app.warning))
