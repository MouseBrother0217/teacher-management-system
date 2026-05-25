"""
权限控制装饰器
基于角色的访问控制（RBAC）
"""

from functools import wraps
from flask import session, flash, redirect, url_for, request
import json
from datetime import datetime

# 角色权限映射
ROLE_PERMISSIONS = {
    'admin': ['all'],  # 管理员拥有所有权限
    'center_director': [
        'teachers.view', 'teachers.edit', 'teachers.delete',
        'classes.view', 'classes.edit', 'classes.delete',
        'courses.view', 'courses.edit',
        'schedules.view', 'schedules.edit',
        'reports.view', 'reports.export',
        'users.view', 'users.edit'
    ],
    'project_manager': [
        'teachers.view',
        'classes.view', 'classes.edit',
        'schedules.view', 'schedules.edit',
        'courses.view'
    ],
    'class_advisor': [
        'teachers.view',
        'classes.view',
        'students.view', 'students.edit',
        'schedules.view'
    ],
    'finance_admin': [
        'teachers.view',
        'compensations.view', 'compensations.edit',
        'reports.view', 'reports.export'
    ],
    'teacher': [
        'teachers.view_own',
        'schedules.view_own'
    ],
    'student': [
        'classes.view',
        'schedules.view'
    ]
}

# 路由权限映射（简化版，按模块控制）
MODULE_PERMISSIONS = {
    'teachers': ['admin', 'center_director', 'project_manager', 'class_advisor', 'finance_admin'],
    'classes': ['admin', 'center_director', 'project_manager', 'class_advisor'],
    'schedules': ['admin', 'center_director', 'project_manager', 'class_advisor'],
    'students': ['admin', 'center_director', 'class_advisor'],
    'compensations': ['admin', 'center_director', 'finance_admin'],
    'reports': ['admin', 'center_director', 'finance_admin'],
    'users': ['admin'],  # 用户管理只有管理员能访问
    'import': ['admin', 'center_director', 'project_manager'],  # 数据导入权限
}

def require_role(*roles):
    """角色权限装饰器
    
    用法：
    @require_role('admin', 'center_director')
    def some_route():
        ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_role = session.get('role', '')
            if not user_role:
                flash('请先登录', 'warning')
                return redirect(url_for('login'))
            
            if user_role not in roles and user_role != 'admin':
                flash(f'权限不足，需要以下角色之一：{", ".join(roles)}', 'error')
                return redirect(url_for('index'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def require_permission(permission):
    """细粒度权限装饰器
    
    用法：
    @require_permission('teachers.delete')
    def delete_teacher(id):
        ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_role = session.get('role', '')
            if not user_role:
                flash('请先登录', 'warning')
                return redirect(url_for('login'))
            
            # 管理员拥有所有权限
            if user_role == 'admin':
                return f(*args, **kwargs)
            
            # 检查角色是否有该权限
            perms = ROLE_PERMISSIONS.get(user_role, [])
            if 'all' not in perms and permission not in perms:
                flash(f'权限不足：需要 {permission} 权限', 'error')
                return redirect(url_for('index'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def log_operation(action, target_type, target_id, target_name, details=None):
    """记录操作日志
    
    用法：
    log_operation('delete_teacher', 'teacher', 123, '张三', {'reason': '重复数据'})
    """
    from flask import session, request
    from models import db, OperationLog
    
    try:
        log = OperationLog(
            user_id=session.get('user_id'),
            username=session.get('username', 'unknown'),
            role=session.get('role', 'unknown'),
            action=action,
            target_type=target_type,
            target_id=target_id,
            target_name=target_name,
            details=json.dumps(details, ensure_ascii=False) if details else None,
            ip_address=request.remote_addr
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        print(f'⚠️ 操作日志记录失败: {e}')

def get_user_role_label(role):
    """获取角色中文名称"""
    labels = {
        'admin': '系统管理员',
        'center_director': '中心主任',
        'project_manager': '项目主任',
        'class_advisor': '班主任',
        'finance_admin': '财务行政',
        'teacher': '教师',
        'student': '学员'
    }
    return labels.get(role, role)

def get_role_color(role):
    """获取角色对应的颜色（用于前端显示）"""
    colors = {
        'admin': 'red',
        'center_director': 'orange',
        'project_manager': 'blue',
        'class_advisor': 'green',
        'finance_admin': 'purple',
        'teacher': 'cyan',
        'student': 'gray'
    }
    return colors.get(role, 'default')
