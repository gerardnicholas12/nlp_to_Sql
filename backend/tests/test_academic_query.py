import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from academic_benchmark import PROMPTS, REFERENCES, ORDERED, fixture, compare, COURSE_STUDENTS, DEPT_TEACHERS
from services.nlp_to_sql import convert_to_sql
from services.academic_query import describe_query_semantics


class AcademicBenchmarkTests(unittest.TestCase):
    def test_all_55_prompts_on_populated_and_empty_databases(self):
        self.assertEqual(set(REFERENCES), {item['id'] for item in PROMPTS})
        for empty in (False, True):
            db = fixture(empty=empty)
            try:
                for item in PROMPTS:
                    with self.subTest(id=item['id'], empty=empty, question=item['question']):
                        compare(db.cursor(), convert_to_sql(item['question']), REFERENCES[item['id']], item['id'] in ORDERED)
            finally:
                db.close()

    def test_thresholds_names_and_limits_are_not_fixed_to_examples(self):
        db = fixture()
        self.addCleanup(db.close)
        cases = [
            ('Find departments that have at least six teachers', DEPT_TEACHERS + ' HAVING COUNT(t.teacher_id) >= 6'),
            ('Show courses with at most ten students', COURSE_STUDENTS + ' HAVING COUNT(DISTINCT e.student_id) <= 10'),
            ('Show the top three courses based on the number of enrolled students', COURSE_STUDENTS + ' ORDER BY student_count DESC, c.course_id ASC LIMIT 3'),
            ('Show teachers working in the Mathematics department', REFERENCES['T03'].replace('Computer Science', 'Mathematics')),
            ('Show students enrolled in the Calculus course', REFERENCES['E03'].replace('Database Management Systems', 'Calculus')),
            ('Show students whose attendance is below 74.5%', 'SELECT id, name FROM students WHERE attendance < 74.5'),
        ]
        for question, expected in cases:
            with self.subTest(question=question):
                compare(db.cursor(), convert_to_sql(question), expected, 'top' in question)

    def test_benchmark_has_nonempty_results_for_strict_thresholds(self):
        db = fixture()
        self.addCleanup(db.close)
        for identifier in ('T08', 'E08', 'E10', 'A13', 'A14', 'X183', 'X187', 'X192'):
            with self.subTest(id=identifier):
                self.assertTrue(db.execute(REFERENCES[identifier]).fetchall())

    def test_unrecognized_conditions_are_not_silently_discarded(self):
        for question in (
            'Show teachers and their departments above 50',
            'Show students with attendance above 80 and gender female',
            'Show teachers and their departments sorted by salary',
            'Show courses with more than 20 students with attendance above 80',
        ):
            with self.subTest(question=question), self.assertRaises(ValueError):
                convert_to_sql(question)

    def test_attendance_definition_is_explained(self):
        notes = describe_query_semantics('Show the average attendance for each course')
        self.assertIn('recorded entries marked Present', notes[0])

    def test_missing_schema_columns_stop_generation(self):
        from mappings import TABLE_COLUMNS
        schema = {table: set(columns) for table, columns in TABLE_COLUMNS.items()}
        schema['enrollments'].remove('student_id')
        with self.assertRaisesRegex(ValueError, 'missing enrollments'):
            convert_to_sql('How many students are enrolled in each course?', schema)


if __name__ == '__main__':
    unittest.main()
