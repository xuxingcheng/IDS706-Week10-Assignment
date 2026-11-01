from decimal import Decimal
import os
import tempfile
import unittest
from unittest.mock import Mock, patch

import chromadb
from chromadb.config import Settings

from grading import quiz_match, results_match
from rag import QUESTIONS, generate_sql, knowledge_documents, retrieve


class TestEmbedding:
    """Small deterministic vectors keep the unit tests offline."""
    def __call__(self, input):
        return [[float("price" in s.lower()), float("rating" in s.lower()), 0.1] for s in input]

    def name(self):
        return "test-embedding"

    def embed_query(self, input):
        return self(input)


class RagTests(unittest.TestCase):
    def test_actual_chroma_vector_search_and_schema_retrieval(self):
        with tempfile.TemporaryDirectory() as folder:
            client = chromadb.PersistentClient(path=folder, settings=Settings(anonymized_telemetry=False))
            collection = client.create_collection("test-retrieval", embedding_function=TestEmbedding())
            docs = ["price dollars", "rating out of five", "name", "restaurant", "schema"]
            collection.add(ids=["price", "rating", "name", "table", "schema"], documents=docs,
                           metadatas=[{"kind": "rules"}] * 4 + [{"kind": "schema"}])
            price_hits = retrieve(collection, "price")
            rating_hits = retrieve(collection, "rating")
            self.assertEqual(price_hits[0]["id"], "price")
            self.assertEqual(rating_hits[0]["id"], "rating")
            self.assertIn("schema", [h["id"] for h in price_hits])
            self.assertTrue(all(isinstance(h["distance"], float) for h in price_hits))

    def test_openai_receives_question_and_retrieved_context(self):
        response = Mock(ok=True)
        response.json.return_value = {"status": "completed", "output": [
            {"type": "reasoning"}, {"type": "message", "content": [
                {"type": "output_text", "text": "```sql\nSELECT name FROM restaurants;\n```"}]}]}
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-secret"}), \
             patch("rag.requests.post", return_value=response) as post:
            sql = generate_sql("Find cheap meals", [{"id": "example-1", "text": "retrieved unique context"}])
        self.assertEqual(sql, "SELECT name FROM restaurants;")
        body = post.call_args.kwargs["json"]
        self.assertIn("retrieved unique context", body["input"])
        self.assertIn("Find cheap meals", body["input"])
        self.assertFalse(body["store"])
        self.assertNotIn("test-secret", str(body))

    def test_no_context_never_calls_ai(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test"}), patch("rag.requests.post") as post:
            with self.assertRaisesRegex(ValueError, "Retrieve context"):
                generate_sql("question", [])
            post.assert_not_called()

    def test_api_errors_are_redacted(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test"}), \
             patch("rag.requests.post", return_value=Mock(ok=False, status_code=401, text="private data")):
            with self.assertRaisesRegex(ValueError, "API key") as error:
                generate_sql("question", [{"id": "a", "text": "context"}])
            self.assertNotIn("private data", str(error.exception))

    def test_incomplete_api_response_is_not_executed(self):
        response = Mock(ok=True)
        response.json.return_value = {"status": "incomplete", "output": []}
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test"}), patch("rag.requests.post", return_value=response):
            with self.assertRaisesRegex(ValueError, "did not finish"):
                generate_sql("question", [{"id": "a", "text": "context"}])

    def test_knowledge_contains_live_schema_and_five_examples(self):
        docs = knowledge_documents("live schema marker")
        self.assertEqual(docs[0]["text"], "live schema marker")
        self.assertEqual(sum(d["kind"] == "example" for d in docs), 5)

    def test_grading_handles_decimal_and_order(self):
        self.assertTrue(results_match(["cost"], [(Decimal("10.50"),)], ["cost"], [[10.5]]))
        self.assertFalse(results_match(["cost"], [(1,), (2,)], ["cost"], [[2], [1]]))
        self.assertFalse(results_match(["wrong"], [(1,)], ["cost"], [[1]]))
        self.assertFalse(results_match(["cost"], [], ["cost"], [[1]]))

    def test_custom_question_is_not_graded_as_selected_quiz(self):
        self.assertIsNone(quiz_match("Find restaurants under $20", QUESTIONS))
        self.assertEqual(quiz_match(QUESTIONS[0]["question"].upper(), QUESTIONS)["id"], 1)
