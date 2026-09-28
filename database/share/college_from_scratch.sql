-- COMPLETE COLLEGE DATABASE: create tables, insert all data, and display.
-- Includes the assigned student Course_ID and employee Department_ID values.
-- MySQL 8.0. Open in MySQL Workbench and execute the entire script.
-- Creates a NEW database named college_shared. Choose another unused name in
-- BOTH statements below if that database already exists. Run once per new DB.
-- Contains the eight data tables only; no application accounts or credentials.

CREATE DATABASE `college_shared` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE `college_shared`;

SET @previous_sql_mode = @@SESSION.sql_mode;
SET SESSION sql_mode = 'STRICT_TRANS_TABLES,NO_AUTO_VALUE_ON_ZERO';
SET NAMES utf8mb4;

-- 1. CREATE TABLES: parent tables come before their dependents.

CREATE TABLE `course` (
  `Course_ID` int NOT NULL,
  `Course_Name` varchar(100) DEFAULT NULL,
  PRIMARY KEY (`Course_ID`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `department` (
  `Department_ID` int NOT NULL,
  `Department_Name` varchar(50) DEFAULT NULL,
  PRIMARY KEY (`Department_ID`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `student_info` (
  `Student_ID` int NOT NULL,
  `Student_Name` varchar(50) DEFAULT NULL,
  `Course_ID` int DEFAULT NULL,
  `Address` varchar(50) DEFAULT NULL,
  `Phone_No` bigint DEFAULT NULL,
  PRIMARY KEY (`Student_ID`),
  KEY `fk_student_info_course` (`Course_ID`),
  CONSTRAINT `fk_student_info_course` FOREIGN KEY (`Course_ID`) REFERENCES `course` (`Course_ID`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `subject` (
  `Subject_ID` int NOT NULL,
  `Subject_Name` varchar(100) DEFAULT NULL,
  `Course_ID` int DEFAULT NULL,
  `Semester` int DEFAULT NULL,
  `Max_Marks` int DEFAULT NULL,
  PRIMARY KEY (`Subject_ID`),
  KEY `Course_ID` (`Course_ID`),
  CONSTRAINT `subject_ibfk_1` FOREIGN KEY (`Course_ID`) REFERENCES `course` (`Course_ID`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `employee_info` (
  `Employee_ID` int NOT NULL,
  `Employee_Name` varchar(50) DEFAULT NULL,
  `Department_ID` int DEFAULT NULL,
  `Address` varchar(50) DEFAULT NULL,
  `Phone_No` bigint DEFAULT NULL,
  PRIMARY KEY (`Employee_ID`),
  KEY `fk_employee_info_department` (`Department_ID`),
  CONSTRAINT `fk_employee_info_department` FOREIGN KEY (`Department_ID`) REFERENCES `department` (`Department_ID`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `project` (
  `Project_ID` int NOT NULL,
  `Project_Name` varchar(100) DEFAULT NULL,
  `Department_ID` int DEFAULT NULL,
  `Start_Year` int DEFAULT NULL,
  `Budget` int DEFAULT NULL,
  PRIMARY KEY (`Project_ID`),
  KEY `Department_ID` (`Department_ID`),
  CONSTRAINT `project_ibfk_1` FOREIGN KEY (`Department_ID`) REFERENCES `department` (`Department_ID`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `marks` (
  `Student_ID` int DEFAULT NULL,
  `Subject_ID` int DEFAULT NULL,
  `Exam` varchar(30) DEFAULT NULL,
  `Marks` int DEFAULT NULL,
  `Result` varchar(20) DEFAULT NULL,
  KEY `Student_ID` (`Student_ID`),
  KEY `Subject_ID` (`Subject_ID`),
  CONSTRAINT `marks_ibfk_1` FOREIGN KEY (`Student_ID`) REFERENCES `student_info` (`Student_ID`),
  CONSTRAINT `marks_ibfk_2` FOREIGN KEY (`Subject_ID`) REFERENCES `subject` (`Subject_ID`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `performance` (
  `Employee_ID` int DEFAULT NULL,
  `Project_ID` int DEFAULT NULL,
  `Rating` decimal(2,1) DEFAULT NULL,
  `Result` varchar(30) DEFAULT NULL,
  KEY `Employee_ID` (`Employee_ID`),
  KEY `Project_ID` (`Project_ID`),
  CONSTRAINT `performance_ibfk_1` FOREIGN KEY (`Employee_ID`) REFERENCES `employee_info` (`Employee_ID`),
  CONSTRAINT `performance_ibfk_2` FOREIGN KEY (`Project_ID`) REFERENCES `project` (`Project_ID`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 2. INSERT ALL EXISTING DATA, INCLUDING THE ASSIGNED IDs.

START TRANSACTION;

-- course: 5 rows
INSERT INTO `course` (`Course_ID`, `Course_Name`) VALUES
    (1, 'BCA'),
    (2, 'BSc Computer Science'),
    (3, 'BE Computer Science'),
    (4, 'BE Electronics'),
    (5, 'BE Mechanical');

-- department: 4 rows
INSERT INTO `department` (`Department_ID`, `Department_Name`) VALUES
    (1, 'HR'),
    (2, 'IT'),
    (3, 'Finance'),
    (4, 'Marketing');

-- student_info: 15 rows
INSERT INTO `student_info` (`Student_ID`, `Student_Name`, `Course_ID`, `Address`, `Phone_No`) VALUES
    (1, 'Ananya', 1, 'Mysore', 9876500001),
    (2, 'Rohan', 1, 'Bangalore', 9876500002),
    (3, 'Sneha', 1, 'Hubli', 9876500003),
    (4, 'Karan', 2, 'Davangere', 9876500004),
    (5, 'Priya', 2, 'Hassan', 9876500005),
    (6, 'Aditya', 2, 'Mangalore', 9876500006),
    (7, 'Meera', 3, 'Belgaum', 9876500007),
    (8, 'Vikram', 3, 'Shimoga', 9876500008),
    (9, 'Divya', 3, 'Tumkur', 9876500009),
    (10, 'Arjun', 4, 'Mysore', 9876500010),
    (11, 'Ishita', 4, 'Bangalore', 9876500011),
    (12, 'Nikhil', 4, 'Hubli', 9876500012),
    (13, 'Kavya', 5, 'Davangere', 9876500013),
    (14, 'Siddharth', 5, 'Hassan', 9876500014),
    (15, 'Tanvi', 5, 'Mangalore', 9876500015);

-- subject: 15 rows
INSERT INTO `subject` (`Subject_ID`, `Subject_Name`, `Course_ID`, `Semester`, `Max_Marks`) VALUES
    (1, 'Web Dev', 1, 3, 100),
    (2, 'Data Structures', 1, 3, 100),
    (3, 'Database Management', 1, 4, 100),
    (4, 'Software Engineering', 2, 3, 100),
    (5, 'Artificial Intelligence', 2, 4, 100),
    (6, 'Machine Learning', 2, 5, 100),
    (7, 'Cloud Technology', 3, 4, 100),
    (8, 'Computer Networks', 3, 4, 100),
    (9, 'Operating Systems', 3, 3, 100),
    (10, 'Digital Electronics', 4, 3, 100),
    (11, 'Circuit Theory', 4, 3, 100),
    (12, 'Power Systems', 4, 5, 100),
    (13, 'Thermodynamics', 5, 3, 100),
    (14, 'Structural Analysis', 5, 4, 100),
    (15, 'Robotics', 5, 4, 100);

-- employee_info: 10 rows
INSERT INTO `employee_info` (`Employee_ID`, `Employee_Name`, `Department_ID`, `Address`, `Phone_No`) VALUES
    (1, 'Amit', 1, 'Mysore', 9876500101),
    (2, 'Neha', 2, 'Bangalore', 9876500102),
    (3, 'Ravi', 3, 'Hubli', 9876500103),
    (4, 'Pooja', 2, 'Davangere', 9876500104),
    (5, 'Karan', 4, 'Hassan', 9876500105),
    (6, 'Divya', 1, 'Mangalore', 9876500106),
    (7, 'Rahul', 2, 'Belgaum', 9876500107),
    (8, 'Sneha', 4, 'Shimoga', 9876500108),
    (9, 'Arjun', 3, 'Tumkur', 9876500109),
    (10, 'Meera', 1, 'Chikmagalur', 9876500110);

-- project: 8 rows
INSERT INTO `project` (`Project_ID`, `Project_Name`, `Department_ID`, `Start_Year`, `Budget`) VALUES
    (1, 'Onboarding', 1, 2026, 50000),
    (2, 'CRM Migration', 2, 2026, 200000),
    (3, 'Cost Optimization', 2, 2026, 150000),
    (4, 'Budget Forecast', 3, 2026, 30000),
    (5, 'Sales Expansion', 4, 2026, 100000),
    (6, 'Brand Refresh', 4, 2026, 80000),
    (7, 'Payroll Upgrade', 1, 2026, 60000),
    (8, 'Security Audit', 2, 2026, 40000);

-- marks: 15 rows
INSERT INTO `marks` (`Student_ID`, `Subject_ID`, `Exam`, `Marks`, `Result`) VALUES
    (1, 1, 'Internal', 78, 'Pass'),
    (2, 2, 'Final', 85, 'Pass'),
    (3, 3, 'Midterm', 45, 'Pass'),
    (4, 4, 'Final', 55, 'Pass'),
    (5, 5, 'Midterm', 90, 'Pass'),
    (6, 6, 'Final', 38, 'Fail'),
    (7, 7, 'Internal', 66, 'Pass'),
    (8, 8, 'Final', 72, 'Pass'),
    (9, 9, 'Midterm', 81, 'Pass'),
    (10, 10, 'Final', 49, 'Pass'),
    (11, 11, 'Final', 93, 'Pass'),
    (12, 12, 'Final', 58, 'Pass'),
    (13, 13, 'Midterm', 88, 'Pass'),
    (14, 14, 'Final', 41, 'Pass'),
    (15, 15, 'Midterm', 76, 'Pass');

-- performance: 10 rows
INSERT INTO `performance` (`Employee_ID`, `Project_ID`, `Rating`, `Result`) VALUES
    (1, 1, '4.1', 'Good'),
    (2, 2, '4.2', 'Good'),
    (3, 4, '4.7', 'Excellent'),
    (4, 3, '3.8', 'Average'),
    (5, 6, '4.3', 'Good'),
    (6, 7, '4.6', 'Excellent'),
    (7, 8, '4.0', 'Good'),
    (8, 5, '4.2', 'Good'),
    (9, 4, '4.0', 'Good'),
    (10, 1, '3.8', 'Average');

COMMIT;

SET SESSION sql_mode = @previous_sql_mode;

-- 3. DISPLAY EVERY TABLE.

SELECT * FROM `course` ORDER BY 1, 2;
SELECT * FROM `department` ORDER BY 1, 2;
SELECT * FROM `student_info` ORDER BY 1, 2;
SELECT * FROM `subject` ORDER BY 1, 2;
SELECT * FROM `employee_info` ORDER BY 1, 2;
SELECT * FROM `project` ORDER BY 1, 2;
SELECT * FROM `marks` ORDER BY 1, 2;
SELECT * FROM `performance` ORDER BY 1, 2;

-- 4. DISPLAY NAMES ALONGSIDE THE RELATED RECORDS.

-- Students and their programs.
SELECT s.Student_ID, s.Student_Name, s.Course_ID, c.Course_Name,
       s.Address, s.Phone_No
FROM student_info AS s
LEFT JOIN course AS c ON c.Course_ID = s.Course_ID
ORDER BY s.Student_ID;

-- Employees and their departments.
SELECT e.Employee_ID, e.Employee_Name, e.Department_ID, d.Department_Name,
       e.Address, e.Phone_No
FROM employee_info AS e
LEFT JOIN department AS d ON d.Department_ID = e.Department_ID
ORDER BY e.Employee_ID;

-- Students' marks for each recorded subject and exam.
SELECT s.Student_ID, s.Student_Name, sub.Subject_Name,
       m.Exam, m.Marks, sub.Max_Marks, m.Result
FROM marks AS m
JOIN student_info AS s ON s.Student_ID = m.Student_ID
JOIN subject AS sub ON sub.Subject_ID = m.Subject_ID
ORDER BY s.Student_ID, sub.Subject_ID, m.Exam;

-- Employee performance on each recorded project.
SELECT e.Employee_ID, e.Employee_Name, p.Project_Name,
       pf.Rating, pf.Result
FROM performance AS pf
JOIN employee_info AS e ON e.Employee_ID = pf.Employee_ID
JOIN project AS p ON p.Project_ID = pf.Project_ID
ORDER BY e.Employee_ID, p.Project_ID;
