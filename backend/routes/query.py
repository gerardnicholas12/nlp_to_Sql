"""The query.py file defines the /query API endpoint. It receives the users natural language query,
converts it to SQL using NLP, executes it on MySQL, and returns the result."""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import verify_jwt_in_request
from db import get_db_connection
from services.nlp_to_sql import convert_to_sql
from services.schema_service import get_schema
from services.academic_query import describe_query_semantics
from services.simple_college_query import is_simple_schema, describe_simple_query

query_bp = Blueprint("query", __name__)

@query_bp.route("/query", methods=["GET", "POST"])
def run_query():

    # For browser testing
    if request.method == "GET":
        return jsonify({"message": "Query endpoint working. Use POST with a question."})

    # Require a valid token for actual queries (both admin and user - this
    # endpoint is read-only for everyone, so no role check needed here yet)
    try:
        verify_jwt_in_request()
    except Exception:
        return jsonify({"error": "Missing or invalid token. Please log in."}), 401

    data = request.get_json(silent=True)

    # Check if question exists
    if not isinstance(data, dict) or "question" not in data:
        return jsonify({"error": "Question missing"}), 400

    question = data["question"]

    # Convert natural language to SQL
    try:
        schema = get_schema()
        sql = convert_to_sql(question, schema=schema)
    except ValueError as e:
        return jsonify({"error": str(e)}), 422

    # Safety net: /query is read-only for everyone (admin and user alike).
    # Insert/update/delete will go through separate admin-only routes once
    # those exist - this blocks it even if nlp_to_sql.py is later extended
    # to generate non-SELECT statements.
    if not sql.strip().upper().startswith("SELECT"):
        return jsonify({"error": "Only SELECT queries are allowed here."}), 403

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(sql)
        result = cursor.fetchall()
        return jsonify({
            "question": question,
            "sql": sql,
            "data": result,
            "interpretation": describe_simple_query(question) if is_simple_schema(schema) else describe_query_semantics(question),
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()
