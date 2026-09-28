"""Verify the six-table college fixture and reject broken relationships."""

import argparse
from datetime import datetime, timezone
import json
import sys

import mysql.connector

from manage import ROOT, HERE, STAGE, TABLES, connect, fingerprint

sys.path.insert(0, str(ROOT / 'backend'))
from services.nlp_to_sql import convert_to_sql


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', choices=[STAGE, 'college'], default=STAGE)
    args = parser.parse_args()
    conn = connect(args.database)
    cur = conn.cursor()
    checks = []

    def check(name, condition):
        if not condition:
            raise AssertionError(name)
        checks.append(name)
        print('PASS', name)

    def rows(sql):
        cur.execute(sql)
        return cur.fetchall()

    def reject(name, sql, expected_errno):
        cur.execute('SAVEPOINT invalid_probe')
        try:
            cur.execute(sql)
        except mysql.connector.Error as error:
            check(name, error.errno == expected_errno)
        else:
            raise AssertionError(name + ': invalid write accepted')
        finally:
            cur.execute('ROLLBACK TO SAVEPOINT invalid_probe')

    before = fingerprint(args.database)
    try:
        check('exactly the six requested academic tables', set(before['tables']) == set(TABLES))
        check('exactly 15 rows in every table', all(t['rows'] == 15 for t in before['tables'].values()))
        check('six simple foreign-key relationships', rows("SELECT COUNT(*) FROM information_schema.table_constraints WHERE constraint_schema=DATABASE() AND constraint_type='FOREIGN KEY'")[0][0] == 6)
        schema = {}
        for table, column, dtype in rows('SELECT table_name,column_name,data_type FROM information_schema.columns WHERE table_schema=DATABASE()'):
            schema.setdefault(table, {})[column] = dtype
        examples = []
        for table in TABLES:
            examples.append(('show ' + table, 15))
        examples += [('count students by class', 15), ('show students with marks above 80', 8),
                     ('show students with marks between 60 and 80', 5),
                     ('show top 5 results with highest marks', 5), ('show courses and faculty', 15),
                     ('show student name and class name', 15), ('show students in semester 3', 10),
                     ('average marks per course', 15), ('average marks per student', 15),
                     ('show students without results', 1), ('show faculty without courses', 5),
                     ('show faculty with experience above 10', 8), ('show courses with credits at least 4', 7),
                     ('show students in class CSE-3A', 2), ('show name and email from students', 15)]
        evidence = []
        for question, expected in examples:
            sql = convert_to_sql(question, schema=schema)
            result = rows(sql)
            check(question, len(result) == expected)
            evidence.append(dict(question=question, sql=sql, row_count=len(result)))
        check('top results rank actual exam marks', [r[3] for r in rows(convert_to_sql('show top 5 results with highest marks',schema))] == [95,92,90,88,86])
        check('student without results is Neil', rows(convert_to_sql('show students without results',schema))[0][0] == 15)
        averages = rows(convert_to_sql('average marks per student',schema))
        check('multiple results average independently per student', averages[0][2] == 89)
        check('missing marks remain NULL', averages[-1][2] is None)
        counts = rows(convert_to_sql('count students by class',schema))
        check('class counts include empty groups', [r[2] for r in counts] == [2]*5 + [1]*5 + [0]*5)
        check('every result matches the student class', rows('SELECT r.result_id FROM results r JOIN students s ON s.student_id=r.student_id JOIN exams e ON e.exam_id=r.exam_id WHERE s.class_id<>e.class_id') == [])

        reject('orphan class rejected', 'UPDATE students SET class_id=999 WHERE student_id=15', 1452)
        reject('orphan faculty rejected', 'UPDATE courses SET faculty_id=999 WHERE course_id=1', 1452)
        reject('duplicate SRN rejected', "UPDATE students SET srn='PES2026001' WHERE student_id=2", 1062)
        reject('duplicate student exam result rejected', 'UPDATE results SET exam_id=1 WHERE result_id=15', 1062)
        reject('wrong-class exam result rejected', 'UPDATE results SET exam_id=2 WHERE result_id=1', 1644)
        reject('student class cannot invalidate results', 'UPDATE students SET class_id=2 WHERE student_id=1', 1644)
        reject('exam class cannot invalidate results', 'UPDATE exams SET class_id=2 WHERE exam_id=1', 1644)
        reject('marks above 100 rejected', 'UPDATE results SET marks=101 WHERE result_id=1', 3819)
        reject('negative marks rejected', 'UPDATE results SET marks=-1 WHERE result_id=1', 3819)
        reject('invalid semester rejected', 'UPDATE classes SET semester=9 WHERE class_id=1', 3819)
        reject('deleting referenced student rejected', 'DELETE FROM students WHERE student_id=1', 1451)
        reject('deleting referenced exam rejected', 'DELETE FROM exams WHERE exam_id=1', 1451)
        cur.execute('UPDATE results SET marks=0 WHERE result_id=1')
        check('zero marks accepted', rows('SELECT marks FROM results WHERE result_id=1')[0][0] == 0)
        conn.rollback()
        after = fingerprint(args.database)
        check('verification left schema and data unchanged', before == after)
        report = dict(database=args.database, checked_at_utc=datetime.now(timezone.utc).isoformat(),
                      fingerprint=after, passed_checks=checks, examples=evidence)
        (HERE / 'verification.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        print(f'{len(checks)} checks passed.')
    finally:
        conn.rollback()
        cur.close()
        conn.close()


if __name__ == '__main__':
    main()
