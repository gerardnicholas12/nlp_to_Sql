"""Create a separate college demo database. Never reset an existing database.

Run from the repository root:
  backend/.venv/Scripts/python.exe database/college_v2/setup.py --database college_v2
"""

import argparse
from datetime import date, datetime, timedelta
from pathlib import Path
import re

import mysql.connector
from dotenv import dotenv_values

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def connect(database=None):
    config = dotenv_values(ROOT / 'backend' / '.env')
    options = dict(host=config.get('DB_HOST'), user=config.get('DB_USER'),
                   password=config.get('DB_PASSWORD'), connection_timeout=10)
    if config.get('DB_PORT'):
        options['port'] = int(config['DB_PORT'])
    if database:
        options['database'] = database
    return mysql.connector.connect(**options)


def statements(path):
    # These project SQL files use only standalone -- comments and simple SQL.
    # Deliberately not a general SQL dump parser.
    sql = '\n'.join(line for line in path.read_text(encoding='utf-8').splitlines()
                    if not line.lstrip().startswith('--'))
    return [part.strip() for part in sql.split(';') if part.strip()]


def seed(cursor):
    def insert(table, columns, rows):
        if rows:
            placeholders = ', '.join(['%s'] * len(columns))
            cursor.executemany(f'INSERT INTO {table} ({", ".join(columns)}) VALUES ({placeholders})', rows)

    insert('departments', ['department_id', 'department_code', 'department_name', 'location'], [
        (1, 'CSE', 'Computer Science', 'North Block'),
        (2, 'ECE', 'Electronics', 'East Block'),
        (3, 'MAT', 'Mathematics', 'West Block'),
        (4, 'HUM', 'Humanities', 'South Block'),
    ])
    insert('programs', ['program_id', 'department_id', 'program_code', 'program_name', 'duration_semesters'], [
        (1, 1, 'BTECH-CS', 'BTech Computer Science', 8),
        (2, 2, 'BTECH-EC', 'BTech Electronics', 8),
        (3, 3, 'BSC-MATH', 'BSc Mathematics', 6),
    ])
    first_names = ['Aarav', 'Diya', 'Kabir', 'Meera', 'Ishaan', 'Ananya', 'Rohan', 'Tara']
    last_names = ['Sharma', 'Nair', 'Patel', 'Rao', 'Das', 'Singh']
    insert('students', ['student_id', 'program_id', 'roll_number', 'student_name', 'email', 'date_of_birth', 'admitted_on', 'city'], [
        (i, (i - 1) // 16 + 1, f'2024-{i:03d}', f'{first_names[(i-1) % 8]} {last_names[(i-1) // 8]}',
         f'student{i:03d}@example.invalid', date(2005, (i-1) % 12 + 1, (i-1) % 27 + 1),
         date(2024, 7, 1), ['Chennai', 'Bengaluru', 'Kochi', 'Hyderabad'][(i-1) % 4])
        for i in range(1, 49)
    ])
    insert('teachers', ['teacher_id', 'department_id', 'teacher_name', 'email', 'hired_on', 'salary'], [
        (i, dept, name, f'teacher{i}@example.invalid', date(2015 + i, 6, 1), 50000 + i * 5000)
        for i, dept, name in [(1, 1, 'Anita Menon'), (2, 1, 'Vikram Shah'), (3, 1, 'Priya Rao'),
                              (4, 2, 'Sanjay Das'), (5, 2, 'Neha Kumar'), (6, 3, 'Arjun Iyer'),
                              (7, 3, 'Kavya Patel'), (8, 3, 'Maya Bose')]
    ])
    insert('courses', ['course_id', 'department_id', 'course_code', 'course_name', 'credits'], [
        (1, 1, 'CS101', 'Programming Fundamentals', 4),
        (2, 1, 'CS201', 'Database Management Systems', 4),
        (3, 1, 'CS202', 'Data Structures', 4),
        (4, 1, 'CS301', 'Machine Learning', 3),
        (5, 2, 'EC101', 'Digital Electronics', 4),
        (6, 2, 'EC201', 'Embedded Systems', 3),
        (7, 3, 'MA101', 'Calculus', 4),
        (8, 3, 'MA201', 'Statistics', 3),
        (9, 3, 'MA301', 'Numerical Methods', 3),
    ])
    insert('terms', ['term_id', 'term_code', 'starts_on', 'ends_on'], [
        (1, '2025-ODD', date(2025, 7, 1), date(2025, 12, 15)),
        (2, '2026-EVEN', date(2026, 1, 5), date(2026, 5, 30)),
        (3, '2026-ODD', date(2026, 7, 1), date(2026, 12, 15)),
    ])
    # Same course in different terms AND parallel sections in the current term.
    offerings = [(1, 1, 1, 'A', 30), (2, 7, 1, 'A', 30), (3, 5, 1, 'A', 30),
                 (4, 2, 2, 'A', 30), (5, 3, 2, 'A', 30), (6, 8, 2, 'A', 30),
                 (7, 2, 3, 'A', 30), (8, 2, 3, 'B', 30), (9, 3, 3, 'A', 30),
                 (10, 4, 3, 'A', 30), (11, 5, 3, 'A', 30), (12, 6, 3, 'A', 30),
                 (13, 7, 3, 'A', 30), (14, 8, 3, 'A', 30), (15, 9, 3, 'A', 30)]
    insert('course_offerings', ['offering_id', 'course_id', 'term_id', 'section_code', 'capacity'], offerings)
    teacher_for_course = {1: 1, 2: 2, 3: 3, 4: 1, 5: 4, 6: 5, 7: 6, 8: 7, 9: 6}
    assignments = [(o, teacher_for_course[c], 'instructor') for o, c, _, _, _ in offerings]
    assignments += [(7, 3, 'assistant'), (10, 7, 'assistant')]
    insert('teaching_assignments', ['offering_id', 'teacher_id', 'teaching_role'], assignments)
    insert('course_prerequisites', ['course_id', 'prerequisite_course_id'], [(2, 1), (3, 1), (4, 3), (4, 8), (6, 5), (8, 7), (9, 7)])

    # Student 48, teacher 8, department 4 and offering 15 have no related activity.
    members = {1: range(1, 33), 2: range(1, 48), 3: range(17, 33),
               4: range(1, 17), 5: range(1, 17), 6: range(1, 48),
               7: range(1, 9), 8: range(9, 17), 9: range(17, 25),
               10: range(1, 9), 11: range(25, 33), 12: range(17, 25),
               13: range(33, 41), 14: range(1, 48), 15: []}
    # Historical offerings with larger classes are explicitly assigned capacity 60.
    cursor.execute('UPDATE course_offerings SET capacity=60 WHERE offering_id IN (1,2,6,14)')
    enrollments, sessions, attendances, assessments, results = [], [], [], [], []
    term_bases = {1: date(2025, 7, 1), 2: date(2026, 1, 5), 3: date(2026, 7, 1)}
    for offering, course, term, section, capacity in offerings:
        start = term_bases[term]
        if offering != 15:
            for n in range(1, 7):
                sessions.append((offering, n, datetime.combine(start + timedelta(days=7*n), datetime.min.time()).replace(hour=9 + offering % 8), 60, f'R-{offering:02d}'))
            for n, name, kind in [(1, 'Quiz 1', 'quiz'), (2, 'Midterm', 'exam'), (3, 'Project', 'project')]:
                assessments.append((offering, n, name, kind, start + timedelta(days=14*n)))
        for student in members[offering]:
            status = 'completed' if term < 3 else ('withdrawn' if (offering, student) == (14, 47) else 'enrolled')
            enrollments.append((offering, student, start, status))
            for n in range(1, 7):
                if (student + n + offering) % 17 == 0 or (status == 'withdrawn' and n > 2):
                    continue  # Unrecorded is unknown, never an implicit absence.
                bucket = (student + n + offering) % 10
                state = 'absent' if bucket < 2 else ('late' if bucket == 2 else ('excused' if bucket == 3 else 'present'))
                attendances.append((offering, n, student, state))
            for n in range(1, 4):
                if status == 'withdrawn' or (term == 3 and n == 3 and student % 5 == 0):
                    continue
                score = 35 + (student * 7 + offering * 3 + n * 11) % 66
                # Everyone has passed seeded prerequisites before advanced offerings.
                if term < 3:
                    score = max(50, score)
                results.append((offering, n, student, score))
    insert('enrollments', ['offering_id', 'student_id', 'enrolled_on', 'enrollment_status'], enrollments)
    insert('class_sessions', ['offering_id', 'session_no', 'starts_at', 'duration_minutes', 'room'], sessions)
    insert('attendance', ['offering_id', 'session_no', 'student_id', 'attendance_status'], attendances)
    insert('assessments', ['offering_id', 'assessment_no', 'assessment_name', 'assessment_type', 'held_on'], assessments)
    insert('assessment_results', ['offering_id', 'assessment_no', 'student_id', 'score_percent'], results)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', default='college_v2')
    args = parser.parse_args()
    # Restrict the tool to clearly separate candidate databases.
    if not re.fullmatch(r'college_v2(?:_[a-z0-9_]+)?', args.database) or len(args.database) > 64:
        parser.error('Use college_v2 or college_v2_<suffix>. Existing databases are never reset.')
    live_name = dotenv_values(ROOT / 'backend' / '.env').get('DB_NAME')
    if args.database == live_name:
        parser.error('Refusing to use the database currently configured in backend/.env.')
    connection = connect()
    cursor = connection.cursor()
    try:
        # No IF NOT EXISTS: fail before touching tables when the name is occupied.
        cursor.execute(f'CREATE DATABASE `{args.database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci')
        connection.database = args.database
        for sql in statements(HERE / 'schema.sql'):
            cursor.execute(sql)
        seed(cursor)
        connection.commit()
        print(f'Created {args.database} with synthetic academic data and zero login accounts.')
        print('backend/.env and the existing application database were not changed.')
    except Exception:
        connection.rollback()
        # DDL is not transactional. Leave any new, partial database for inspection.
        # Never clean up by dropping a database automatically.
        raise
    finally:
        cursor.close()
        connection.close()


if __name__ == '__main__':
    main()
