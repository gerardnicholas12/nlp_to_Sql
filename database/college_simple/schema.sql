-- Six academic tables, based on the supplied reference picture.
-- classes are student groups; exams associate a group with a course.
-- Each mark belongs to a student through results, rather than to the exam itself.
CREATE TABLE faculty (
    faculty_id INT PRIMARY KEY AUTO_INCREMENT,
    faculty_name VARCHAR(100) NOT NULL,
    designation VARCHAR(60) NOT NULL,
    qualification VARCHAR(60) NOT NULL,
    experience INT NOT NULL,
    CONSTRAINT chk_faculty_experience CHECK (experience BETWEEN 0 AND 60)
) ENGINE=InnoDB;

CREATE TABLE classes (
    class_id INT PRIMARY KEY AUTO_INCREMENT,
    class_name VARCHAR(40) NOT NULL UNIQUE,
    semester INT NOT NULL,
    CONSTRAINT chk_class_semester CHECK (semester BETWEEN 1 AND 8)
) ENGINE=InnoDB;

CREATE TABLE courses (
    course_id INT PRIMARY KEY AUTO_INCREMENT,
    course_name VARCHAR(100) NOT NULL UNIQUE,
    credits INT NOT NULL,
    faculty_id INT NOT NULL,
    CONSTRAINT chk_course_credits CHECK (credits BETWEEN 1 AND 6),
    CONSTRAINT fk_course_faculty FOREIGN KEY (faculty_id) REFERENCES faculty(faculty_id)
) ENGINE=InnoDB;

CREATE TABLE students (
    student_id INT PRIMARY KEY AUTO_INCREMENT,
    srn VARCHAR(20) NOT NULL UNIQUE,
    student_name VARCHAR(100) NOT NULL,
    address VARCHAR(200) NOT NULL,
    phone VARCHAR(20) NOT NULL,
    email VARCHAR(120) NOT NULL UNIQUE,
    class_id INT NOT NULL,
    CONSTRAINT fk_student_class FOREIGN KEY (class_id) REFERENCES classes(class_id)
) ENGINE=InnoDB;

CREATE TABLE exams (
    exam_id INT PRIMARY KEY AUTO_INCREMENT,
    exam_name VARCHAR(60) NOT NULL,
    class_id INT NOT NULL,
    course_id INT NOT NULL,
    exam_date DATE NOT NULL,
    CONSTRAINT uq_exam UNIQUE (class_id, course_id, exam_name),
    CONSTRAINT fk_exam_class FOREIGN KEY (class_id) REFERENCES classes(class_id),
    CONSTRAINT fk_exam_course FOREIGN KEY (course_id) REFERENCES courses(course_id)
) ENGINE=InnoDB;

CREATE TABLE results (
    result_id INT PRIMARY KEY AUTO_INCREMENT,
    student_id INT NOT NULL,
    exam_id INT NOT NULL,
    marks DECIMAL(5,2) NOT NULL,
    CONSTRAINT uq_student_exam UNIQUE (student_id, exam_id),
    CONSTRAINT chk_result_marks CHECK (marks BETWEEN 0 AND 100),
    CONSTRAINT fk_result_student FOREIGN KEY (student_id) REFERENCES students(student_id),
    CONSTRAINT fk_result_exam FOREIGN KEY (exam_id) REFERENCES exams(exam_id)
) ENGINE=InnoDB;

-- Ordinary single-column foreign keys stay easy to explain. These small guards
-- also reject a result for an exam belonging to a different student's class.
DELIMITER $$
CREATE TRIGGER result_class_insert BEFORE INSERT ON results FOR EACH ROW
BEGIN
    DECLARE student_class INT;
    DECLARE exam_class INT;
    SELECT class_id INTO student_class FROM students WHERE student_id=NEW.student_id FOR SHARE;
    SELECT class_id INTO exam_class FROM exams WHERE exam_id=NEW.exam_id FOR SHARE;
    IF student_class <> exam_class THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Student and exam must belong to the same class';
    END IF;
END$$
CREATE TRIGGER result_class_update BEFORE UPDATE ON results FOR EACH ROW
BEGIN
    DECLARE student_class INT;
    DECLARE exam_class INT;
    SELECT class_id INTO student_class FROM students WHERE student_id=NEW.student_id FOR SHARE;
    SELECT class_id INTO exam_class FROM exams WHERE exam_id=NEW.exam_id FOR SHARE;
    IF student_class <> exam_class THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Student and exam must belong to the same class';
    END IF;
END$$
CREATE TRIGGER student_class_update BEFORE UPDATE ON students FOR EACH ROW
BEGIN
    IF NEW.class_id <> OLD.class_id AND EXISTS (
        SELECT 1 FROM results r JOIN exams e ON e.exam_id=r.exam_id
        WHERE r.student_id=OLD.student_id AND e.class_id <> NEW.class_id
    ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Existing exam results prevent changing this student class';
    END IF;
END$$
CREATE TRIGGER exam_class_update BEFORE UPDATE ON exams FOR EACH ROW
BEGIN
    IF NEW.class_id <> OLD.class_id AND EXISTS (
        SELECT 1 FROM results r JOIN students s ON s.student_id=r.student_id
        WHERE r.exam_id=OLD.exam_id AND s.class_id <> NEW.class_id
    ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Existing results prevent changing this exam class';
    END IF;
END$$
DELIMITER ;
