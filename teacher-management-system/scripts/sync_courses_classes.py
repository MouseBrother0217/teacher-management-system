#!/usr/bin/env python3
"""
从 teachers_data.json 清洗并同步班级和课程数据到数据库
"""
import json
import sqlite3
import re
from datetime import datetime

def clean_course_name(name):
    """清洗课程名称"""
    if not name:
        return None
    # Remove book marks 《》
    name = name.strip('《》')
    # Remove leading/trailing whitespace
    name = name.strip()
    # Remove extra spaces
    name = re.sub(r'\s+', ' ', name)
    return name if name else None

def split_courses(course_text):
    """拆分多个课程名称（用》、《分隔）"""
    if not course_text:
        return []
    # Split by 》、《
    courses = re.split(r'[》、]+', course_text)
    result = []
    for c in courses:
        cleaned = clean_course_name(c)
        if cleaned and len(cleaned) > 1:
            result.append(cleaned)
    return result

def extract_data():
    """从 JSON 文件中提取班级和课程"""
    with open('data/teachers_data.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    teachers = data['teachers']
    
    courses_set = set()
    classes_set = set()
    class_details = {}  # class_name -> {班主任, 项目主任, etc.}
    
    for t in teachers:
        # From basic_info - 课程信息
        course_info = t.get('basic_info', {}).get('课程信息', '')
        if course_info:
            for course in split_courses(course_info):
                courses_set.add(course)
        
        # From teaching_records
        for record in t.get('teaching_records', []):
            class_name = record.get('所属班级', '').strip()
            course_name = record.get('课程名称', '').strip()
            
            if class_name:
                classes_set.add(class_name)
                # Store class details
                if class_name not in class_details:
                    class_details[class_name] = {
                        '班主任': record.get('班主任', ''),
                        '项目主任': record.get('项目主任', ''),
                    }
            
            if course_name:
                cleaned = clean_course_name(course_name)
                if cleaned:
                    courses_set.add(cleaned)
    
    return sorted(list(courses_set)), sorted(list(classes_set)), class_details

def sync_to_database(courses, classes, class_details):
    """同步到 SQLite 数据库"""
    conn = sqlite3.connect('instance/teacher_system.db')
    c = conn.cursor()
    
    # Get existing courses to avoid duplicates
    c.execute('SELECT name FROM courses')
    existing_courses = {row[0] for row in c.fetchall()}
    
    # Insert new courses - use teacher_id=1 as placeholder for catalog courses
    # These will be re-linked when teaching records are imported
    courses_added = 0
    for course_name in courses:
        if course_name not in existing_courses:
            c.execute('''
                INSERT INTO courses (teacher_id, name, description, created_at)
                VALUES (?, ?, ?, ?)
            ''', (1, course_name, None, datetime.now()))
            courses_added += 1
    
    # Get existing classes to avoid duplicates
    c.execute('SELECT name FROM class_info')
    existing_classes = {row[0] for row in c.fetchall()}
    
    # Insert new classes
    classes_added = 0
    for class_name in classes:
        if class_name not in existing_classes:
            details = class_details.get(class_name, {})
            c.execute('''
                INSERT INTO class_info 
                (name, class_type, class_teacher, project_manager, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                class_name,
                '培训班',  # default type
                details.get('班主任', ''),
                details.get('项目主任', ''),
                '进行中',
                datetime.now()
            ))
            classes_added += 1
    
    conn.commit()
    conn.close()
    
    return courses_added, classes_added

def main():
    print("=" * 50)
    print("数据清洗与同步工具")
    print("=" * 50)
    
    print("\n1. 从 teachers_data.json 提取数据...")
    courses, classes, class_details = extract_data()
    print(f"   发现唯一课程: {len(courses)} 个")
    print(f"   发现唯一班级: {len(classes)} 个")
    
    print("\n2. 同步到数据库...")
    courses_added, classes_added = sync_to_database(courses, classes, class_details)
    print(f"   新增课程: {courses_added} 个")
    print(f"   新增班级: {classes_added} 个")
    
    # Verify
    conn = sqlite3.connect('instance/teacher_system.db')
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM courses')
    total_courses = c.fetchone()[0]
    c.execute('SELECT COUNT(*) FROM class_info')
    total_classes = c.fetchone()[0]
    conn.close()
    
    print("\n3. 同步完成!")
    print(f"   课程表总计: {total_courses} 条")
    print(f"   班级表总计: {total_classes} 条")
    print("\n" + "=" * 50)

if __name__ == '__main__':
    main()
