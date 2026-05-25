from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session
from datetime import datetime
from auth_module import login_required_web

users_bp = Blueprint('users', __name__, url_prefix='/users')
categories_bp = Blueprint('categories', __name__, url_prefix='/categories')
compensations_bp = Blueprint('compensations', __name__, url_prefix='/compensations')
approvals_bp = Blueprint('approvals', __name__, url_prefix='/approvals')
home_bp = Blueprint('home', __name__)

def _get_globals():
    import sys
    app_module = sys.modules.get('app')
    return {
        'classes': getattr(app_module, 'classes', []),
        'courses': getattr(app_module, 'courses', []),
        'teachers': getattr(app_module, 'teachers', []),
        'students': getattr(app_module, 'students', []),
        'classrooms': getattr(app_module, 'classrooms', []),
        'teaching_sites': getattr(app_module, 'teaching_sites', []),
        'teacher_categories': getattr(app_module, 'teacher_categories', []),
        'users': getattr(app_module, 'users', []),
    }

# ==================== 用户管理 ====================

@users_bp.route('/')
@login_required_web
def list():
    """用户列表"""
    g = _get_globals()
    return render_template('users/list.html', users=g['users'])


@users_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
def edit(id):
    """编辑用户"""
    g = _get_globals()
    user = next((u for u in g['users'] if u.get('id') == id), None)
    if not user:
        flash('用户不存在', 'error')
        return redirect(url_for('users.list'))
    if request.method == 'POST':
        user['name'] = request.form.get('name')
        user['role'] = request.form.get('role')
        user['status'] = request.form.get('status', 'active')
        flash('用户更新成功', 'success')
        return redirect(url_for('users.list'))
    return render_template('users/form.html', user=user)


@users_bp.route('/<int:id>/delete', methods=['POST'])
def delete(id):
    """删除用户"""
    g = _get_globals()
    user = next((u for u in g['users'] if u.get('id') == id), None)
    if user:
        g['users'].remove(user)
        flash('用户删除成功', 'success')
    else:
        flash('用户不存在', 'error')
    return redirect(url_for('users.list'))


# ==================== 分类管理 ====================

@categories_bp.route('/')
def categories_list():
    """分类列表"""
    g = _get_globals()
    return render_template('categories/list.html', categories=g['teacher_categories'])


@categories_bp.route('/new', methods=['POST'])
@login_required_web
def category_new():
    """新增分类"""
    g = _get_globals()
    new_category = {
        'id': len(g['teacher_categories']) + 1,
        'name': request.form.get('name'),
        'description': request.form.get('description', ''),
        'created_at': datetime.now()
    }
    g['teacher_categories'].append(new_category)
    flash('分类添加成功', 'success')
    return redirect(url_for('categories.categories_list'))


@categories_bp.route('/<int:id>/edit', methods=['POST'])
def category_edit(id):
    """编辑分类"""
    g = _get_globals()
    category = next((c for c in g['teacher_categories'] if c.get('id') == id), None)
    if category:
        category['name'] = request.form.get('name')
        category['description'] = request.form.get('description', '')
        flash('分类更新成功', 'success')
    else:
        flash('分类不存在', 'error')
    return redirect(url_for('categories.categories_list'))


@categories_bp.route('/<int:id>/delete', methods=['POST'])
def category_delete(id):
    """删除分类"""
    g = _get_globals()
    category = next((c for c in g['teacher_categories'] if c.get('id') == id), None)
    if category:
        g['teacher_categories'].remove(category)
        flash('分类删除成功', 'success')
    else:
        flash('分类不存在', 'error')
    return redirect(url_for('categories.categories_list'))


# ==================== 课酬管理 ====================

@compensations_bp.route('/')
def compensations_list():
    """课酬列表"""
    return render_template('compensations/list.html')


@compensations_bp.route('/<int:id>')
def compensation_detail(id):
    """课酬详情"""
    return render_template('compensations/detail.html', compensation={'id': id})


@compensations_bp.route('/new', methods=['GET', 'POST'])
@login_required_web
def compensation_new():
    """新增课酬"""
    if request.method == 'POST':
        flash('课酬添加成功', 'success')
        return redirect(url_for('compensations.compensations_list'))
    return render_template('compensations/form.html')


@compensations_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
def compensation_edit(id):
    """编辑课酬"""
    if request.method == 'POST':
        flash('课酬更新成功', 'success')
        return redirect(url_for('compensations.compensation_detail', id=id))
    return render_template('compensations/form.html')


@compensations_bp.route('/<int:id>/delete', methods=['POST'])
def compensation_delete(id):
    """删除课酬"""
    flash('课酬删除成功', 'success')
    return redirect(url_for('compensations.compensations_list'))


# ==================== 审批 ====================

@approvals_bp.route('/compensation')
def approvals_compensation():
    """课酬审批"""
    return render_template('approvals/compensation.html')


@approvals_bp.route('/teacher')
def approvals_teacher():
    """教师审批"""
    return render_template('approvals/teacher.html')


@approvals_bp.route('/site')
def approvals_site():
    """教学点审批"""
    return render_template('approvals/site.html')


# ==================== 首页 + 统计 API ====================

@home_bp.route('/')
def index():
    """首页"""
    g = _get_globals()
    # 计算统计数据
    stats = {
        'pending': 0,
        'approvals': 0,
        'teachers': len(g['teachers']),
        'classes': len(g['classes']),
        'students': len(g['students']),
        'courses': len(g['courses']),
    }
    # 计算今日开班完成度
    today_classes = [c for c in g['classes'] if c.get('status') == '进行中']
    total_progress = 0
    if today_classes:
        total_progress = 100
    current_month = datetime.now().strftime('%Y年%m月')
    return render_template('index.html',
                         classes=g['classes'],
                         teachers=g['teachers'],
                         stats=stats,
                         today=datetime.now().strftime('%Y年%m月%d日'),
                         total_classes=len(g['classes']),
                         class_count=len(g['classes']),
                         teacher_count=len(g['teachers']),
                         student_count=len(g['students']),
                         course_count=len(g['courses']),
                         total_progress=total_progress,
                         current_month=current_month)


@home_bp.route('/api/stats')
def api_stats():
    """统计数据 API"""
    g = _get_globals()
    return jsonify({
        'success': True,
        'data': {
            'teacher_count': len(g['teachers']),
            'course_count': len(g['courses']),
            'class_count': len(g['classes']),
            'student_count': len(g['students']),
            'classroom_count': len(g['classrooms']),
            'site_count': len(g['teaching_sites']),
        }
    })
