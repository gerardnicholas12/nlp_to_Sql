"""Read-only live verification plus independent populated/empty fixture checks.

Run: backend/.venv/Scripts/python.exe backend/tests/verify_academic_system.py
Saves SQL and verification metadata, never database result rows.
"""

import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from academic_benchmark import PROMPTS, REFERENCES, ORDERED, fixture, compare
from db import get_db_connection
from services.schema_service import get_schema
from services.nlp_to_sql import convert_to_sql
from services.academic_query import describe_query_semantics


def main():
    root = Path(__file__).resolve().parents[2]
    schema = get_schema()
    live = get_db_connection()
    populated = fixture()
    empty = fixture(empty=True)
    results = []
    try:
        cursor = live.cursor()
        for item in PROMPTS:
            row = dict(item)
            try:
                sql = convert_to_sql(item['question'], schema=schema)
                row['sql'] = sql
                row['reference_sql'] = REFERENCES[item['id']]
                row['interpretation'] = describe_query_semantics(item['question'])
                for label, connection in (('populated_fixture', populated), ('empty_fixture', empty)):
                    count = compare(connection.cursor(), sql, row['reference_sql'], item['id'] in ORDERED)
                    row[label] = {'matches_reference': True, 'row_count': count}
                cursor.execute('EXPLAIN ' + sql)
                cursor.fetchall()
                count = compare(cursor, sql, row['reference_sql'], item['id'] in ORDERED)
                row['mysql'] = {'matches_reference': True, 'row_count': count}
                row['verdict'] = 'passes'
                print(item['id'], 'PASS (fixtures + MySQL)')
            except Exception as error:
                row['verdict'] = 'failed'
                # Avoid saving actual rows from a live comparison failure.
                row['error_type'] = type(error).__name__
                print(item['id'], 'FAIL', type(error).__name__)
            results.append(row)
        cursor.close()
    finally:
        live.close()
        populated.close()
        empty.close()
    artifact = {
        'checked_at_utc': datetime.now(timezone.utc).isoformat(),
        'method': 'Each of the 55 prompts compared with independent reference SQL on populated and empty SQLite fixtures and read-only MySQL. Required fields, values, multiplicity and ranking checked; extra useful columns permitted.',
        'semantics': {
            'student_attendance': 'Stored students.attendance percentage; missing values excluded from averages/rankings.',
            'course_attendance': 'Recorded Present entries / recorded Present plus Absent entries * 100; NULL when there are no records.',
            'computer_science_students': 'students.subject = Computer Science',
            'database_course_alias': 'Database Management Systems',
            'counts': 'Distinct students/courses where counted; enrollment count counts enrollment records. Empty groups included.',
            'ties': 'Singular rankings return one row, top N returns N rows; primary key provides deterministic tie order.',
        },
        'totals': dict(Counter(row['verdict'] for row in results)),
        'source_sha256': {str(p.relative_to(root)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest() for p in (root / 'backend/services/academic_query.py', root / 'backend/services/nlp_to_sql.py', root / 'backend/mappings.py')},
        'results': results,
    }
    output = root / 'reports/query_verification_after.json'
    output.write_text(json.dumps(artifact, indent=2), encoding='utf-8')
    print('TOTAL', artifact['totals'])
    print('Evidence:', output)
    return 1 if artifact['totals'].get('failed') else 0


if __name__ == '__main__':
    raise SystemExit(main())
