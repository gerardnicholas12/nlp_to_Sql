"""Table and column vocabulary shared by query generation and refinement."""

TABLE_MAP = {
    "student": "students", "students": "students", "stu": "students",
    "employee": "employees", "employees": "employees", "emp": "employees",
    "staff": "employees",
    "department": "departments", "departments": "departments", "dept": "departments",
    "course": "courses", "courses": "courses",
    "teacher": "teachers", "teachers": "teachers",
    "enrollment": "enrollments", "enrollments": "enrollments",
    "attendance_record": "attendance", "attendance_records": "attendance",
    "faculty": "faculty", "faculties": "faculty",
    "class": "classes", "classes": "classes",
    "exam": "exams", "exams": "exams",
    "result": "results", "results": "results",
}

# An unqualified FK name can occur on several tables; its owner is resolved
# per question rather than overwritten by another entry in this dictionary.
COLUMN_MAP = {
    "marks": "marks", "mark": "marks",
    "attendance": "attendance", "attendance_pct": "students.attendance",
    "semester": "semester", "semesters": "semester",
    "subject": "subject", "subjects": "subject",
    "salary": "salary", "salaries": "salary", "experience": "experience",
    "joining": "joining_year", "joined": "joining_year", "hired": "joining_year",
    "year": "joining_year", "years": "joining_year", "joining_year": "joining_year",
    "department": "department", "dept": "department",
    "department_id": "department_id", "department_name": "department_name",
    "dept_name": "department_name", "location": "location",
    "course_id": "course_id", "course_name": "course_name", "credits": "credits",
    "teacher_id": "teacher_id", "teacher_name": "teacher_name", "email": "email",
    "teacher_department_id": "teachers.department_id",
    "enrollment_id": "enrollment_id", "student_id": "student_id",
    "enrollment_date": "enrollment_date", "grade": "grade",
    "attendance_id": "attendance_id", "att_student_id": "attendance.student_id",
    "att_course_id": "attendance.course_id", "attendance_date": "attendance_date",
    "status": "status", "blood_groupp": "blood_groupp",
    "id": "id", "ids": "id", "age": "age", "ages": "age",
    "name": "name", "names": "name", "city": "city", "cities": "city",
    "gender": "gender", "genders": "gender",
    "srn": "srn", "address": "address", "phone": "phone",
    "designation": "designation", "qualification": "qualification",
    "class_id": "class_id", "faculty_id": "faculty_id",
    "exam_id": "exam_id", "exam_date": "exam_date",
}

# Offline defaults; /query supplies the current database schema so columns
# added through the admin panel are also recognized.
TABLE_COLUMNS = {
    "students": {"id", "name", "marks", "age", "gender", "city", "semester", "attendance", "subject", "blood_groupp"},
    "employees": {"id", "name", "salary", "department", "age", "gender", "city", "experience", "joining_year"},
    "departments": {"department_id", "department_name", "location"},
    "courses": {"course_id", "course_name", "credits", "department_id", "teacher_id"},
    "teachers": {"teacher_id", "teacher_name", "email", "department_id", "salary"},
    "enrollments": {"enrollment_id", "student_id", "course_id", "enrollment_date", "grade"},
    "attendance": {"attendance_id", "student_id", "course_id", "attendance_date", "status"},
}

TABLE_NAME_COLUMN = {
    "departments": "department_name", "courses": "course_name", "teachers": "teacher_name",
    "students": "student_name", "faculty": "faculty_name", "classes": "class_name", "exams": "exam_name",
}
TABLE_ID_COLUMN = {
    "students": "student_id", "faculty": "faculty_id", "classes": "class_id", "exams": "exam_id", "results": "result_id",
    "departments": "department_id", "courses": "course_id", "teachers": "teacher_id",
    "enrollments": "enrollment_id", "attendance": "attendance_id",
}

RELATIONSHIPS = [
    ("courses", "department_id", "departments", "department_id"),
    ("courses", "teacher_id", "teachers", "teacher_id"),
    ("teachers", "department_id", "departments", "department_id"),
    ("enrollments", "student_id", "students", "id"),
    ("enrollments", "course_id", "courses", "course_id"),
    ("attendance", "student_id", "students", "id"),
    ("attendance", "course_id", "courses", "course_id"),
]


def query_schema(schema=None):
    """Restrict query vocabulary to the application's supported data tables."""
    if schema is None:
        return TABLE_COLUMNS
    from services.simple_college_query import TABLE_COLUMNS as SIMPLE_COLUMNS
    return {table: set(columns) for table, columns in schema.items() if table in TABLE_COLUMNS or table in SIMPLE_COLUMNS}


def table_column(word, table, schema):
    column = COLUMN_MAP.get(word, word)
    if "." in column:
        owner, column = column.split(".")
        if owner != table:
            return None
    if column == "name":
        candidate = TABLE_NAME_COLUMN.get(table, column)
        column = candidate if candidate in schema.get(table, ()) else column
    elif column == "id":
        candidate = TABLE_ID_COLUMN.get(table, column)
        column = candidate if candidate in schema.get(table, ()) else column
    return column if column in schema.get(table, ()) else None


def infer_table(tokens, schema):
    scores = {table: 0 for table in TABLE_COLUMNS if table in schema}
    for word in tokens:
        owners = [table for table in schema if table_column(word, table, schema)]
        for owner in owners:
            scores[owner] += 10 if len(owners) == 1 else 1
        # Keep established defaults for otherwise ambiguous column-only prompts.
        if word in ("salary", "salaries") and "employees" in owners:
            scores["employees"] += 2
        for owner in owners:
            if word in (TABLE_ID_COLUMN.get(owner), TABLE_NAME_COLUMN.get(owner)):
                scores[owner] += 2
    return max(scores, key=scores.get) if any(scores.values()) else "students"


def build_column_map(table, tables=(), schema=None):
    """Resolve bare aliases in context; preserve explicitly qualified owners."""
    schema = query_schema(schema)
    active = list(dict.fromkeys((table, *tables)))
    qualify = len(active) > 1
    vocabulary = set(COLUMN_MAP)
    for columns in schema.values():
        vocabulary.update(columns)
    result = {}
    for word in vocabulary:
        owners = [(owner, table_column(word, owner, schema)) for owner in active]
        owners = [(owner, column) for owner, column in owners if column]
        if owners:
            owner, column = owners[0]
            result[word] = f"{owner}.{column}" if qualify else column
        for alias, owner in {**TABLE_MAP, "attendance": "attendance"}.items():
            if owner not in active:
                continue
            column = table_column(word, owner, schema)
            if column:
                result[f"{alias}.{word}"] = f"{owner}.{column}" if qualify else column
    return result
