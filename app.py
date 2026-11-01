"""Run with: streamlit run app.py"""
import os
import time

import pandas as pd
import psycopg2
import requests
import streamlit as st

from grading import quiz_match, results_match
from rag import QUESTIONS, generate_sql, get_collection, retrieve
from services import load_answer, read_query, run_query, save_answer, sign_in, sign_up

st.set_page_config(page_title="Campus Food SQL Quiz", page_icon="🍽️")
st.title("Campus Food SQL Quiz")
st.write("Ask a question about our six fictional restaurants and let AI help you write SQL.")
st.caption("Week 10 · Built from the Week 7 quiz")

db_keys = ["DB_HOST", "POSTGRES_USER", "POSTGRES_PASSWORD"]
if any(not os.getenv(key) for key in db_keys):
    st.info("Add the Week 7 database settings to .env or Streamlit secrets. See README.md.")
    st.stop()


@st.cache_resource(ttl=3600, show_spinner=False)
def knowledge_base():
    return get_collection()


def show_result(columns, rows):
    st.dataframe(pd.DataFrame(rows, columns=columns), hide_index=True, width="stretch")


with st.sidebar:
    st.header("Quiz account")
    st.caption("Sign in to save answers in the original quiz. The AI helper works without an account.")
    if not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_KEY"):
        st.info("Saving answers needs the Week 7 Supabase Auth settings.")
    elif st.session_state.get("token"):
        st.write(st.session_state.get("email", "Signed in"))
        if st.button("Sign out"):
            st.session_state.clear()
            st.rerun()
    else:
        with st.form("login"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            login = st.form_submit_button("Sign in")
            register = st.form_submit_button("Create account")
        try:
            if login:
                st.session_state.token = sign_in(email.strip(), password)
                st.session_state.email = email.strip()
                st.rerun()
            if register:
                result = sign_up(email.strip(), password)
                if result.get("access_token"):
                    st.session_state.token = result["access_token"]
                    st.session_state.email = email.strip()
                    st.rerun()
                st.success("Check your email to confirm your account, then sign in.")
        except ValueError as exc:
            st.error(str(exc))
        except requests.RequestException:
            st.error("Could not reach Supabase. Please try again.")

ai_tab, quiz_tab = st.tabs(["AI SQL helper", "Original SQL quiz"])
with ai_tab:
    preset = st.selectbox("Choose a quiz question", QUESTIONS + [None],
                          format_func=lambda q: f"Q{q['id']}. {q['title']}" if q else "My own question")
    with st.form("generate"):
        question = st.text_area(
            "Your question", value=preset["question"] if preset else "",
            key=f"question_{preset['id'] if preset else 'custom'}", max_chars=1000, height=100,
            placeholder="Which restaurants cost $12 or less?",
        )
        execute = st.checkbox("Run the SQL and check the quiz answer", value=True)
        submitted = st.form_submit_button("Generate SQL", type="primary")
    if submitted:
        st.session_state.pop("generation", None)
        try:
            if not question.strip():
                raise ValueError("Enter a question first.")
            if not os.getenv("OPENAI_API_KEY"):
                raise ValueError("Add OPENAI_API_KEY to the app secrets or local .env file.")
            if time.monotonic() - st.session_state.get("last_request", 0) < 10:
                raise ValueError("Wait a few seconds before generating another answer.")
            st.session_state.last_request = time.monotonic()
            with st.spinner("Finding relevant knowledge in ChromaDB..."):
                collection = knowledge_base()
                hits = retrieve(collection, question)
            with st.spinner("Asking OpenAI to write SQL..."):
                sql = generate_sql(question, hits)
            output = {"question": question, "sql": sql, "hits": hits, "count": collection.count()}
            st.session_state.generation = output
            if execute:
                try:
                    with st.spinner("Running a read-only query..."):
                        columns, rows = read_query(sql)
                        output.update(columns=columns, rows=rows)
                        matched = quiz_match(question, QUESTIONS)
                        if matched:
                            expected_columns, expected_rows = read_query(matched["sql"])
                            output["correct"] = results_match(columns, rows, expected_columns, expected_rows)
                            output["quiz_id"] = matched["id"]
                except ValueError as exc:
                    output["execution_error"] = str(exc)
                except psycopg2.Error:
                    output["execution_error"] = "The database could not run this SQL. Check the SQL or try generating it again."
        except ValueError as exc:
            st.error(str(exc))
        except psycopg2.Error:
            st.error("Could not read the Week 7 database schema. Check the database connection.")
        except Exception:
            # Provider/database exceptions may contain secrets; keep them out of the UI.
            st.error("Could not prepare the Chroma knowledge base. Check the server connection and try again.")

    output = st.session_state.get("generation")
    if output and output["question"] == question:
        st.subheader("Generated SQL")
        st.code(output["sql"], language="sql")
        st.caption(f"ChromaDB retrieved {len(output['hits'])} of {output['count']} knowledge documents → OpenAI → SQL")
        if "columns" in output:
            st.subheader("Result from the Week 7 database")
            show_result(output["columns"], output["rows"])
            if "correct" in output:
                if output["correct"]:
                    st.success(f"Correct! The result matches Q{output['quiz_id']}, including column names and row order.")
                else:
                    st.warning(f"The result does not match Q{output['quiz_id']}. Check the original quiz hint.")
            elif "execution_error" not in output:
                st.info("Custom question: SQL ran, but there is no expected answer to check.")
        if "execution_error" in output:
            st.warning(output["execution_error"])
        with st.expander("Knowledge retrieved from ChromaDB"):
            for hit in output["hits"]:
                st.caption(f"{hit['id']} · {hit['kind']} · cosine distance {hit['distance']:.3f}")
                st.code(hit["text"], language="text", wrap_lines=True)
    with st.expander("Table and column meanings"):
        st.code("restaurants(id, name, cuisine, avg_cost, rating, distance_miles)", language="text")
        st.write("avg_cost is dollars, rating is out of 5, and distance_miles is miles from campus.")

with quiz_tab:
    st.write("Five questions · 4 points each · 20 points total")
    token = st.session_state.get("token")
    if not token:
        st.info("Sign in using the sidebar to run and save your own SQL answers.")
    quiz = st.selectbox("Choose a question", QUESTIONS,
                        format_func=lambda q: f"Q{q['id']}. {q['title']} — {q['points']} points")
    st.write(quiz["question"])
    with st.expander("Hint: expected SQL and result"):
        st.code(quiz["sql"], language="sql")
        show_result(quiz["columns"], quiz["rows"])
    editor_key = f"answer_{quiz['id']}"
    st.session_state.setdefault(editor_key, "")
    if st.button("Load my saved answer", disabled=not token):
        try:
            st.session_state[editor_key] = load_answer(token, quiz["id"])
            st.success("Saved answer loaded (blank if you have not saved one).")
        except (ValueError, requests.RequestException):
            st.error("Could not load your answer. Try signing in again.")
    query = st.text_area("Your SQL", key=editor_key, height=160)
    run_col, save_col = st.columns(2)
    run = run_col.button("Run SQL", disabled=not token, type="primary")
    save = save_col.button("Save answer", disabled=not token)
    try:
        if run:
            columns, rows = run_query(token, query)
            st.subheader("Your query result")
            show_result(columns, rows)
        if save:
            save_answer(token, quiz["id"], query)
            st.success("Answer saved to your account.")
    except ValueError as exc:
        st.error(str(exc))
    except psycopg2.Error:
        st.error("The database could not run this query. Check the SQL and try again.")
    except requests.RequestException:
        st.error("Could not reach Supabase. Please try again.")
