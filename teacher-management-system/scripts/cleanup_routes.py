#!/usr/bin/env python3
"""
Clean Architecture 路由清理脚本
自动删除 app.py 中已迁移到蓝图的路由代码
用法: python3 cleanup_routes.py
"""

import re

APP_FILE = '/root/.openclaw/workspace/teacher-management-system/app.py'
BACKUP_FILE = APP_FILE + '.backup_cleanup'

# 已迁移到蓝图的路由函数列表
MIGRATED_ROUTES = [
    # classrooms
    'classrooms_list', 'classroom_detail', 'classroom_new', 'classroom_edit', 'classroom_delete',
    # sites
    'sites_list', 'site_detail', 'site_new', 'site_edit', 'site_delete',
    # api
    'api_add_classroom', 'api_add_teaching_site',
    # teachers
    'teachers_list', 'teacher_detail', 'teacher_new', 'teacher_edit', 'teacher_delete',
    'api_teachers', 'api_teacher_add_course',
    # classes
    'classes_list', 'class_detail', 'class_generate_schedule', 'class_schedule', 'class_new',
    'class_edit', 'class_delete', 'class_checklist', 'class_checklist_progress', 'import_students',
    # courses
    'courses_list', 'course_detail', 'course_new', 'course_edit', 'course_delete',
    # students
    'students_list', 'student_detail', 'student_edit', 'student_delete', 'download_student_template',
    # schedules
    'schedules_list', 'schedule_detail', 'schedule_new', 'schedule_edit', 'schedule_delete',
    # users
    'users_list', 'user_edit', 'user_delete',
    # categories
    'categories_list', 'category_new', 'category_edit', 'category_delete',
    # compensations
    'compensations_list', 'compensation_detail', 'compensation_new', 'compensation_edit', 'compensation_delete',
    # approvals
    'approvals_compensation', 'approvals_teacher', 'approvals_site',
    # home
    'index', 'api_stats',
]

def cleanup_routes():
    with open(APP_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 备份
    with open(BACKUP_FILE, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'✅ 已备份到 {BACKUP_FILE}')
    
    # 找到所有路由函数并删除
    lines = content.split('\n')
    result_lines = []
    skip_until_next_def = False
    skip_indent = None
    
    for i, line in enumerate(lines):
        if skip_until_next_def:
            # 检查是否到达下一个顶层定义
            if line.startswith('def ') or line.startswith('@app.route') or line.startswith('# ==='):
                skip_until_next_def = False
                skip_indent = None
                result_lines.append(line)
            elif line.strip() and not line.startswith('#'):
                # 检查缩进是否回到顶层
                if not line.startswith(' ') and not line.startswith('\t'):
                    skip_until_next_def = False
                    skip_indent = None
                    result_lines.append(line)
            continue
        
        # 检查是否是已迁移的路由函数定义
        if line.startswith('def '):
            func_match = re.match(r'def\s+([a-z_]+)\(', line)
            if func_match:
                func_name = func_match.group(1)
                if func_name in MIGRATED_ROUTES:
                    # 找到该函数前面的装饰器（如果有）
                    # 回溯找到 @app.route 或其他装饰器
                    j = len(result_lines) - 1
                    while j >= 0:
                        prev_line = result_lines[j].strip()
                        if prev_line.startswith('@app.route') or prev_line.startswith('@login_required') or prev_line.startswith('@'):
                            result_lines.pop(j)
                            j -= 1
                        elif prev_line == '' or prev_line.startswith('#'):
                            j -= 1
                        else:
                            break
                    
                    print(f'🗑️  删除已迁移路由: {func_name}')
                    skip_until_next_def = True
                    continue
        
        result_lines.append(line)
    
    new_content = '\n'.join(result_lines)
    
    with open(APP_FILE, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    # 统计
    original_lines = len(lines)
    new_lines = len(result_lines)
    removed = original_lines - new_lines
    print(f'\n📊 清理统计:')
    print(f'   原始行数: {original_lines}')
    print(f'   清理后行数: {new_lines}')
    print(f'   删除行数: {removed}')
    print(f'   缩减比例: {removed/original_lines*100:.1f}%')

if __name__ == '__main__':
    cleanup_routes()
    print('\n⚠️  清理完成，请运行测试验证: pytest tests/test_basic.py -v')
