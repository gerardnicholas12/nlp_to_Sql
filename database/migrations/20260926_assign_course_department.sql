-- Run after 20260926_student_course_employee_department.sql.
-- Use the existing subject/course and project/department relationships as
-- the assignments for this dataset. Preserve any previously assigned IDs.
-- Missing or conflicting relationships are left for explicit assignment.
START TRANSACTION;

UPDATE student_info AS student
JOIN (
    SELECT marks.Student_ID, MIN(subject.Course_ID) AS Course_ID
    FROM marks
    LEFT JOIN subject ON subject.Subject_ID = marks.Subject_ID
    GROUP BY marks.Student_ID
    HAVING COUNT(DISTINCT subject.Course_ID) = 1
       AND COUNT(*) = COUNT(subject.Course_ID)
) AS assignment ON assignment.Student_ID = student.Student_ID
SET student.Course_ID = assignment.Course_ID
WHERE student.Course_ID IS NULL;

UPDATE employee_info AS employee
JOIN (
    SELECT performance.Employee_ID, MIN(project.Department_ID) AS Department_ID
    FROM performance
    LEFT JOIN project ON project.Project_ID = performance.Project_ID
    GROUP BY performance.Employee_ID
    HAVING COUNT(DISTINCT project.Department_ID) = 1
       AND COUNT(*) = COUNT(project.Department_ID)
) AS assignment ON assignment.Employee_ID = employee.Employee_ID
SET employee.Department_ID = assignment.Department_ID
WHERE employee.Department_ID IS NULL;

COMMIT;
