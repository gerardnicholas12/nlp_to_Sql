"""Build the requested query TXT and matching SVG/PNG relationship diagram."""

from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
TABLES = ('faculty', 'classes', 'courses', 'students', 'exams', 'results')


def write_queries():
    header = '''-- COLLEGE DATABASE: CREATE, INSERT AND DISPLAY
-- MySQL 8.0.16 or later. Run this file in MySQL Workbench or the mysql client.
-- This script creates a NEW demonstration database named college_demo.
-- It does not drop or change the existing college application database.
-- Run the complete script once. To use another new database, change the
-- database name in the CREATE DATABASE and USE statements below.
-- To display the existing app database only, execute USE college; and then
-- run sections 4 onward, without running the creation or insert sections.

-- 1. CREATE AND SELECT THE DATABASE
CREATE DATABASE college_demo CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE college_demo;

-- 2. CREATE THE SIX TABLES AND THEIR RELATIONSHIP CONSTRAINTS
'''
    parts = [header, (HERE / 'schema.sql').read_text(),
             '\n-- 3. INSERT 15 RECORDS INTO EACH TABLE (90 RECORDS IN TOTAL)\n',
             (HERE / 'seed.sql').read_text(),
             '\n-- 4. DISPLAY ALL TABLE NAMES\nSHOW TABLES;\n',
             '\n-- 5. DISPLAY THE STRUCTURE OF EACH TABLE\n']
    parts += [f'DESCRIBE {table};\n' for table in TABLES]
    parts += ['\n-- 6. DISPLAY ALL 15 RECORDS FROM EACH TABLE\n']
    pk = {'faculty':'faculty_id','classes':'class_id','courses':'course_id','students':'student_id','exams':'exam_id','results':'result_id'}
    parts += [f'\n-- {table.upper()}\nSELECT * FROM {table} ORDER BY {pk[table]};\n' for table in TABLES]
    parts += ['\n-- 7. VERIFY THAT EACH TABLE HAS 15 RECORDS\n']
    parts += ['\nUNION ALL\n'.join(f"SELECT '{table}' AS table_name, COUNT(*) AS record_count FROM {table}" for table in TABLES) + ';\n']
    parts += ['''
-- 8. DISPLAY RELATED DATA USING SIMPLE JOINS

-- Students and the classes they belong to.
SELECT s.srn, s.student_name, cl.class_name, cl.semester
FROM students s
JOIN classes cl ON cl.class_id = s.class_id
ORDER BY s.student_id;

-- Courses and the faculty teaching them.
SELECT c.course_name, c.credits, f.faculty_name
FROM courses c
JOIN faculty f ON f.faculty_id = c.faculty_id
ORDER BY c.course_id;

-- Exams, their courses, and the classes taking them.
SELECT e.exam_id, e.exam_name, c.course_name,
       cl.class_name, cl.semester, e.exam_date
FROM exams e
JOIN courses c ON c.course_id = e.course_id
JOIN classes cl ON cl.class_id = e.class_id
ORDER BY e.exam_id;

-- Each student's marks for each recorded exam.
SELECT s.srn, s.student_name, e.exam_name,
       c.course_name, r.marks
FROM results r
JOIN students s ON s.student_id = r.student_id
JOIN exams e ON e.exam_id = r.exam_id
JOIN courses c ON c.course_id = e.course_id
ORDER BY s.student_id, e.exam_id;

-- 9. DISPLAY ALL SIX FOREIGN-KEY RELATIONSHIPS
SELECT TABLE_NAME AS child_table, COLUMN_NAME AS foreign_key,
       REFERENCED_TABLE_NAME AS parent_table,
       REFERENCED_COLUMN_NAME AS parent_key
FROM information_schema.KEY_COLUMN_USAGE
WHERE TABLE_SCHEMA = DATABASE()
  AND REFERENCED_TABLE_NAME IS NOT NULL
ORDER BY TABLE_NAME, COLUMN_NAME;
''']
    (HERE / 'college_queries.txt').write_text(''.join(parts), encoding='utf-8')


def write_diagram():
    from PIL import Image, ImageDraw, ImageFont

    width, height, scale = 1600, 1040, 2
    background = '#f6f8fc'
    ink, muted, border, blue = '#17263c', '#52627b', '#d5deeb', '#2859a0'
    image = Image.new('RGB', (width * scale, height * scale), background)
    draw = ImageDraw.Draw(image)
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
           '<title>College database: six tables and six one-to-many relationships</title>',
           '<desc>Faculty teaches courses. Classes contain students and schedule exams. Courses have exams. Results link each student to an exam.</desc>',
           f'<rect width="100%" height="100%" fill="{background}"/>']
    fonts = {}

    def font(size, bold=False):
        key = size, bold
        if key not in fonts:
            path = Path('C:/Windows/Fonts') / ('segoeuib.ttf' if bold else 'segoeui.ttf')
            fonts[key] = ImageFont.truetype(str(path), size * scale)
        return fonts[key]

    def text(x, y, value, size=20, fill=ink, bold=False, anchor='start'):
        # y is the baseline in both SVG and Pillow.
        svg.append(f'<text x="{x}" y="{y}" font-family="Segoe UI, Arial, sans-serif" font-size="{size}" font-weight="{600 if bold else 400}" fill="{fill}" text-anchor="{anchor}">{escape(value)}</text>')
        draw.text((x * scale, y * scale), value, font=font(size, bold), fill=fill,
                  anchor={'start': 'ls', 'middle': 'ms', 'end': 'rs'}[anchor])

    def rect(x, y, w, h, fill, stroke=None, radius=0):
        svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke or "none"}" stroke-width="1.5"/>')
        draw.rounded_rectangle((x*scale,y*scale,(x+w)*scale,(y+h)*scale), radius=radius*scale,
                               fill=fill, outline=stroke, width=3 if stroke else 1)

    def line(points, color=muted, thickness=2):
        coords = ' '.join(f'{x},{y}' for x, y in points)
        svg.append(f'<polyline points="{coords}" fill="none" stroke="{color}" stroke-width="{thickness}" stroke-linejoin="round"/>')
        draw.line([(x*scale,y*scale) for x,y in points],fill=color,width=thickness*scale,joint='curve')

    def label(x, y, value):
        size = 18
        w = draw.textlength(value,font=font(size)) / scale + 22
        rect(x-w/2, y-23, w, 32, background, radius=5)
        text(x, y, value, size, muted, anchor='middle')

    def one(x, y, horizontal=True):
        if horizontal:
            line([(x,y-8),(x,y+8)])
            line([(x+7,y-8),(x+7,y+8)])
        else:
            line([(x-8,y),(x+8,y)])
            line([(x-8,y+7),(x+8,y+7)])

    def many(x, y, vertical=False):
        # Crow's foot at the child and a zero circle just before it.
        if vertical:
            line([(x-9,y),(x,y-16),(x+9,y)])
            cx, cy = x, y-25
        else:
            line([(x,y-9),(x-16,y),(x,y+9)])
            cx, cy = x-25, y
        svg.append(f'<circle cx="{cx}" cy="{cy}" r="4" fill="{background}" stroke="{muted}" stroke-width="2"/>')
        draw.ellipse(((cx-4)*scale,(cy-4)*scale,(cx+4)*scale,(cy+4)*scale),fill=background,outline=muted,width=2*scale)

    text(60, 64, 'College database', 40, bold=True)
    text(60, 102, '6 tables  /  6 relationships  /  15 records per table', 21, muted)

    # Edges are drawn first, then table cards cover their endpoints cleanly.
    line([(420,240),(620,240)]); one(433,240); many(620,240); label(520,220,'teaches')
    line([(980,240),(1180,240)]); one(993,240); many(1180,240); label(1080,220,'assessed by')
    line([(420,740),(620,740)]); one(433,740); many(620,740); label(520,720,'contains')
    line([(980,740),(1180,740)]); one(993,740); many(1180,740); label(1080,720,'receives')
    line([(1360,392),(1360,650)]); one(1360,405,False); many(1360,650,True); label(1431,532,'produces')
    line([(240,650),(240,475),(1110,475),(1110,340),(1180,340)])
    one(240,630,False); many(1180,340); label(715,467,'schedules')

    table_data = [
        ('faculty',60,150,[('faculty_id','INT','PK'),('faculty_name','VARCHAR',''),('designation','VARCHAR',''),('qualification','VARCHAR',''),('experience','INT','')]),
        ('courses',620,150,[('course_id','INT','PK'),('course_name','VARCHAR','UK'),('credits','INT',''),('faculty_id','INT','FK')]),
        ('exams',1180,150,[('exam_id','INT','PK'),('exam_name','VARCHAR',''),('class_id','INT','FK'),('course_id','INT','FK'),('exam_date','DATE','')]),
        ('classes',60,650,[('class_id','INT','PK'),('class_name','VARCHAR','UK'),('semester','INT','')]),
        ('students',620,610,[('student_id','INT','PK'),('srn','VARCHAR','UK'),('student_name','VARCHAR',''),('address','VARCHAR',''),('phone','VARCHAR',''),('email','VARCHAR','UK'),('class_id','INT','FK')]),
        ('results',1180,650,[('result_id','INT','PK'),('student_id','INT','FK'),('exam_id','INT','FK'),('marks','DECIMAL','')]),
    ]
    for table,x,y,fields in table_data:
        h = 87 + 31*len(fields)
        rect(x,y,360,h,'#ffffff',border,10)
        rect(x+1,y+1,358,52,'#eaf0fa',radius=9)
        rect(x+1,y+35,358,18,'#eaf0fa')
        text(x+20,y+35,table,24,blue,True)
        text(x+340,y+34,'15 rows',16,muted,anchor='end')
        line([(x,y+54),(x+360,y+54)],border,1)
        for i,(name,dtype,key) in enumerate(fields):
            yy=y+83+31*i
            if key:
                rect(x+17,yy-20,35,24,'#eaf0fa' if key!='FK' else '#e5f3ed',radius=4)
                text(x+34.5,yy-3,key,13,blue if key!='FK' else '#23674c',True,'middle')
            text(x+66,yy,name,20)
            text(x+340,yy,dtype,15,muted,anchor='end')
    line([(60,962),(1540,962)],border,1)
    text(60,1000,'PK  Primary key     FK  Foreign key     UK  Unique key',19,muted)
    text(840,1000,'Each relationship: one parent to zero or many children',19,muted)
    svg.append('</svg>')
    (HERE / 'college_relationships.svg').write_text('\n'.join(svg),encoding='utf-8')
    image.save(HERE / 'college_relationships.png')


if __name__ == '__main__':
    write_queries()
    write_diagram()
    print('Created college_queries.txt, college_relationships.svg and college_relationships.png')
