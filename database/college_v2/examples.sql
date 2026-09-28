-- Q1: Show students taking Database Management Systems in 2026-ODD, with section.
SELECT s.student_id, s.student_name, c.course_name, t.term_code, o.section_code
FROM students s
JOIN enrollments e ON e.student_id = s.student_id
JOIN course_offerings o ON o.offering_id = e.offering_id
JOIN courses c ON c.course_id = o.course_id
JOIN terms t ON t.term_id = o.term_id
WHERE c.course_code = 'CS201' AND t.term_code = '2026-ODD'
  AND e.enrollment_status <> 'withdrawn'
ORDER BY s.student_id;

-- Q2: Count home-program students per department, including empty departments.
SELECT d.department_name, COUNT(s.student_id) AS student_count
FROM departments d
LEFT JOIN programs p ON p.department_id = d.department_id
LEFT JOIN students s ON s.program_id = p.program_id
GROUP BY d.department_id, d.department_name
ORDER BY d.department_id;

-- Q3: Students studying courses offered by a different department in 2026-ODD.
SELECT DISTINCT s.student_id, s.student_name, home.department_name AS home_department,
       owner.department_name AS course_department
FROM students s
JOIN programs p ON p.program_id = s.program_id
JOIN departments home ON home.department_id = p.department_id
JOIN enrollments e ON e.student_id = s.student_id
JOIN course_offerings o ON o.offering_id = e.offering_id
JOIN terms t ON t.term_id = o.term_id
JOIN courses c ON c.course_id = o.course_id
JOIN departments owner ON owner.department_id = c.department_id
WHERE p.department_id <> c.department_id AND t.term_code = '2026-ODD'
  AND e.enrollment_status <> 'withdrawn'
ORDER BY s.student_id, owner.department_name;

-- Q4: Students below 75% recorded attendance per current offering.
-- Present + late / (present + late + absent). Excused and unrecorded are excluded.
-- NULL means there are no eligible records, not zero attendance.
SELECT s.student_id, s.student_name, c.course_name, o.section_code,
       ROUND(100.0 * SUM(a.attendance_status IN ('present', 'late')) /
             NULLIF(SUM(a.attendance_status IN ('present', 'late', 'absent')), 0), 2) AS attendance_percent
FROM enrollments e
JOIN students s ON s.student_id = e.student_id
JOIN course_offerings o ON o.offering_id = e.offering_id
JOIN courses c ON c.course_id = o.course_id
JOIN terms t ON t.term_id = o.term_id
LEFT JOIN attendance a ON a.offering_id = e.offering_id AND a.student_id = e.student_id
WHERE t.term_code = '2026-ODD' AND e.enrollment_status <> 'withdrawn'
GROUP BY e.offering_id, s.student_id, s.student_name, c.course_name, o.section_code
HAVING attendance_percent < 75
ORDER BY attendance_percent, s.student_id, e.offering_id;

-- Q5: Rank students by complete, equally weighted assessment scores per offering.
-- A score is final only when every defined assessment has a result.
WITH complete_scores AS (
    SELECT e.offering_id, e.student_id, AVG(r.score_percent) AS final_percent
    FROM enrollments e
    JOIN assessments a ON a.offering_id = e.offering_id
    LEFT JOIN assessment_results r ON r.offering_id = a.offering_id
        AND r.assessment_no = a.assessment_no AND r.student_id = e.student_id
    WHERE e.enrollment_status <> 'withdrawn'
    GROUP BY e.offering_id, e.student_id
    HAVING COUNT(r.assessment_no) = COUNT(a.assessment_no)
), ranked AS (
    SELECT cs.*, DENSE_RANK() OVER (PARTITION BY offering_id ORDER BY final_percent DESC) AS score_rank
    FROM complete_scores cs
)
SELECT r.offering_id, s.student_name, ROUND(r.final_percent, 2) AS final_percent, r.score_rank
FROM ranked r JOIN students s ON s.student_id = r.student_id
WHERE r.score_rank <= 3
ORDER BY r.offering_id, r.score_rank, r.student_id;

-- Q6: Teachers with no assigned offerings in 2026-ODD.
SELECT th.teacher_id, th.teacher_name
FROM teachers th
WHERE NOT EXISTS (
    SELECT 1 FROM teaching_assignments ta
    JOIN course_offerings o ON o.offering_id = ta.offering_id
    JOIN terms t ON t.term_id = o.term_id
    WHERE ta.teacher_id = th.teacher_id AND t.term_code = '2026-ODD'
)
ORDER BY th.teacher_id;

-- Q7: Courses that have multiple teachers in an offering.
SELECT o.offering_id, c.course_name, t.term_code, o.section_code,
       COUNT(ta.teacher_id) AS teacher_count
FROM course_offerings o
JOIN courses c ON c.course_id = o.course_id
JOIN terms t ON t.term_id = o.term_id
JOIN teaching_assignments ta ON ta.offering_id = o.offering_id
GROUP BY o.offering_id, c.course_name, t.term_code, o.section_code
HAVING COUNT(ta.teacher_id) > 1
ORDER BY o.offering_id;

-- Q8: Students with no enrollment in any term.
SELECT s.student_id, s.student_name
FROM students s
WHERE NOT EXISTS (SELECT 1 FROM enrollments e WHERE e.student_id = s.student_id)
ORDER BY s.student_id;

-- Q9: All direct and indirect prerequisites of Machine Learning.
-- UNION DISTINCT deduplicates converging paths and terminates even if bad cycles exist.
WITH RECURSIVE prerequisites AS (
    SELECT p.prerequisite_course_id
    FROM course_prerequisites p JOIN courses c ON c.course_id = p.course_id
    WHERE c.course_code = 'CS301'
    UNION DISTINCT
    SELECT p.prerequisite_course_id
    FROM course_prerequisites p
    JOIN prerequisites chain ON p.course_id = chain.prerequisite_course_id
)
SELECT c.course_code, c.course_name
FROM prerequisites p JOIN courses c ON c.course_id = p.prerequisite_course_id
ORDER BY c.course_code;

-- Q10: Enrollment totals per current offering, including empty offerings.
-- Aggregate before adding other one-to-many relationships to avoid inflated counts.
SELECT o.offering_id, c.course_name, o.section_code, o.capacity,
       COALESCE(ec.enrolled_students, 0) AS enrolled_students
FROM course_offerings o
JOIN courses c ON c.course_id = o.course_id
JOIN terms t ON t.term_id = o.term_id
LEFT JOIN (
    SELECT offering_id, COUNT(*) AS enrolled_students
    FROM enrollments WHERE enrollment_status <> 'withdrawn' GROUP BY offering_id
) ec ON ec.offering_id = o.offering_id
WHERE t.term_code = '2026-ODD'
ORDER BY o.offering_id;
