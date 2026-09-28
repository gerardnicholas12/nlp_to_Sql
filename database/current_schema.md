# Student courses and employee departments

The live database is `college`. The course table describes programs of study
such as BCA and BE Computer Science. A student's `Course_ID` identifies their
current program; this does not model enrollment in multiple programs.

| Table | Columns in database order |
| --- | --- |
| student_info | Student_ID (PK), Student_Name, Course_ID (FK), Address, Phone_No |
| course | Course_ID (PK), Course_Name |
| subject | Subject_ID (PK), Subject_Name, Course_ID (FK), Semester, Max_Marks |
| marks | Student_ID (FK), Subject_ID (FK), Exam, Marks, Result |
| employee_info | Employee_ID (PK), Employee_Name, Department_ID (FK), Address, Phone_No |
| department | Department_ID (PK), Department_Name |
| project | Project_ID (PK), Project_Name, Department_ID (FK), Start_Year, Budget |
| performance | Employee_ID (FK), Project_ID (FK), Rating, Result |

Keep course and department names in their lookup tables. Many students can
reference the same course, and many employees can reference the same department.
Changing a name then requires editing only the lookup row. Subjects still
reference courses, and projects still reference departments.

The additive migration is
[20260926_student_course_employee_department.sql](migrations/20260926_student_course_employee_department.sql).
Run it once against the existing database after taking a backup. It adds two
nullable foreign keys without replacing any existing records or lookup tables.
The initial migration left assignments NULL. At the user's request, the follow-up
[assignment migration](migrations/20260926_assign_course_department.sql) uses
the existing marks -> subject -> course and performance -> project -> department
relationships to fill them. Every one of the 15 students maps to a single course,
and every one of the 10 employees maps to a single department in this dataset.
All current rows now have assignments.

The assignment migration preserves existing non-NULL IDs and skips people with
missing or conflicting relationships. It can be rerun without overwriting manual
assignments. This inference is a convention for this dataset: in a broader system,
an exam subject need not establish a student's program, and a project's department
need not establish an employee's home department. New records can still be entered
with NULL until their assignment is known.

## Display the names

These queries retain students and employees whose assignment is still unknown.

```sql
SELECT s.Student_ID, s.Student_Name, c.Course_Name, s.Address, s.Phone_No
FROM student_info AS s
LEFT JOIN course AS c ON c.Course_ID = s.Course_ID
ORDER BY s.Student_ID;

SELECT e.Employee_ID, e.Employee_Name, d.Department_Name, e.Address, e.Phone_No
FROM employee_info AS e
LEFT JOIN department AS d ON d.Department_ID = e.Department_ID
ORDER BY e.Employee_ID;
```

## Primary keys and marks/performance

A table has one primary key, which may contain multiple columns (a composite
primary key). A foreign key does not have to be part of the primary key.
Currently, `marks` and `performance` have foreign keys and indexes, but no
primary key. This migration leaves their rows and constraints unchanged.

If each student can have one score per subject per exam, the candidate primary
key for `marks` is `(Student_ID, Subject_ID, Exam)`. Using only Student_ID and
Subject_ID would prevent storing separate exams for the same subject. Retakes
would require an attempt identifier as well.

If each employee can have one rating per project, the candidate primary key for
`performance` is `(Employee_ID, Project_ID)`. Repeated reviews would require an
additional review identifier or period. Choose these rules before adding keys;
primary-key fields must be non-null and existing combinations must be unique.

The schema API now orders fields by their database position, so student and
marks fields are no longer reordered alphabetically in the admin forms.

The existing NLP planners target earlier schemas. These display examples are
SQL queries; support for this eight-table schema in natural-language queries is
a separate application change.
