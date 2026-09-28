# Shivani's part

from nltk.tokenize import word_tokenize
from mappings import (
    TABLE_MAP, COLUMN_MAP, RELATIONSHIPS, build_column_map, infer_table,
    query_schema,
)
from services.relationship_filters import extract_enrollment_filter
from services.academic_query import compile_academic_query

# ---------------- INTENT MAP ----------------

INTENT_MAP = {
    "show": "select",
    "display": "select",
    "list": "select",
    "count": "count",
    "total": "count",
}

SELECT_INTENT_WORDS = ["show", "display", "list", "get", "find"]

# ---------------- AGGREGATE MAP ----------------

AGGREGATE_MAP = {
    "average": "AVG",
    "avg": "AVG",

    "sum": "SUM",

    "minimum": "MIN",
    "min": "MIN",

    "maximum": "MAX",
    "max": "MAX",
    
    "distinct": "DISTINCT",
    "unique": "DISTINCT"
}

# ---------------- CONDITION MAP ----------------

CONDITION_MAP = {
    "above": "above",
    "greater": "above",
    "more": "above",
    "over": "above",
    ">": "above",
    ">=": "on_or_after",

    "below": "below",
    "less": "below",
    "lesser": "below",
    "under": "below",
    "<": "below",
    "<=": "on_or_before",

    "highest": "highest",
    "top": "highest",

    "lowest": "lowest",
    "least": "lowest",
    "bottom": "lowest",
    "last": "lowest",

    "equal": "equal",
    "equals": "equal",
    "is": "equal",
    "=": "equal",

    "before": "below",
    "after": "above",

    "since": "on_or_after",
    "till": "on_or_before",
    "until": "on_or_before",

    "older": "above",
    "younger": "below",

    # sentinel tokens produced by merge_comparison_phrases() below, standing
    # in for multi-word >=/<= phrasings ("at least", "3 or more", "equal to
    # or greater than", etc.) that a single-token scan can't recognize
    "AT_LEAST": "gte",
    "AT_MOST": "lte"
}

# CONDITION_MAP values that pick a *record* (ORDER BY ... LIMIT), as opposed
# to a WHERE comparison value
RECORD_CONDITION_TYPES = {"highest", "lowest"}

# CONDITION_MAP values that build a WHERE numeric comparison
VALUE_CONDITION_TYPES = {"above", "below", "equal", "on_or_after", "on_or_before", "gte", "lte"}

# raw trigger words that are always about the joining/hiring date, regardless
# of which column word (if any) happens to sit nearby
DATE_TRIGGER_WORDS = {"before", "after", "since", "till", "until"}

# columns that should never be treated as the "numeric_column" used in
# aggregates / above / below / equal / highest / lowest
CATEGORICAL_COLUMNS = ["department", "city", "gender", "name", "subject", "department_name", "course_name", "teacher_name", "email", "location", "grade", "status", "blood_groupp"]

# Tables that have a 'city' column (used for shared-column joins)
TABLES_WITH_CITY = {"students", "employees"}

# ---------------- DEPARTMENTS ----------------

DEPARTMENTS = [
    "it",
    "hr",
    "finance",
    "sales",
    "marketing"
]

# ---------------- CITIES ----------------

CITIES = [
    "bangalore",
    "mysore",
    "mangalore",
    "hubli",
    "belgaum"
]

# ---------------- GENDERS ----------------

GENDERS = [
    "male",
    "female"
]

# ---------------- LIKE ----------------

LIKE_KEYWORDS = ["like", "contains", "containing"]
STARTS_KEYWORDS = ["starting", "starts"]
ENDS_KEYWORDS = ["ending", "ends"]
LIKE_FILLER_WORDS = {"with", "the", "in", "of"}

# ---------------- ORDER BY ----------------

ORDER_TRIGGER_WORDS = ["order", "sort", "arrange"]

SORT_DIRECTION_MAP = {
    "ascending": "ASC",
    "asc": "ASC",
    "increasing": "ASC",

    "descending": "DESC",
    "desc": "DESC",
    "decreasing": "DESC",
}

# ---------------- JOIN ----------------

JOIN_TRIGGER_WORDS = ["join", "joined", "combined", "along", "same", "match", "matches", "matching"]

JOIN_TYPE_MAP = {
    "inner": "INNER JOIN",
    "left": "LEFT JOIN",
    "right": "RIGHT JOIN",
    "outer": "FULL OUTER",   # Special marker for full outer join simulation
    "full": "FULL OUTER",    # Special marker for full outer join simulation
    "cross": "CROSS JOIN",
}

# department only exists on employees - it is NOT shared with students,
# so it can't be a safe default join/compare key. name, age, gender, and
# city are the columns both tables actually have (confirmed against the
# real schema); city is the most meaningful one to match students and
# employees on by default when no join column is stated explicitly.
SHARED_COLUMN = "city"

# ---------------- NULL ----------------

NULL_TRIGGER_WORDS = ["null", "missing", "blank", "empty"]

# ---------------- HAVING ----------------

HAVING_TRIGGER_WORDS = ["having"]

# ---------------- EXISTS ----------------

EXISTS_TRIGGER_WORDS = ["exists", "exist", "belong", "belongs", "live", "lives", "lived"]

# ---------------- ANY / ALL ----------------

ANY_ALL_TRIGGER_WORDS = {"any": "ANY", "all": "ALL"}

# ---------------- UNION ----------------

UNION_TRIGGER_WORDS = ["union"]

# ---------------- CASE ----------------

CASE_TRIGGER_WORDS = ["label", "case"]

# ---------------- NULL FUNCTIONS (IFNULL / COALESCE) ----------------

IFNULL_TRIGGER_WORDS = ["ifnull", "coalesce"]


# ---------------- WORD NUMBERS ("fifty", "one hundred and five") ----------------

NUMBER_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}

SCALE_WORDS = {
    "hundred": 100,
    "thousand": 1000,
}


def words_to_numbers(tokens):
    """
    Replaces sequences of English number words with a single digit-string
    token, e.g. ["more", "than", "fifty"] -> ["more", "than", "50"],
    ["one", "hundred", "and", "five"] -> ["105"].

    "and" only bridges two number words when it directly follows a scale
    word (hundred/thousand) - this keeps "between twenty and fifty" as two
    separate numbers (20, 50) instead of merging them into one.
    """
    result = []
    i = 0
    n = len(tokens)

    while i < n:
        word = tokens[i]

        if word in NUMBER_WORDS or word in SCALE_WORDS:
            total = 0
            current = 0
            matched = False
            after_scale = False
            j = i

            while j < n:
                w = tokens[j]

                if w in NUMBER_WORDS:
                    current += NUMBER_WORDS[w]
                    matched = True
                    after_scale = False
                    j += 1

                elif w in SCALE_WORDS:
                    if current == 0:
                        current = 1
                    current *= SCALE_WORDS[w]
                    total += current
                    current = 0
                    matched = True
                    after_scale = True
                    j += 1

                elif w == "and" and after_scale:
                    after_scale = False
                    j += 1

                else:
                    break

            total += current

            if matched:
                result.append(str(total))
                i = j
                continue

        result.append(word)
        i += 1

    return result


def is_negated(tokens, idx, window=3):
    """Checks if the word 'not' appears shortly before tokens[idx]."""
    start = max(0, idx - window)
    return "not" in tokens[start:idx]


def build_categorical_condition(column, values, use_in, not_in=False):
    """
    values: list of (value, negated) tuples, in the order they were found.
    - if multiple values + 'or'/'in' present -> IN (...) / NOT IN (...) clause
    - otherwise -> use the last value found (keeps old behaviour), = or !=
    """
    if not values:
        return None

    if len(values) > 1 and use_in:
        in_list = ", ".join(f"'{v}'" for v, _ in values)
        keyword = "NOT IN" if not_in else "IN"
        return f"{column} {keyword} ({in_list})"

    val, negated = values[-1]
    operator = "!=" if negated else "="
    return f"{column} {operator} '{val}'"


def parse_or_clause(tokens, default_column=None, column_map=None):
    """
    Parses one half of an 'X or Y' sentence into a single WHERE condition
    string, e.g. ['below', '40'] -> 'marks < 40', or
    ['department', 'is', 'hr'] -> "department = 'HR'".
    default_column fills in the column when a clause only gives an
    operator + value (e.g. "or below 40" with no column word of its own).
    Returns None if nothing usable was found in this clause.
    """
    column_map = column_map if column_map is not None else COLUMN_MAP
    col = None
    operator_word = None
    val = None
    text_col = None
    text_val = None

    for word in tokens:
        if word in column_map and column_map[word].split(".")[-1] not in CATEGORICAL_COLUMNS:
            col = column_map[word]
        if word in DEPARTMENTS:
            text_col = "department"
            text_val = word.upper()
        if word in CITIES:
            text_col = "city"
            text_val = word.title()
        if word in GENDERS:
            text_col = "gender"
            text_val = word.capitalize()
        if word in CONDITION_MAP and CONDITION_MAP[word] in VALUE_CONDITION_TYPES:
            operator_word = CONDITION_MAP[word]
        if word.isdigit():
            val = word

    if text_col and text_val:
        return f"{column_map.get(text_col, text_col)} = '{text_val}'"

    if not col:
        col = default_column

    op_symbol_map = {"above": ">", "below": "<", "equal": "=", "on_or_after": ">=", "on_or_before": "<=", "gte": ">=", "lte": "<="}

    if col and operator_word and val:
        return f"{col} {op_symbol_map[operator_word]} {val}"

    return None


def merge_comparison_phrases(tokens):
    """
    Collapses multi-word >=/<= phrasings ('at least', 'equal to or greater
    than', '3 or more', etc.) into single sentinel tokens (AT_LEAST /
    AT_MOST) before any other parsing happens.

    This has to run first, because several of these phrases are built out
    of words that already mean something else on their own - "least" alone
    means "lowest" (ORDER BY ... LIMIT 1), and "more"/"greater" alone mean
    a strict ">". Collapsing the whole phrase up front stops those other
    rules from firing on words that are actually part of a >=/<= phrase.
    """
    AT_LEAST_PHRASES = [
        ("at", "least"),
        ("equal", "to", "or", "more", "than"),
        ("equal", "to", "or", "greater", "than"),
        ("equal", "to", "and", "more", "than"),
        ("equal", "to", "and", "greater", "than"),
        ("greater", "than", "or", "equal", "to"),
        ("more", "than", "or", "equal", "to"),
        ("or", "more"),
        ("or", "greater"),
        (">", "="),
    ]
    AT_MOST_PHRASES = [
        ("at", "most"),
        ("equal", "to", "or", "less", "than"),
        ("equal", "to", "or", "lesser", "than"),
        ("equal", "to", "and", "less", "than"),
        ("equal", "to", "and", "lesser", "than"),
        ("less", "than", "or", "equal", "to"),
        ("lesser", "than", "or", "equal", "to"),
        ("or", "less"),
        ("or", "fewer"),
        ("<", "="),
    ]

    # longest phrases first, so e.g. "...or more than" matches whole
    # before the shorter "or more" tail could match it partially
    all_phrases = sorted(
        [(p, "AT_LEAST") for p in AT_LEAST_PHRASES] + [(p, "AT_MOST") for p in AT_MOST_PHRASES],
        key=lambda pair: -len(pair[0])
    )

    result = []
    i = 0
    n = len(tokens)

    while i < n:
        matched = False
        for phrase, sentinel in all_phrases:
            plen = len(phrase)
            if tuple(tokens[i:i + plen]) == phrase:
                result.append(sentinel)
                i += plen
                matched = True
                break
        if not matched:
            result.append(tokens[i])
            i += 1

    return result


def convert_to_sql(question, schema=None):

    if not isinstance(question, str) or not question.strip():
        raise ValueError("Enter a non-empty question.")
    from services.simple_college_query import is_simple_schema, compile_simple_query
    if schema is not None and is_simple_schema(schema):
        return compile_simple_query(question, schema)
    schema = query_schema(schema)
    academic_sql = compile_academic_query(
        question, schema, words_to_numbers(word_tokenize(question.lower(), preserve_line=True))
    )
    if academic_sql is not None:
        return academic_sql
    question, enrollment_condition = extract_enrollment_filter(question, schema)
    question = question.lower()
    tokens = word_tokenize(question, preserve_line=True)
    tokens = words_to_numbers(tokens)
    tokens = merge_comparison_phrases(tokens)

    table = "students"
    intent = "select"
    aggregate_function = None

    record_condition = None
    record_condition_idx = None

    value_condition = None
    value_condition_idx = None
    value_condition_word = None

    value = None

    numeric_column = None
    condition_column = None
    column_aliases = {}

    department_values = []
    city_values = []
    gender_values = []
    name_value = None
    subject_value = None

    group_by_column = None
    limit_value = None
    between_values = None

    order_by_column = None
    order_by_direction = "ASC"
    order_requested = False

    like_column = None
    like_pattern = None
    like_mode = "contains"
    like_negated = False

    conditions = [enrollment_condition] if enrollment_condition else []

    # ---------------- SUBJECT DETECTION ----------------

    if "computer science" in question:
        subject_value = "Computer Science"

    elif "mathematics" in question:
        subject_value = "Mathematics"

    elif "science" in question:
        subject_value = "Science"

    elif "english" in question:
        subject_value = "English"

    # Table mentions and column ownership are resolved before clause parsing.
    # Singular "department" describes employees.department unless a join or
    # an explicit departments-table reference makes it a table request.
    inferred_table = infer_table(tokens, schema)
    employee_context = any(TABLE_MAP.get(w) == "employees" for w in tokens) or inferred_table == "employees"
    table_mentions = []
    for i, word in enumerate(tokens):
        key = word.split(".")[0]
        owner = "attendance" if key == "attendance" and "." in word else TABLE_MAP.get(key)
        if owner is None:
            continue
        if word in ("department", "dept") and employee_context:
            if not any(w in ("join", "joined") for w in tokens[max(0, i - 2):i]):
                continue
        if owner not in schema:
            raise ValueError(f"Table '{owner}' is not available in the database.")
        table_mentions.append((i, owner))
    tables_found = list(dict.fromkeys(owner for _, owner in table_mentions))
    table = tables_found[0] if tables_found else inferred_table
    if table not in schema:
        raise ValueError("Couldn't identify an available table. Include the table name.")

    join_type = next((JOIN_TYPE_MAP[w] for w in tokens if w in JOIN_TYPE_MAP), None)
    second_table = None
    join_columns = []
    join_pairs = []
    join_related_indices = set()
    union_second_table = None
    union_all = "all" in tokens
    is_subquery = any(w in EXISTS_TRIGGER_WORDS for w in tokens) or any(
        w in ("any", "all") and any(t in CONDITION_MAP for t in tokens[:i])
        for i, w in enumerate(tokens)
    ) or any(tokens[i - 1] == "no" for i, _ in table_mentions if i > 0)
    if len(tables_found) > 2:
        raise ValueError("Please use at most two tables in one question.")
    if len(tables_found) == 2 and "union" in tokens:
        union_second_table = tables_found[1]
    elif len(tables_found) == 2 and not is_subquery:
        second_table = tables_found[1]
        join_type = join_type or "INNER JOIN"
        join_related_indices = {i for i, w in enumerate(tokens) if w in JOIN_TRIGGER_WORDS}
        for local, local_col, foreign, foreign_col in RELATIONSHIPS:
            if (local, foreign) == (table, second_table):
                join_pairs = [(local_col, foreign_col)]
                break
            if (foreign, local) == (table, second_table):
                join_pairs = [(foreign_col, local_col)]
                break
        # Explicit shared-column comparisons override the FK default.
        explicit_columns = []
        for i, word in enumerate(tokens):
            if word in ("same", "matching"):
                indices = range(i + 1, len(tokens))
            elif word in ("match", "matches"):
                indices = range(i - 1, -1, -1)
            else:
                continue
            for j in indices:
                if tokens[j] in ("where", "whose", "if", "when", "order", "sort", "with"):
                    break
                column = COLUMN_MAP.get(tokens[j])
                if column:
                    if column not in schema[table] or column not in schema[second_table]:
                        raise ValueError(f"Column '{column}' is not shared by {table} and {second_table}.")
                    if column not in explicit_columns:
                        explicit_columns.append(column)
                    join_related_indices.add(j)
        if explicit_columns:
            join_pairs = [(column, column) for column in explicit_columns]
        if not join_pairs and table in TABLES_WITH_CITY and second_table in TABLES_WITH_CITY:
            join_pairs = [(SHARED_COLUMN, SHARED_COLUMN)]
        if not join_pairs and join_type != "CROSS JOIN":
            raise ValueError(f"No direct relationship is defined between {table} and {second_table}.")
        for left, right in join_pairs:
            if left not in schema[table] or right not in schema[second_table]:
                raise ValueError("The join relationship does not match the database schema.")
        join_columns = [left for left, _ in join_pairs]

    column_map = build_column_map(table, [second_table] if second_table else [], schema)
    # "course name and teacher name" carries the same ownership as dotted
    # notation. Preserve it throughout SELECT, filtering, sorting and grouping.
    mention_by_index = dict(table_mentions)
    for i, word in enumerate(tokens):
        if i - 1 in mention_by_index and word in column_map and word not in TABLE_MAP:
            owner = mention_by_index[i - 1]
            qualified = f"{owner}.{word}"
            if qualified in column_map:
                tokens[i] = qualified
        if (word in COLUMN_MAP and word not in column_map and word not in TABLE_MAP
                and i not in join_related_indices and not is_subquery):
            raise ValueError(f"Column '{word}' is not available on the requested tables.")
        if "." in tokens[i] and tokens[i] != "." and not tokens[i].replace(".", "", 1).isdigit():
            if tokens[i] not in column_map and not is_subquery:
                raise ValueError(f"Unknown column '{tokens[i]}' for the requested tables.")

    # ---------------- INTENT ----------------

    for word in tokens:
        if word in INTENT_MAP:
            intent = INTENT_MAP[word]

    # ---------------- AGGREGATE ----------------

    aggregate_idx = None

    for i, word in enumerate(tokens):
        if word in AGGREGATE_MAP:
            aggregate_function = AGGREGATE_MAP[word]
            aggregate_idx = i

    # ---------------- CONDITION ----------------
    # split into "record" conditions (highest/lowest -> ORDER BY ... LIMIT)
    # and "value" conditions (above/below/since/etc -> WHERE comparison), so
    # a query using both doesn't let one silently overwrite the other.

    for i, word in enumerate(tokens):
        if word in CONDITION_MAP:
            mapped = CONDITION_MAP[word]

            if mapped in RECORD_CONDITION_TYPES:
                record_condition = mapped
                record_condition_idx = i

            elif mapped in VALUE_CONDITION_TYPES:
                value_condition = mapped
                value_condition_idx = i
                value_condition_word = word

    # ---------------- GROUP BY ("... by department", "... per subject") ----------------
    # only meaningful alongside an aggregate or a count, otherwise "top 3 by
    # salary" would be mistaken for a GROUP BY instead of a sort column.

    if aggregate_function or intent == "count":
        for keyword in ["by", "per", "each"]:
            if keyword in tokens:
                idx = tokens.index(keyword)
                if idx + 1 < len(tokens):
                    next_word = tokens[idx + 1]
                    if next_word in column_map:
                        group_by_column = column_map[next_word]

        # implicit pattern: "cities where average marks..." / "departments
        # where avg salary..." - the categorical column mentioned before the
        # aggregate word is treated as the GROUP BY target when no explicit
        # by/per/each keyword was found
        if not group_by_column and aggregate_idx is not None:
            for word in tokens[:aggregate_idx]:
                if word in column_map and column_map[word].split(".")[-1] in ("department", "city", "gender"):
                    group_by_column = column_map[word]
                    break

    # implicit COUNT: "<column>s having more than N ..." with no explicit
    # "count"/aggregate word still means "how many rows per column value"
    if not group_by_column and "having" in tokens:
        having_word_idx = tokens.index("having")
        for word in tokens[:having_word_idx]:
            if word in column_map:
                group_by_column = column_map[word]
        if group_by_column and intent != "count" and not aggregate_function:
            intent = "count"

    # a numeric comparison alongside a GROUP BY + aggregate/count belongs in
    # HAVING (applied after grouping), not WHERE (applied before) - this
    # covers both "... having more than 2 ..." and "... average marks are
    # greater than 80" phrasings, so it's checked once here and reused both
    # to build HAVING later and to skip the normal WHERE numeric condition
    # (computed further down, right after `value` itself is resolved)

    # ---------------- BETWEEN ----------------

    between_negated = False
    between_idx = None

    if "between" in tokens:
        b_idx = tokens.index("between")
        between_idx = b_idx
        nums_after = [w for w in tokens[b_idx:] if w.isdigit()]
        if len(nums_after) >= 2:
            between_values = (nums_after[0], nums_after[1])
            between_negated = is_negated(tokens, b_idx, window=3)

    between_nums = set(between_values) if between_values else set()

    # ---------------- NUMERIC COLUMN RESOLUTION ----------------
    # numeric_column = the aggregate/sort target ("average SALARY", "highest MARKS")
    # condition_column = the WHERE-comparison column ("marks ABOVE 80", "joined SINCE 2015")
    # These can differ (e.g. "average salary ... since 2015" aggregates
    # salary but filters on joining_year), so they're resolved independently.

    numeric_candidates = []
    for i, word in enumerate(tokens):
        if i in join_related_indices:
            continue
        if word in column_map and column_map[word].split(".")[-1] not in CATEGORICAL_COLUMNS:
            numeric_candidates.append((i, column_map[word]))

    def nearest_column(anchor_idx):
        if anchor_idx is None or not numeric_candidates:
            return None
        return min(
            numeric_candidates, key=lambda c: abs(c[0] - anchor_idx)
        )[1]

    # numeric_column: anchor on the aggregate word, else the highest/lowest
    # word, else just the last numeric-looking column mentioned
    sort_anchor_idx = None
    if aggregate_idx is not None:
        sort_anchor_idx = aggregate_idx
    elif record_condition_idx is not None:
        sort_anchor_idx = record_condition_idx

    if sort_anchor_idx is not None:
        numeric_column = nearest_column(sort_anchor_idx)
    elif numeric_candidates:
        numeric_column = numeric_candidates[-1][1]

    # condition_column: date words (before/after/since/till/until) always
    # mean the joining/hiring year, regardless of any other column mentioned
    if value_condition_word in DATE_TRIGGER_WORDS:
        condition_column = column_map.get("joining_year", "joining_year")
    else:
        value_anchor_idx = value_condition_idx if value_condition_idx is not None else between_idx
        condition_column = nearest_column(value_anchor_idx)

    # "older/younger than" implies an age comparison even when the word
    # "age" itself is never mentioned - applies generally, not just inside
    # an ANY/ALL clause
    if "older" in tokens or "younger" in tokens:
        if condition_column is None:
            condition_column = column_map.get("age", "age")
        if numeric_column is None:
            numeric_column = column_map.get("age", "age")

    # ---------------- TOP / FIRST N / BOTTOM / LAST N ----------------
    # (computed before the generic number scan so its digit token can be
    # excluded from being treated as a WHERE comparison value)

    limit_value_idx = None

    for keyword in ["top", "first", "bottom", "last"]:
        if keyword in tokens:
            idx = tokens.index(keyword)
            for i, word in enumerate(tokens[idx:idx + 3], start=idx):
                if word.isdigit():
                    limit_value = word
                    limit_value_idx = i
                    break

    if limit_value is None and record_condition in ("highest", "lowest") and record_condition_idx is not None:
        window_start = max(0, record_condition_idx - 2)
        window_end = record_condition_idx + 3
        for i, word in enumerate(tokens[window_start:window_end], start=window_start):
            if word.isdigit():
                limit_value = word
                limit_value_idx = i
                break

    # ---------------- EXPLICIT LIMIT ----------------

    if limit_value is None and "limit" in tokens:
        idx = tokens.index("limit")
        for i, word in enumerate(tokens[idx:idx + 3], start=idx):
            if word.isdigit():
                limit_value = word
                limit_value_idx = i
                break

    # ---------------- NUMBER (generic comparison value) ----------------

    for i, word in enumerate(tokens):
        if word.isdigit() and word not in between_nums and i != limit_value_idx:
            value = word

    # a numeric comparison alongside a GROUP BY + aggregate/count belongs in
    # HAVING (applied after grouping), not WHERE (applied before) - this
    # covers both "... having more than 2 ..." and "... average marks are
    # greater than 80" phrasings
    condition_is_having = bool(
        group_by_column and (aggregate_function or intent == "count")
        and value_condition in ("above", "below", "gte", "lte") and value
    )

    # ---------------- DEPARTMENT ----------------

    for i, word in enumerate(tokens):
        if word in DEPARTMENTS:
            department_values.append((word.upper(), is_negated(tokens, i)))

    # ---------------- CITY ----------------

    for i, word in enumerate(tokens):
        if word in CITIES:
            city_values.append((word.title(), is_negated(tokens, i)))

    # ---------------- GENDER ----------------

    for i, word in enumerate(tokens):
        if word in GENDERS:
            gender_values.append((word.capitalize(), is_negated(tokens, i)))

    # ---------------- NAME ----------------

    if "named" in tokens:

        idx = tokens.index("named")

        if idx + 1 < len(tokens):
            name_value = tokens[idx + 1].capitalize()

    # ---------------- NULL CONDITION ----------------

    null_column = None
    null_negated = False

    for i, word in enumerate(tokens):
        if word in NULL_TRIGGER_WORDS:
            null_negated = is_negated(tokens, i, window=3)

            # the column can appear either before ("null marks") or after
            # ("missing department") the trigger word
            backward_window = tokens[max(0, i - 3):i]
            for w in backward_window:
                if w in column_map:
                    null_column = column_map[w]

            if null_column is None:
                forward_window = tokens[i + 1:i + 4]
                for w in forward_window:
                    if w in column_map:
                        null_column = column_map[w]
                        break
            break

    if null_column is None and "no" in tokens:
        idx = tokens.index("no")
        if idx + 1 < len(tokens):
            next_word = tokens[idx + 1]
            if next_word in column_map:
                null_column = column_map[next_word]

    # ---------------- NO TABLE (for relationships) ----------------
    no_table = None
    if "no" in tokens:
        idx = tokens.index("no")
        if idx + 1 < len(tokens):
            next_word = tokens[idx + 1]
            if next_word in TABLE_MAP:
                no_table = TABLE_MAP[next_word]

    if no_table and no_table != table:
        # Find a relationship between table and no_table
        found = False
        for local_table, local_col, foreign_table, foreign_col in RELATIONSHIPS:
            if local_table == no_table and foreign_table == table:
                # no_table has a foreign key to table
                conditions.append(f"NOT EXISTS (SELECT 1 FROM {no_table} WHERE {no_table}.{local_col} = {table}.{foreign_col})")
                found = True
                break
            elif local_table == table and foreign_table == no_table:
                # table has a foreign key to no_table
                conditions.append(f"NOT EXISTS (SELECT 1 FROM {no_table} WHERE {no_table}.{foreign_col} = {table}.{local_col})")
                found = True
                break
        if not found:
            # Fallback: try to use SHARED_COLUMN? But we don't know.
            # For now, do nothing and maybe the query will be wrong.
            pass

     # ---------------- EXISTS ----------------

    exists_second_table = None
    exists_column = SHARED_COLUMN

    if any(w in tokens for w in EXISTS_TRIGGER_WORDS):
        tables_found_exists = []
        for word in tokens:
            if word in TABLE_MAP and TABLE_MAP[word] not in tables_found_exists:
                tables_found_exists.append(TABLE_MAP[word])

        if len(tables_found_exists) >= 2:
            table = tables_found_exists[0]
            exists_second_table = tables_found_exists[1]

        # the column both tables should match on - the first column_map
        # word anywhere in the sentence, defaulting to department if none
        # is mentioned at all
        for word in tokens:
            if word in column_map:
                exists_column = column_map[word]
                break

    # ---------------- ANY / ALL ----------------

    any_all_keyword = None
    any_all_sub_table = None
    any_all_sub_column = None

    for i, word in enumerate(tokens):
        if word in ANY_ALL_TRIGGER_WORDS:
            any_all_keyword = ANY_ALL_TRIGGER_WORDS[word]
            # the comparison table is whichever TABLE_MAP word appears at
            # or after ANY/ALL (e.g. "... ANY EMPLOYEE in HR" -> employees);
            # falls back to the same table as the main query if none found
            for t in tokens[i:]:
                if t in TABLE_MAP:
                    any_all_sub_table = TABLE_MAP[t]
                    break

            # the column being compared INSIDE the subquery isn't
            # necessarily the same as the outer column - "salary above any
            # STUDENT MARKS" compares employees.salary against
            # students.marks, not students.salary. Look for a column word
            # after the ANY/ALL keyword; only fall back to reusing the
            # outer condition_column if the sentence never names one.
            sub_columns = build_column_map(any_all_sub_table or table, schema=schema)
            for t in tokens[i:]:
                if t in sub_columns and sub_columns[t].split(".")[-1] not in CATEGORICAL_COLUMNS:
                    any_all_sub_column = sub_columns[t]
                    break

    # ---------------- CASE ----------------
    # e.g. "label employees as high earner if salary above 50000 else low earner"

    case_label_true = None
    case_label_false = None
    case_column = None
    case_operator = None
    case_value = None

    if any(w in tokens for w in CASE_TRIGGER_WORDS) and "if" in tokens and "else" in tokens:
        if_idx = tokens.index("if")
        else_idx = tokens.index("else")

        if "as" in tokens:
            as_idx = tokens.index("as")
            if as_idx < if_idx:
                case_label_true = " ".join(tokens[as_idx + 1:if_idx]).strip()

        condition_tokens = tokens[if_idx + 1:else_idx]
        for word in condition_tokens:
            if word in column_map and column_map[word].split(".")[-1] not in CATEGORICAL_COLUMNS:
                case_column = column_map[word]
            if word in CONDITION_MAP and CONDITION_MAP[word] in VALUE_CONDITION_TYPES:
                case_operator = CONDITION_MAP[word]
            if word.isdigit():
                case_value = word

        case_label_false = " ".join(tokens[else_idx + 1:]).strip()

    is_case_query = bool(
        case_column and case_operator and case_value and case_label_true and case_label_false
    )
    if is_case_query:
        # This condition belongs to the CASE expression, not a WHERE
        # filter - the whole point of a label is to bucket every row into
        # one branch or the other, not exclude rows from the result.
        value_condition = None
        value = None

    # ---------------- NULL FUNCTIONS (IFNULL / COALESCE) ----------------
    # e.g. "show salary or 0 if salary is null", "replace missing department with unknown"

    ifnull_column = None
    ifnull_default = None

    if "replace" in tokens and "missing" in tokens and "with" in tokens:
        missing_idx = tokens.index("missing")
        with_idx = tokens.index("with")

        if missing_idx + 1 < len(tokens):
            candidate_col = tokens[missing_idx + 1]
            if candidate_col in column_map:
                ifnull_column = column_map[candidate_col]

        if with_idx + 1 < len(tokens):
            ifnull_default = tokens[with_idx + 1]

    elif "null" in tokens and "or" in tokens:
        or_idx = tokens.index("or")

        if or_idx > 0 and tokens[or_idx - 1] in column_map:
            ifnull_column = column_map[tokens[or_idx - 1]]

        if or_idx + 1 < len(tokens):
            ifnull_default = tokens[or_idx + 1]

    # ---------------- LIKE ----------------

    like_trigger_idx = None

    for i, word in enumerate(tokens):
        if word in LIKE_KEYWORDS:
            like_trigger_idx = i
            like_mode = "contains"
            break
        if word in STARTS_KEYWORDS:
            like_trigger_idx = i
            like_mode = "starts"
            break
        if word in ENDS_KEYWORDS:
            like_trigger_idx = i
            like_mode = "ends"
            break

    if like_trigger_idx is not None:

        like_negated = is_negated(tokens, like_trigger_idx, window=3)

        # nearest text-like column mentioned before the trigger word
        text_candidates = [
            (i, word) for i, word in enumerate(tokens[:like_trigger_idx])
            if word in column_map
        ]

        if text_candidates:
            like_column = column_map[text_candidates[-1][1]]
        else:
            like_column = column_map.get("name", "name")

        for word in tokens[like_trigger_idx + 1:]:
            if word.isalpha() and word not in LIKE_FILLER_WORDS:
                like_pattern = word.capitalize() if like_column == "name" else word
                break

    # ---------------- ORDER BY ----------------

    for i, word in enumerate(tokens):
        if word in ORDER_TRIGGER_WORDS:
            order_requested = True
            window_start = max(0, i - 3)
            window = tokens[window_start:i] + tokens[i:i + 6]
            for w in window:
                if w in column_map:
                    order_by_column = column_map[w]
                if w in SORT_DIRECTION_MAP:
                    order_by_direction = SORT_DIRECTION_MAP[w]
            break

    # ---------------- SELECTED COLUMNS ----------------
    stop_words = {
        "where", "whose", "having", "with", "between", "above", "below",
        "over", "under", "greater", "less", "more", "order", "sort", "arrange",
        "limit", "like", "contains", "containing", "starting", "starts",
        "ending", "ends", "on", "top", "bottom", "highest", "lowest",
    }
    intent_word_idx = next((i for i, w in enumerate(tokens) if w in SELECT_INTENT_WORDS), None)
    selected_columns = []
    if intent_word_idx is not None and intent != "count" and aggregate_function is None:
        i = intent_word_idx + 1
        while i < len(tokens) and tokens[i] not in stop_words:
            word = tokens[i]
            if i not in join_related_indices and word in column_map:
                col = column_map[word]
                base = col.split(".")[-1]
                descriptors = {"city": CITIES, "department": DEPARTMENTS, "gender": GENDERS}
                if i > 0 and tokens[i - 1] in descriptors.get(base, ()):
                    i += 1
                    continue
                if col not in selected_columns:
                    selected_columns.append(col)
                if i + 2 < len(tokens) and tokens[i + 1] == "as":
                    column_aliases[col] = tokens[i + 2]
                    i += 2
            i += 1
    select_columns_sql = ", ".join(
        f"{col} AS {column_aliases[col]}" if col in column_aliases else col
        for col in selected_columns
    ) or "*"

    # ---------------- DEFAULT NUMERIC COLUMN ----------------

    if not numeric_column:

        if table == "students":
            numeric_column = column_map.get("marks", "marks")

        elif table == "employees":
            numeric_column = column_map.get("salary", "salary")

    if order_requested and not order_by_column:
        order_by_column = numeric_column

    if condition_column is None:
        condition_column = numeric_column

    # ---------------- DEFAULT EQUAL ----------------

    if value and value_condition is None:
        value_condition = "equal"

    use_in = "or" in tokens or "in" in tokens
    has_not_in = "not in" in question

    # ---------------- OR CONDITION (true OR across different conditions) ----------------
    # A plain "IT or HR" list for one categorical column is already handled
    # as an IN (...) clause above (via department_values/city_values/
    # gender_values + use_in) - this block only kicks in when " or " joins
    # two genuinely different conditions (different columns, or a numeric
    # comparison), which the IN path can't express. When it does trigger,
    # it replaces the whole WHERE clause with the OR expression - other
    # AND-style filters in the same sentence aren't combined with it.

    or_where_clause = None

    if " or " in question:
        or_parts = question.split(" or ")

        if len(or_parts) >= 2:
            parsed_or_conditions = []

            for part in or_parts:
                part_tokens = word_tokenize(part, preserve_line=True)
                part_tokens = words_to_numbers(part_tokens)
                cond = parse_or_clause(part_tokens, default_column=numeric_column, column_map=column_map)
                if cond:
                    parsed_or_conditions.append(cond)

            if len(parsed_or_conditions) >= 2:
                cols_in_or = {c.split(" ")[0] for c in parsed_or_conditions}
                all_equality = all(" = " in c for c in parsed_or_conditions)
                same_column_list = (len(cols_in_or) == 1 and all_equality)

                if not same_column_list:
                    or_where_clause = " OR ".join(parsed_or_conditions)

    # ---------------- BUILD CONDITIONS ----------------

    # department only for employees
    if table == "employees":
        dept_condition = build_categorical_condition(
            column_map.get("department", "department"), department_values, use_in, not_in=has_not_in
        )
        if dept_condition:
            conditions.append(dept_condition)

    city_condition = build_categorical_condition(
        column_map.get("city", "city"), city_values, use_in, not_in=has_not_in
    )
    if city_condition:
        conditions.append(city_condition)

    gender_condition = build_categorical_condition(
        column_map.get("gender", "gender"), gender_values, use_in, not_in=has_not_in
    )
    if gender_condition:
        conditions.append(gender_condition)

    if subject_value and table == "students":
        conditions.append(
            f"{column_map.get('subject', 'subject')} = '{subject_value}'"
        )

    if name_value:
        conditions.append(
            f"{column_map.get('name', 'name')} = '{name_value}'"
        )

    if null_column:
        null_keyword = "IS NOT NULL" if null_negated else "IS NULL"
        conditions.append(f"{null_column} {null_keyword}")

    # ---------------- LIKE CONDITION ----------------

    if like_column and like_pattern:

        if like_mode == "starts":
            pattern_sql = f"{like_pattern}%"
        elif like_mode == "ends":
            pattern_sql = f"%{like_pattern}"
        else:
            pattern_sql = f"%{like_pattern}%"

        like_keyword = "NOT LIKE" if like_negated else "LIKE"
        conditions.append(f"{like_column} {like_keyword} '{pattern_sql}'")

    # ---------------- NUMERIC CONDITIONS ----------------

    if between_values:
        between_keyword = "NOT BETWEEN" if between_negated else "BETWEEN"
        conditions.append(
            f"{condition_column} {between_keyword} {between_values[0]} AND {between_values[1]}"
        )

    elif value_condition == "above" and value and not condition_is_having:
        conditions.append(
            f"{condition_column} > {value}"
        )

    elif value_condition == "below" and value and not condition_is_having:
        conditions.append(
            f"{condition_column} < {value}"
        )

    elif value_condition == "on_or_after" and value:
        conditions.append(
            f"{condition_column} >= {value}"
        )

    elif value_condition == "on_or_before" and value:
        conditions.append(
            f"{condition_column} <= {value}"
        )

    elif value_condition == "equal" and value:
        conditions.append(
            f"{condition_column} = {value}"
        )

    elif value_condition == "gte" and value and not condition_is_having:
        conditions.append(
            f"{condition_column} >= {value}"
        )

    elif value_condition == "lte" and value and not condition_is_having:
        conditions.append(
            f"{condition_column} <= {value}"
        )

    # ---------------- WHERE ----------------

    where_clause = ""

    if or_where_clause:
        where_clause = f" WHERE ({or_where_clause})"
        if enrollment_condition:
            where_clause += f" AND {enrollment_condition}"
    elif conditions:
        where_clause = (
            " WHERE " +
            " AND ".join(conditions)
        )

    # ---------------- GROUP BY ----------------

    group_by_clause = ""

    if group_by_column:
        group_by_clause = f" GROUP BY {group_by_column}"


        # ---------------- HAVING ----------------

    having_clause = ""

    if condition_is_having:
        op_symbol_map = {"above": ">", "below": "<", "gte": ">=", "lte": "<="}
        having_agg = "COUNT(*)" if intent == "count" else f"{aggregate_function}({numeric_column})"
        having_clause = f" HAVING {having_agg} {op_symbol_map[value_condition]} {value}"


    # ---------------- ORDER BY / LIMIT (for the default / non-aggregate paths) ----------------

    order_by_clause = ""
    limit_clause = ""

    if record_condition is None:

        if order_requested and order_by_column:
            order_by_clause = f" ORDER BY {order_by_column} {order_by_direction}"

        if limit_value:
            limit_clause = f" LIMIT {limit_value}"

            # ---------------- JOIN QUERY ----------------

    if second_table:
        on_clause = " AND ".join(
            f"{table}.{left} = {second_table}.{right}" for left, right in join_pairs
        )
        select_cols = select_columns_sql
        if intent == "count":
            select_cols = "COUNT(*)"
        elif aggregate_function in ("AVG", "SUM", "MIN", "MAX"):
            if not numeric_column:
                raise ValueError("Specify a numeric column to aggregate.")
            select_cols = f"{aggregate_function}({numeric_column})"
        elif aggregate_function == "DISTINCT":
            distinct_cols = list(dict.fromkeys(column_map[w] for w in tokens if w in column_map))
            if not distinct_cols:
                raise ValueError("Specify the column to select distinct values from.")
            select_cols = "DISTINCT " + ", ".join(distinct_cols)
        if group_by_column:
            select_cols = f"{group_by_column}, {select_cols}"
        if record_condition:
            direction = "DESC" if record_condition == "highest" else "ASC"
            order_by_clause = f" ORDER BY {numeric_column} {direction}"
            limit_clause = f" LIMIT {limit_value or '1'}"

        if join_type == "FULL OUTER":
            if aggregate_function or intent == "count" or order_by_clause:
                raise ValueError("Full outer joins with aggregation or sorting are not supported yet.")
            return (
                f"SELECT {select_cols} FROM {table} LEFT JOIN {second_table} ON {on_clause}{where_clause} "
                f"UNION SELECT {select_cols} FROM {table} RIGHT JOIN {second_table} ON {on_clause}{where_clause}"
                f"{limit_clause}"
            )

        join_clause = f"{table} {join_type} {second_table}"
        if join_type != "CROSS JOIN":
            join_clause += f" ON {on_clause}"
        if aggregate_function in ("AVG", "SUM", "MIN", "MAX") and record_condition and limit_value and not group_by_column:
            return (
                f"SELECT {aggregate_function}(aggregate_value) FROM "
                f"(SELECT {numeric_column} AS aggregate_value FROM {join_clause}"
                f"{where_clause}{order_by_clause}{limit_clause}) AS top_rows"
            )
        return (
            f"SELECT {select_cols} FROM {join_clause}"
            f"{where_clause}{group_by_clause}{having_clause}{order_by_clause}{limit_clause}"
        )

    # ---------------- UNION QUERY ----------------

    # Columns (and WHERE conditions, further below) that actually exist on
    # BOTH students and employees - same set the JOIN logic already treats
    # as the only safe cross-table columns (see SHARED_COLUMN above). Kept
    # as an ordered list (not a set) so the default "show everything safe"
    # case below always renders columns in the same, predictable order.
    UNION_SHARED_COLUMNS = ["id", "name", "age", "gender", "city"]

    if union_second_table:

        # SELECT * across two differently-shaped tables would break a UNION
        # (mismatched column counts). If specific columns were genuinely
        # requested, keep only the ones valid on both sides (e.g. "marks"
        # or "salary" only exist on one table and would error out on the
        # other). If NOTHING was requested (or nothing requested survived
        # that filter), default to every column common to both tables -
        # as close to "show everything" as a UNION can safely get, rather
        # than an arbitrary single column.
        if selected_columns:
            safe_cols = [c for c in selected_columns if c in UNION_SHARED_COLUMNS]
        else:
            safe_cols = []
        union_cols = ", ".join(safe_cols) if safe_cols else ", ".join(UNION_SHARED_COLUMNS)

        union_keyword = "UNION ALL" if union_all else "UNION"

        # Only reuse WHERE conditions built on columns common to both
        # tables (city/gender/age/name/id) - department, marks, salary,
        # subject, joining_year, etc. are table-specific and would error
        # out on whichever side of the UNION doesn't have that column.
        union_safe_conditions = [
            c for c in conditions
            if c.split(" ")[0] in UNION_SHARED_COLUMNS
        ]
        union_where = ""
        if union_safe_conditions:
            union_where = " WHERE " + " AND ".join(union_safe_conditions)

        return f"""
        SELECT {union_cols} FROM {table}{union_where}
        {union_keyword}
        SELECT {union_cols} FROM {union_second_table}{union_where}
        """.strip()

    # ---------------- CASE QUERY ----------------

    if case_column and case_operator and case_value and case_label_true and case_label_false:

        op_symbol_map = {"above": ">", "below": "<", "equal": "=", "gte": ">=", "lte": "<="}
        op_symbol = op_symbol_map.get(case_operator, "=")

        case_sql = (
            f"CASE WHEN {case_column} {op_symbol} {case_value} "
            f"THEN '{case_label_true}' ELSE '{case_label_false}' END AS category"
        )

        return f"""
        SELECT *, {case_sql}
        FROM {table}
        {where_clause}
        """.strip()

    # ---------------- IFNULL / COALESCE QUERY ----------------

    if ifnull_column and ifnull_default:

        default_sql = ifnull_default if ifnull_default.isdigit() else f"'{ifnull_default}'"

        return f"""
        SELECT IFNULL({ifnull_column}, {default_sql}) AS {ifnull_column}
        FROM {table}
        """.strip()

    # ---------------- EXISTS QUERY ----------------

    if exists_second_table:

        exists_where = (
            f" WHERE EXISTS (SELECT 1 FROM {exists_second_table} "
            f"WHERE {exists_second_table}.{exists_column} = {table}.{exists_column})"
        )

        return f"""
        SELECT {select_columns_sql}
        FROM {table}
        {exists_where}
        """.strip()

    # ---------------- ANY / ALL QUERY ----------------

    if any_all_keyword and value_condition in ("above", "below", "gte", "lte") and condition_column:

        op_symbol_map = {"above": ">", "below": "<", "gte": ">=", "lte": "<="}
        sub_table = any_all_sub_table if any_all_sub_table else table
        sub_column = any_all_sub_column if any_all_sub_column else condition_column

        # scope the subquery to whichever qualifier was mentioned -
        # department, city, or a specific semester number - falling back
        # to no filter (compare against every row of sub_table) if none
        scope_column = None
        scope_value = None

        if department_values:
            scope_column = "department"
            scope_value = f"'{department_values[-1][0]}'"
        elif city_values:
            scope_column = "city"
            scope_value = f"'{city_values[-1][0]}'"
        elif "semester" in tokens:
            sem_idx = tokens.index("semester")
            for t in tokens[sem_idx:sem_idx + 3]:
                if t.isdigit():
                    scope_column = "semester"
                    scope_value = t
                    break

        sub_where = f" WHERE {scope_column} = {scope_value}" if scope_column else ""

        any_all_where = (
            f" WHERE {condition_column} {op_symbol_map[value_condition]} {any_all_keyword} "
            f"(SELECT {sub_column} FROM {sub_table}{sub_where})"
        )

        return f"""
        SELECT {select_columns_sql}
        FROM {table}
        {any_all_where}
        """.strip()

    # ---------------- DISTINCT ----------------

    if aggregate_function == "DISTINCT":

        distinct_column = None

        for word in tokens:

            if word in column_map:
                distinct_column = column_map[word]

        if distinct_column:

            return f"""
            SELECT DISTINCT {distinct_column}
            FROM {table}
            {where_clause}
            """.strip()

    # ---------------- AVG / SUM / MIN / MAX ----------------

    if aggregate_function in ("AVG", "SUM", "MIN", "MAX"):

        select_cols = f"{aggregate_function}({numeric_column})"

        if group_by_column:
            select_cols = f"{group_by_column}, {select_cols}"

        # "average salary of top 4 employees", "sum of marks of bottom 3
        # students", etc: the aggregate should run over just the top/bottom
        # N rows (ranked by numeric_column), not the whole table. A plain
        # LIMIT on the outer aggregate query wouldn't do anything - an
        # aggregate always collapses the result to a single row - so this
        # needs a subquery: rank + limit first, then aggregate over that
        # subset. Only applies when there's no GROUP BY; "top N rows
        # overall" and "grouped by department/city/etc" are two different
        # requests that don't currently combine.
        if record_condition in ("highest", "lowest") and limit_value and not group_by_column:
            sort_dir = "DESC" if record_condition == "highest" else "ASC"
            subquery = (
                f"SELECT * FROM {table}"
                f"{where_clause}"
                f" ORDER BY {numeric_column} {sort_dir}"
                f" LIMIT {limit_value}"
            )
            return f"""
            SELECT {select_cols}
            FROM ({subquery}) AS top_rows
            """.strip()

        return f"""
        SELECT {select_cols}
        FROM {table}
        {where_clause}{group_by_clause}{having_clause}
        """.strip()

    # ---------------- COUNT ----------------

    if intent == "count":

        select_cols = "COUNT(*)"

        if group_by_column:
            select_cols = f"{group_by_column}, COUNT(*)"

        return f"""
        SELECT {select_cols}
        FROM {table}
        {where_clause}{group_by_clause}{having_clause}
        """.strip()

    # ---------------- HIGHEST ----------------

    if record_condition == "highest":

        limit_n = limit_value if limit_value else "1"

        return f"""
        SELECT {select_columns_sql}
        FROM {table}
        {where_clause}
        ORDER BY {numeric_column} DESC
        LIMIT {limit_n}
        """.strip()

    # ---------------- LOWEST ----------------

    if record_condition == "lowest":

        limit_n = limit_value if limit_value else "1"

        return f"""
        SELECT {select_columns_sql}
        FROM {table}
        {where_clause}
        ORDER BY {numeric_column} ASC
        LIMIT {limit_n}
        """.strip()

    # ---------------- DEFAULT SELECT ----------------

    return f"""
    SELECT {select_columns_sql}
    FROM {table}
    {where_clause}{order_by_clause}{limit_clause}
    """.strip()
