# College database

The live `college` database uses eight tables: `student_info`, `course`,
`subject`, `marks`, `employee_info`, `department`, `project`, and `performance`.
Its course and department relationships are documented in
[current_schema.md](current_schema.md).

`college_simple/` and `college_v2/` contain earlier designs and fixtures; their
reset scripts do not describe the current database and should not be run over it.
Local backups are in `backups/` and are excluded from version control.
