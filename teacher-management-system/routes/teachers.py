from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session
from datetime import datetime
from auth_module import login_required_web
from auth_decorators import require_role, log_operation

teachers_bp = Blueprint('teachers', __name__, url_prefix='/teachers')

# 延迟导入全局变量（避免循环导入）
def _get_globals():
    import sys
    app_module = sys.modules.get('app')
    return {
        'teachers': getattr(app_module, 'teachers', []),
        'courses': getattr(app_module, 'courses', []),
        'teacher_categories': getattr(app_module, 'teacher_categories', []),
        'teachers_full_map': getattr(app_module, 'teachers_full_map', {}),
        'teacher_evaluations_map': getattr(app_module, 'teacher_evaluations_map', {}),
        'teacher_likes_map': getattr(app_module, 'teacher_likes_map', {}),
    }

# ==================== 师资管理列表 ====================

@teachers_bp.route('/')
def teachers_list():
    """师资管理列表（卡片式布局）- 支持分页、排序、跳转"""
    from services.legacy_teacher_service import LegacyTeacherService
    
    g = _get_globals()
    service = LegacyTeacherService(g)
    
    keyword = request.args.get('keyword', '')
    in_stock = request.args.get('in_stock', '')
    approval_status = request.args.get('approval_status', '')
    status = request.args.get('status', '')
    title = request.args.get('title', '')
    sort_by = request.args.get('sort', '')
    page = request.args.get('page', 1, type=int)
    
    result = service.get_teacher_list(
        page=page,
        per_page=20,
        sort_by=sort_by,
        keyword=keyword,
        in_stock=in_stock,
        approval_status=approval_status,
        status=status,
        title=title
    )
    
    return render_template('teachers/list.html',
                         teachers=result['filtered_teachers'],
                         keyword=keyword,
                         in_stock=in_stock,
                         approval_status=approval_status,
                         status=status,
                         title=title,
                         sort_by=sort_by,
                         pagination=result,
                         categories=g['teacher_categories'])


# ==================== 教师详情 ====================

@teachers_bp.route('/<int:id>')
def detail(id):
    """教师详情页"""
    from services.legacy_teacher_service import LegacyTeacherService
    
    g = _get_globals()
    service = LegacyTeacherService(g)
    result = service.get_teacher_detail(id)
    
    if not result['found']:
        flash('教师不存在', 'error')
        return redirect(url_for('teachers.teachers_list'))
    
    return render_template('teachers/detail.html',
                         teacher=result['teacher'],
                         full_info=result['full_info'],
                         courses=result['courses'],
                         evaluations=result['evaluations'],
                         likes=result['likes'])


# ==================== 新增教师 ====================

@teachers_bp.route('/new', methods=['GET', 'POST'])
@login_required_web
@require_role('admin', 'center_director', 'project_manager')
def new():
    """新增教师（需要管理员、中心主任或项目主任权限）"""
    from services.legacy_teacher_service import LegacyTeacherService
    
    g = _get_globals()
    service = LegacyTeacherService(g)
    
    if request.method == 'POST':
        form_data = {
            'name': request.form.get('name'),
            'title': request.form.get('title'),
            'field': request.form.get('field'),
            'specialty': request.form.get('specialty'),
            'introduction': request.form.get('introduction'),
            'organization': request.form.get('organization'),
            'phone': request.form.get('phone'),
            'email': request.form.get('email'),
        }
        result = service.create_teacher(form_data)
        
        if result['success']:
            # 记录操作日志
            log_operation('create_teacher', 'teacher', result['teacher']['id'], result['teacher']['name'], {
                'created_by': session.get('username'),
                'role': session.get('role')
            })
            flash('教师添加成功', 'success')
            return redirect(url_for('teachers.teachers_list'))
        else:
            flash(result['error'], 'error')
    
    return render_template('teachers/form.html', teacher=None, categories=g['teacher_categories'])


# ==================== 编辑教师 ====================

@teachers_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required_web
@require_role('admin', 'center_director', 'project_manager')
def edit(id):
    """编辑教师（需要管理员、中心主任或项目主任权限）"""
    from services.legacy_teacher_service import LegacyTeacherService
    
    g = _get_globals()
    service = LegacyTeacherService(g)
    
    # 查找教师
    detail_result = service.get_teacher_detail(id)
    if not detail_result['found']:
        flash('教师不存在', 'error')
        return redirect(url_for('teachers.teachers_list'))
    
    teacher = detail_result['teacher']
    
    if request.method == 'POST':
        old_name = teacher.get('name', '')
        form_data = {
            'name': request.form.get('name'),
            'title': request.form.get('title'),
            'field': request.form.get('field'),
            'specialty': request.form.get('specialty'),
            'introduction': request.form.get('introduction'),
            'organization': request.form.get('organization'),
            'phone': request.form.get('phone'),
            'email': request.form.get('email'),
        }
        result = service.update_teacher(id, form_data)
        
        if result['success']:
            # 记录操作日志
            log_operation('update_teacher', 'teacher', id, result['teacher']['name'], {
                'updated_by': session.get('username'),
                'role': session.get('role'),
                'old_name': old_name
            })
            flash('教师更新成功', 'success')
            return redirect(url_for('teachers.detail', id=id))
        else:
            flash(result['error'], 'error')
    
    return render_template('teachers/form.html', teacher=teacher, categories=g['teacher_categories'])


# ==================== 删除教师 ====================

@teachers_bp.route('/<int:id>/delete', methods=['POST'])
@login_required_web
@require_role('admin', 'center_director')
def delete(id):
    """删除教师（需要管理员或中心主任权限）"""
    from services.legacy_teacher_service import LegacyTeacherService
    
    g = _get_globals()
    service = LegacyTeacherService(g)
    
    result = service.delete_teacher(id)
    
    if result['success']:
        # 记录操作日志
        log_operation('delete_teacher', 'teacher', id, result['teacher_name'], {
            'deleted_by': session.get('username'),
            'role': session.get('role')
        })
        flash(f'教师 "{result["teacher_name"]}" 删除成功', 'success')
    else:
        flash(result['error'], 'error')
    
    return redirect(url_for('teachers.teachers_list'))
