"""Resolve enrollment clauses before the general keyword parser sees them.

Department names belong to the related course here. Removing that clause
from the outer question prevents names like "Computer Science" or "English"
from also becoming filters on students.subject.
"""

import re

from mappings import RELATIONSHIPS, TABLE_MAP


ENROLLED_COURSES = re.compile(
    r"\b(?P<negated>not\s+)?enrolled\s+(?:in|on)\s+(?:the\s+)?courses?\b",
    re.IGNORECASE,
)
DEPARTMENT_LINK = r"\s+(?:(?:offered|provided|run)\s+by|from|in|of)\s+(?:the\s+)?"
DEPARTMENT_NAME = r'''(?:"[^"]+"|'[^']+'|[\w][\w\s&'/-]*?)'''
NAMED_DEPARTMENT = re.compile(
    DEPARTMENT_LINK + r"(?P<name>" + DEPARTMENT_NAME + r")\s+(?:department|dept)\b",
    re.IGNORECASE,
)
DEPARTMENT_NAMED = re.compile(
    DEPARTMENT_LINK + r"(?:department|dept)\s+(?:of\s+|named\s+)?"
    r"(?P<name>" + DEPARTMENT_NAME + r")"
    r"(?=\s+(?:where|with|whose|having|order|sort|limit)\b|[?.!]?$)",
    re.IGNORECASE,
)


def _relationship_path(tables, schema):
    """Render each FK with its own column name, validating the live schema."""
    conditions = []
    for left, right in zip(tables, tables[1:]):
        for local, local_col, foreign, foreign_col in RELATIONSHIPS:
            if (local, foreign) == (left, right):
                left_col, right_col = local_col, foreign_col
            elif (foreign, local) == (left, right):
                left_col, right_col = foreign_col, local_col
            else:
                continue
            if left_col not in schema.get(left, ()) or right_col not in schema.get(right, ()):
                raise ValueError("The enrollment relationship does not match the database schema.")
            conditions.append(f"{left}.{left_col} = {right}.{right_col}")
            break
        else:
            raise ValueError(f"No enrollment relationship is defined between {left} and {right}.")
    return conditions


def extract_enrollment_filter(question, schema):
    """Return the outer question and a correlated enrollment condition, if any.

    This handles student enrollment requests, including an optional course
    department. Other query intents continue through the general parser.
    """
    match = ENROLLED_COURSES.search(question)
    if not match:
        return question, None
    outer_question = question[:match.start()]
    owners = [TABLE_MAP[word] for word in re.findall(r"\w+", outer_question.lower()) if word in TABLE_MAP]
    if not owners or owners[0] != "students":
        return question, None

    tail = question[match.end():]
    department_match = DEPARTMENT_NAMED.match(tail) or NAMED_DEPARTMENT.match(tail)
    department_name = None
    if department_match:
        department_name = department_match.group("name").strip().strip("\"'")
        tail = tail[department_match.end():]
    elif re.match(r"\s+(?:offered|provided|run|from|in|of)\b", tail, re.IGNORECASE):
        raise ValueError("Specify the course department, for example 'courses offered by the Computer Science department'.")

    tables = ["students", "enrollments", "courses"]
    if department_name is not None:
        tables.append("departments")
        if "department_name" not in schema.get("departments", ()):
            raise ValueError("The departments table has no department_name column.")
    relationships = _relationship_path(tables, schema)
    sql = "SELECT 1 FROM enrollments"
    for table, condition in zip(tables[2:], relationships[1:]):
        sql += f" JOIN {table} ON {condition}"
    sql += f" WHERE {relationships[0]}"
    if department_name is not None:
        # The API returns SQL text, so literals must be escaped for MySQL.
        literal = department_name.replace("\\", "\\\\").replace("'", "''")
        sql += f" AND departments.department_name = '{literal}'"
    exists = "NOT EXISTS" if match.group("negated") else "EXISTS"
    return outer_question + " " + tail, f"{exists} ({sql})"
