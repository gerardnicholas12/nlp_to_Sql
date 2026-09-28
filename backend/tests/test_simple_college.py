"""Independent query checks for the simplified, six-table college schema."""

import sqlite3
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))

from services.nlp_to_sql import convert_to_sql
from services.simple_college_query import TABLE_COLUMNS
from services.query_refiner import apply_feedback, parse_query, rebuild_sql, RefinementError


class SimpleCollegeTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.addCleanup(self.db.close)
        self.schema = {table: {col: 'text' for col in cols} for table, cols in TABLE_COLUMNS.items()}
        numeric = {'student_id', 'faculty_id', 'course_id', 'class_id', 'exam_id', 'result_id', 'experience', 'credits', 'semester', 'marks'}
        for table, cols in TABLE_COLUMNS.items():
            self.db.execute(f'CREATE TABLE {table} (' + ','.join(f'{col} {"REAL" if col in numeric else "TEXT"}' for col in cols) + ')')
        self.db.executescript((ROOT / 'database/college_simple/seed.sql').read_text().replace('START TRANSACTION;', 'BEGIN;'))

    def query(self, question):
        return self.db.execute(convert_to_sql(question, self.schema)).fetchall()

    def test_all_six_tables_have_fifteen_records(self):
        for table in TABLE_COLUMNS:
            self.assertEqual(len(self.query('show ' + table)), 15)

    def test_group_counts_preserve_empty_classes(self):
        self.assertEqual([r[2] for r in self.query('count students by class')], [2]*5+[1]*5+[0]*5)

    def test_result_filter_uses_actual_result_not_scheduled_exams(self):
        got = self.query('show student name and marks with marks above 90')
        self.assertEqual(got, [('Aarav Sharma',92), ('Ananya Singh',95)])

    def test_marks_secured_by_named_student(self):
        cases = [
            ('show the marks secured by Meera from students', [('Meera Rao', 64)]),
            ('Show marks scored by MEERA RAO from students.', [('Meera Rao', 64)]),
            ('show scores obtained by Aarav from students', [('Aarav Sharma', 92), ('Aarav Sharma', 86)]),
            ('show marks earned by student Ananya from students', [('Ananya Singh', 95)]),
            ('show marks for Meera', [('Meera Rao', 64)]),
            ('show marks of Meera from students', [('Meera Rao', 64)]),
            ('show marks secured by Nobody from students', []),
        ]
        for question, expected in cases:
            with self.subTest(question=question):
                self.assertEqual(self.query(question), expected)

    def test_first_name_matches_whole_name_or_first_word(self):
        self.db.executemany('INSERT INTO students (student_id, student_name) VALUES (?, ?)',
                            [(100, 'Meera'), (101, 'Meera Iyer'), (102, 'Meeran Patel'), (103, 'Ananya Meera')])
        self.db.executemany('INSERT INTO results (result_id, student_id, exam_id, marks) VALUES (?, ?, 4, ?)',
                            [(100, 100, 70), (101, 101, 81), (102, 102, 91), (103, 103, 99)])
        self.assertEqual(self.query('show marks secured by Meera from students'),
                         [('Meera Rao', 64), ('Meera', 70), ('Meera Iyer', 81)])
        self.assertEqual(self.query('show marks secured by Meera Iyer from students'), [('Meera Iyer', 81)])

    def test_name_filter_preserves_other_filters_and_all_exam_scores(self):
        self.db.execute('INSERT INTO results VALUES (100, 4, 14, 74)')
        question = 'show marks secured by Meera from students'
        self.assertEqual(self.query(question), [('Meera Rao', 64), ('Meera Rao', 74)])
        self.assertEqual(self.query(question + ' with marks above 70'), [('Meera Rao', 74)])
        self.assertEqual(self.query(question + ' order by marks descending'), [('Meera Rao', 74), ('Meera Rao', 64)])
        self.assertEqual(self.query('average marks secured by Meera from students'), [(69,)])

    def test_names_are_not_normalized_as_column_aliases(self):
        self.db.execute('INSERT INTO students (student_id, student_name) VALUES (?, ?)', (100, "Mark O'Neil"))
        self.db.execute('INSERT INTO results VALUES (100, 100, 4, 82)')
        for name in ("Mark O'Neil", '"Mark O\'Neil"'):
            with self.subTest(name=name):
                self.assertEqual(self.query(f'show marks secured by {name} from students'), [("Mark O'Neil", 82)])
        # Table references after "of" must retain their previous meaning.
        expected = self.db.execute('SELECT AVG(marks) FROM results').fetchall()
        self.assertEqual(self.query('average marks of results'), expected)

    def test_top_results_are_in_descending_score_order(self):
        self.assertEqual([r[3] for r in self.query('show top 3 results with highest marks')], [95,92,90])

    def test_class_join_and_semester_filter(self):
        self.assertEqual(len(self.query('show students in semester 3')), 10)
        self.assertEqual([r[1] for r in self.query('show students in class CSE-3A')], ['Aarav Sharma','Vihaan Reddy'])

    def test_average_is_per_student_and_missing_stays_null(self):
        rows = self.query('average marks per student')
        self.assertEqual(rows[0][2], 89)
        self.assertIsNone(rows[-1][2])

    def test_two_courses_share_one_faculty(self):
        got = self.query('show course name and faculty name with faculty.faculty_id is 1')
        self.assertEqual(got, [('Database Management Systems','Anita Rao'), ('Computer Networks','Anita Rao')])

    def test_faculty_qualification_phrases(self):
        cases = [
            ('show the faculties with PhD in Mathematics??', [2, 11]),
            ('Show teachers with a Ph.D. in Mathematics', [2, 11]),
            ('show faculty with PhD Mathematics', [2, 11]),
            ('show faculty with PhD in Computer Science', [1, 6]),
            ('show faculties with M.Tech. in Information Technology', [5]),
            ('show faculty with MSc Statistics', [7]),
            ('show faculty with MBA', [14]),
            ('show faculty with PhD in Geography', []),
            ('show faculty with PhD', [1, 2, 4, 6, 8, 9, 11, 13, 15]),
        ]
        for question, expected in cases:
            with self.subTest(question=question):
                self.assertEqual([row[0] for row in self.query(question)], expected)

    def test_qualification_filters_preserve_projection_count_and_other_conditions(self):
        self.assertEqual(self.query('show faculty name with PhD in Mathematics and experience above 15'), [('Latha Krishnan',)])
        self.assertEqual(self.query('count faculties with PhD in Mathematics'), [(2,)])
        self.assertEqual([r[0] for r in self.query('show faculties with PhD in Mathematics order by experience descending')], [11, 2])
        self.assertEqual([r[0] for r in self.query('show faculty with experience above 15 and PhD in Mathematics')], [11])
        self.assertEqual([r[0] for r in self.query('show faculty with qualification is "PhD Mathematics"')], [2, 11])

    def test_qualification_matches_degree_and_subject_without_substring_false_positives(self):
        self.db.executemany('INSERT INTO faculty (faculty_id, qualification) VALUES (?, ?)', [
            (100, 'Ph.D. in MATHEMATICS'), (101, 'MSc Mathematics'),
            (102, 'PhD Applied Mathematics'), (103, 'PhD Mathematics Education'), (104, None),
        ])
        self.assertEqual([r[0] for r in self.query('show the faculties with PhD in Mathematics??')], [2, 11, 100])

    def test_no_results_is_different_from_low_marks(self):
        self.assertEqual(self.query('show students without results')[0][0],15)
        self.assertEqual(self.query('show results with marks below 40')[0][1],10)

    def test_unsupported_or_ambiguous_questions_are_rejected(self):
        for question in ['show employees', 'show students with attendance above 75',
                         'show students with marks above 80 or marks below 40',
                         'show top 5 students with highest marks', 'show students; DROP DATABASE college',
                         'show marks secured by Meera or Aarav from students',
                         'show marks secured by Meera above 70 from students',
                         'show faculty with PhD in Mathematics or experience above 10',
                         'show faculty with PhD in Mathematics and',
                         'show faculty with PhD in Mathematics experience above 10',
                         'show faculty with PhD in',
                         'show students who dance', 'show courses with credits above 3 and']:
            with self.subTest(question=question), self.assertRaises(ValueError):
                self.query(question)

    def test_single_table_refinement_still_works(self):
        ctx = parse_query(convert_to_sql('show results', self.schema))
        ctx, _ = apply_feedback(ctx, 'only show marks', schema=self.schema)
        ctx, _ = apply_feedback(ctx, 'sort by marks descending', schema=self.schema)
        self.assertEqual(self.db.execute(rebuild_sql(ctx)).fetchone(),(95,))

    def test_join_refinement_is_declined_clearly(self):
        with self.assertRaises(RefinementError):
            parse_query(convert_to_sql('show courses and faculty', self.schema))

    def test_query_api_uses_new_schema(self):
        from flask import Flask
        from routes.query import query_bp
        app = Flask(__name__)
        app.register_blueprint(query_bp)
        class Cursor:
            def execute(inner, sql):
                inner.result = self.db.execute(sql)
            def fetchall(inner):
                columns = [x[0] for x in inner.result.description]
                return [dict(zip(columns,row)) for row in inner.result.fetchall()]
            def close(inner):
                pass
        class Connection:
            def cursor(inner, **kwargs):
                return Cursor()
            def close(inner):
                pass
        with patch('routes.query.get_schema', return_value=self.schema), patch('routes.query.get_db_connection', return_value=Connection()), patch('routes.query.verify_jwt_in_request'):
            response = app.test_client().post('/query', json={'question':'show students with marks above 90'})
            self.assertEqual(response.status_code,200)
            self.assertEqual(len(response.get_json()['data']),2)
            self.assertIn('out of 100',response.get_json()['interpretation'][0])
            response = app.test_client().post('/query', json={'question':'show the marks secured by Meera from students'})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()['data'], [{'students_student_name': 'Meera Rao', 'results_marks': 64}])
            response = app.test_client().post('/query', json={'question':'show the faculties with PhD in Mathematics??'})
            self.assertEqual(response.status_code, 200)
            self.assertEqual([row['faculty_name'] for row in response.get_json()['data']], ['Vikram Nair', 'Latha Krishnan'])


if __name__ == '__main__':
    unittest.main()
