#!/usr/bin/env python3
"""
认证与权限模块 - Flask Blueprint
包含登录/登出/权限检查装饰器
"""

from functools import wraps
from flask import Blueprint, request, jsonify, session, g, redirect, url_for, flash
from datetime import datetime, timedelta
import secrets

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

# 简单的token存储（生产环境用Redis）
active_tokens = {}  # token -> user_id

# ==================== 角色与权限配置 ====================

ROLES = {
    'admin': {'label': '系统管理员', 'level': 100},
    'center_director': {'label': '中心主任', 'level': 90},
    'project_manager': {'label': '项目主任', 'level': 80},
    'class_advisor': {'label': '班主任', 'level': 70},
    'finance_admin': {'label': '财务+行政', 'level': 60},
    'teacher': {'label': '老师', 'level': 50},
    'student': {'label': '学员', 'level': 10}
}

# 权限矩阵
PERMISSIONS = {
    # 师资权限
    'teacher_view': ['admin', 'center_director', 'project_manager', 'class_advisor'],
    'teacher_edit': ['admin', 'center_director'],
    'teacher_add': ['admin', 'center_director', 'project_manager'],
    'teacher_approve': ['admin', 'center_director', 'finance_admin'],
    
    # 班级权限
    'class_create': ['admin', 'center_director', 'project_manager'],
    'class_manage_all': ['admin', 'center_director', 'project_manager'],
    'class_manage_own': ['admin', 'center_director', 'project_manager', 'class_advisor'],
    
    # 学员权限
    'student_view_all': ['admin', 'center_director', 'project_manager', 'class_advisor'],
    'student_view_no_privacy': ['teacher'],  # 老师看不到手机号、身份证号、单位、职务
    
    # 课表权限
    'schedule_view_all': ['admin', 'center_director', 'project_manager', 'class_advisor', 'teacher', 'student'],
    'schedule_edit': ['admin', 'center_director', 'class_advisor'],
    'schedule_view_own': ['teacher', 'student'],
    
    # 财务权限
    'finance_view': ['admin', 'center_director', 'finance_admin'],
    'payment_manage': ['admin', 'center_director', 'finance_admin'],
    'payment_view_own': ['teacher'],
    
    # 物资/盘点
    'inventory_manage': ['admin', 'center_director', 'finance_admin'],
    
    # 数据导出
    'data_export': ['admin', 'center_director'],
    
    # 评价
    'evaluation_view': ['admin', 'center_director', 'project_manager', 'class_advisor', 'teacher', 'student'],
    'evaluation_submit': ['student'],
    
    # 签到
    'sign_in': ['admin', 'center_director', 'project_manager', 'class_advisor', 'student'],
    
    # 系统管理
    'user_manage': ['admin', 'center_director']
}

def has_permission(user_role, perm_code):
    """检查角色是否拥有指定权限"""
    if user_role == 'admin':
        return True
    allowed_roles = PERMISSIONS.get(perm_code, [])
    return user_role in allowed_roles

def get_role_label(role):
    """获取角色中文名称"""
    return ROLES.get(role, {}).get('label', role)

# ==================== 认证装饰器 ====================

def require_auth(f):
    """要求登录的装饰器（API Token方式）"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '').strip()
        if not token or token not in active_tokens:
            return jsonify({'success': False, 'message': '未登录或Token无效'}), 401
        
        user_id = active_tokens[token]
        from models import User
        g.current_user = User.query.get(user_id)
        
        if not g.current_user or not g.current_user.is_active:
            return jsonify({'success': False, 'message': '用户不存在或已禁用'}), 401
        
        return f(*args, **kwargs)
    return decorated

def require_role(*roles):
    """要求指定角色的装饰器（API方式）"""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not hasattr(g, 'current_user'):
                return jsonify({'success': False, 'message': '未登录'}), 401
            
            if g.current_user.role not in roles:
                return jsonify({'success': False, 'message': '无权访问：需要角色 ' + '/'.join(roles)}), 403
            
            return f(*args, **kwargs)
        return decorated
    return decorator

def login_required_web(f):
    """网页端：要求登录的装饰器（基于 Session）"""
    @wraps(f)
    def decorated(*args, **kwargs):
        from models import User
        user_id = session.get('user_id')
        if not user_id:
            return redirect(url_for('auth.web_login_page'))
        
        user = User.query.get(user_id)
        if not user or not user.is_active:
            session.clear()
            return redirect(url_for('auth.web_login_page'))
        
        g.current_user = user
        return f(*args, **kwargs)
    return decorated

def require_permission_web(perm_code):
    """网页端：要求指定权限的装饰器"""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not hasattr(g, 'current_user'):
                return redirect(url_for('auth.web_login_page'))
            
            if not has_permission(g.current_user.role, perm_code):
                flash('无权访问：您没有该功能的权限', 'error')
                return redirect(url_for('index'))
            
            return f(*args, **kwargs)
        return decorated
    return decorator

def require_role_web(*roles):
    """网页端：要求指定角色的装饰器"""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not hasattr(g, 'current_user'):
                return redirect(url_for('auth.web_login_page'))
            
            if g.current_user.role not in roles and g.current_user.role != 'admin':
                flash('无权访问：需要角色 ' + '/'.join(ROLES.get(r, {}).get('label', r) for r in roles), 'error')
                return redirect(url_for('index'))
            
            return f(*args, **kwargs)
        return decorated
    return decorator


# ==================== API 认证路由 ====================

@auth_bp.route('/login', methods=['POST'])
def api_login():
    """API用户登录"""
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')
    
    if not username or not password:
        return jsonify({'success': False, 'message': '用户名和密码不能为空'}), 400
    
    from models import User, db
    user = User.query.filter_by(username=username, is_active=True).first()
    
    if not user:
        return jsonify({'success': False, 'message': '用户名或密码错误'}), 401
    
    # 检查密码
    from werkzeug.security import check_password_hash
    import hashlib
    password_valid = False
    
    if user.password_hash.startswith('pbkdf2:sha256:'):
        password_valid = check_password_hash(user.password_hash, password)
    else:
        password_valid = user.password_hash == hashlib.sha256(password.encode()).hexdigest()
    
    if not password_valid:
        return jsonify({'success': False, 'message': '用户名或密码错误'}), 401
    
    # 生成token
    token = secrets.token_urlsafe(32)
    active_tokens[token] = user.id
    
    # 更新最后登录时间
    user.last_login = datetime.now()
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': '登录成功',
        'token': token,
        'user': {
            'id': user.id,
            'username': user.username,
            'real_name': user.name or user.username,
            'role': user.role,
            'role_name': get_role_label(user.role)
        }
    })


@auth_bp.route('/logout', methods=['POST'])
@require_auth
def api_logout():
    """API用户登出"""
    token = request.headers.get('Authorization', '').replace('Bearer ', '').strip()
    if token in active_tokens:
        del active_tokens[token]
    return jsonify({'success': True, 'message': '登出成功'})


@auth_bp.route('/me', methods=['GET'])
@require_auth
def api_me():
    """获取当前用户信息（API）"""
    user = g.current_user
    return jsonify({
        'success': True,
        'user': {
            'id': user.id,
            'username': user.username,
            'real_name': user.name or user.username,
            'role': user.role,
            'role_name': get_role_label(user.role)
        }
    })


# ==================== 网页端登录路由 ====================

from flask import render_template_string

LOGIN_PAGE_TEMPLATE = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>师资管理系统 - 登录</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .login-box {
            background: white;
            padding: 40px;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            width: 100%;
            max-width: 400px;
        }
        h1 { text-align: center; color: #333; margin-bottom: 8px; font-size: 24px; }
        .subtitle { text-align: center; color: #888; font-size: 14px; margin-bottom: 30px; }
        .form-group { margin-bottom: 20px; }
        label { display: block; margin-bottom: 6px; color: #555; font-size: 14px; font-weight: 500; }
        input[type="text"], input[type="password"] {
            width: 100%; padding: 12px; border: 2px solid #e0e0e0; border-radius: 8px;
            font-size: 14px; transition: border-color 0.2s;
        }
        input:focus { outline: none; border-color: #667eea; }
        .btn-login {
            width: 100%; padding: 14px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white; border: none; border-radius: 8px;
            font-size: 16px; font-weight: 600; cursor: pointer;
        }
        .btn-login:hover { opacity: 0.9; }
        .alert {
            font-size: 13px; margin-top: 10px;
            text-align: center; padding: 8px; border-radius: 4px;
        }
        .alert-error { color: #f44336; background: #ffebee; }
        .alert-success { color: #4caf50; background: #e8f5e9; }
        .role-info {
            margin-top: 20px; padding: 12px;
            background: #f5f5f5; border-radius: 8px;
            font-size: 12px; color: #666;
        }
        .role-info strong { color: #333; }
    </style>
</head>
<body>
    <div class="login-box">
        <h1>🏫 师资管理系统</h1>
        <div class="subtitle">浙江大学继续教育学院</div>
        
        {% if error %}
        <div class="alert alert-error">{{ error }}</div>
        {% endif %}
        {% if success %}
        <div class="alert alert-success">{{ success }}</div>
        {% endif %}
        
        <form method="post" action="/api/auth/web-login">
            <div class="form-group">
                <label>用户名</label>
                <input type="text" name="username" placeholder="请输入用户名" required>
            </div>
            <div class="form-group">
                <label>密码</label>
                <input type="password" name="password" placeholder="请输入密码" required>
            </div>
            <button type="submit" class="btn-login">登录</button>
        </form>
        
        <div class="role-info">
            <strong>测试账号:</strong><br>
            admin / admin123 (系统管理员)<br>
            center / 123456 (中心主任)<br>
            project / 123456 (项目主任)<br>
            advisor / 123456 (班主任)<br>
            finance / 123456 (财务+行政)<br>
            teacher01 / 123456 (老师)<br>
            student01 / 123456 (学员)
        </div>
    </div>
</body>
</html>
'''

@auth_bp.route('/web-login', methods=['GET'])
def web_login_page():
    """网页端登录页面"""
    error = request.args.get('error')
    success = request.args.get('success')
    return render_template_string(LOGIN_PAGE_TEMPLATE, error=error, success=success)


@auth_bp.route('/web-login', methods=['POST'])
def web_login():
    """网页端登录处理（基于 Session）"""
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    
    if not username or not password:
        flash('用户名和密码不能为空', 'error')
        return redirect(url_for('auth.web_login_page'))
    
    from models import User, db
    from werkzeug.security import check_password_hash
    import hashlib
    
    user = User.query.filter_by(username=username, is_active=True).first()
    
    if not user:
        flash('用户名或密码错误', 'error')
        return redirect(url_for('auth.web_login_page'))
    
    # 检查密码
    password_valid = False
    if user.password_hash.startswith('pbkdf2:sha256:') or user.password_hash.startswith('scrypt:'):
        password_valid = check_password_hash(user.password_hash, password)
    else:
        password_valid = user.password_hash == hashlib.sha256(password.encode()).hexdigest()
    
    if not password_valid:
        flash('用户名或密码错误', 'error')
        return redirect(url_for('auth.web_login_page'))
    
    # 登录成功，写入 Session
    session['user_id'] = user.id
    session['username'] = user.username
    session['role'] = user.role
    session['name'] = user.name or user.username
    
    # 更新最后登录时间
    user.last_login = datetime.now()
    db.session.commit()
    
    flash(f'欢迎回来，{user.name or user.username}！', 'success')
    # 使用JS重定向代替HTTP重定向，避免cloudflare tunnels的POST跟随问题
    from flask import make_response
    response = make_response('''
    <!DOCTYPE html>
    <html>
    <head>
        <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
        <meta http-equiv="Pragma" content="no-cache">
        <meta http-equiv="Expires" content="0">
        <meta http-equiv="refresh" content="0;url=/">
    </head>
    <body>
        <p>登录成功，正在跳转...</p>
        <script>window.location.href='/';</script>
    </body>
    </html>
    ''')
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@auth_bp.route('/web-logout')
def web_logout():
    """网页端登出"""
    session.clear()
    flash('已安全退出登录', 'info')
    return redirect(url_for('auth.web_login_page'))


# ==================== 账号初始化 ====================

from werkzeug.security import generate_password_hash

DEFAULT_ACCOUNTS = [
    {'username': 'admin', 'name': '系统管理员', 'role': 'admin', 'password': 'admin123'},
    {'username': 'center', 'name': '中心主任', 'role': 'center_director', 'password': '123456'},
    {'username': 'project', 'name': '项目主任', 'role': 'project_manager', 'password': '123456'},
    {'username': 'advisor', 'name': '班主任', 'role': 'class_advisor', 'password': '123456'},
    {'username': 'finance', 'name': '财务行政', 'role': 'finance_admin', 'password': '123456'},
    {'username': 'teacher01', 'name': '李老师', 'role': 'teacher', 'password': '123456'},
    {'username': 'student01', 'name': '张学员', 'role': 'student', 'password': '123456'},
]

def init_default_users(db):
    """初始化默认用户账号"""
    from models import User
    
    created = []
    for account in DEFAULT_ACCOUNTS:
        user = User.query.filter_by(username=account['username']).first()
        if not user:
            user = User(
                username=account['username'],
                name=account['name'],
                role=account['role'],
                is_active=True
            )
            user.password_hash = generate_password_hash(account['password'])
            db.session.add(user)
            created.append(account['username'])
    
    if created:
        db.session.commit()
        print(f"✅ 创建默认账号: {', '.join(created)}")
    else:
        print("✅ 默认账号已存在，无需创建")
    
    return created


# ==================== 用户管理 API ====================

@auth_bp.route('/users', methods=['GET'])
@require_auth
def api_list_users():
    """获取用户列表（仅限管理员和中心主任）"""
    if g.current_user.role not in ['admin', 'center_director']:
        return jsonify({'success': False, 'message': '无权访问'}), 403
    
    from models import User
    users = User.query.all()
    return jsonify({
        'success': True,
        'users': [{
            'id': u.id,
            'username': u.username,
            'name': u.name or u.username,
            'role': u.role,
            'role_name': get_role_label(u.role),
            'is_active': u.is_active,
            'last_login': u.last_login.strftime('%Y-%m-%d %H:%M') if u.last_login else None,
            'created_at': u.created_at.strftime('%Y-%m-%d') if u.created_at else None
        } for u in users]
    })


@auth_bp.route('/users', methods=['POST'])
@require_auth
def api_create_user():
    """创建新用户"""
    if g.current_user.role not in ['admin', 'center_director']:
        return jsonify({'success': False, 'message': '无权访问'}), 403
    
    from models import User, db
    data = request.get_json() or {}
    
    username = data.get('username', '').strip()
    name = data.get('name', '').strip()
    role = data.get('role', '').strip()
    password = data.get('password', '').strip()
    
    if not username or not password or not role:
        return jsonify({'success': False, 'message': '用户名、密码、角色不能为空'}), 400
    
    if role not in ROLES:
        return jsonify({'success': False, 'message': f'无效角色: {role}'}), 400
    
    # 检查用户名是否已存在
    if User.query.filter_by(username=username).first():
        return jsonify({'success': False, 'message': '用户名已存在'}), 400
    
    user = User(
        username=username,
        name=name or username,
        role=role,
        is_active=True
    )
    user.password_hash = generate_password_hash(password)
    db.session.add(user)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': '用户创建成功',
        'user': {
            'id': user.id,
            'username': user.username,
            'name': user.name,
            'role': user.role,
            'role_name': get_role_label(user.role)
        }
    })


@auth_bp.route('/users/<int:user_id>', methods=['PUT'])
@require_auth
def api_update_user(user_id):
    """更新用户信息（角色、状态）"""
    if g.current_user.role not in ['admin', 'center_director']:
        return jsonify({'success': False, 'message': '无权访问'}), 403
    
    from models import User, db
    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'message': '用户不存在'}), 404
    
    # 不能修改自己
    if user.id == g.current_user.id:
        return jsonify({'success': False, 'message': '不能修改自己的信息'}), 400
    
    data = request.get_json() or {}
    
    # 更新角色
    if 'role' in data:
        new_role = data['role']
        if new_role not in ROLES:
            return jsonify({'success': False, 'message': f'无效角色: {new_role}'}), 400
        user.role = new_role
    
    # 更新名称
    if 'name' in data:
        user.name = data['name'].strip()
    
    # 更新状态
    if 'is_active' in data:
        user.is_active = bool(data['is_active'])
    
    # 重置密码
    if 'password' in data and data['password']:
        user.password_hash = generate_password_hash(data['password'])
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': '用户信息更新成功',
        'user': {
            'id': user.id,
            'username': user.username,
            'name': user.name,
            'role': user.role,
            'role_name': get_role_label(user.role),
            'is_active': user.is_active
        }
    })


@auth_bp.route('/users/<int:user_id>', methods=['DELETE'])
@require_auth
def api_delete_user(user_id):
    """删除用户"""
    if g.current_user.role not in ['admin', 'center_director']:
        return jsonify({'success': False, 'message': '无权访问'}), 403
    
    from models import User, db
    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'message': '用户不存在'}), 404
    
    # 不能删除自己
    if user.id == g.current_user.id:
        return jsonify({'success': False, 'message': '不能删除自己'}), 400
    
    # 不能删除admin账号
    if user.username == 'admin' and g.current_user.username != 'admin':
        return jsonify({'success': False, 'message': '不能删除系统管理员账号'}), 400
    
    db.session.delete(user)
    db.session.commit()
    
    return jsonify({'success': True, 'message': '用户已删除'})


@auth_bp.route('/users/<int:user_id>/toggle', methods=['POST'])
@require_auth
def api_toggle_user(user_id):
    """启用/禁用用户"""
    if g.current_user.role not in ['admin', 'center_director']:
        return jsonify({'success': False, 'message': '无权访问'}), 403
    
    from models import User, db
    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'message': '用户不存在'}), 404
    
    # 不能禁用自己
    if user.id == g.current_user.id:
        return jsonify({'success': False, 'message': '不能禁用自己'}), 400
    
    user.is_active = not user.is_active
    db.session.commit()
    
    status = '启用' if user.is_active else '禁用'
    return jsonify({
        'success': True,
        'message': f'用户已{status}',
        'is_active': user.is_active
    })


# ==================== 模块初始化 ====================

def init_auth_module(app, db):
    """初始化认证模块"""
    from models import User
    
    # 注册蓝图
    app.register_blueprint(auth_bp)
    
    # 在每个请求前加载当前用户到 g
    @app.before_request
    def load_current_user():
        user_id = session.get('user_id')
        if user_id:
            g.current_user = User.query.get(user_id)
        else:
            g.current_user = None
    
    # 创建默认账号
    with app.app_context():
        # 确保数据库表已创建
        db.create_all()
        init_default_users(db)


if __name__ == '__main__':
    print("认证模块加载完成")
