#!/usr/bin/env python3
"""
清洗课程名称并重建课程-教师关联
"""
import json
import re
import sqlite3
from datetime import datetime

def clean_course_name(name):
    """清洗单个课程名称"""
    if not name:
        return None
    
    # Remove all Chinese book title marks
    name = name.replace('《', '').replace('》', '')
    
    # Remove English quotes
    name = name.replace('"', '').replace("'", '')
    
    # Remove leading commas, spaces, and special characters
    name = re.sub(r'^[、,，\s\-]+', '', name)
    
    # Remove trailing commas and spaces
    name = re.sub(r'[、,，\s\-]+$', '', name)
    
    # Remove extra spaces
    name = re.sub(r'\s+', ' ', name)
    
    # Remove content that looks like dates or pure numbers
    if re.match(r'^[\d\.\-:]+$', name.strip()):
        return None
    if re.match(r'^\d{2,4}$', name.strip()):
        return None
    
    # Remove empty content
    if not name or len(name.strip()) <= 2:
        return None
    
    return name.strip()

def split_courses(course_text):
    """Split multiple courses (separated by 》、《)"""
    if not course_text:
        return []
    
    # Use 》、《as separator
    courses = re.split(r'[》、]+', course_text)
    result = []
    for c in courses:
        cleaned = clean_course_name(c)
        if cleaned and len(cleaned) > 1:
            result.append(cleaned)
    return result

def main():
    print("=" * 60)
    print("Course data cleaning and teacher association tool")
    print("=" * 60)
    
    # 1. Read original data
    print("\n1. Reading original data...")
    with open('data/teachers_data.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    teachers = data['teachers']
    print(f"   Total teachers: {len(teachers)}")
    
    # 2. Extract all courses and teacher associations
    print("\n2. Extracting course-teacher associations...")
    course_teachers = {}  # course_name -> set of teacher_ids
    
    for teacher in teachers:
        teacher_name = teacher.get('top_info', {}).get('name', '')
        teacher_id = teacher.get('_merge_id', 0)
        
        # From basic_info - course information
        course_info = teacher.get('basic_info', {}).get('课程信息', '')
        if course_info:
            for course in split_courses(course_info):
                if course not in course_teachers:
                    course_teachers[course] = set()
                course_teachers[course].add((teacher_id, teacher_name))
        
        # From teaching_records
        for record in teacher.get('teaching_records', []):
            course_name = record.get('课程名称', '')
            if course_name:
                for course in split_courses(course_name):
                    if course not in course_teachers:
                        course_teachers[course] = set()
                    course_teachers[course].add((teacher_id, teacher_name))
    
    print(f"   Unique courses: {len(course_teachers)}")
    
    # 3. Connect to database, clear old data, insert new data
    print("\n3. Updating database...")
    conn = sqlite3.connect('instance/teacher_system.db')
    c = conn.cursor()
    
    # Clear old courses
    c.execute('DELETE FROM courses')
    try:
        c.execute('DELETE FROM sqlite_sequence WHERE name="courses"')
    except:
        pass
    print("   Cleared old course data")
    
    # Insert new courses and build teacher associations
    courses_added = 0
    teacher_links = []  # (course_id, teacher_id)
    
    for course_name, teachers_set in sorted(course_teachers.items()):
        c.execute('''
            INSERT INTO courses (teacher_id, name, description, created_at)
            VALUES (?, ?, ?, ?)
        ''', (1, course_name, None, datetime.now()))
        
        course_id = c.lastrowid
        courses_added += 1
        
        # Record teacher associations
        for teacher_id, teacher_name in teachers_set:
            if teacher_id > 0:
                teacher_links.append((course_id, teacher_id, teacher_name))
    
    # Create course-teacher association table (if it doesn't exist)
    c.execute('''
        CREATE TABLE IF NOT EXISTS course_teachers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            teacher_id INTEGER NOT NULL,
            teacher_name TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(course_id, teacher_id)
        )
    ''')
    c.execute('DELETE FROM course_teachers')
    
    # Insert associations
    links_added = 0
    for course_id, teacher_id, teacher_name in teacher_links:
        try:
            c.execute('''
                INSERT OR IGNORE INTO course_teachers (course_id, teacher_id, teacher_name)
                VALUES (?, ?, ?)
            ''', (course_id, teacher_id, teacher_name))
            if c.rowcount > 0:
                links_added += 1
        except:
            pass
    
    conn.commit()
    
    # Statistics
    c.execute('SELECT COUNT(*) FROM courses')
    total_courses = c.fetchone()[0]
    c.execute('SELECT COUNT(*) FROM course_teachers')
    total_links = c.fetchone()[0]
    c.execute('SELECT COUNT(DISTINCT teacher_id) FROM course_teachers')
    teachers_with_courses = c.fetchone()[0]
    
    conn.close()
    
    print(f"\n4. Processing complete!")
    print(f"   New courses: {courses_added}")
    print(f"   Teacher associations: {links_added}")
    print(f"   Teachers involved: {teachers_with_courses}")
    print(f"   Total courses in DB: {total_courses}")
    print(f"   Total associations in DB: {total_links}")
    
    # Show examples
    print("\n5. Sample courses:")
    sample_courses = sorted(course_teachers.keys())[:10]
    for course in sample_courses:
        teachers_list = [t[1] for t in list(course_teachers[course])[:3]]
        print(f"   - {course} (Teachers: {', '.join(teachers_list)})")
    
    print("\n" + "=" * 60)

if __name__ == '__main__':
    main()
