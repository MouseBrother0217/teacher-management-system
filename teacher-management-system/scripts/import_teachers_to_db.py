import sys
sys.path.insert(0, 'data')
from teachers_full import teachers
import sqlite3
from datetime import datetime

print(f'📊 开始导入 {len(teachers)} 位教师数据...')

conn = sqlite3.connect('instance/teacher_system.db')
cursor = conn.cursor()

# 清空现有数据（如果有）
cursor.execute('DELETE FROM teachers')
print('🗑️ 清空现有教师数据')

# 解析课酬字段
def parse_compensation(comp_str):
    """解析课酬字符串，如 '半天:2300' -> (2300, None) 或 '半天:2300 一天:4500' -> (2300, 4500)"""
    half_day = None
    full_day = None
    if comp_str:
        parts = comp_str.split()
        for part in parts:
            if '半天' in part:
                try:
                    half_day = int(part.split(':')[1])
                except:
                    pass
            elif '一天' in part or '全天' in part:
                try:
                    full_day = int(part.split(':')[1])
                except:
                    pass
    return half_day, full_day

# 转换状态
def parse_status(status_str):
    return 1 if status_str == '已入库' else 0

# 导入计数
imported = 0
errors = []

for teacher in teachers:
    try:
        half_day, full_day = parse_compensation(teacher.get('compensation_before_tax', ''))
        
        cursor.execute('''
            INSERT OR REPLACE INTO teachers (
                id, name, field, description, avatar_url, 
                lecture_fee_half_day, lecture_fee_full_day,
                id_card, bank_name, bank_account, phone,
                teacher_type, is_in_storage, level, service_client,
                total_teaching_count, overall_score, total_evaluations,
                created_at, updated_at, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            teacher.get('id'),
            teacher.get('name'),
            teacher.get('field'),
            teacher.get('introduction'),
            teacher.get('avatar_url'),
            half_day,
            full_day,
            teacher.get('id_card'),
            teacher.get('bank_name'),
            teacher.get('bank_card'),
            teacher.get('phone'),
            teacher.get('teacher_type'),
            parse_status(teacher.get('status', '')),
            teacher.get('level'),
            teacher.get('service_customers'),
            teacher.get('teaching_count', 0),
            teacher.get('evaluation_score', 0),
            len(teacher.get('detailed_evaluations', [])) if teacher.get('detailed_evaluations') else 0,
            datetime.now(),
            datetime.now(),
            1  # created_by: admin
        ))
        imported += 1
    except Exception as e:
        errors.append(f"教师 {teacher.get('name', 'unknown')}: {str(e)}")

conn.commit()

# 验证导入结果
cursor.execute('SELECT COUNT(*) FROM teachers')
total = cursor.fetchone()[0]

conn.close()

print(f'\n✅ 导入完成: {imported}/{len(teachers)} 位教师')
print(f'📊 数据库当前教师总数: {total}')

if errors:
    print(f'\n⚠️ 导入错误 ({len(errors)} 条):')
    for err in errors[:5]:
        print(f'  - {err}')
    if len(errors) > 5:
        print(f'  ... 还有 {len(errors) - 5} 条错误')
else:
    print('🎉 无导入错误！')
