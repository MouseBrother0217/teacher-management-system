#!/usr/bin/env python3
"""
从师资数据中提取课程和班级信息
"""

import json
from datetime import datetime

def extract_courses_and_classes():
    """提取课程和班级数据"""
    print("📖 读取师资数据...")
    
    with open('/root/.openclaw/workspace/.kimi/downloads/19d9abe3-2892-8cbc-8000-0000b58ccf8b_teachers_final_complete.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    teachers_data = data.get('teachers', [])
    
    # 收集课程和班级
    courses_dict = {}  # 课程名称 -> 信息
    classes_dict = {}  # 班级名称 -> 信息
    
    for t in teachers_data:
        # 从课程信息字段提取
        course_info = t.get('basic_info', {}).get('课程信息', '')
        if course_info:
            # 去除书名号和多余空格
            course_name = course_info.replace('《', '').replace('》', '').strip()
            if course_name and course_name not in courses_dict:
                field = t.get('top_info', {}).get('field', '')
                courses_dict[course_name] = {
                    'name': course_name,
                    'category': field if field else '其他',
                    'description': ''
                }
        
        # 从上课记录提取
        for record in t.get('teaching_records', []):
            # 提取课程
            course_name = record.get('课程名称', '').strip()
            if course_name and course_name not in courses_dict:
                field = t.get('top_info', {}).get('field', '')
                courses_dict[course_name] = {
                    'name': course_name,
                    'category': field if field else '其他',
                    'description': ''
                }
            
            # 提取班级
            class_name = record.get('所属班级', '').strip()
            if class_name and class_name not in classes_dict:
                # 尝试从班级名提取分类
                category = '其他'
                if '税务' in class_name or '督察' in class_name:
                    category = '财税系统'
                elif '领导力' in class_name or '管理' in class_name:
                    category = '管理类'
                elif '技术' in class_name or 'IT' in class_name:
                    category = '技术类'
                elif '金融' in class_name or '经济' in class_name:
                    category = '金融类'
                
                classes_dict[class_name] = {
                    'name': class_name,
                    'category': category,
                    'status': '已结课',  # 根据上课时间判断
                    'teacher_name': t.get('top_info', {}).get('name', '')
                }
    
    # 转换为列表
    courses = []
    for idx, (name, info) in enumerate(sorted(courses_dict.items()), 1):
        courses.append({
            'id': idx,
            'name': info['name'],
            'category': info['category'],
            'description': info['description']
        })
    
    classes = []
    for idx, (name, info) in enumerate(sorted(classes_dict.items()), 1):
        classes.append({
            'id': idx,
            'name': info['name'],
            'category_name': info['category'],
            'status': info['status'],
            'teacher_name': info['teacher_name'],
            'student_count': 0,
            'sign_in_rate': 0,
            'evaluation_rate': 0
        })
    
    print(f"✅ 提取完成!")
    print(f"  - 课程: {len(courses)} 门")
    print(f"  - 班级: {len(classes)} 个")
    
    return courses, classes


if __name__ == '__main__':
    courses, classes = extract_courses_and_classes()
    
    # 打印前10个示例
    print("\n📚 课程示例（前10）:")
    for c in courses[:10]:
        print(f"  - {c['name']} ({c['category']})")
    
    print("\n📋 班级示例（前10）:")
    for c in classes[:10]:
        print(f"  - {c['name']} ({c['category_name']})")
    
    # 生成Python数据文件
    output = []
    output.append('#!/usr/bin/env python3')
    output.append(f'# 课程和班级数据 - {datetime.now().isoformat()}')
    output.append(f'# 共 {len(courses)} 门课程, {len(classes)} 个班级')
    output.append('')
    output.append('# 课程列表')
    output.append('courses = ')
    output.append(json.dumps(courses, ensure_ascii=False, indent=2))
    output.append('')
    output.append('')
    output.append('# 班级列表')
    output.append('classes = ')
    output.append(json.dumps(classes, ensure_ascii=False, indent=2))
    
    content = '\n'.join(output)
    with open('/root/.openclaw/workspace/projects/teacher-management-system/data/imported_courses_classes.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"\n✅ 数据文件已保存: data/imported_courses_classes.py")