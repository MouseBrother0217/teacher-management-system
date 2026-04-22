#!/usr/bin/env python3
"""
从 teachers_data.json 提取完整的上课记录，更新 teaching_records 表
补充：课程关联、班级关联、上课时间、场所、课酬等
"""
import json
import sqlite3
from datetime import datetime
import re

def parse_datetime(dt_str):
    """解析日期时间字符串"""
    if not dt_str:
        return None, None
    
    # 格式如: 2025-05-20 08:30-11:30
    match = re.match(r'(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})-(\d{2}:\d{2})', dt_str)
    if match:
        date_str = match.group(1)
        start_time = match.group(2)
        end_time = match.group(3)
        return date_str, start_time + ':00', end_time + ':00'
    
    # 只有日期
    match = re.match(r'(\d{4}-\d{2}-\d{2})', dt_str)
    if match:
        return match.group(1), None, None
    
    return None, None, None

def main():
    print("=" * 60)
    print("上课记录数据补充工具")
    print("=" * 60)
    
    # 1. 读取原始数据
    print("\n1. 读取原始数据...")
    with open('data/teachers_data.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    teachers = data['teachers']
    print(f"   总教师数: {len(teachers)}")
    
    # 2. 连接数据库
    conn = sqlite3.connect('instance/teacher_system.db')
    c = conn.cursor()
    
    # 3. 获取现有课程和班级的ID映射
    c.execute('SELECT id, name FROM courses')
    course_map = {row[1]: row[0] for row in c.fetchall()}
    
    c.execute('SELECT id, name FROM class_info')
    class_map = {row[1]: row[0] for row in c.fetchall()}
    
    c.execute('SELECT id, name FROM teachers')
    teacher_map = {row[1]: row[0] for row in c.fetchall()}
    
    print(f"   课程数: {len(course_map)}")
    print(f"   班级数: {len(class_map)}")
    print(f"   教师数: {len(teacher_map)}")
    
    # 4. 从原始数据提取上课记录
    print("\n2. 提取上课记录...")
    records_to_update = []
    
    for teacher in teachers:
        teacher_name = teacher.get('top_info', {}).get('name', '')
        teacher_id = teacher_map.get(teacher_name)
        
        if not teacher_id:
            continue
        
        for record in teacher.get('teaching_records', []):
            class_name = record.get('所属班级', '')
            course_name = record.get('课程名称', '')
            date_time_str = record.get('上课时间', '')
            student_count = int(record.get('上课人数', 0) or 0)
            score = float(record.get('评分', 0) or 0) if record.get('评分') else None
            duration = record.get('课时', '半天')
            
            # 解析日期时间
            teaching_date, start_time, end_time = parse_datetime(date_time_str)
            
            # 查找关联ID
            course_id = course_map.get(course_name)
            class_id = class_map.get(class_name)
            
            records_to_update.append({
                'teacher_id': teacher_id,
                'course_id': course_id,
                'class_id': class_id,
                'class_name': class_name,
                'course_name': course_name,
                'teaching_date': teaching_date,
                'start_time': start_time,
                'end_time': end_time,
                'student_count': student_count,
                'score': score,
                'duration_type': duration
            })
    
    print(f"   提取记录数: {len(records_to_update)}")
    
    # 5. 更新现有记录（保留score等已有数据）
    print("\n3. 更新数据库...")
    
    updated = 0
    skipped = 0
    
    for rec in records_to_update:
        # 查找对应的teaching_records记录
        c.execute('''
            SELECT id FROM teaching_records 
            WHERE teacher_id = ? AND teaching_date = ? AND student_count = ?
            LIMIT 1
        ''', (rec['teacher_id'], rec['teaching_date'], rec['student_count']))
        
        existing = c.fetchone()
        
        if existing:
            # Update existing record
            c.execute('''
                UPDATE teaching_records SET
                    course_id = ?,
                    class_id = ?,
                    start_time = ?,
                    end_time = ?,
                    duration_type = ?
                WHERE id = ?
            ''', (
                rec['course_id'],
                rec['class_id'],
                rec['start_time'],
                rec['end_time'],
                rec['duration_type'],
                existing[0]
            ))
            updated += 1
        else:
            # Insert new record
            c.execute('''
                INSERT INTO teaching_records 
                (teacher_id, course_id, class_id, teaching_date, start_time, end_time, 
                 duration_type, venue, student_count, evaluation_rate, checkin_rate, 
                 score, lecture_fee, is_paid, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                rec['teacher_id'],
                rec['course_id'],
                rec['class_id'],
                rec['teaching_date'],
                rec['start_time'],
                rec['end_time'],
                rec['duration_type'],
                None,
                rec['student_count'],
                0,
                0,
                rec['score'],
                None,
                0,
                datetime.now()
            ))
            skipped += 1
    
    conn.commit()
    
    # 6. 验证
    c.execute('SELECT COUNT(*) FROM teaching_records')
    total = c.fetchone()[0]
    
    c.execute('SELECT COUNT(*) FROM teaching_records WHERE course_id IS NOT NULL')
    with_course = c.fetchone()[0]
    
    c.execute('SELECT COUNT(*) FROM teaching_records WHERE class_id IS NOT NULL')
    with_class = c.fetchone()[0]
    
    c.execute('SELECT COUNT(*) FROM teaching_records WHERE start_time IS NOT NULL')
    with_time = c.fetchone()[0]
    
    conn.close()
    
    print(f"\n4. 处理完成!")
    print(f"   总记录数: {total}")
    print(f"   更新记录: {updated}")
    print(f"   新增记录: {skipped}")
    print(f"   有课程关联: {with_course}")
    print(f"   有班级关联: {with_class}")
    print(f"   有时间信息: {with_time}")
    print("\n" + "=" * 60)

if __name__ == '__main__':
    main()
