#!/usr/bin/env python3
"""
师资数据导入脚本
将 teachers_final_complete.json 导入到师资管理系统
"""

import json
from datetime import datetime
import re

def parse_compensation(comp_str):
    """解析课酬字符串，如'半天:2300' -> 2300"""
    if not comp_str:
        return None
    match = re.search(r'(\d+)', str(comp_str))
    return int(match.group(1)) if match else None

def parse_datetime(dt_str):
    """解析日期时间字符串"""
    if not dt_str:
        return None
    try:
        return datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
    except:
        try:
            return datetime.strptime(dt_str, '%Y-%m-%d %H:%M')
        except:
            return None

def parse_date(dt_str):
    """解析日期字符串"""
    if not dt_str:
        return None
    try:
        return datetime.strptime(dt_str.split()[0], '%Y-%m-%d')
    except:
        return None

def import_teachers():
    """导入师资数据"""
    print("📖 读取师资数据文件...")
    
    with open('/root/.openclaw/workspace/.kimi/downloads/19d9abe3-2892-8cbc-8000-0000b58ccf8b_teachers_final_complete.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    teachers_data = data.get('teachers', [])
    total = len(teachers_data)
    print(f"✅ 读取成功，共 {total} 位教师")
    
    # 转换数据格式
    teachers = []
    schedules = []
    evaluations = []
    
    for idx, t in enumerate(teachers_data, 1):
        if idx % 100 == 0:
            print(f"⏳ 处理中... {idx}/{total}")
        
        top_info = t.get('top_info', {})
        basic_info = t.get('basic_info', {})
        teaching_records = t.get('teaching_records', [])
        likes_data = t.get('likes_data', [])
        detailed_evaluations = t.get('detailed_evaluations', [])
        metadata = t.get('metadata', {})
        
        # 提取课酬信息
        compensation_str = basic_info.get('税前课酬', '')
        compensation = parse_compensation(compensation_str)
        
        # 构建教师对象
        teacher = {
            'id': idx,
            'name': top_info.get('name', ''),
            'phone': basic_info.get('手机号', ''),
            'email': None,
            'avatar_url': top_info.get('avatar'),
            'gender': None,
            'title': basic_info.get('所属领域', ''),
            'organization': basic_info.get('服务客户', ''),
            'education': None,
            'major': None,
            'specialty': top_info.get('field', ''),
            'introduction': top_info.get('desc', ''),
            'compensation_before_tax': compensation,
            'compensation_after_tax': None,
            'level': basic_info.get('讲师级别', '普通'),
            'bank_name': basic_info.get('开户银行', ''),
            'bank_card': basic_info.get('银行卡号', ''),
            'id_card': basic_info.get('身份证号', ''),
            'service_customers': basic_info.get('服务客户', ''),
            'status': '已入库' if basic_info.get('是否入库') == '是' else '待审核',
            'evaluation_score': float(basic_info.get('综合评分', 0)) if basic_info.get('综合评分') else 0,
            'teaching_count': int(basic_info.get('上课次数', 0)) if basic_info.get('上课次数') else 0,
            'creator': '数据导入',
            'created_at': parse_datetime(metadata.get('extraction_time')) or datetime.now()
        }
        teachers.append(teacher)
        
        # 处理上课记录（转为schedules）
        for rec in teaching_records:
            schedule = {
                'id': len(schedules) + 1,
                'teacher_id': idx,
                'teacher_name': teacher['name'],
                'subject': rec.get('课程名称', ''),
                'class_name': rec.get('所属班级', ''),
                'teaching_date': parse_date(rec.get('上课时间')),
                'start_time': rec.get('上课时间', '').split()[1].split('-')[0] if rec.get('上课时间') and ' ' in rec.get('上课时间') else None,
                'end_time': rec.get('上课时间', '').split()[1].split('-')[1] if rec.get('上课时间') and ' ' in rec.get('上课时间') and '-' in rec.get('上课时间', '').split()[1] else None,
                'duration': rec.get('课时', ''),
                'location': None,
                'classroom_id': None,
                'compensation': compensation,
                'status': '已完成',
                'student_count': int(rec.get('上课人数', 0)) if rec.get('上课人数') else None,
                'director': rec.get('项目主任', ''),
                'teacher_manager': rec.get('班主任', ''),
                'score': float(rec.get('评分', 0)) if rec.get('评分') else None,
                'evaluation_rate': 0,
                'created_at': parse_date(rec.get('上课时间')) or datetime.now()
            }
            schedules.append(schedule)
        
        # 处理评价数据
        like_stats = {}
        for like in likes_data:
            like_stats[like.get('点赞内容', '')] = int(like.get('点赞次数', 0))
        
        for eval_rec in detailed_evaluations:
            evaluation = {
                'id': len(evaluations) + 1,
                'teacher_id': idx,
                'teacher_name': teacher['name'],
                'created_at': parse_datetime(eval_rec.get('评价时间')),
                'evaluator_name': eval_rec.get('评价人', ''),
                'class_name': eval_rec.get('所属班级', ''),
                'score': float(teacher['evaluation_score']) if teacher['evaluation_score'] else None,
                'content': eval_rec.get('评论', ''),
                'like_case_rich': like_stats.get('案例丰富，贴近实际', 0),
                'like_atmosphere': like_stats.get('氛围活跃，时常互动', 0),
                'like_humor': like_stats.get('幽默风趣，寓教于乐', 0),
                'like_key_points': like_stats.get('重点突出，层次分明', 0)
            }
            evaluations.append(evaluation)
    
    print(f"\n✅ 数据转换完成！")
    print(f"  - 教师: {len(teachers)} 人")
    print(f"  - 上课记录: {len(schedules)} 条")
    print(f"  - 评价记录: {len(evaluations)} 条")
    
    return teachers, schedules, evaluations


def generate_sql(teachers, schedules, evaluations):
    """生成SQL插入语句"""
    print("\n📝 生成SQL文件...")
    
    lines = []
    lines.append('-- 师资数据导入脚本')
    lines.append(f'-- 生成时间: {datetime.now().isoformat()}')
    lines.append(f'-- 教师数量: {len(teachers)}')
    lines.append(f'-- 上课记录: {len(schedules)}')
    lines.append(f'-- 评价记录: {len(evaluations)}')
    lines.append('')
    
    # 清空现有数据
    lines.append('DELETE FROM evaluations;')
    lines.append('DELETE FROM schedules;')
    lines.append('DELETE FROM teachers;')
    lines.append('')
    
    # 插入教师数据
    lines.append('-- 插入教师数据')
    for t in teachers:
        sql = f"""INSERT INTO teachers (id, name, phone, email, avatar_url, gender, title, organization, 
            education, major, specialty, introduction, compensation_before_tax, compensation_after_tax,
            level, bank_name, bank_card, id_card, service_customers, status, evaluation_score, 
            teaching_count, creator, created_at) 
            VALUES ({t['id']}, '{t['name'].replace("'", "''")}', '{t['phone'] or ''}', 
            {f"'{t['email']}'" if t['email'] else 'NULL'}, 
            {f"'{t['avatar_url']}'" if t['avatar_url'] else 'NULL'},
            {f"'{t['gender']}'" if t['gender'] else 'NULL'},
            {f"'{t['title'].replace(chr(39), chr(39)+chr(39))}'" if t['title'] else 'NULL'},
            {f"'{t['organization'].replace(chr(39), chr(39)+chr(39))}'" if t['organization'] else 'NULL'},
            {f"'{t['education']}'" if t['education'] else 'NULL'},
            {f"'{t['major']}'" if t['major'] else 'NULL'},
            {f"'{t['specialty'].replace(chr(39), chr(39)+chr(39))}'" if t['specialty'] else 'NULL'},
            {f"'{t['introduction'].replace(chr(39), chr(39)+chr(39))}'" if t['introduction'] else 'NULL'},
            {t['compensation_before_tax'] if t['compensation_before_tax'] else 'NULL'},
            {t['compensation_after_tax'] if t['compensation_after_tax'] else 'NULL'},
            {f"'{t['level']}'" if t['level'] else 'NULL'},
            {f"'{t['bank_name'].replace(chr(39), chr(39)+chr(39))}'" if t['bank_name'] else 'NULL'},
            {f"'{t['bank_card']}'" if t['bank_card'] else 'NULL'},
            {f"'{t['id_card']}'" if t['id_card'] else 'NULL'},
            {f"'{t['service_customers'].replace(chr(39), chr(39)+chr(39))}'" if t['service_customers'] else 'NULL'},
            '{t['status']}',
            {t['evaluation_score'] if t['evaluation_score'] else 0},
            {t['teaching_count']},
            '{t['creator']}',
            '{t['created_at'].isoformat() if t['created_at'] else datetime.now().isoformat()}');"""
        lines.append(sql)
    
    lines.append('')
    lines.append('-- 插入上课记录')
    for s in schedules:
        lines.append(f"""INSERT INTO schedules (id, teacher_id, teacher_name, subject, class_name, 
            teaching_date, start_time, end_time, duration, location, classroom_id, compensation, 
            status, student_count, director, teacher_manager, score, evaluation_rate, created_at)
            VALUES ({s['id']}, {s['teacher_id']}, '{s['teacher_name'].replace("'", "''")}',
            '{s['subject'].replace("'", "''")}', '{s['class_name'].replace("'", "''")}',
            {f"'{s['teaching_date'].date()}'" if s['teaching_date'] else 'NULL'},
            {f"'{s['start_time']}'" if s['start_time'] else 'NULL'},
            {f"'{s['end_time']}'" if s['end_time'] else 'NULL'},
            {f"'{s['duration']}'" if s['duration'] else 'NULL'},
            {f"'{s['location']}'" if s['location'] else 'NULL'},
            {s['classroom_id'] if s['classroom_id'] else 'NULL'},
            {s['compensation'] if s['compensation'] else 'NULL'},
            '{s['status']}',
            {s['student_count'] if s['student_count'] else 'NULL'},
            {f"'{s['director']}'" if s['director'] else 'NULL'},
            {f"'{s['teacher_manager']}'" if s['teacher_manager'] else 'NULL'},
            {s['score'] if s['score'] else 'NULL'},
            {s['evaluation_rate']},
            '{s['created_at'].isoformat() if s['created_at'] else datetime.now().isoformat()}');""")
    
    # 保存SQL文件
    sql_content = '\n'.join(lines)
    with open('/root/.openclaw/workspace/projects/teacher-management-system/database/import_teachers.sql', 'w', encoding='utf-8') as f:
        f.write(sql_content)
    
    print(f"✅ SQL文件已保存: database/import_teachers.sql")
    print(f"   大小: {len(sql_content)} 字符")


def generate_python_data(teachers, schedules, evaluations):
    """生成Python数据文件供Flask直接加载"""
    print("\n🐍 生成Python数据文件...")
    
    output = []
    output.append('#!/usr/bin/env python3')
    output.append(f'# 师资数据导入文件 - {datetime.now().isoformat()}')
    output.append(f'# 共 {len(teachers)} 位教师')
    output.append('')
    output.append('from datetime import datetime')
    output.append('')
    output.append('# 教师列表')
    output.append('teachers = ')
    output.append(json.dumps(teachers, ensure_ascii=False, indent=2, default=str))
    output.append('')
    output.append('')
    output.append('# 上课记录列表')
    output.append('schedules = ')
    output.append(json.dumps(schedules, ensure_ascii=False, indent=2, default=str))
    output.append('')
    output.append('')
    output.append('# 评价列表')
    output.append('evaluations = ')
    output.append(json.dumps(evaluations, ensure_ascii=False, indent=2, default=str))
    
    content = '\n'.join(output)
    with open('/root/.openclaw/workspace/projects/teacher-management-system/data/imported_teachers.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✅ Python数据文件已保存: data/imported_teachers.py")
    print(f"   大小: {len(content)} 字符")


if __name__ == '__main__':
    print("="*60)
    print("  师资数据导入工具")
    print("="*60)
    
    teachers, schedules, evaluations = import_teachers()
    generate_python_data(teachers, schedules, evaluations)
    
    print("\n" + "="*60)
    print("  导入完成！")
    print("="*60)
    print(f"教师数据: {len(teachers)} 人")
    print(f"上课记录: {len(schedules)} 条")
    print(f"评价记录: {len(evaluations)} 条")