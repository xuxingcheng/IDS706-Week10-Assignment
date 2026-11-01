import json
from pathlib import Path
import sqlite3
import unittest
from unittest.mock import patch

from services import validate_query, run_query, save_answer

ROOT = Path(__file__).resolve().parents[1]


class QuizTests(unittest.TestCase):
    def test_hints_match_seed_data(self):
        questions = json.loads((ROOT / "questions.json").read_text())
        self.assertEqual(sum(q["points"] for q in questions), 20)
        # SQLite checks the basic SQL and fixed fixture offline. CI also checks Postgres.
        seed = (ROOT / "setup.sql").read_text().split("-- A separate database login")[0]
        db = sqlite3.connect(":memory:")
        db.executescript(seed.replace("public.", ""))
        for q in questions:
            cursor = db.execute(validate_query(q["sql"]))
            self.assertEqual([c[0] for c in cursor.description], q["columns"])
            self.assertEqual([list(r) for r in cursor.fetchall()], q["rows"])
        db.close()

    def test_reject_unsafe_sql(self):
        for sql in ["DELETE FROM restaurants", "SELECT * FROM restaurants; DROP TABLE restaurants",
                    "SELECT * FROM auth.users", "SELECT * FROM quiz_answers",
                    "SELECT pg_sleep(50) FROM restaurants", "SELECT * INTO stolen FROM restaurants",
                    "SELECT * FROM restaurants FOR UPDATE", "SELECT set_config('a','b',false) FROM restaurants",
                    "WITH x AS (DELETE FROM restaurants RETURNING *) SELECT * FROM x",
                    "SELECT * FROM pg_catalog.restaurants", "SELECT * FROM restaurants WHERE true; SELECT 1"]:
            with self.subTest(sql=sql), self.assertRaises(ValueError):
                validate_query(sql)

    def test_signed_out_cannot_run_or_save(self):
        with patch("services.connect_database") as connection, patch("services.api") as api:
            with self.assertRaises(ValueError):
                run_query(None, "SELECT * FROM restaurants")
            with self.assertRaises(ValueError):
                save_answer(None, 1, "SELECT * FROM restaurants")
            connection.assert_not_called()
            api.assert_not_called()

    def test_rejected_session_cannot_reach_database(self):
        with patch("services.api", side_effect=ValueError("Expired session")), patch("services.connect_database") as connection:
            with self.assertRaises(ValueError):
                run_query("expired", "SELECT * FROM restaurants")
            connection.assert_not_called()


if __name__ == "__main__":
    unittest.main()
