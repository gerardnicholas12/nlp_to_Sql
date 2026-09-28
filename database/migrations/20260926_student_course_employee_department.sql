-- Select the existing college database before running this migration once.
-- Existing rows keep NULL until their course/department is explicitly assigned.
-- Course and department names remain in their lookup tables.
ALTER TABLE student_info
    ADD COLUMN Course_ID INT NULL AFTER Student_Name,
    ADD CONSTRAINT fk_student_info_course
        FOREIGN KEY (Course_ID) REFERENCES course (Course_ID);

ALTER TABLE employee_info
    ADD COLUMN Department_ID INT NULL AFTER Employee_Name,
    ADD CONSTRAINT fk_employee_info_department
        FOREIGN KEY (Department_ID) REFERENCES department (Department_ID);
