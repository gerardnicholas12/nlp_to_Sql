-- MySQL 8.0.16+. Apply only to a NEW, empty database using setup.py.
-- Academic history uses RESTRICT deletes. No DROP, TRUNCATE or FK disabling.

CREATE TABLE departments (
    department_id INT PRIMARY KEY AUTO_INCREMENT,
    department_code VARCHAR(12) NOT NULL UNIQUE,
    department_name VARCHAR(100) NOT NULL UNIQUE,
    location VARCHAR(100)
) ENGINE=InnoDB;

CREATE TABLE programs (
    program_id INT PRIMARY KEY AUTO_INCREMENT,
    department_id INT NOT NULL,
    program_code VARCHAR(20) NOT NULL UNIQUE,
    program_name VARCHAR(100) NOT NULL,
    duration_semesters SMALLINT NOT NULL,
    CONSTRAINT ck_program_duration CHECK (duration_semesters BETWEEN 1 AND 16),
    CONSTRAINT fk_program_department FOREIGN KEY (department_id)
        REFERENCES departments(department_id) ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE students (
    student_id INT PRIMARY KEY AUTO_INCREMENT,
    program_id INT NOT NULL,
    roll_number VARCHAR(30) NOT NULL UNIQUE,
    student_name VARCHAR(100) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    date_of_birth DATE NOT NULL,
    admitted_on DATE NOT NULL,
    city VARCHAR(80),
    CONSTRAINT ck_student_dates CHECK (date_of_birth < admitted_on),
    CONSTRAINT fk_student_program FOREIGN KEY (program_id)
        REFERENCES programs(program_id) ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE teachers (
    teacher_id INT PRIMARY KEY AUTO_INCREMENT,
    department_id INT NOT NULL,
    teacher_name VARCHAR(100) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    hired_on DATE NOT NULL,
    salary DECIMAL(12,2) NOT NULL,
    CONSTRAINT ck_teacher_salary CHECK (salary >= 0),
    CONSTRAINT fk_teacher_department FOREIGN KEY (department_id)
        REFERENCES departments(department_id) ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE courses (
    course_id INT PRIMARY KEY AUTO_INCREMENT,
    department_id INT NOT NULL,
    course_code VARCHAR(20) NOT NULL UNIQUE,
    course_name VARCHAR(120) NOT NULL,
    credits SMALLINT NOT NULL,
    CONSTRAINT ck_course_credits CHECK (credits BETWEEN 1 AND 12),
    CONSTRAINT fk_course_department FOREIGN KEY (department_id)
        REFERENCES departments(department_id) ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE terms (
    term_id INT PRIMARY KEY AUTO_INCREMENT,
    term_code VARCHAR(20) NOT NULL UNIQUE,
    starts_on DATE NOT NULL,
    ends_on DATE NOT NULL,
    CONSTRAINT ck_term_dates CHECK (starts_on < ends_on)
) ENGINE=InnoDB;

CREATE TABLE course_offerings (
    offering_id INT PRIMARY KEY AUTO_INCREMENT,
    course_id INT NOT NULL,
    term_id INT NOT NULL,
    section_code VARCHAR(10) NOT NULL,
    capacity SMALLINT NOT NULL,
    CONSTRAINT uq_offering UNIQUE (course_id, term_id, section_code),
    CONSTRAINT ck_offering_capacity CHECK (capacity > 0),
    CONSTRAINT fk_offering_course FOREIGN KEY (course_id)
        REFERENCES courses(course_id) ON DELETE RESTRICT,
    CONSTRAINT fk_offering_term FOREIGN KEY (term_id)
        REFERENCES terms(term_id) ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE teaching_assignments (
    offering_id INT NOT NULL,
    teacher_id INT NOT NULL,
    teaching_role VARCHAR(20) NOT NULL DEFAULT 'instructor',
    PRIMARY KEY (offering_id, teacher_id),
    CONSTRAINT ck_teaching_role CHECK (teaching_role IN ('instructor', 'assistant')),
    CONSTRAINT fk_assignment_offering FOREIGN KEY (offering_id)
        REFERENCES course_offerings(offering_id) ON DELETE RESTRICT,
    CONSTRAINT fk_assignment_teacher FOREIGN KEY (teacher_id)
        REFERENCES teachers(teacher_id) ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE enrollments (
    offering_id INT NOT NULL,
    student_id INT NOT NULL,
    enrolled_on DATE NOT NULL,
    enrollment_status VARCHAR(12) NOT NULL DEFAULT 'enrolled',
    PRIMARY KEY (offering_id, student_id),
    CONSTRAINT ck_enrollment_status CHECK (enrollment_status IN ('enrolled', 'completed', 'withdrawn')),
    CONSTRAINT fk_enrollment_offering FOREIGN KEY (offering_id)
        REFERENCES course_offerings(offering_id) ON DELETE RESTRICT,
    CONSTRAINT fk_enrollment_student FOREIGN KEY (student_id)
        REFERENCES students(student_id) ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE course_prerequisites (
    course_id INT NOT NULL,
    prerequisite_course_id INT NOT NULL,
    PRIMARY KEY (course_id, prerequisite_course_id),
    CONSTRAINT ck_prerequisite_self CHECK (course_id <> prerequisite_course_id),
    CONSTRAINT fk_prerequisite_course FOREIGN KEY (course_id)
        REFERENCES courses(course_id) ON DELETE RESTRICT,
    CONSTRAINT fk_prerequisite_required FOREIGN KEY (prerequisite_course_id)
        REFERENCES courses(course_id) ON DELETE RESTRICT
) ENGINE=InnoDB;

-- Session numbers are local to an offering, just like section-specific roll calls.
CREATE TABLE class_sessions (
    offering_id INT NOT NULL,
    session_no SMALLINT NOT NULL,
    starts_at DATETIME NOT NULL,
    duration_minutes SMALLINT NOT NULL,
    room VARCHAR(30),
    PRIMARY KEY (offering_id, session_no),
    CONSTRAINT uq_session_time UNIQUE (offering_id, starts_at),
    CONSTRAINT ck_session_no CHECK (session_no > 0),
    CONSTRAINT ck_session_duration CHECK (duration_minutes BETWEEN 1 AND 480),
    CONSTRAINT fk_session_offering FOREIGN KEY (offering_id)
        REFERENCES course_offerings(offering_id) ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE attendance (
    offering_id INT NOT NULL,
    session_no SMALLINT NOT NULL,
    student_id INT NOT NULL,
    attendance_status VARCHAR(10) NOT NULL,
    PRIMARY KEY (offering_id, session_no, student_id),
    CONSTRAINT ck_attendance_status CHECK (attendance_status IN ('present', 'absent', 'late', 'excused')),
    CONSTRAINT fk_attendance_session FOREIGN KEY (offering_id, session_no)
        REFERENCES class_sessions(offering_id, session_no) ON DELETE RESTRICT,
    CONSTRAINT fk_attendance_enrollment FOREIGN KEY (offering_id, student_id)
        REFERENCES enrollments(offering_id, student_id) ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE assessments (
    offering_id INT NOT NULL,
    assessment_no SMALLINT NOT NULL,
    assessment_name VARCHAR(100) NOT NULL,
    assessment_type VARCHAR(12) NOT NULL,
    held_on DATE NOT NULL,
    PRIMARY KEY (offering_id, assessment_no),
    CONSTRAINT uq_assessment_name UNIQUE (offering_id, assessment_name),
    CONSTRAINT ck_assessment_no CHECK (assessment_no > 0),
    CONSTRAINT ck_assessment_type CHECK (assessment_type IN ('quiz', 'assignment', 'exam', 'project')),
    CONSTRAINT fk_assessment_offering FOREIGN KEY (offering_id)
        REFERENCES course_offerings(offering_id) ON DELETE RESTRICT
) ENGINE=InnoDB;

-- Scores are percentages out of 100. Assessments have equal weight in demo reports.
CREATE TABLE assessment_results (
    offering_id INT NOT NULL,
    assessment_no SMALLINT NOT NULL,
    student_id INT NOT NULL,
    score_percent DECIMAL(5,2) NOT NULL,
    PRIMARY KEY (offering_id, assessment_no, student_id),
    CONSTRAINT ck_result_score CHECK (score_percent BETWEEN 0 AND 100),
    CONSTRAINT fk_result_assessment FOREIGN KEY (offering_id, assessment_no)
        REFERENCES assessments(offering_id, assessment_no) ON DELETE RESTRICT,
    CONSTRAINT fk_result_enrollment FOREIGN KEY (offering_id, student_id)
        REFERENCES enrollments(offering_id, student_id) ON DELETE RESTRICT
) ENGINE=InnoDB;

-- Authentication is a separate concern. No demo passwords or accounts are seeded.
-- Keep the current authentication field names for a later, explicit cutover.
CREATE TABLE app_users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'user',
    student_id INT UNIQUE,
    teacher_id INT UNIQUE,
    CONSTRAINT ck_user_role CHECK (role IN ('user', 'admin')),
    CONSTRAINT ck_user_identity CHECK (student_id IS NULL OR teacher_id IS NULL),
    CONSTRAINT fk_user_student FOREIGN KEY (student_id)
        REFERENCES students(student_id) ON DELETE RESTRICT,
    CONSTRAINT fk_user_teacher FOREIGN KEY (teacher_id)
        REFERENCES teachers(teacher_id) ON DELETE RESTRICT
) ENGINE=InnoDB;
