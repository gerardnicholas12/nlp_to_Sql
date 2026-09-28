-- Synthetic demo records. Each of the six tables has exactly 15 rows.
START TRANSACTION;
INSERT INTO faculty (faculty_id,faculty_name,designation,qualification,experience) VALUES
(1,'Anita Rao','Professor','PhD Computer Science',18),
(2,'Vikram Nair','Associate Professor','PhD Mathematics',12),
(3,'Meera Shah','Assistant Professor','MTech Computer Science',7),
(4,'Arjun Das','Professor','PhD Electronics',20),
(5,'Priya Menon','Assistant Professor','MTech Information Technology',6),
(6,'Sanjay Kumar','Associate Professor','PhD Computer Science',11),
(7,'Kavya Iyer','Assistant Professor','MSc Statistics',5),
(8,'Rohit Patel','Professor','PhD Physics',16),
(9,'Nisha Singh','Associate Professor','PhD English',10),
(10,'Dev Verma','Assistant Professor','MTech Electronics',4),
(11,'Latha Krishnan','Professor','PhD Mathematics',22),
(12,'Amit Joshi','Assistant Professor','MTech Computer Science',3),
(13,'Sara Thomas','Associate Professor','PhD Chemistry',13),
(14,'Kiran Reddy','Assistant Professor','MBA',8),
(15,'Maya Bose','Professor','PhD Economics',19);

INSERT INTO classes (class_id,class_name,semester) VALUES
(1,'CSE-3A',3),(2,'CSE-3B',3),(3,'ECE-3A',3),(4,'ECE-3B',3),(5,'ISE-3A',3),
(6,'CSE-5A',5),(7,'CSE-5B',5),(8,'ECE-5A',5),(9,'ISE-5A',5),(10,'ISE-5B',5),
(11,'CSE-1A',1),(12,'ECE-1A',1),(13,'ISE-1A',1),(14,'CSE-7A',7),(15,'ECE-7A',7);

INSERT INTO courses (course_id,course_name,credits,faculty_id) VALUES
(1,'Database Management Systems',4,1),(2,'Discrete Mathematics',4,2),
(3,'Data Structures',4,3),(4,'Digital Electronics',3,4),
(5,'Web Technology',3,5),(6,'Operating Systems',4,6),
(7,'Probability and Statistics',3,7),(8,'Engineering Physics',4,8),
(9,'Technical Communication',2,9),(10,'Microcontrollers',3,10),
(11,'Computer Networks',4,1),(12,'Linear Algebra',3,2),
(13,'Python Programming',3,3),(14,'Embedded Systems',4,4),
(15,'Software Engineering',3,5);

INSERT INTO students (student_id,srn,student_name,address,phone,email,class_id) VALUES
(1,'PES2026001','Aarav Sharma','12 Lake Road, Bengaluru','0000000001','aarav@example.invalid',1),
(2,'PES2026002','Diya Nair','24 Park Road, Mysuru','0000000002','diya@example.invalid',2),
(3,'PES2026003','Kabir Patel','36 Hill Road, Bengaluru','0000000003','kabir@example.invalid',3),
(4,'PES2026004','Meera Rao','48 Temple Road, Mangaluru','0000000004','meera@example.invalid',4),
(5,'PES2026005','Ishaan Das','15 Garden Road, Hubballi','0000000005','ishaan@example.invalid',5),
(6,'PES2026006','Ananya Singh','27 College Road, Bengaluru','0000000006','ananya@example.invalid',6),
(7,'PES2026007','Rohan Kumar','39 Station Road, Mysuru','0000000007','rohan@example.invalid',7),
(8,'PES2026008','Tara Menon','51 Market Road, Bengaluru','0000000008','tara@example.invalid',8),
(9,'PES2026009','Aditya Shah','18 River Road, Shivamogga','0000000009','aditya@example.invalid',9),
(10,'PES2026010','Sana Iyer','30 School Road, Bengaluru','0000000010','sana@example.invalid',10),
(11,'PES2026011','Vihaan Reddy','42 Palace Road, Mysuru','0000000011','vihaan@example.invalid',1),
(12,'PES2026012','Anika Joshi','54 Green Road, Hubballi','0000000012','anika@example.invalid',2),
(13,'PES2026013','Dhruv Verma','21 Main Road, Mangaluru','0000000013','dhruv@example.invalid',3),
(14,'PES2026014','Kiara Thomas','33 Palm Road, Bengaluru','0000000014','kiara@example.invalid',4),
(15,'PES2026015','Neil Bose','45 Cross Road, Belagavi','0000000015','neil@example.invalid',5);

INSERT INTO exams (exam_id,exam_name,class_id,course_id,exam_date) VALUES
(1,'Internal 1',1,1,'2026-09-01'),(2,'Internal 1',2,2,'2026-09-01'),
(3,'Internal 1',3,3,'2026-09-02'),(4,'Internal 1',4,4,'2026-09-02'),
(5,'Internal 1',5,5,'2026-09-03'),(6,'Internal 1',6,6,'2026-09-03'),
(7,'Internal 1',7,7,'2026-09-04'),(8,'Internal 1',8,8,'2026-09-04'),
(9,'Internal 1',9,9,'2026-09-05'),(10,'Internal 1',10,10,'2026-09-05'),
(11,'Internal 1',1,11,'2026-09-08'),(12,'Internal 1',2,12,'2026-09-08'),
(13,'Internal 1',3,13,'2026-09-09'),(14,'Internal 1',4,14,'2026-09-09'),
(15,'Internal 1',5,15,'2026-09-10');

INSERT INTO results (result_id,student_id,exam_id,marks) VALUES
(1,1,1,92),(2,2,2,85),(3,3,3,78),(4,4,4,64),(5,5,5,88),
(6,6,6,95),(7,7,7,56),(8,8,8,73),(9,9,9,81),(10,10,10,39),
(11,11,11,90),(12,12,12,67),(13,13,13,84),(14,14,14,76),(15,1,11,86);
COMMIT;
