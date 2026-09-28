"""Independent reference SQL and populated/empty fixtures for the 55 prompts.

Production uses scalar correlated metrics; these references predominantly use
joins, GROUP BY and HAVING. Output values, multiplicity, required fields and
ranking are checked, allowing extra useful output fields.
"""

import json
import sqlite3
from collections import Counter
from numbers import Number
from pathlib import Path

PROMPTS = json.loads(Path(__file__).with_name('audit_prompts.json').read_text())
DEPT_TEACHERS = "SELECT d.department_id, d.department_name, COUNT(t.teacher_id) AS teacher_count FROM departments d LEFT JOIN teachers t ON t.department_id = d.department_id GROUP BY d.department_id, d.department_name"
COURSE_STUDENTS = "SELECT c.course_id, c.course_name, COUNT(DISTINCT e.student_id) AS student_count FROM courses c LEFT JOIN enrollments e ON e.course_id = c.course_id GROUP BY c.course_id, c.course_name"
STUDENT_COURSES = "SELECT s.id, s.name, COUNT(DISTINCT e.course_id) AS course_count FROM students s LEFT JOIN enrollments e ON e.student_id = s.id"
STUDENT_GROUP = " GROUP BY s.id, s.name"
COURSE_ATTENDANCE = "SELECT c.course_id, c.course_name, 100.0 * SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) / COUNT(a.attendance_id) AS average_attendance FROM courses c LEFT JOIN attendance a ON a.course_id = c.course_id GROUP BY c.course_id, c.course_name"
DEPT_STUDENTS = "SELECT d.department_id, d.department_name, COUNT(DISTINCT e.student_id) AS student_count FROM departments d LEFT JOIN courses c ON c.department_id = d.department_id LEFT JOIN enrollments e ON e.course_id = c.course_id GROUP BY d.department_id, d.department_name"
PAIRS = "SELECT DISTINCT s.id, s.name, c.course_id, c.course_name FROM students s LEFT JOIN enrollments e ON e.student_id = s.id LEFT JOIN courses c ON c.course_id = e.course_id"
TEACHERS = "SELECT t.teacher_id, t.teacher_name, d.department_name FROM teachers t LEFT JOIN departments d ON d.department_id = t.department_id"
DETAILS = "SELECT a.*, s.name, c.course_name FROM attendance a JOIN students s ON s.id = a.student_id JOIN courses c ON c.course_id = a.course_id"


REFERENCES = {
    'T01': TEACHERS,
    'T02': TEACHERS,
    'T03': TEACHERS + " WHERE d.department_name = 'Computer Science'",
    'T04': DEPT_TEACHERS,
    'T05': DEPT_TEACHERS + " ORDER BY teacher_count DESC, d.department_id ASC LIMIT 1",
    'T06': DEPT_TEACHERS + " ORDER BY teacher_count ASC, d.department_id ASC LIMIT 1",
    'T07': "SELECT d.department_name, t.teacher_name FROM teachers t LEFT JOIN departments d ON d.department_id = t.department_id",
    'T08': DEPT_TEACHERS + " HAVING COUNT(t.teacher_id) > 5",
    'T09': TEACHERS + " WHERE t.department_id = 2",
    'T10': "SELECT DISTINCT d.department_id, d.department_name FROM departments d JOIN teachers t ON t.department_id = d.department_id",
    'E01': PAIRS,
    'E02': "SELECT DISTINCT s.id, s.name, c.course_id, c.course_name FROM courses c LEFT JOIN enrollments e ON e.course_id = c.course_id LEFT JOIN students s ON s.id = e.student_id",
    'E03': "SELECT DISTINCT s.id, s.name FROM students s JOIN enrollments e ON e.student_id = s.id JOIN courses c ON c.course_id = e.course_id WHERE c.course_name = 'Database Management Systems'",
    'E04': "SELECT DISTINCT s.id, s.name FROM students s JOIN enrollments e ON e.student_id = s.id JOIN courses c ON c.course_id = e.course_id WHERE c.course_name = 'Python'",
    'E05': COURSE_STUDENTS,
    'E06': COURSE_STUDENTS + " ORDER BY student_count DESC, c.course_id ASC LIMIT 1",
    'E07': COURSE_STUDENTS + " ORDER BY student_count ASC, c.course_id ASC LIMIT 1",
    'E08': COURSE_STUDENTS + " HAVING COUNT(DISTINCT e.student_id) > 20",
    'E09': COURSE_STUDENTS + " HAVING COUNT(DISTINCT e.student_id) < 10",
    'E10': STUDENT_COURSES + STUDENT_GROUP + " HAVING COUNT(DISTINCT e.course_id) > 3",
    'E11': STUDENT_COURSES + STUDENT_GROUP,
    'E12': "SELECT s.id, s.name FROM students s LEFT JOIN enrollments e ON e.student_id = s.id WHERE e.enrollment_id IS NULL",
    'E13': "SELECT c.course_id, c.course_name FROM courses c LEFT JOIN enrollments e ON e.course_id = c.course_id WHERE e.enrollment_id IS NULL",
    'E14': "SELECT e.*, s.name FROM enrollments e JOIN students s ON s.id = e.student_id",
    'E15': "SELECT e.*, c.course_name FROM enrollments e JOIN courses c ON c.course_id = e.course_id",
    'A01': "SELECT id, name, attendance FROM students",
    'A02': "SELECT id, name, attendance FROM students WHERE attendance < 75",
    'A03': "SELECT id, name, attendance FROM students WHERE attendance > 90",
    'A04': "SELECT id, name, attendance FROM students WHERE attendance IS NOT NULL ORDER BY attendance DESC, id ASC LIMIT 1",
    'A05': "SELECT id, name, attendance FROM students WHERE attendance IS NOT NULL ORDER BY attendance ASC, id ASC LIMIT 1",
    'A06': "SELECT AVG(attendance) AS average_attendance FROM students",
    'A07': COURSE_ATTENDANCE,
    'A08': DETAILS + " WHERE c.course_name = 'Database Management Systems'",
    'A09': DETAILS + " WHERE c.course_name = 'Python'",
    'A10': "SELECT id, name, attendance FROM students WHERE attendance BETWEEN 75 AND 90",
    'A11': "SELECT COUNT(*) AS student_count FROM students WHERE attendance < 75",
    'A12': "SELECT COUNT(*) AS student_count FROM students WHERE attendance > 90",
    'A13': COURSE_ATTENDANCE + " HAVING 100.0 * SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) / COUNT(a.attendance_id) < 75",
    'A14': COURSE_ATTENDANCE + " HAVING 100.0 * SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) / COUNT(a.attendance_id) > 85",
    'A15': "SELECT id, name, attendance FROM students ORDER BY attendance IS NULL ASC, attendance DESC, id ASC",
    'X181': DEPT_STUDENTS + " ORDER BY student_count DESC, d.department_id ASC LIMIT 1",
    'X182': COURSE_STUDENTS + " ORDER BY student_count DESC, c.course_id ASC LIMIT 5",
    'X183': STUDENT_COURSES + " WHERE s.attendance < 75" + STUDENT_GROUP + " HAVING COUNT(DISTINCT e.course_id) > 2",
    'X184': COURSE_ATTENDANCE,
    'X185': "SELECT t.teacher_id, t.teacher_name, COUNT(c.course_id) AS course_count FROM teachers t LEFT JOIN courses c ON c.teacher_id = t.teacher_id GROUP BY t.teacher_id, t.teacher_name ORDER BY course_count DESC, t.teacher_id ASC LIMIT 1",
    'X186': PAIRS + " WHERE LOWER(s.subject) = 'computer science'",
    'X187': "SELECT counts.course_id, counts.course_name, counts.student_count, scores.average_attendance FROM (" + COURSE_STUDENTS + ") counts JOIN (" + COURSE_ATTENDANCE + ") scores ON scores.course_id = counts.course_id WHERE counts.student_count > 20 AND scores.average_attendance > 80",
    'X188': "SELECT d.department_id, d.department_name, COUNT(DISTINCT t.teacher_id) AS teacher_count, COUNT(DISTINCT c.course_id) AS course_count, COUNT(DISTINCT e.student_id) AS student_count FROM departments d LEFT JOIN teachers t ON t.department_id = d.department_id LEFT JOIN courses c ON c.department_id = d.department_id LEFT JOIN enrollments e ON e.course_id = c.course_id GROUP BY d.department_id, d.department_name",
    'X189': "SELECT DISTINCT s.id, s.name FROM students s JOIN enrollments e ON e.student_id = s.id JOIN courses c ON c.course_id = e.course_id WHERE c.course_name = 'Database Management Systems' AND s.id NOT IN (SELECT e2.student_id FROM enrollments e2 JOIN courses c2 ON c2.course_id = e2.course_id WHERE c2.course_name = 'Python')",
    'X190': "SELECT id, name, attendance FROM students WHERE attendance IS NOT NULL ORDER BY attendance DESC, id ASC LIMIT 5",
    'X191': "SELECT d.department_id, d.department_name, AVG(s.marks) AS average_marks FROM departments d LEFT JOIN (SELECT DISTINCT c.department_id, e.student_id FROM courses c JOIN enrollments e ON e.course_id = c.course_id) member ON member.department_id = d.department_id LEFT JOIN students s ON s.id = member.student_id GROUP BY d.department_id, d.department_name HAVING AVG(s.marks) IS NOT NULL ORDER BY average_marks DESC, d.department_id ASC LIMIT 1",
    'X192': STUDENT_COURSES + " WHERE s.attendance > 80" + STUDENT_GROUP + " HAVING COUNT(DISTINCT e.course_id) > 3",
    'X193': "SELECT c.course_id, c.course_name FROM courses c LEFT JOIN enrollments e ON e.course_id = c.course_id WHERE e.enrollment_id IS NULL",
    'X194': "SELECT d.department_id, d.department_name FROM departments d LEFT JOIN teachers t ON t.department_id = d.department_id WHERE t.teacher_id IS NULL",
    'X195': "SELECT c.course_id, c.course_name, COUNT(e.enrollment_id) AS enrollment_count FROM courses c LEFT JOIN enrollments e ON e.course_id = c.course_id GROUP BY c.course_id, c.course_name ORDER BY enrollment_count DESC, c.course_id ASC LIMIT 1",
}
ORDERED = {'T05', 'T06', 'E06', 'E07', 'A04', 'A05', 'A15', 'X181', 'X182', 'X185', 'X190', 'X191', 'X195'}


def fixture(empty=False):
    db = sqlite3.connect(':memory:')
    db.row_factory = sqlite3.Row
    db.executescript("""
        CREATE TABLE students (id INT, name TEXT, marks INT, age INT, gender TEXT, city TEXT, semester INT, attendance REAL, subject TEXT, blood_groupp TEXT);
        CREATE TABLE employees (id INT, name TEXT, salary INT, department TEXT, age INT, gender TEXT, city TEXT, experience INT, joining_year INT);
        CREATE TABLE departments (department_id INT, department_name TEXT, location TEXT);
        CREATE TABLE teachers (teacher_id INT, teacher_name TEXT, email TEXT, department_id INT, salary INT);
        CREATE TABLE courses (course_id INT, course_name TEXT, credits INT, department_id INT, teacher_id INT);
        CREATE TABLE enrollments (enrollment_id INT, student_id INT, course_id INT, enrollment_date TEXT, grade TEXT);
        CREATE TABLE attendance (attendance_id INT, student_id INT, course_id INT, attendance_date TEXT, status TEXT);
        INSERT INTO students (id, name, marks, attendance, subject) VALUES
            (1, 'Ada', 85, 70, 'Computer Science'), (2, 'Ben', 60, 95, 'Mathematics'),
            (3, 'Cora', 98, 80, 'Computer Science'), (4, 'Dan', 75, 95, 'English'), (5, 'Eve', 99, NULL, 'Science');
        INSERT INTO departments (department_id, department_name) VALUES
            (1, 'Computer Science'), (2, 'Mathematics'), (3, 'English'), (4, 'Empty');
        INSERT INTO teachers (teacher_id, teacher_name, department_id) VALUES
            (10, 'Alpha', 1), (20, 'Beta', 1), (30, 'Gamma', 2), (40, 'Delta', NULL);
        INSERT INTO courses (course_id, course_name, department_id, teacher_id) VALUES
            (100, 'Database Management Systems', 1, 10), (200, 'Python', 1, 10),
            (300, 'Calculus', 2, 30), (400, 'Writing', 3, NULL), (500, 'Networks', 1, 20);
        INSERT INTO enrollments (enrollment_id, student_id, course_id) VALUES
            (1000, 1, 100), (1001, 1, 200), (1002, 2, 100),
            (1003, 3, 300), (1004, 4, 100), (1005, 4, 200);
    """)
    if empty:
        for table in ('attendance', 'enrollments', 'courses', 'teachers', 'departments', 'students', 'employees'):
            db.execute('DELETE FROM ' + table)
        return db
    db.executemany("INSERT INTO teachers (teacher_id, teacher_name, department_id) VALUES (?, ?, 1)", [(i, f'Teacher {i}') for i in (50, 60, 70, 80)])
    db.executemany("INSERT INTO courses (course_id, course_name, department_id, teacher_id) VALUES (?, ?, 1, ?)", [(600, 'Ten students', 10), (700, 'Twenty students', 20)])
    db.executemany("INSERT INTO students (id, name, marks, attendance, subject) VALUES (?, ?, ?, ?, 'Mathematics')", [(i, f'Student {i}', 60 + i % 4, (75, 80, 85, 90, 95)[i % 5]) for i in range(100, 125)])
    rows = [(1, 300), (1, 500), (2, 200), (2, 300), (2, 500), (1, 100)]
    rows += [(i, 100) for i in range(100, 125)]
    rows += [(i, 200) for i in range(100, 108)]
    rows += [(i, 600) for i in range(100, 110)]
    rows += [(i, 700) for i in range(100, 120)]
    db.executemany("INSERT INTO enrollments (enrollment_id, student_id, course_id) VALUES (?, ?, ?)", [(2000 + idx, student, course) for idx, (student, course) in enumerate(rows)])
    logs = []
    for course, present, absent in ((100, 9, 1), (200, 3, 1), (300, 1, 1), (500, 20, 0), (600, 17, 3), (700, 16, 4)):
        for status in ['Present'] * present + ['Absent'] * absent:
            logs.append((len(logs) + 1, 1, course, '2026-01-01', status))
    db.executemany("INSERT INTO attendance VALUES (?, ?, ?, ?, ?)", logs)
    return db


def normalized(value):
    if isinstance(value, Number):
        return round(float(value), 8)
    return value


def fetch(cursor, sql):
    cursor.execute(sql)
    columns = [column[0] for column in cursor.description]
    values = cursor.fetchall()
    if len(set(columns)) != len(columns):
        raise AssertionError(f'Duplicate output field names: {columns}')
    return columns, values


def compare(cursor, actual_sql, reference_sql, ordered=False):
    required, expected = fetch(cursor, reference_sql)
    columns, actual = fetch(cursor, actual_sql)
    missing = set(required) - set(columns)
    if missing:
        raise AssertionError(f'Missing required fields: {sorted(missing)}')
    indices = [columns.index(name) for name in required]
    actual = [tuple(normalized(row[index]) for index in indices) for row in actual]
    expected = [tuple(normalized(value) for value in row) for row in expected]
    matches = actual == expected if ordered else Counter(actual) == Counter(expected)
    if not matches:
        raise AssertionError(f'Rows differ: {len(actual)} actual vs {len(expected)} expected; sample actual {actual[:3]}, expected {expected[:3]}')
    return len(actual)
