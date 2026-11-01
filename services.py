"""Small helpers for Supabase Auth, saved answers, and Postgres queries."""
import os
from pathlib import Path

import psycopg2
import requests
import sqlglot
from sqlglot import exp
from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))


def api(method, path, token=None, **kwargs):
    headers = {"apikey": os.environ["SUPABASE_KEY"]}
    if token:
        headers["Authorization"] = "Bearer " + token
    headers.update(kwargs.pop("headers", {}))
    response = requests.request(
        method, os.environ["SUPABASE_URL"].rstrip("/") + path,
        headers=headers, timeout=15, **kwargs
    )
    if not response.ok:
        # Translate known codes; never display raw responses or credentials.
        try:
            code = response.json().get("error_code", "")
        except (ValueError, AttributeError):
            code = ""
        messages = {
            "email_address_not_authorized": "Supabase cannot send confirmation emails to this address with its default email service. The project owner needs to configure custom SMTP.",
            "over_email_send_rate_limit": "Supabase's confirmation email limit has been reached. Wait before retrying, or configure custom SMTP.",
            "over_request_rate_limit": "Too many attempts. Wait a few minutes before trying again.",
            "weak_password": "Your password does not meet the project's requirements. Use a longer password with letters, numbers, and symbols.",
            "email_address_invalid": "Enter a valid email address.",
            "validation_failed": "Check your email address and password format.",
            "user_already_exists": "An account already exists. Try Sign in instead.",
            "email_exists": "An account already exists. Try Sign in instead.",
            "email_not_confirmed": "Confirm your email using the link from Supabase before signing in.",
            "invalid_credentials": "The email or password is incorrect.",
            "signup_disabled": "Registration is disabled in this Supabase project.",
            "email_provider_disabled": "Enable email sign-in in Supabase Authentication settings.",
        }
        raise ValueError(messages.get(code, f"Supabase could not complete the request (HTTP {response.status_code}). Check the project's Authentication logs."))
    return response.json() if response.content else None


def current_user(token):
    if not token:
        raise ValueError("Please sign in first.")
    return api("GET", "/auth/v1/user", token)["id"]


def sign_in(email, password):
    return api("POST", "/auth/v1/token?grant_type=password",
               json={"email": email, "password": password})["access_token"]


def sign_up(email, password):
    email = email.strip()
    if "@" not in email or not email.rsplit("@", 1)[-1] or " " in email:
        raise ValueError("Enter a valid email address.")
    if len(password) < 6:
        raise ValueError("Use a password with at least 6 characters.")
    return api("POST", "/auth/v1/signup", json={"email": email, "password": password})


def save_answer(token, question_id, query):
    user_id = current_user(token)
    if question_id not in range(1, 6) or len(query) > 5000:
        raise ValueError("Choose a quiz question and use no more than 5,000 characters.")
    api("POST", "/rest/v1/quiz_answers", token,
        headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
        json={"user_id": user_id, "question_id": question_id, "answer_sql": query})


def load_answer(token, question_id):
    user_id = current_user(token)
    rows = api("GET", "/rest/v1/quiz_answers", token,
               params={"select": "answer_sql", "user_id": "eq." + user_id,
                       "question_id": "eq." + str(question_id)})
    return rows[0]["answer_sql"] if rows else ""


# This beginner quiz intentionally supports basic SELECT syntax only.
# An explicit node allowlist also excludes functions with side effects,
# catalog access, custom casts, SELECT INTO, locks, and multiple statements.
ALLOWED_NODES = {
    "Select", "Column", "Identifier", "Star", "From", "Table", "Where",
    "Order", "Ordered", "Limit", "Literal", "Group", "Having", "Alias",
    "EQ", "NEQ", "GT", "GTE", "LT", "LTE", "And", "Or", "Not", "Paren",
    "Add", "Sub", "Mul", "Div", "Mod", "Neg", "Count", "Avg", "Sum",
    "Min", "Max", "Round", "Distinct", "Between", "In", "Like", "ILike",
    "Is", "Null", "Boolean", "TableAlias", "Join", "Offset"
}


def validate_query(query):
    if not query.strip() or len(query) > 5000:
        raise ValueError("Enter a SELECT query of no more than 5,000 characters.")
    try:
        statements = sqlglot.parse(query, read="postgres")
    except sqlglot.errors.ParseError as exc:
        raise ValueError("Check your SQL syntax.") from exc
    if len(statements) != 1 or not isinstance(statements[0], exp.Select):
        raise ValueError("Use one SELECT statement.")
    tree = statements[0]
    if any(type(node).__name__ not in ALLOWED_NODES for node in tree.walk()):
        raise ValueError("Use basic SELECT, WHERE, ORDER BY, LIMIT, or GROUP BY syntax for this quiz.")
    tables = list(tree.find_all(exp.Table))
    if not tables or any(t.name != "restaurants" or t.db not in ("", "public") or t.catalog for t in tables):
        raise ValueError("Query only the restaurants table.")
    # Execute the parsed/rebuilt SQL, not unchecked original input.
    return tree.sql(dialect="postgres")


def connect_database():
    user = os.environ["POSTGRES_USER"]
    if user.split(".")[0] != "quiz_reader":
        raise ValueError("Use the quiz_reader database login, not postgres.")
    return psycopg2.connect(
        host=os.environ["DB_HOST"], port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("POSTGRES_DB", "postgres"), user=user,
        password=os.environ["POSTGRES_PASSWORD"], sslmode="require",
        connect_timeout=10,
    )


def read_query(query):
    """Run a restricted query on the public quiz data in a read-only transaction."""
    safe_sql = validate_query(query)
    conn = connect_database()
    try:
        conn.set_session(readonly=True)
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '5s'")
            cur.execute("SET LOCAL search_path = public")
            cur.execute(safe_sql)
            columns = [col.name for col in cur.description]
            rows = cur.fetchmany(201)
            if len(rows) > 200:
                raise ValueError("Too many rows. Add LIMIT 200 or less.")
            return columns, rows
    finally:
        conn.rollback()
        conn.close()


def read_schema():
    """Read the real Week 7 table definition for the RAG knowledge base."""
    conn = connect_database()
    try:
        conn.set_session(readonly=True)
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '5s'")
            cur.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'restaurants'
                ORDER BY ordinal_position
            """)
            columns = cur.fetchall()
            if not columns:
                raise ValueError("The Week 7 restaurants table was not found.")
            return "Table public.restaurants:\n" + "\n".join(
                f"- {name}: {kind}, nullable={nullable}" for name, kind, nullable in columns
            )
    finally:
        conn.rollback()
        conn.close()


def run_query(token, query):
    current_user(token)  # Verify with Supabase on every run, including expired tokens.
    return read_query(query)
