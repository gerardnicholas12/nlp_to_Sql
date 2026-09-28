"""Regression checks for table ownership and the SQL's actual results.

Run from the project root:
    backend/.venv/Scripts/python.exe -m unittest discover -s backend/tests -v
"""

import sqlite3
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flask import Flask
from mappings import TABLE_COLUMNS
from routes.query import query_bp
from services.nlp_to_sql import convert_to_sql
from services.query_refiner import apply_feedback, parse_query, rebuild_sql


def sql_for(question, schema=None):
    return " ".join(convert_to_sql(question, schema=schema).split())


class QueryMappingTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        self.db.executescript("""
            CREATE TABLE students (id INT, name TEXT, marks INT, age INT, city TEXT, subject TEXT);
            CREATE TABLE employees (id INT, name TEXT, salary INT, department TEXT, age INT, city TEXT);
            CREATE TABLE departments (department_id INT, department_name TEXT, location TEXT);
            CREATE TABLE teachers (teacher_id INT, teacher_name TEXT, email TEXT, department_id INT, salary INT);
            CREATE TABLE courses (course_id INT, course_name TEXT, credits INT, department_id INT, teacher_id INT);
            CREATE TABLE enrollments (enrollment_id INT, student_id INT, course_id INT, enrollment_date TEXT, grade TEXT);
            CREATE TABLE attendance (attendance_id INT, student_id INT, course_id INT, attendance_date TEXT, status TEXT);
            INSERT INTO students VALUES (10, 'Ada', 90, 20, 'Bangalore', 'Science'), (20, 'Ben', 70, 22, 'Mysore', 'Science');
            INSERT INTO employees VALUES (1, 'Cora', 100, 'HR', 25, 'Bangalore'), (2, 'Dan', 300, 'HR', 30, 'Mysore'), (3, 'Eve', 500, 'IT', 40, 'Hubli');
            INSERT INTO departments VALUES (7, 'Computing', 'North');
            INSERT INTO teachers VALUES (50, 'Fay', 'fay@example.test', 7, 1000), (60, 'Gus', 'gus@example.test', 7, 2000);
            INSERT INTO courses VALUES (100, 'Databases', 4, 7, 50), (200, 'Networks', 3, 7, 60);
            INSERT INTO enrollments VALUES (900, 10, 100, '2026-01-01', 'A');
            INSERT INTO attendance VALUES (800, 20, 200, '2026-01-02', 'Present');
        """)

    def rows(self, question):
        return self.db.execute(convert_to_sql(question)).fetchall()

    def test_shared_foreign_key_names_use_the_requested_table(self):
        cases = [
            ("show course_id and course_name from courses", [(100, 'Databases'), (200, 'Networks')]),
            ("show teacher_id and teacher_name from teachers", [(50, 'Fay'), (60, 'Gus')]),
            ("show department_id and department_name from departments", [(7, 'Computing')]),
            ("show student_id and course_id from enrollments", [(10, 100)]),
            ("show student_id and course_id from attendance_records", [(20, 200)]),
        ]
        for question, expected in cases:
            with self.subTest(question=question):
                self.assertEqual(self.rows(question), expected)

    def test_generic_id_and_name_use_table_specific_columns(self):
        self.assertEqual(self.rows("show courses id and name"), [(100, 'Databases'), (200, 'Networks')])
        self.assertEqual(self.rows("show teachers name"), [('Fay',), ('Gus',)])

    def test_employee_department_is_a_column(self):
        self.assertEqual(self.rows("show employee name and department"), [('Cora', 'HR'), ('Dan', 'HR'), ('Eve', 'IT')])
        self.assertEqual(self.rows("average salary of employees by department"), [('HR', 200.0), ('IT', 500.0)])

    def test_column_only_prompt_infers_owner_from_salary(self):
        self.assertEqual(self.rows("show name and salary"), [('Cora', 100), ('Dan', 300), ('Eve', 500)])

    def test_inference_is_independent_of_schema_row_order(self):
        reversed_schema = dict(reversed(list(TABLE_COLUMNS.items())))
        self.assertEqual(sql_for("show name", reversed_schema), "SELECT name FROM students")

    def test_foreign_keys_with_different_names_work_in_both_directions(self):
        for question in (
            "show students.name and enrollments.grade",
            "show enrollments.grade and students.name",
        ):
            with self.subTest(question=question):
                self.assertEqual(set(self.rows(question)[0]), {'Ada', 'A'})
                self.assertEqual(len(self.rows(question)), 1)
        self.assertEqual(self.rows("show students.name and attendance_records.status"), [('Ben', 'Present')])

    def test_natural_column_owners_are_preserved(self):
        self.assertEqual(self.rows("show course name and teacher name"), [('Databases', 'Fay'), ('Networks', 'Gus')])

    def test_qualified_references_add_both_tables(self):
        self.assertEqual(self.rows("show students.name and employees.salary"), [('Ada', 100), ('Ben', 300)])

    def test_filter_column_does_not_replace_requested_rows(self):
        sql = sql_for("show students with marks above 80")
        self.assertEqual(sql, "SELECT * FROM students WHERE marks > 80")
        self.assertEqual(self.rows("show students with marks above 80")[0][1], 'Ada')

    def test_join_filters_sorting_and_aggregates_keep_column_owners(self):
        self.assertEqual(self.rows("show courses.course_name and teachers.teacher_name with teachers.salary above 1500"), [('Networks', 'Gus')])
        self.assertEqual(self.rows("show courses.course_name and teachers.teacher_name order by teachers.salary descending"), [('Networks', 'Gus'), ('Databases', 'Fay')])
        self.assertEqual(self.rows("count courses and teachers"), [(2,)])
        self.assertEqual(self.rows("average teachers.salary from courses and teachers"), [(1500.0,)])

    def test_qualified_grouping_uses_the_named_owner(self):
        self.assertEqual(self.rows("count courses and teachers by teachers.teacher_name"), [('Fay', 1), ('Gus', 1)])

    def test_unmatched_rows_survive_left_join(self):
        self.assertEqual(self.rows("show students.name and enrollments.grade left join students and enrollments"), [('Ada', 'A'), ('Ben', None)])

    def test_full_join_preserves_both_foreign_key_names(self):
        sql = sql_for("show students full outer join enrollments")
        self.assertEqual(sql.count("students.id = enrollments.student_id"), 2)
        self.assertNotIn("enrollments.id", sql)

    def test_existing_range_grouping_and_top_aggregate_features(self):
        self.assertEqual(self.rows("show students with marks between 60 and 80")[0][1], 'Ben')
        self.assertEqual(self.rows("count students by subject"), [('Science', 2)])
        self.assertEqual(self.rows("average salary of top 2 employees"), [(400.0,)])
        self.assertEqual(self.rows("average teachers.salary of top 1 courses and teachers"), [(2000.0,)])

    def test_missing_related_rows_use_not_exists(self):
        self.assertEqual(self.rows("show courses with no enrollments")[0][1], 'Networks')

    def test_current_schema_recognizes_added_columns(self):
        schema = {table: set(columns) for table, columns in TABLE_COLUMNS.items()}
        schema['students'].add('scholarship')
        self.assertEqual(sql_for("show scholarship from students with scholarship above 100", schema), "SELECT scholarship FROM students WHERE scholarship > 100")

    def test_invalid_ownership_is_rejected(self):
        for question in ("show students.salary", "show salary from students", "show courses join employees"):
            with self.subTest(question=question), self.assertRaises(ValueError):
                convert_to_sql(question)

    def test_refinement_uses_the_same_table_context(self):
        ctx = parse_query(convert_to_sql("show courses"))
        ctx, _ = apply_feedback(ctx, "only show id and name")
        self.assertEqual(self.db.execute(rebuild_sql(ctx)).fetchall(), [(100, 'Databases'), (200, 'Networks')])


class EnrollmentDepartmentTests(unittest.TestCase):
    question = "Find students who are enrolled in courses offered by the Computer Science department"

    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        self.db.executescript("""
            CREATE TABLE students (id INT, name TEXT, subject TEXT, marks INT);
            CREATE TABLE departments (department_id INT, department_name TEXT);
            CREATE TABLE courses (course_id INT, department_id INT, teacher_id INT);
            CREATE TABLE teachers (teacher_id INT, department_id INT);
            CREATE TABLE enrollments (enrollment_id INT, student_id INT, course_id INT);
            CREATE TABLE attendance (attendance_id INT, student_id INT, course_id INT);
            INSERT INTO students VALUES
                (1, 'Alice', 'Mathematics', 90),
                (2, 'Bob', 'Computer Science', 85),
                (3, 'Cora', 'Computer Science', 75),
                (4, 'Dan', 'English', 60);
            INSERT INTO departments VALUES (10, 'Computer Science'), (20, 'Mathematics'), (30, 'English');
            -- Teacher departments deliberately differ from course departments.
            INSERT INTO teachers VALUES (50, 20), (60, 10);
            INSERT INTO courses VALUES (100, 10, 50), (200, 10, 50), (300, 20, 60), (400, 30, 60);
            -- Alice has two CS enrollments; Bob only attends a CS course.
            INSERT INTO enrollments VALUES (901, 1, 100), (902, 1, 200), (903, 2, 300), (904, 4, 100), (905, 4, 400);
            INSERT INTO attendance VALUES (800, 2, 100);
        """)

    def rows(self, question):
        return self.db.execute(convert_to_sql(question)).fetchall()

    def test_exact_question_filters_course_department_not_student_subject(self):
        sql = sql_for(self.question)
        self.assertIn("departments.department_name = 'Computer Science'", sql)
        self.assertNotIn("subject =", sql)
        self.assertNotIn("teachers", sql)
        self.assertEqual(self.rows(self.question), [(1, 'Alice', 'Mathematics', 90), (4, 'Dan', 'English', 60)])

    def test_student_count_does_not_count_multiple_enrollments(self):
        self.assertEqual(self.rows(self.question.replace('Find students', 'Count students')), [(2,)])

    def test_department_name_and_common_phrasings_are_not_hardcoded(self):
        for question, expected in (
            ("List students enrolled in courses offered by the Mathematics department", [2]),
            ("Find students enrolled in courses from the English department", [4]),
            ("Find students enrolled in courses offered by the department of Computer Science", [1, 4]),
            ('Find students enrolled in courses offered by the "Computer Science" department.', [1, 4]),
        ):
            with self.subTest(question=question):
                self.assertEqual([row[0] for row in self.rows(question)], expected)

    def test_other_student_filters_and_projection_are_preserved(self):
        self.assertEqual([row[0] for row in self.rows(self.question + ' with marks above 80')], [1])
        self.assertEqual(self.rows(self.question.replace('Find students', 'Find name of students with marks above 80')), [('Alice',)])
        self.assertEqual([row[0] for row in self.rows(self.question + ' with marks above 80 or below 70')], [1, 4])

    def test_department_name_apostrophes_remain_literal_values(self):
        self.db.execute('UPDATE departments SET department_name = ? WHERE department_id = 20', ("Women's Studies",))
        question = 'Find students enrolled in courses offered by the "Women\'s Studies" department'
        self.assertEqual([row[0] for row in self.rows(question)], [2])

    def test_negated_enrollment_uses_not_exists(self):
        question = self.question.replace('are enrolled', 'are not enrolled')
        self.assertEqual([row[0] for row in self.rows(question)], [2, 3])

    def test_enrollment_without_department_still_uses_enrollments(self):
        self.assertEqual([row[0] for row in self.rows('Find students enrolled in courses')], [1, 2, 4])

    def test_explicit_student_subject_filter_still_works(self):
        self.assertEqual([row[0] for row in self.rows('Show students with subject Computer Science')], [2, 3])

    def test_missing_relationship_column_is_rejected(self):
        schema = {table: set(columns) for table, columns in TABLE_COLUMNS.items()}
        schema['enrollments'].remove('student_id')
        with self.assertRaisesRegex(ValueError, 'enrollment relationship'):
            convert_to_sql(self.question, schema)


class QueryRouteTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.register_blueprint(query_bp)
        self.client = app.test_client()

    @patch('routes.query.get_db_connection')
    @patch('routes.query.get_schema', return_value=TABLE_COLUMNS)
    @patch('routes.query.verify_jwt_in_request')
    def test_invalid_mapping_returns_422_without_executing_sql(self, auth, schema, connection):
        response = self.client.post('/query', json={'question': 'show students.salary'})
        self.assertEqual(response.status_code, 422)
        self.assertIn('Unknown column', response.get_json()['error'])
        connection.assert_not_called()

    @patch('routes.query.get_db_connection')
    @patch('routes.query.get_schema', return_value=TABLE_COLUMNS)
    @patch('routes.query.verify_jwt_in_request')
    def test_endpoint_uses_corrected_sql(self, auth, schema, connection):
        cursor = connection.return_value.cursor.return_value
        cursor.fetchall.return_value = [{'course_id': 100}]
        response = self.client.post('/query', json={'question': 'show course_id from courses'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(' '.join(response.get_json()['sql'].split()), 'SELECT course_id FROM courses')
        cursor.execute.assert_called_once_with(response.get_json()['sql'])

    @patch('routes.query.get_db_connection')
    @patch('routes.query.get_schema', return_value=TABLE_COLUMNS)
    @patch('routes.query.verify_jwt_in_request')
    def test_endpoint_accepts_student_enrollment_department_question(self, auth, schema, connection):
        cursor = connection.return_value.cursor.return_value
        cursor.fetchall.return_value = [{'id': 1, 'name': 'Alice'}]
        response = self.client.post('/query', json={'question': EnrollmentDepartmentTests.question})
        self.assertEqual(response.status_code, 200)
        sql = response.get_json()['sql']
        self.assertIn('EXISTS (SELECT 1 FROM enrollments', sql)
        self.assertIn("departments.department_name = 'Computer Science'", sql)
        self.assertNotIn("subject =", sql)
        cursor.execute.assert_called_once_with(sql)


if __name__ == '__main__':
    unittest.main()
