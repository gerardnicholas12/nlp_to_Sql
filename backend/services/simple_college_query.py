"""Small, explicit NLP-to-SQL grammar for the six-table college schema.

All identity columns and name columns are entity-specific. That keeps generated
joins unambiguous and makes the schema readable in a guide or ER diagram.
"""

from collections import deque
import re

TABLE_COLUMNS = {
    'students': ('student_id', 'srn', 'student_name', 'address', 'phone', 'email', 'class_id'),
    'faculty': ('faculty_id', 'faculty_name', 'designation', 'qualification', 'experience'),
    'courses': ('course_id', 'course_name', 'credits', 'faculty_id'),
    'classes': ('class_id', 'class_name', 'semester'),
    'exams': ('exam_id', 'exam_name', 'class_id', 'course_id', 'exam_date'),
    'results': ('result_id', 'student_id', 'exam_id', 'marks'),
}
ALIASES = {
    'student': 'students', 'studinfo': 'students', 'teacher': 'faculty',
    'teachers': 'faculty', 'faculties': 'faculty', 'faculty_member': 'faculty',
    'course': 'courses', 'class': 'classes', 'exam': 'exams', 'result': 'results',
}
TABLE_ID = {table: columns[0] for table, columns in TABLE_COLUMNS.items()}
TABLE_NAME = {'students': 'student_name', 'faculty': 'faculty_name',
              'courses': 'course_name', 'classes': 'class_name', 'exams': 'exam_name'}
FIELD_ALIASES = {
    'names': 'name', 'name': 'name', 'mark': 'marks', 'score': 'marks', 'scores': 'marks',
    'sem': 'semester', 'exp': 'experience', 'emailid': 'email',
    'studentname': 'student_name', 'facultyname': 'faculty_name',
    'coursename': 'course_name', 'classname': 'class_name', 'examname': 'exam_name',
    'studentid': 'student_id', 'facultyid': 'faculty_id', 'courseid': 'course_id',
    'classid': 'class_id', 'examid': 'exam_id', 'resultid': 'result_id',
}
EDGES = [
    ('students', 'class_id', 'classes', 'class_id'),
    ('courses', 'faculty_id', 'faculty', 'faculty_id'),
    ('exams', 'class_id', 'classes', 'class_id'),
    ('exams', 'course_id', 'courses', 'course_id'),
    ('results', 'student_id', 'students', 'student_id'),
    ('results', 'exam_id', 'exams', 'exam_id'),
]
NUMERIC = {'marks', 'experience', 'credits', 'semester', 'student_id', 'result_id',
           'exam_id', 'class_id', 'course_id', 'faculty_id'}
OPERATORS = {'above': '>', 'greater than': '>', 'more than': '>', 'over': '>',
             'below': '<', 'less than': '<', 'under': '<', 'at least': '>=',
             'at most': '<=', 'equal to': '=', 'equals': '=', 'is': '=',
             '>': '>', '<': '<', '>=': '>=', '<=': '<=', '=': '='}


def is_simple_schema(schema):
    return all(set(columns) <= set(schema.get(table, ())) for table, columns in TABLE_COLUMNS.items())


def literal(text):
    return "'" + text.replace('\\', '\\\\').replace("'", "''") + "'"


def normalize(question):
    pieces = re.split(r'("[^"]*"|\'[^\']*\')', question.strip().rstrip('?.!').lower())
    for i in range(0, len(pieces), 2):
        text = pieces[i]
        for source, target in sorted(ALIASES.items(), key=lambda item: -len(item[0])):
            text = re.sub(r'\b' + re.escape(source) + r'\b', target, text)
        for source, target in sorted(FIELD_ALIASES.items(), key=lambda item: -len(item[0])):
            text = re.sub(r'\b' + re.escape(source) + r'\b', target, text)
        text = re.sub(r'\bstudents?\s+name\b', 'students.student_name', text)
        text = re.sub(r'\bfacult(?:y|ies)\s+name\b', 'faculty.faculty_name', text)
        text = re.sub(r'\bcourses?\s+name\b', 'courses.course_name', text)
        text = re.sub(r'\bclasses?\s+name\b', 'classes.class_name', text)
        text = re.sub(r'\bexams?\s+name\b', 'exams.exam_name', text)
        pieces[i] = text
    return re.sub(r'\s+', ' ', ''.join(pieces)).strip()


def extract_student_name(question):
    """Bind a named recipient of marks before normalizing field aliases."""
    match = re.search(
        r'\b(?P<field>marks?|scores?)\s+'
        r'(?:(?:secured|scored|obtained|earned)\s+by|of|for)\s+'
        r'(?:the\s+student\s+|student\s+)?'
        r'(?P<name>"[^"]+"|\'[^\']+\'|.+?)'
        r'(?=\s+(?:from|with|where|whose|order|sort)\b|[?.!]*\s*$)',
        question, re.IGNORECASE,
    )
    if not match:
        return question, None
    name = match['name'].strip()
    if name in TABLE_COLUMNS or name.lower() in {*TABLE_COLUMNS, *ALIASES}:
        # "Average marks of results" still refers to a table.
        return question, None
    if len(name) >= 2 and name[0] in ('"', "'") and name[-1] == name[0]:
        name = name[1:-1]
    name = ' '.join(name.lower().split())
    word = r"[^\W\d_]+(?:[-'\u2019][^\W\d_]+)*"
    if (not re.fullmatch(word + r'(?:\s+' + word + r')*', name)
            or set(name.split()) & {'and', 'or', 'not', 'with', 'without', 'above', 'below'}):
        raise ValueError('Specify one student name; put additional conditions after WITH or WHERE.')
    return question[:match.start()] + match['field'] + question[match.end():], name


def qualification_filter(text):
    """Parse an implicit qualification, leaving later AND filters intact."""
    match = re.match(
        r'(?:(?:a|an)\s+)?'
        r'(?P<degree>ph\.?d\.?|[mb]\.?tech\.?|[mb]\.?sc\.?|mba|mca)'
        r'(?![\w.])(?P<subject>(?:\s+.*?)?)'
        r'(?=\s+(?:and|or)\b|$)', text,
    )
    if not match:
        return None
    subject = match['subject'].strip()
    if subject == 'in':
        raise ValueError('Name the qualification subject after IN, for example PhD in Mathematics.')
    subject = re.sub(r'^in\s+', '', subject)
    word = r"[^\W\d_]+(?:[-'\u2019][^\W\d_]+)*"
    if subject and (
        not re.fullmatch(word + r'(?:\s+' + word + r')*', subject)
        or set(subject.split()) & {'not', 'no', 'with', 'without', 'where', 'whose', 'above', 'below', 'from'}
    ):
        raise ValueError('Use a degree and subject, followed by AND for additional filters.')
    return {
        'field': 'faculty.qualification',
        'between': None,
        'degree': match['degree'].replace('.', ''),
        'subject': subject,
    }, match.end()


def special(q):
    if re.fullmatch(r'(?:count|number of|how many) students (?:by|per|in each) classes', q):
        return ('SELECT classes.class_id, classes.class_name, COUNT(students.student_id) AS student_count '
                'FROM classes LEFT JOIN students ON students.class_id=classes.class_id '
                'GROUP BY classes.class_id, classes.class_name ORDER BY classes.class_id')
    if re.fullmatch(r'(?:show |list |find )?students (?:with no|without) results', q):
        return ('SELECT students.* FROM students WHERE NOT EXISTS '
                '(SELECT 1 FROM results WHERE results.student_id=students.student_id) '
                'ORDER BY students.student_id')
    if re.fullmatch(r'(?:show |list |find )?faculty (?:with no|without) courses', q):
        return ('SELECT faculty.* FROM faculty WHERE NOT EXISTS '
                '(SELECT 1 FROM courses WHERE courses.faculty_id=faculty.faculty_id) '
                'ORDER BY faculty.faculty_id')
    if re.fullmatch(r'(?:show )?(?:average|avg) marks (?:by|per|for each) courses', q):
        return ('SELECT courses.course_id, courses.course_name, AVG(results.marks) AS average_marks '
                'FROM courses LEFT JOIN exams ON exams.course_id=courses.course_id '
                'LEFT JOIN results ON results.exam_id=exams.exam_id '
                'GROUP BY courses.course_id, courses.course_name ORDER BY courses.course_id')
    if re.fullmatch(r'(?:show )?(?:average|avg) marks (?:by|per|for each) students', q):
        return ('SELECT students.student_id, students.student_name, AVG(results.marks) AS average_marks '
                'FROM students LEFT JOIN results ON results.student_id=students.student_id '
                'GROUP BY students.student_id, students.student_name ORDER BY students.student_id')
    return None


def _path(start, target):
    queue = deque([(start, [])])
    seen = {start}
    while queue:
        node, path = queue.popleft()
        if node == target:
            return path
        for left, left_col, right, right_col in EDGES:
            if node == left:
                neighbor = right
                condition = f'{left}.{left_col} = {right}.{right_col}'
            elif node == right:
                neighbor = left
                condition = f'{left}.{left_col} = {right}.{right_col}'
            else:
                continue
            if neighbor not in seen:
                seen.add(neighbor)
                queue.append((neighbor, path + [(neighbor, condition)]))
    return None


def compile_simple_query(question, schema):
    if not isinstance(question, str) or not question.strip():
        raise ValueError('Enter a non-empty question.')
    if any(fragment in question for fragment in (';', '--', '/*', '*/', '`')):
        raise ValueError('Enter a natural-language question, not SQL.')
    question, student_name = extract_student_name(question)
    q = normalize(question)
    sql = special(q)
    if sql:
        return sql

    limit = None
    direction = 'ASC'
    sort_field = None
    match = re.search(r'\b(?:top|bottom|first|last) (\d+)\b', q)
    if match:
        limit = int(match[1])
        if not 1 <= limit <= 1000:
            raise ValueError('Choose a limit between 1 and 1000.')
        direction = 'DESC' if match[0].startswith(('top', 'last')) else 'ASC'
        q = q[:match.start()] + q[match.end():]
    match = re.search(r'\b(?:with (?:the )?)?(highest|lowest) (marks|experience|credits)\b', q)
    if match:
        direction = 'DESC' if match[1] == 'highest' else 'ASC'
        sort_field = match[2]
        limit = limit or 1
        q = q[:match.start()] + q[match.end():]
    match = re.search(r'\b(?:order|sort)(?:ed)? by ([\w.]+)(?: (ascending|descending|asc|desc))?$', q.strip())
    if match:
        sort_field = match[1]
        direction = 'DESC' if match[2] in ('descending', 'desc') else 'ASC'
        q = q[:match.start()]

    q = re.sub(r'\bin semester (\d+)\b', r'with classes.semester = \1', q)
    q = re.sub(r'\bin classes\s+("[^"]+"|\'[^\']+\'|[a-z]+-\d+[a-z]?)', r'with classes.class_name = \1', q)
    parts = re.split(r'\b(?:with|where|whose)\b', q, maxsplit=1)
    body = parts[0].strip()
    raw_filters = []
    if len(parts) > 1:
        remainder = parts[1].strip()
        op_pattern = '|'.join(re.escape(x) for x in sorted(OPERATORS, key=len, reverse=True))
        pattern = re.compile(rf'(?P<field>[\w.]+)\s+(?:(?P<between>between)\s+(?P<low>\d+(?:\.\d+)?)\s+and\s+(?P<high>\d+(?:\.\d+)?)|(?P<op>{op_pattern})\s+(?P<value>"[^"]*"|\'[^\']*\'|[-\w.]+))')
        while remainder:
            item = pattern.match(remainder)
            qualification = qualification_filter(remainder) if not item and re.search(r'\bfaculty\b', body) else None
            if item:
                raw_filters.append(item.groupdict())
                consumed = item.end()
            elif qualification:
                spec, consumed = qualification
                raw_filters.append(spec)
            else:
                raise ValueError('Use an explicit filter such as marks above 80, semester is 3, or class name is "CSE-3A".')
            remainder = remainder[consumed:].strip()
            if remainder:
                if not remainder.startswith('and '):
                    raise ValueError('Combine filters with AND, or ask separate questions.')
                remainder = remainder[4:].strip()

    tokens = re.findall(r'[a-z_]+(?:\.[a-z_]+)?', body)
    mentions = list(dict.fromkeys(t.split('.')[0] for t in tokens if t.split('.')[0] in TABLE_COLUMNS))
    if student_name and not mentions:
        mentions = ['students']
    aggregate = next(({'average': 'AVG', 'avg': 'AVG', 'sum': 'SUM', 'minimum': 'MIN', 'maximum': 'MAX'}[t]
                      for t in tokens if t in ('average', 'avg', 'sum', 'minimum', 'maximum')), None)
    count = 'count' in tokens or ('how' in tokens and 'many' in tokens)
    stop = {'show', 'list', 'find', 'get', 'display', 'all', 'the', 'their', 'and', 'of', 'from',
            'details', 'records', 'for', 'count', 'how', 'many', 'average', 'avg', 'sum', 'minimum', 'maximum'}
    field_tokens = [t for t in tokens if t not in stop and t not in TABLE_COLUMNS]
    if not mentions:
        raise ValueError('Name a table: students, faculty, courses, classes, exams, or results.')
    primary = mentions[0]

    def resolve(field):
        if field == 'name':
            return primary, TABLE_NAME.get(primary, field)
        if field == 'id':
            return primary, TABLE_ID[primary]
        if '.' in field:
            owner, column = field.split('.', 1)
            if owner in TABLE_COLUMNS and column in schema.get(owner, {}):
                return owner, column
        elif field in schema.get(primary, {}):
            return primary, field
        else:
            owners = [table for table in TABLE_COLUMNS if field in schema.get(table, {})]
            if len(owners) == 1:
                return owners[0], field
        raise ValueError(f'Unknown or ambiguous column "{field}". Use an entity-qualified column name.')

    fields = [resolve(f) for f in field_tokens]
    if student_name and fields and not (aggregate or count):
        # First names may match several students. Show the full name beside
        # each score so the output never silently chooses one person.
        identity = resolve('students.student_name')
        if identity not in fields:
            fields.insert(0, identity)
    filters = [(resolve(item['field']), item) for item in raw_filters]
    sort_owner = resolve(sort_field) if sort_field else ((primary, TABLE_ID[primary]) if limit else None)
    needed = list(dict.fromkeys(mentions + [table for table, _ in fields] + [table for (table, _), _ in filters] + ([sort_owner[0]] if sort_owner else []) + (['students'] if student_name else [])))
    root = 'results' if 'results' in needed else primary
    joined = [root]
    joins = []
    for target in needed:
        path = _path(root, target)
        if path is None:
            raise ValueError(f'No relationship is defined between {root} and {target}.')
        for table, condition in path:
            if table not in joined:
                joins.append(f'JOIN {table} ON {condition}')
                joined.append(table)
    multi = len(joined) > 1

    def column(owner):
        table, field = owner
        return f'{table}.{field}' if multi else field

    if count:
        selection = f'COUNT(DISTINCT {column((primary, TABLE_ID[primary]))}) AS total'
    elif aggregate:
        if len(fields) != 1 or fields[0][1] not in NUMERIC:
            raise ValueError('Name one numeric column to aggregate, for example average marks of results.')
        selection = f'{aggregate}({column(fields[0])}) AS value'
    elif fields:
        selection = ', '.join(column(owner) + (f' AS {owner[0]}_{owner[1]}' if multi else '')
                              for owner in dict.fromkeys(fields))
    elif multi:
        defaults = [(primary, TABLE_ID[primary])]
        if primary in TABLE_NAME:
            defaults.append((primary, TABLE_NAME[primary]))
        if 'results' in joined:
            defaults += [('results', 'result_id'), ('results', 'exam_id'), ('results', 'marks')]
        defaults += [(table, TABLE_NAME[table]) for table in mentions if table in TABLE_NAME and table != primary]
        selection = ', '.join(f'{column(owner)} AS {owner[0]}_{owner[1]}' for owner in dict.fromkeys(defaults))
    else:
        selection = '*'

    predicates = []
    if student_name:
        name_column = 'LOWER(' + column(resolve('students.student_name')) + ')'
        exact = f'{name_column} = {literal(student_name)}'
        if ' ' in student_name:
            predicates.append(exact)
        else:
            predicates.append(f'({exact} OR {name_column} LIKE {literal(student_name + " %")})')
    for owner, spec in filters:
        rendered_col = column(owner)
        if 'degree' in spec:
            # Match both "PhD Mathematics" and "Ph.D. in Mathematics".
            normalized = f"REPLACE(LOWER(REPLACE(TRIM({rendered_col}), '.', '')), ' in ', ' ')"
            degree = spec['degree']
            if spec['subject']:
                predicates.append(f"{normalized} = {literal(degree + ' ' + spec['subject'])}")
            else:
                predicates.append(f"({normalized} = {literal(degree)} OR {normalized} LIKE {literal(degree + ' %')})")
            continue
        if spec['between']:
            if owner[1] not in NUMERIC:
                raise ValueError('BETWEEN currently supports numeric columns only.')
            predicates.append(f'{rendered_col} BETWEEN {spec["low"]} AND {spec["high"]}')
            continue
        value = spec['value']
        if owner[1] in NUMERIC:
            if not re.fullmatch(r'-?\d+(?:\.\d+)?', value):
                raise ValueError('Use a number for ' + owner[1])
            rendered = value
        else:
            if OPERATORS[spec['op']] != '=':
                raise ValueError('Use IS or = for text filters.')
            rendered = literal(value.strip('\'"'))
            rendered_col = f'LOWER({rendered_col})'
        predicates.append(f'{rendered_col} {OPERATORS[spec["op"]]} {rendered}')

    if (count or aggregate) and (sort_owner or limit):
        raise ValueError('Ask for the aggregate without a ranking, or rank the individual records.')
    if limit and primary == 'students' and 'results' in joined:
        raise ValueError('Marks belong to exams. Ask for top results with highest marks, or average marks per student.')
    sql = f'SELECT {selection} FROM {root}'
    if joins:
        sql += ' ' + ' '.join(joins)
    if predicates:
        sql += ' WHERE ' + ' AND '.join(predicates)
    if not count and not aggregate:
        order_col = column(sort_owner) if sort_owner else column((root, TABLE_ID[root]))
        sql += f' ORDER BY {order_col} {direction}'
        if limit and sort_owner and sort_owner != (root, TABLE_ID[root]):
            sql += f', {column((root, TABLE_ID[root]))} ASC'
        if limit:
            sql += f' LIMIT {limit}'
    return sql


def describe_simple_query(question):
    return ['Marks are out of 100 for each student and exam. Missing results are not zero.'] if re.search(r'\b(marks?|scores?|results?)\b', question.lower()) else []
