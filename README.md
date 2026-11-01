# Campus Food SQL Quiz

This app adds an AI SQL helper to my [Week 7 quiz](https://github.com/xuxingcheng/IDS706-Week7-Assignment). It uses the same Supabase PostgreSQL database.

**Website:** https://ids706-week10-campus-food.streamlit.app/

## How to use

1. Choose a quiz question or type your own question.
2. Click **Generate SQL**.
3. See the SQL, result table, and answer check.
4. Open **Knowledge retrieved from ChromaDB** to see what the AI used.

The **Original SQL quiz** tab lets you write SQL yourself. Sign in to run and save those answers.

## How it works

Question → ChromaDB search → OpenAI Responses API → SQL.

ChromaDB uses MiniLM embeddings to search the database schema, column meanings, and example queries. OpenAI uses the retrieved information to write SQL. The app runs SELECT queries with a read-only database login. It also checks answers for the five quiz questions.

## How I met the assignment criteria

### PostgreSQL Database Integration (15 points)

I reused my Week 7 Supabase PostgreSQL database and its `restaurants` table. The app reads the real table schema and uses the restaurant data to run SQL queries.

### Vector Database & Retrieval (25 points)

I used ChromaDB to store nine pieces of information: the table schema, three notes about the columns and query rules, and five example questions with SQL. MiniLM turns the text into vectors, and ChromaDB searches for information related to each question. Users can open the retrieved knowledge section to see what it found.

### AI API Integration (15 points)

I used the OpenAI Responses API to generate SQL. I send the user's question together with the information retrieved from ChromaDB, so the AI has useful context for its answer.

### Web Application Integration (20 points)

I added the AI helper to my Streamlit quiz and deployed it on Streamlit Community Cloud. Users can open the website, choose or type a question, and click **Generate SQL** to see the answer. The AI helper does not require sign-in.

### End-to-End RAG Demonstration (15 points)

I tested the full flow: question → vector retrieval → OpenAI → generated SQL. For example, the question about meals costing at most $12 returned SQL that found Campus Tacos, Burrito House, and Pizza Corner. The screenshots below show this example.

### GitHub & Documentation (10 points)

I uploaded the app code to this repository. This README includes the website link, basic usage, setup steps, and screenshots of the generated SQL and query result. Passwords and API keys are kept out of the repository.

### Bonus: Automatic SQL Execution (+3 points)

When **Run the SQL and check the quiz answer** is checked, the app automatically runs the generated SQL and displays a result table. It only allows basic SELECT queries on `restaurants` and uses the read-only `quiz_reader` login.

### Bonus: Result Validation (+2 points)

For the five original quiz questions, the app compares the generated query's result with the expected query's result. It checks the values, column names, and row order, then shows whether they match. Custom or rewritten questions can run, but do not get an automatic answer check.

## Run locally

Use Python 3.11.

```bash
pip install -r requirements.txt
cp .env.example .env
streamlit run app.py
```

Before starting the app, add your Week 7 database settings, Supabase Auth settings, and `OPENAI_API_KEY` to `.env`. The default model is `gpt-6.1-sol`. The first question downloads the embedding model. Do not commit `.env` or API keys.

For Streamlit Community Cloud, use `app.py`, Python 3.11, and add the same settings in app secrets.

## Screenshots

Question and generated SQL:

![Question and generated SQL](screenshots/rag-sql.jpg)

Read-only query result and answer check:

![Result table and validation](screenshots/rag-result-check.jpg)
