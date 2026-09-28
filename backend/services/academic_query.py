"""Structured plans for academic questions.

Entity identity, output columns, metrics, predicates and ranking are resolved
before rendering SQL. Correlated aggregates avoid multiplying counts when a
department has several teachers, courses and enrollments. This is a bounded
grammar, not a promise to understand arbitrary English.
"""

import re
from dataclasses import dataclass, field


COURSE_ALIASES = {"database": "database management systems", "dbms": "database management systems"}
COURSE_ATTENDANCE_BASIS = "records"  # alternatively: "student_percentages"
CS_STUDENT_BASIS = "subject"  # alternatively: "enrolled_department"

OP = r"(?:greater than or equal to|less than or equal to|more than|greater than|fewer than|less than|at least|at most|above|below|over|under|>=|<=|>|<|equals?|=)"
NUMBER = r"\d+(?:\.\d+)?"
COMPARISON = re.compile(rf"(?P<op>{OP})\s*(?P<number>{NUMBER})\b")
OPERATORS = {
    "greater than or equal to": ">=", "less than or equal to": "<=",
    "more than": ">", "greater than": ">", "above": ">", "over": ">",
    "fewer than": "<", "less than": "<", "below": "<", "under": "<",
    "at least": ">=", "at most": "<=", "equals": "=", "equal": "=",
    ">": ">", "<": "<", ">=": ">=", "<=": "<=", "=": "=",
}
ENTITY_WORDS = {
    "students": r"students?", "teachers": r"teachers?",
    "departments": r"(?:departments?|dept)", "courses": r"courses?",
    "enrollments": r"enrollments?",
}
IDENTITY = {
    "students": ("id", "name"), "teachers": ("teacher_id", "teacher_name"),
    "departments": ("department_id", "department_name"), "courses": ("course_id", "course_name"),
}
GRAMMAR_WORDS = set("""
show list find get display which who what how many count number numbers all
each every per their they the a an and or but not no any in on for from to of
by with without along working work belong belongs belonging does do has have
are is that whose than more less fewer greater equal equals at least most
fewest highest lowest greatest largest smallest top bottom first last based
enrolled enrollment enrollments course courses student students teacher teachers
department departments dept details name names id teaches teach taken taught
average avg mean attendance percentage percentages percent between above below
over under sort sorted order ordered ascending descending marks salary age
""".split())


def literal(value):
    return "'" + value.replace("\\", "\\\\").replace("'", "''") + "'"


@dataclass
class QueryPlan:
    source: str
    columns: list[str]
    predicates: list[str] = field(default_factory=list)
    ordering: list[str] = field(default_factory=list)
    limit: int | None = None
    distinct: bool = False

    def sql(self):
        sql = "SELECT " + ("DISTINCT " if self.distinct else "") + ", ".join(self.columns)
        sql += " FROM " + self.source
        if self.predicates:
            sql += " WHERE " + " AND ".join(f"({p})" for p in self.predicates)
        if self.ordering:
            sql += " ORDER BY " + ", ".join(self.ordering)
        if self.limit is not None:
            sql += f" LIMIT {self.limit}"
        return sql


class AcademicQuestion:
    def __init__(self, text, schema):
        self.text = text
        self.schema = schema
        self.used_comparisons = set()
        self.values = set()

    def value(self, value):
        self.values.add(value)
        return literal(value)

    def has(self, entity):
        return bool(re.search(rf"\b{ENTITY_WORDS[entity]}\b", self.text))

    def require(self, table, *columns):
        missing = set(columns) - set(self.schema.get(table, ()))
        if missing:
            raise ValueError(f"The database is missing {table} columns: {', '.join(sorted(missing))}.")

    def base(self, table, all_columns=False):
        key, name = IDENTITY[table]
        self.require(table, key, name)
        return QueryPlan(table, [f"{table}.*"] if all_columns else [f"{table}.{key}", f"{table}.{name}"])

    def threshold(self, entity):
        match = re.search(rf"(?P<op>{OP})\s*(?P<number>{NUMBER})\s+(?:distinct\s+)?{ENTITY_WORDS[entity]}\b", self.text)
        if not match:
            return None
        self.used_comparisons.add(match.start('op'))
        return OPERATORS[match['op']], match['number']

    def attribute_filters(self, plan, table, attributes):
        for attribute in attributes:
            filters = []
            for match in re.finditer(rf"\b{attribute}\s+(?:is\s+)?(?P<op>{OP})\s*(?P<number>{NUMBER})", self.text):
                self.require(table, attribute)
                self.used_comparisons.add(match.start('op'))
                filters.append(f"{table}.{attribute} {OPERATORS[match['op']]} {match['number']}")
            match = re.search(rf"\b{attribute}\s+(?:is\s+)?between\s+({NUMBER})\s*%?\s+and\s+({NUMBER})", self.text)
            if match:
                self.require(table, attribute)
                filters.append(f"{table}.{attribute} BETWEEN {match[1]} AND {match[2]}")
            if filters:
                plan.predicates.append((" OR " if " or " in self.text else " AND ").join(filters))

    def rank(self, plan, expression, table, nullable=False):
        # "at most 10" is a predicate, not a request for the maximum row.
        text = COMPARISON.sub(" ", self.text)
        top = re.search(r"\b(?:top|bottom|first|last)\s+(\d+)\b", text)
        sorting = bool(re.search(r"\b(?:sorted|sort|ordered|order|ascending|descending)\b|highest to lowest|lowest to highest", text))
        descending = bool(re.search(r"\b(?:highest|most|greatest|largest|top|descending)\b", text))
        ascending = bool(re.search(r"\b(?:lowest|fewest|least|smallest|bottom|ascending)\b", text))
        if "highest to lowest" in text:
            descending, ascending = True, False
        elif "lowest to highest" in text:
            descending, ascending = False, True
        if not (top or sorting or descending or ascending):
            return
        direction = "ASC" if ascending and not descending else "DESC"
        if nullable:
            if sorting and not top:
                plan.ordering.append(f"{expression} IS NULL ASC")
            else:
                plan.predicates.append(f"{expression} IS NOT NULL")
        plan.ordering += [f"{expression} {direction}", f"{table}.{IDENTITY[table][0]} ASC"]
        if top:
            plan.limit = int(top[1])
        elif not sorting:
            plan.limit = 1

    def complete(self, plan):
        # A recognized academic intent must never silently discard a numerical
        # constraint it could not bind to an attribute or an entity count.
        for match in COMPARISON.finditer(self.text):
            if match.start() not in self.used_comparisons:
                raise ValueError("Couldn't determine what that comparison applies to. Name the attribute or counted entity explicitly.")
        remaining = self.text
        for value in sorted(self.values, key=len, reverse=True):
            remaining = remaining.replace(value, " ")
        unknown = set(re.findall(r"[a-z_]+", remaining)) - GRAMMAR_WORDS
        if unknown:
            raise ValueError("Couldn't interpret part of the academic question: " + ", ".join(sorted(unknown)) + ". Please rephrase it explicitly.")
        if re.search(r"\b(?:not|no|without)\b", remaining):
            if not any("NOT " in p or " = 0" in p for p in plan.predicates):
                raise ValueError("Couldn't determine which condition to negate. Please state the exclusion explicitly.")
        if " or " in remaining and len(plan.predicates) > 1:
            raise ValueError("Please split the OR conditions into separate questions so their grouping is explicit.")
        rank_text = COMPARISON.sub(" ", remaining)
        if re.search(r"\b(?:highest|lowest|most|fewest|top|bottom|sorted|sort|order|ascending|descending)\b", rank_text) and not plan.ordering:
            raise ValueError("Couldn't determine which value to rank or sort. Specify a count or numeric attribute.")
        return plan.sql()

    def enrollment_exists(self, course_name=None, department_name=None):
        self.require("students", "id")
        self.require("enrollments", "student_id", "course_id")
        self.require("courses", "course_id", "course_name")
        sql = "SELECT 1 FROM enrollments e JOIN courses c ON c.course_id = e.course_id"
        if department_name is not None:
            self.require("courses", "department_id")
            self.require("departments", "department_id", "department_name")
            sql += " JOIN departments d ON d.department_id = c.department_id"
        sql += " WHERE e.student_id = students.id"
        if course_name is not None:
            self.values.add(course_name)
            value = COURSE_ALIASES.get(course_name, course_name)
            sql += f" AND LOWER(c.course_name) = {literal(value)}"
        if department_name is not None:
            self.values.add(department_name)
            sql += f" AND LOWER(d.department_name) = {literal(department_name)}"
        return f"EXISTS ({sql})"

    def metric(self, table, name):
        if table == "students" and name == "course_count":
            self.require("enrollments", "student_id", "course_id")
            return "(SELECT COUNT(DISTINCT e.course_id) FROM enrollments e WHERE e.student_id = students.id)"
        if table == "teachers" and name == "course_count":
            self.require("courses", "teacher_id", "course_id")
            return "(SELECT COUNT(*) FROM courses c WHERE c.teacher_id = teachers.teacher_id)"
        if table == "departments" and name in ("teacher_count", "course_count"):
            related = "teachers" if name == "teacher_count" else "courses"
            self.require(related, "department_id")
            return f"(SELECT COUNT(*) FROM {related} r WHERE r.department_id = departments.department_id)"
        if table == "courses" and name in ("student_count", "enrollment_count"):
            self.require("enrollments", "student_id", "course_id")
            aggregate = "COUNT(DISTINCT e.student_id)" if name == "student_count" else "COUNT(*)"
            return f"(SELECT {aggregate} FROM enrollments e WHERE e.course_id = courses.course_id)"
        if table == "departments" and name in ("student_count", "average_marks"):
            self.require("courses", "course_id", "department_id")
            self.require("enrollments", "student_id", "course_id")
            self.require("students", "id", "marks" if name == "average_marks" else "id")
            aggregate = "AVG(s.marks)" if name == "average_marks" else "COUNT(*)"
            return (
                f"(SELECT {aggregate} FROM students s WHERE EXISTS "
                "(SELECT 1 FROM enrollments e JOIN courses c ON c.course_id = e.course_id "
                "WHERE e.student_id = s.id AND c.department_id = departments.department_id))"
            )
        if table == "courses" and name == "average_attendance":
            if COURSE_ATTENDANCE_BASIS == "student_percentages":
                self.require("students", "id", "attendance")
                self.require("enrollments", "student_id", "course_id")
                return (
                    "(SELECT AVG(s.attendance) FROM students s WHERE EXISTS "
                    "(SELECT 1 FROM enrollments e WHERE e.student_id = s.id AND e.course_id = courses.course_id))"
                )
            self.require("attendance", "course_id", "status")
            return (
                "(SELECT 100.0 * AVG(CASE WHEN a.status = 'Present' THEN 1.0 "
                "WHEN a.status = 'Absent' THEN 0.0 END) FROM attendance a "
                "WHERE a.course_id = courses.course_id)"
            )
        raise ValueError(f"Unsupported metric '{name}' for {table}.")

    def counts(self, table, metrics, thresholds=(), no_entity=False, has_entity=False):
        plan = self.base(table)
        expressions = {}
        for name in metrics:
            expressions[name] = self.metric(table, name)
            plan.columns.append(f"{expressions[name]} AS {name}")
        for name, threshold in thresholds:
            if threshold:
                operator, number = threshold
                plan.predicates.append(f"{expressions[name]} {operator} {number}")
        if no_entity or has_entity:
            name = metrics[0]
            plan.predicates.append(f"{expressions[name]} {'=' if no_entity else '>'} 0")
        if table == "students":
            self.attribute_filters(plan, table, ("attendance", "marks", "age"))
        rank_name = metrics[-1] if "average" in self.text else metrics[0]
        self.rank(plan, expressions[rank_name], table, nullable=rank_name.startswith("average"))
        return self.complete(plan)


def _label(value):
    return re.sub(r"^(?:the|a|an)\s+", "", value.strip()).strip(" .?!\"'")


def department_label(text):
    # Suffix and prefix forms, bounded by relation/filter words. Values can
    # contain several words; they are not inferred from the subject vocabulary.
    for pattern in (
        r"\b(?:in|from|to|of)\s+(?:the\s+)?(.+?)\s+(?:department|dept)\b",
        r"\b(?:department|dept)\s+(?:of\s+|named\s+)(.+?)(?=\s+(?:with|where|and|order|sort)\b|$)",
    ):
        match = re.search(pattern, text)
        if match:
            return _label(match[1])
    return None


def course_labels(text):
    match = re.search(r"\benrolled\s+in\s+(.+?)\s+but\s+not\s+(.+?)(?:\s+courses?)?$", text)
    if match:
        return _label(match[1]), _label(match[2])
    for pattern in (
        r"\benrolled\s+in\s+(?:the\s+)?(.+?)\s+course\b",
        r"\battendance\s+(?:for|in|of)\s+(?:the\s+)?(.+?)\s+course\b",
        r"\benrolled\s+in\s+(?:the\s+)?(.+?)(?=\s+(?:with|where|whose)\b|$)",
    ):
        match = re.search(pattern, text)
        if match and not re.search(r"\b(?:courses?|each|any|no|more|less|fewer|than|least|most)\b", match[1]):
            return _label(match[1]), None
    return None, None


def compile_academic_query(question, schema, number_tokens):
    # Keep labels intact while using the existing number-word normalizer.
    text = " ".join(number_tokens).strip(" .?!\"'").lower()
    text = re.sub(r"\s+%", "%", text)
    q = AcademicQuestion(text, schema)
    if re.search(r"\b(?:employees?|staff|emp)\b", text):
        return None
    # Explicit column syntax and raw join requests stay on the existing path.
    if re.search(r"\b[a-z_]\w*\.[a-z_]\w*\b", text) or re.search(r"\b(?:join|joined|union|cross)\b", text):
        return None
    if re.search(r"\benrolled\b.*\b(?:offered|provided|run)\s+by\b", text):
        return None  # existing validated enrollment-department clause parser

    students, courses = q.has("students"), q.has("courses")
    teachers, departments = q.has("teachers"), q.has("departments")
    enrollment = q.has("enrollments") or bool(re.search(r"\b(?:enrolled|enrollment|taken)\b", text))
    attendance = "attendance" in text
    count_language = bool(re.search(r"\b(?:count|number|many|most|fewest|least)\b", text))
    course_name, excluded_course = course_labels(text)
    if departments and re.search(r"\benrolled\s+(?:in|on)\s+(?:the\s+)?courses?\b", text):
        return None

    if q.has("enrollments") and "details" in text:
        q.require("enrollments", "enrollment_id", "student_id", "course_id")
        plan = QueryPlan("enrollments", ["enrollments.*"])
        if students:
            q.require("students", "id", "name")
            plan.source += " JOIN students ON students.id = enrollments.student_id"
            plan.columns.append("students.name")
        if courses:
            q.require("courses", "course_id", "course_name")
            plan.source += " JOIN courses ON courses.course_id = enrollments.course_id"
            plan.columns.append("courses.course_name")
        return q.complete(plan)

    if departments and teachers and courses and students:
        return q.counts("departments", ["teacher_count", "course_count", "student_count"])
    if departments and students and (count_language or "average" in text):
        name = "average_marks" if "average" in text and "marks" in text else "student_count"
        return q.counts("departments", [name], [(name, q.threshold("students"))])
    if teachers and courses and (re.search(r"\bnumber of courses\b|\bcourses? (?:taught|teaches)\b|\beach teacher\b", text)):
        return q.counts("teachers", ["course_count"], [("course_count", q.threshold("courses"))])

    if teachers and departments:
        threshold = q.threshold("teachers")
        no_teachers = bool(re.search(r"\bno teachers?\b|\bwithout teachers?\b", text))
        has_teachers = bool(re.search(r"\b(?:have|has|with) teachers\b(?!\s+names?)", text))
        department_number = re.search(r"\b(?:department|dept)\s+(?:number\s+|id\s+)?(\d+)\b", text)
        if (count_language and not department_number) or threshold or no_teachers or has_teachers:
            return q.counts("departments", ["teacher_count"], [("teacher_count", threshold)], no_teachers, has_teachers)
        plan = q.base("teachers", all_columns=True)
        q.require("teachers", "department_id")
        q.require("departments", "department_id", "department_name")
        plan.source += " LEFT JOIN departments ON departments.department_id = teachers.department_id"
        plan.columns.append("departments.department_name")
        if re.search(r"\bdepartment names?\b", text) and re.search(r"\bteacher names?\b", text):
            plan.columns = ["departments.department_name", "teachers.teacher_name"]
        label = department_label(text)
        number = re.search(r"\b(?:department|dept)\s+(?:number\s+|id\s+)?(\d+)\b", text)
        if number:
            plan.predicates.append(f"teachers.department_id = {number[1]}")
        elif label:
            plan.predicates.append(f"LOWER(departments.department_name) = {q.value(label)}")
        q.attribute_filters(plan, "teachers", ("salary",))
        return q.complete(plan)

    if attendance and courses and not students:
        if course_name and "average" not in text:
            q.require("attendance", "attendance_id", "student_id", "course_id", "attendance_date", "status")
            q.require("students", "id", "name")
            q.require("courses", "course_id", "course_name")
            plan = QueryPlan(
                "attendance JOIN students ON students.id = attendance.student_id JOIN courses ON courses.course_id = attendance.course_id",
                ["attendance.*", "students.name", "courses.course_name"],
                [f"LOWER(courses.course_name) = {literal(COURSE_ALIASES.get(course_name, course_name))}"],
            )
            q.values.add(course_name)
            return q.complete(plan)
        plan = q.base("courses")
        metric = q.metric("courses", "average_attendance")
        plan.columns.append(f"{metric} AS average_attendance")
        for match in re.finditer(rf"\battendance\s+(?P<op>{OP})\s*(?P<number>{NUMBER})", text):
            q.used_comparisons.add(match.start('op'))
            plan.predicates.append(f"{metric} {OPERATORS[match['op']]} {match['number']}")
        q.rank(plan, metric, "courses", nullable=True)
        return q.complete(plan)

    if (students and (courses or course_name)) or (courses and enrollment):
        course_threshold = q.threshold("courses")
        student_threshold = q.threshold("students")
        no_students = bool(re.search(r"\b(?:no|without) (?:students?|enrollments?)\b", text))
        per_student = bool(re.search(r"\b(?:each|per) student\b|\bcourses? (?:taken|enrolled in) by\b", text))
        if students and (course_threshold or (per_student and count_language)):
            return q.counts("students", ["course_count"], [("course_count", course_threshold)])
        if student_threshold or no_students or (count_language and not course_name):
            name = "enrollment_count" if q.has("enrollments") and not students else "student_count"
            metrics = [name]
            if attendance:
                if "average" not in text:
                    raise ValueError("Specify whether attendance filters students or is an average for each course.")
                metrics.append("average_attendance")
            plan = q.base("courses")
            expressions = {metric: q.metric("courses", metric) for metric in metrics}
            plan.columns += [f"{expr} AS {metric}" for metric, expr in expressions.items()]
            if student_threshold:
                op, value = student_threshold
                plan.predicates.append(f"{expressions[name]} {op} {value}")
            if no_students:
                plan.predicates.append(f"{expressions[name]} = 0")
            if attendance:
                for match in re.finditer(rf"\battendance\s+(?P<op>{OP})\s*(?P<number>{NUMBER})", text):
                    q.used_comparisons.add(match.start('op'))
                    plan.predicates.append(f"{expressions['average_attendance']} {OPERATORS[match['op']]} {match['number']}")
            q.rank(plan, expressions[name], "courses")
            return q.complete(plan)
        if re.search(r"\b(?:not enrolled|no courses|without courses)\b", text) or course_name:
            plan = q.base("students", all_columns=True)
            predicate = q.enrollment_exists(course_name)
            if "not enrolled" in text or re.search(r"\b(?:no|without) courses?\b", text):
                predicate = "NOT " + predicate
            plan.predicates.append(predicate)
            if excluded_course:
                plan.predicates.append("NOT " + q.enrollment_exists(excluded_course))
            q.attribute_filters(plan, "students", ("attendance", "marks", "age"))
            return q.complete(plan)
        # A simple enrolled-in-courses condition selects students once. A
        # request to show the courses themselves selects student/course pairs.
        pairs = bool(re.search(r"\bcourses? (?:they|that|taken|each)\b|\beach course\b|\bstudents? and\b", text))
        if enrollment and not pairs:
            plan = q.base("students", all_columns=True)
            plan.predicates.append(q.enrollment_exists())
            return q.complete(plan)
        q.require("students", "id", "name")
        q.require("enrollments", "student_id", "course_id")
        q.require("courses", "course_id", "course_name")
        plan = QueryPlan(
            "students LEFT JOIN enrollments ON enrollments.student_id = students.id LEFT JOIN courses ON courses.course_id = enrollments.course_id",
            ["students.id", "students.name", "courses.course_id", "courses.course_name"], distinct=True,
        )
        if re.search(r"\beach course\b", text):
            plan.source = "courses LEFT JOIN enrollments ON enrollments.course_id = courses.course_id LEFT JOIN students ON students.id = enrollments.student_id"
        if "computer science students" in text:
            q.values.add("computer science")
            if CS_STUDENT_BASIS == "subject":
                q.require("students", "subject")
                plan.predicates.append("LOWER(students.subject) = 'computer science'")
            else:
                plan.predicates.append(q.enrollment_exists(department_name="computer science"))
        q.attribute_filters(plan, "students", ("attendance", "marks", "age"))
        return q.complete(plan)

    if students and excluded_course:
        plan = q.base("students", all_columns=True)
        plan.predicates += [q.enrollment_exists(course_name), "NOT " + q.enrollment_exists(excluded_course)]
        return q.complete(plan)

    if attendance and students:
        q.require("students", "attendance")
        plan = q.base("students", all_columns=True)
        q.attribute_filters(plan, "students", ("attendance", "marks", "age"))
        ranking = bool(re.search(r"\b(?:highest|lowest|top|bottom|sorted|sort|order|descending|ascending)\b", text))
        if "average" in text and not ranking:
            plan.columns = ["AVG(students.attendance) AS average_attendance"]
        elif re.search(r"\bcount\b|\bhow many\b", text):
            plan.columns = ["COUNT(*) AS student_count"]
        else:
            q.rank(plan, "students.attendance", "students", nullable=True)
        return q.complete(plan)
    return None


def describe_query_semantics(question):
    """User-visible definitions for measures or labels that need context."""
    text = question.lower()
    notes = []
    if "attendance" in text:
        if re.search(r"\bcourses?\b", text) and "average" in text:
            if COURSE_ATTENDANCE_BASIS == "records":
                notes.append("Course attendance is the percentage of recorded entries marked Present. Courses without records have no percentage (NULL).")
            else:
                notes.append("Course attendance is the average overall attendance percentage of its enrolled students. Missing percentages are excluded.")
        elif re.search(r"\bstudents?\b", text):
            notes.append("Student attendance uses the stored overall percentage. Missing percentages are excluded from averages and top/bottom rankings.")
        else:
            notes.append("Course attendance details show recorded dates and Present/Absent statuses.")
    if "computer science students" in text:
        if CS_STUDENT_BASIS == "subject":
            notes.append("Computer Science students means students whose subject is Computer Science.")
        else:
            notes.append("Computer Science students means students enrolled in a course offered by that department.")
    if re.search(r"\bdatabase\b", text) and "database management systems" not in text:
        notes.append("Database refers to the Database Management Systems course.")
    return notes
