from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session
from datetime import datetime
from auth_module import login_required_web

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
    g = _get_globals()
    teachers = g['teachers']
    
    keyword = request.args.get('keyword', '')
    in_stock = request.args.get('in_stock', '')
    approval_status = request.args.get('approval_status', '')
    status = request.args.get('status', '')
    title = request.args.get('title', '')
    sort_by = request.args.get('sort', '')
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    filtered_teachers = teachers.copy()
    
    # 综合搜索
    if keyword:
        keywords = [k.strip().lower() for k in keyword.split() if k.strip()]
        def matches_all_keywords(teacher, keywords):
            search_parts = [
                str(teacher.get('name', '')),
                str(teacher.get('field', '')),
                str(teacher.get('title', '')),
                str(teacher.get('specialty', '')),
                str(teacher.get('introduction', '')),
                str(teacher.get('organization', '')),
                str(teacher.get('phone', '')),
                str(teacher.get('contact_phone', '')),
                str(teacher.get('course_info', '')),
            ]
            for rec in teacher.get('teaching_records', []):
                search_parts.append(str(rec.get('课程名称', '')))
            search_text = ' '.join(search_parts).lower()
            return all(kw in search_text for kw in keywords)
        filtered_teachers = [t for t in filtered_teachers if matches_all_keywords(t, keywords)]
    
    # 是否入库筛选
    if in_stock:
        if in_stock == '是':
            filtered_teachers = [t for t in filtered_teachers if t.get('status') == '已入库']
        elif in_stock == '否':
            filtered_teachers = [t for t in filtered_teachers if t.get('status') != '已入库']
    
    # 审批状态筛选
    if approval_status:
        if approval_status == '已通过':
            filtered_teachers = [t for t in filtered_teachers if t.get('status') == '已入库']
        elif approval_status == '待审核':
            filtered_teachers = [t for t in filtered_teachers if t.get('status') == '待审核']
    
    if title:
        filtered_teachers = [t for t in filtered_teachers if t.get('title') == title]
    
    # 排序
    if sort_by == 'score':
        filtered_teachers = sorted(filtered_teachers, 
                                  key=lambda x: float(x.get('evaluation_score') or 0), 
                                  reverse=True)
    elif sort_by == 'count':
        filtered_teachers = sorted(filtered_teachers, 
                                  key=lambda x: int(x.get('teaching_count') or 0), 
                                  reverse=True)
    elif sort_by == 'name':
        filtered_teachers = sorted(filtered_teachers, 
                                  key=lambda x: x.get('name', ''))
    
    # 分页计算
    total = len(filtered_teachers)
    total_pages = (total + per_page - 1) // per_page
    page = max(1, min(page, total_pages)) if total_pages > 0 else 1
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    paginated_teachers = filtered_teachers[start_idx:end_idx]
    
    # 生成分页页码列表
    pages_list = []
    if total_pages <= 7:
        pages_list = list(range(1, total_pages + 1))
    else:
        if page <= 4:
            pages_list = list(range(1, 6)) + ['...', total_pages]
        elif page >= total_pages - 3:
            pages_list = [1, '...'] + list(range(total_pages - 4, total_pages + 1))
        else:
            pages_list = [1, '...'] + list(range(page - 1, page + 2)) + ['...', total_pages]
    
    pagination = {
        'page': page,
        'per_page': per_page,
        'total': total,
        'pages': total_pages,
        'has_prev': page > 1,
        'has_next': page < total_pages,
        'prev_num': page - 1,
        'next_num': page + 1,
        'pages_list': pages_list
    }
    
    # 为每位讲师添加课程数量（从 course_teachers 表查询）
    try:
        import sqlite3
        conn = sqlite3.connect('instance/teacher_system.db')
        c = conn.cursor()
        for teacher in paginated_teachers:
            teacher_id = teacher.get('id', 0)
            c.execute('SELECT COUNT(*) FROM course_teachers WHERE teacher_id = ?', (teacher_id,))
            teacher['course_count'] = c.fetchone()[0]
        conn.close()
    except:
        for teacher in paginated_teachers:
            teacher['course_count'] = 0
    
    return render_template('teachers/list.html',
                         teachers=paginated_teachers,
                         keyword=keyword,
                         in_stock=in_stock,
                         approval_status=approval_status,
                         status=status,
                         title=title,
                         sort_by=sort_by,
                         pagination=pagination,
                         categories=g['teacher_categories'])


# ==================== 教师详情 ====================

@teachers_bp.route('/<int:id>')
def detail(id):
    """教师详情页"""
    g = _get_globals()
    teachers = g['teachers']
    teachers_full_map = g['teachers_full_map']
    teacher_evaluations_map = g['teacher_evaluations_map']
    teacher_likes_map = g['teacher_likes_map']
    
    teacher = next((t for t in teachers if t['id'] == id), None)
    if not teacher:
        flash('教师不存在', 'error')
        return redirect(url_for('teachers.teachers_list'))
    
    # 从完整数据中获取额外信息
    full_info = teachers_full_map.get(teacher['name'], {})
    
    # 获取该教师的课程
    teacher_courses = [c for c in g.get('courses', []) if c.get('teacher_id') == id]
    
    # 获取评价数据
    evaluations = teacher_evaluations_map.get(teacher['name'], [])
    likes = teacher_likes_map.get(teacher['name'], [])
    
    return render_template('teachers/detail.html',
                         teacher=teacher,
                         full_info=full_info,
                         courses=teacher_courses,
                         evaluations=evaluations,
                         likes=likes)


# ==================== 新增教师 ====================

@teachers_bp.route('/new', methods=['GET', 'POST'])
@login_required_web
def new():
    """新增教师"""
    g = _get_globals()
    teachers = g['teachers']
    
    if request.method == 'POST':
        new_teacher = {
            'id': len(teachers) + 1,
            'name': request.form.get('name'),
            'title': request.form.get('title'),
            'field': request.form.get('field'),
            'specialty': request.form.get('specialty'),
            'introduction': request.form.get('introduction'),
            'organization': request.form.get('organization'),
            'phone': request.form.get('phone'),
            'email': request.form.get('email'),
            'status': '待审核',
            'created_at': datetime.now()
        }
        teachers.append(new_teacher)
        flash('教师添加成功', 'success')
        return redirect(url_for('teachers.teachers_list'))
    
    return render_template('teachers/form.html', teacher=None, categories=g['teacher_categories'])


# ==================== 编辑教师 ====================

@teachers_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
def edit(id):
    """编辑教师"""
    g = _get_globals()
    teachers = g['teachers']
    
    teacher = next((t for t in teachers if t['id'] == id), None)
    if not teacher:
        flash('教师不存在', 'error')
        return redirect(url_for('teachers.teachers_list'))
    
    if request.method == 'POST':
        teacher['name'] = request.form.get('name')
        teacher['title'] = request.form.get('title')
        teacher['field'] = request.form.get('field')
        teacher['specialty'] = request.form.get('specialty')
        teacher['introduction'] = request.form.get('introduction')
        teacher['organization'] = request.form.get('organization')
        teacher['phone'] = request.form.get('phone')
        teacher['email'] = request.form.get('email')
        flash('教师更新成功', 'success')
        return redirect(url_for('teachers.detail', id=id))
    
    return render_template('teachers/form.html', teacher=teacher, categories=g['teacher_categories'])


# ==================== 删除教师 ====================

@teachers_bp.route('/<int:id>/delete', methods=['POST'])
def delete(id):
    """删除教师"""
    g = _get_globals()
    teachers = g['teachers']
    
    teacher = next((t for t in teachers if t['id'] == id), None)
    if teacher:
        teachers.remove(teacher)
        flash('教师删除成功', 'success')
    else:
        flash('教师不存在', 'error')
    return redirect(url_for('teachers.teachers_list'))
