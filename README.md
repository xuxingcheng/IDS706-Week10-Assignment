# Campus Food SQL Quiz

This is my Week 10 app. It adds an AI SQL helper to my [Week 7 quiz](https://github.com/xuxingcheng/IDS706-Week7-Assignment) and uses the same Supabase PostgreSQL database.

## Use the app

The website link will be added after deployment.

1. Choose a quiz question or type your own question.
2. Click **Generate SQL**.
3. Read the SQL, result table, and answer check. Open **Knowledge retrieved from ChromaDB** to see what the AI used.

The **Original SQL quiz** tab still lets you write SQL yourself. Sign in to run and save those answers.

## How it works

Question → ChromaDB search → OpenAI Responses API → SQL.

ChromaDB stores the live table schema, column meanings, and five example queries. It uses local MiniLM embeddings to find related information. OpenAI uses that information to write SQL. The app runs allowed SELECT queries with the Week 7 read-only login. For the five quiz questions, it compares the result with the expected query, including column names and row order.

## Run locally

Use Python 3.11.

```bash
pip install -r requirements.txt
cp .env.example .env
streamlit run app.py
```

Put your Week 7 database settings, Supabase Auth settings, and `OPENAI_API_KEY` in `.env`. The default model is `gpt-6.1-sol`; `OPENAI_MODEL` can change it. The first question downloads the embedding model. Never commit `.env` or API keys.

For Streamlit Community Cloud, choose `app.py`, Python 3.11, and put the same settings in app secrets.

Run tests with `python -m unittest discover -s tests -v`. Run `python check_rag.py` to check the real pipeline (uses API credits).
