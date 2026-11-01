"""Run one real RAG request (uses OpenAI API credits)."""
from grading import results_match
from rag import QUESTIONS, generate_sql, get_collection, retrieve
from services import read_query

if __name__ == "__main__":
    question = QUESTIONS[0]
    collection = get_collection()
    hits = retrieve(collection, question["question"])
    print(f"Chroma documents: {collection.count()}; retrieved: {[h['id'] for h in hits]}")
    sql = generate_sql(question["question"], hits)
    print(sql)
    columns, rows = read_query(sql)
    expected_columns, expected_rows = read_query(question["sql"])
    correct = results_match(columns, rows, expected_columns, expected_rows)
    print(f"Rows: {len(rows)}; matches expected answer: {correct}")
    if not correct:
        raise SystemExit("SQL was generated, but the answer did not match.")
