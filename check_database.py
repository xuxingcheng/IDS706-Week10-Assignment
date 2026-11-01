"""GitHub Actions runs this against the real hosted database using Secrets."""
import json
from decimal import Decimal
from pathlib import Path

from services import read_query

questions = json.loads(Path(__file__).with_name("questions.json").read_text())
assert sum(q["points"] for q in questions) == 20
for question in questions:
    columns, rows = read_query(question["sql"])
    actual = [[float(v) if isinstance(v, Decimal) else v for v in row] for row in rows]
    assert columns == question["columns"], f"Q{question['id']}: wrong columns"
    assert actual == question["rows"], f"Q{question['id']}: wrong result"
    print(f"Q{question['id']}: live database result matches hint")
print("All five hints verified over an encrypted Postgres connection.")
