"""Verify a synthetic college_v2 database. Rejected writes are rolled back.

Run: backend/.venv/Scripts/python.exe database/college_v2/verify.py --database college_v2
This deliberately checks the candidate directly, not the old NLP application.
"""

import argparse
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import json
import re

import mysql.connector

from setup import HERE, ROOT, connect, statements
from dotenv import dotenv_values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', default='college_v2')
    args = parser.parse_args()
    if not re.fullmatch(r'college_v2(?:_[a-z0-9_]+)?', args.database):
        parser.error('Only a separately created college_v2 candidate may be tested.')
    if args.database == dotenv_values(ROOT / 'backend' / '.env').get('DB_NAME'):
        parser.error('Refusing mutation probes against the active application database.')
    connection = connect(args.database)
    cursor = connection.cursor()
    checks = []

    def expect(name, condition):
        if not condition:
            raise AssertionError(name)
        checks.append(name)
        print('PASS', name)

    def query(sql):
        cursor.execute(sql)
        return cursor.fetchall()

    def reject(name, sql, errno):
        cursor.execute('SAVEPOINT constraint_probe')
        try:
            cursor.execute(sql)
        except mysql.connector.Error as error:
            expect(name, error.errno == errno)
        else:
            raise AssertionError(f'{name}: invalid write was accepted')
        finally:
            cursor.execute('ROLLBACK TO SAVEPOINT constraint_probe')

    try:
        tables = [row[0] for row in query('SHOW TABLES')]
        expect('15 tables created', len(tables) == 15)
        row_counts = {table: query(f'SELECT COUNT(*) FROM `{table}`')[0][0] for table in tables}
        expect('48 synthetic students', row_counts['students'] == 48)
        expect('no seeded login accounts', row_counts['app_users'] == 0)
        expect('enrollments fit capacity', query('''
            SELECT o.offering_id FROM course_offerings o JOIN enrollments e USING (offering_id)
            WHERE e.enrollment_status <> 'withdrawn'
            GROUP BY o.offering_id, o.capacity HAVING COUNT(*) > o.capacity
        ''') == [])
        expect('session dates inside offering term', query('''
            SELECT cs.offering_id FROM class_sessions cs
            JOIN course_offerings o USING (offering_id) JOIN terms t USING (term_id)
            WHERE DATE(cs.starts_at) NOT BETWEEN t.starts_on AND t.ends_on
        ''') == [])
        expect('assessment dates inside offering term', query('''
            SELECT a.offering_id FROM assessments a
            JOIN course_offerings o USING (offering_id) JOIN terms t USING (term_id)
            WHERE a.held_on NOT BETWEEN t.starts_on AND t.ends_on
        ''') == [])
        outputs = [query(sql) for sql in statements(HERE / 'examples.sql')]
        expect('10 example SQL queries execute', len(outputs) == 10)
        expect('term and section enrollment query', [r[0] for r in outputs[0]] == list(range(1, 17)))
        expect('home departments include zero students', [r[1] for r in outputs[1]] == [16, 16, 16, 0])
        expect('cross-department study present', len(outputs[2]) > 0)
        expect('attendance threshold query has valid percentages', bool(outputs[3]) and all(0 <= r[4] < 75 for r in outputs[3]))
        expect('ranking query includes complete results', bool(outputs[4]) and all(1 <= r[3] <= 3 for r in outputs[4]))
        expect('teacher without current assignments', [r[0] for r in outputs[5]] == [8])
        expect('co-teaching query avoids duplicate assignments', [(r[0], r[4]) for r in outputs[6]] == [(7, 2), (10, 2)])
        expect('student without enrollments', [r[0] for r in outputs[7]] == [48])
        expect('recursive prerequisites cover both branches', [r[0] for r in outputs[8]] == ['CS101', 'CS202', 'MA101', 'MA201'])
        expect('empty offering included and withdrawn enrollment excluded', [(r[0], r[4]) for r in outputs[9]] == [(7,8), (8,8), (9,8), (10,8), (11,8), (12,8), (13,8), (14,46), (15,0)])

        # Independently compute attendance and final ranks from base rows in Python.
        active = {r for r in query("SELECT e.offering_id, e.student_id FROM enrollments e JOIN course_offerings o USING (offering_id) WHERE o.term_id=3 AND e.enrollment_status <> 'withdrawn'")}
        tally = {}
        for offering, student, status in query('SELECT offering_id, student_id, attendance_status FROM attendance'):
            if (offering, student) in active and status != 'excused':
                numbers = tally.setdefault((offering, student), [0, 0])
                numbers[0] += status in ('present', 'late')
                numbers[1] += 1
        actual_low = query('''
            SELECT a.offering_id, a.student_id FROM attendance a
            JOIN enrollments e USING (offering_id, student_id)
            JOIN course_offerings o USING (offering_id)
            WHERE o.term_id=3 AND e.enrollment_status <> 'withdrawn'
            GROUP BY a.offering_id, a.student_id
            HAVING ROUND(100.0 * SUM(a.attendance_status IN ('present','late')) /
                NULLIF(SUM(a.attendance_status IN ('present','late','absent')),0), 2) < 75
        ''')
        expect('attendance matches independent calculation', set(actual_low) == {key for key, (p, n) in tally.items() if round(100*p/n, 2) < 75})

        assessment_counts = dict(query('SELECT offering_id, COUNT(*) FROM assessments GROUP BY offering_id'))
        eligible = set(query("SELECT offering_id, student_id FROM enrollments WHERE enrollment_status <> 'withdrawn'"))
        student_names = dict(query('SELECT student_id, student_name FROM students'))
        score_groups = {}
        for offering, student, score in query('SELECT offering_id, student_id, score_percent FROM assessment_results'):
            score_groups.setdefault((offering, student), []).append(score)
        averages = {key: sum(scores) / len(scores) for key, scores in score_groups.items()
                    if key in eligible and len(scores) == assessment_counts[key[0]]}
        score_levels = {offering: sorted({avg for (owner, student), avg in averages.items() if owner == offering}, reverse=True)
                        for offering in assessment_counts}
        expected_ranks = set()
        for (offering, student), average in averages.items():
            rank = score_levels[offering].index(average) + 1
            if rank <= 3:
                expected_ranks.add((offering, student_names[student], average.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP), rank))
        expect('complete-score ranks match independent calculation', set(outputs[4]) == expected_ranks)

        reject('orphan student program rejected', "INSERT INTO students VALUES (999,999,'TEST','Test','test@example.invalid','2000-01-01','2024-01-01',NULL)", 1452)
        reject('duplicate enrollment rejected', "INSERT INTO enrollments VALUES (7,1,'2026-07-01','enrolled')", 1062)
        reject('duplicate section rejected', "INSERT INTO course_offerings VALUES (999,2,3,'A',30)", 1062)
        reject('attendance without enrollment rejected', "INSERT INTO attendance VALUES (7,1,48,'present')", 1452)
        reject('attendance in wrong section rejected', "INSERT INTO attendance VALUES (8,1,1,'present')", 1452)
        reject('attendance for missing session rejected', "INSERT INTO attendance VALUES (7,99,1,'present')", 1452)
        reject('assessment result in wrong section rejected', "INSERT INTO assessment_results VALUES (8,1,1,75)", 1452)
        reject('result for missing assessment rejected', "INSERT INTO assessment_results VALUES (7,99,1,75)", 1452)
        reject('score above 100 rejected', "UPDATE assessment_results SET score_percent=101 WHERE offering_id=7 AND assessment_no=1 AND student_id=1", 3819)
        reject('negative score rejected', "UPDATE assessment_results SET score_percent=-1 WHERE offering_id=7 AND assessment_no=1 AND student_id=1", 3819)
        reject('invalid attendance status rejected', "UPDATE attendance SET attendance_status='unknown' WHERE offering_id=7 AND session_no=1 AND student_id=1", 3819)
        reject('self prerequisite rejected', "INSERT INTO course_prerequisites VALUES (1,1)", 3819)
        reject('invalid term dates rejected', "INSERT INTO terms VALUES (999,'INVALID','2026-12-01','2026-01-01')", 3819)
        reject('deleting referenced student rejected', 'DELETE FROM students WHERE student_id=1', 1451)
        reject('deleting referenced offering rejected', 'DELETE FROM course_offerings WHERE offering_id=7', 1451)
        cursor.execute('SAVEPOINT valid_probe')
        cursor.execute('UPDATE assessment_results SET score_percent=0 WHERE offering_id=7 AND assessment_no=1 AND student_id=1')
        expect('zero is a valid score', query('SELECT score_percent FROM assessment_results WHERE offering_id=7 AND assessment_no=1 AND student_id=1')[0][0] == 0)
        cursor.execute('ROLLBACK TO SAVEPOINT valid_probe')
        connection.rollback()
        expect('verification preserves all row counts', row_counts == {table: query(f'SELECT COUNT(*) FROM `{table}`')[0][0] for table in tables})
        fk_count = query("SELECT COUNT(*) FROM information_schema.table_constraints WHERE constraint_schema=DATABASE() AND constraint_type='FOREIGN KEY'")[0][0]
        report = dict(database=args.database, checked_at_utc=datetime.now(timezone.utc).isoformat(),
                      server_version=query('SELECT VERSION()')[0][0], table_count=len(tables),
                      foreign_key_count=fk_count, row_counts=row_counts,
                      example_query_row_counts=[len(rows) for rows in outputs], passed_checks=checks,
                      scope='Candidate database only. Existing NLP application has not been migrated or validated against this schema.')
        (HERE / 'verification.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        print(f'{len(checks)} checks passed; {fk_count} foreign keys; evidence: {HERE / "verification.json"}')
    finally:
        connection.rollback()
        cursor.close()
        connection.close()


if __name__ == '__main__':
    main()
