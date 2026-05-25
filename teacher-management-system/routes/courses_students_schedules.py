from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session
from datetime import datetime
from auth_module import login_required_web

courses_bp = Blueprint('courses', __name__, url_prefix='/courses')
students_bp = Blueprint('students', __name__, url_prefix='/students')
schedules_bp = Blueprint('schedules', __name__, url_prefix='/schedules')

def _get_globals():
    import sys
    app_module = sys.modules.get('app')
    return {
        'courses': getattr(app_module, 'courses', []),
        'classes': getattr(app_module, 'classes', []),
        'teachers': getattr(app_module, 'teachers', []),
        'students': getattr(app_module, 'students', []),
        'schedules': getattr(app_module, 'schedules', []),
        'classrooms': getattr(app_module, 'classrooms', []),
        'teacher_categories': getattr(app_module, 'teacher_categories', []),
    }

# ==================== 课程管理 ====================

@courses_bp.route('/<int:id>')
def detail(id):
    """课程详情"""
    g = _get_globals()
    course = next((c for c in g['courses'] if c.get('id') == id), None)
    if not course:
        flash('课程不存在', 'error')
        return redirect(url_for('courses.list'))
    return render_template('courses/detail.html', course=course)


@courses_bp.route('/new', methods=['GET', 'POST'])
@login_required_web
def new():
    """新增课程"""
    g = _get_globals()
    if request.method == 'POST':
        new_course = {
            'id': len(g['courses']) + 1,
            'name': request.form.get('name'),
            'category_id': int(request.form.get('category_id', 0)),
            'teacher_id': int(request.form.get('teacher_id', 0)) if request.form.get('teacher_id') else None,
            'description': request.form.get('description', ''),
            'status': '进行中',
            'created_at': datetime.now()
        }
        g['courses'].append(new_course)
        flash('课程添加成功', 'success')
        return redirect(url_for('courses.list'))
    return render_template('courses/form.html', course=None, categories=g['teacher_categories'], teachers=g['teachers'])


@courses_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
def edit(id):
    """编辑课程"""
    g = _get_globals()
    course = next((c for c in g['courses'] if c.get('id') == id), None)
    if not course:
        flash('课程不存在', 'error')
        return redirect(url_for('courses.list'))
    if request.method == 'POST':
        course['name'] = request.form.get('name')
        course['category_id'] = int(request.form.get('category_id', 0))
        course['teacher_id'] = int(request.form.get('teacher_id', 0)) if request.form.get('teacher_id') else None
        course['description'] = request.form.get('description', '')
        flash('课程更新成功', 'success')
        return redirect(url_for('courses.detail', id=id))
    return render_template('courses/form.html', course=course, categories=g['teacher_categories'], teachers=g['teachers'])


@courses_bp.route('/<int:id>/delete', methods=['POST'])
def delete(id):
    """删除课程"""
    g = _get_globals()
    course = next((c for c in g['courses'] if c.get('id') == id), None)
    if course:
        g['courses'].remove(course)
        flash('课程删除成功', 'success')
    else:
        flash('课程不存在', 'error')
    return redirect(url_for('courses.list'))


# ==================== 学生管理 ====================

@students_bp.route('/')
def list():
    """学生列表"""
    g = _get_globals()
    return render_template('students/list.html', students=g['students'])


@students_bp.route('/<int:id>')
def student_detail(id):
    """学生详情"""
    g = _get_globals()
    student = next((s for s in g['students'] if s.get('id') == id), None)
    if not student:
        flash('学生不存在', 'error')
        return redirect(url_for('students.list'))
    return render_template('students/detail.html', student=student)


@students_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
def student_edit(id):
    """编辑学生"""
    g = _get_globals()
    student = next((s for s in g['students'] if s.get('id') == id), None)
    if not student:
        flash('学生不存在', 'error')
        return redirect(url_for('students.list'))
    if request.method == 'POST':
        student['name'] = request.form.get('name')
        student['gender'] = request.form.get('gender')
        student['phone'] = request.form.get('phone')
        student['company'] = request.form.get('company')
        student['job'] = request.form.get('job')
        flash('学生更新成功', 'success')
        return redirect(url_for('students.student_detail', id=id))
    return render_template('students/form.html', student=student)


@students_bp.route('/<int:id>/delete', methods=['POST'])
def student_delete(id):
    """删除学生"""
    g = _get_globals()
    student = next((s for s in g['students'] if s.get('id') == id), None)
    if student:
        g['students'].remove(student)
        flash('学生删除成功', 'success')
    else:
        flash('学生不存在', 'error')
    return redirect(url_for('students.list'))


@students_bp.route('/template')
def download_template():
    """下载学生导入模板"""
    from flask import Response
    import csv
    import io
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['姓名', '性别', '手机号', '单位', '职务', '省份'])
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=student_template.csv'}
    )


# ==================== 排课管理 ====================

@schedules_bp.route('/')
def list():
    """排课列表"""
    g = _get_globals()
    return render_template('schedules/list.html', schedules=g['schedules'])


@schedules_bp.route('/<int:id>')
def schedule_detail(id):
    """排课详情"""
    g = _get_globals()
    schedule = next((s for s in g['schedules'] if s.get('id') == id), None)
    if not schedule:
        flash('排课记录不存在', 'error')
        return redirect(url_for('schedules.list'))
    return render_template('schedules/detail.html', schedule=schedule)


@schedules_bp.route('/new', methods=['GET', 'POST'])
@login_required_web
def new():
    """新增排课"""
    g = _get_globals()
    if request.method == 'POST':
        new_schedule = {
            'id': len(g['schedules']) + 1,
            'class_id': int(request.form.get('class_id', 0)),
            'teacher_id': int(request.form.get('teacher_id', 0)) if request.form.get('teacher_id') else None,
            'subject': request.form.get('subject', ''),
            'teaching_date': datetime.strptime(request.form.get('teaching_date'), '%Y-%m-%d').date() if request.form.get('teaching_date') else None,
            'time_slot': request.form.get('time_slot', 'morning'),
            'location': request.form.get('location', ''),
            'status': '待安排',
            'created_at': datetime.now()
        }
        g['schedules'].append(new_schedule)
        flash('排课添加成功', 'success')
        return redirect(url_for('schedules.list'))
    return render_template('schedules/form.html', schedule=None, classes=g['classes'], teachers=g['teachers'])


@schedules_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
def edit(id):
    """编辑排课"""
    g = _get_globals()
    schedule = next((s for s in g['schedules'] if s.get('id') == id), None)
    if not schedule:
        flash('排课记录不存在', 'error')
        return redirect(url_for('schedules.list'))
    if request.method == 'POST':
        schedule['class_id'] = int(request.form.get('class_id', 0))
        schedule['teacher_id'] = int(request.form.get('teacher_id', 0)) if request.form.get('teacher_id') else None
        schedule['subject'] = request.form.get('subject', '')
        schedule['teaching_date'] = datetime.strptime(request.form.get('teaching_date'), '%Y-%m-%d').date() if request.form.get('teaching_date') else None
        schedule['time_slot'] = request.form.get('time_slot', 'morning')
        schedule['location'] = request.form.get('location', '')
        flash('排课更新成功', 'success')
        return redirect(url_for('schedules.schedule_detail', id=id))
    return render_template('schedules/form.html', schedule=schedule, classes=g['classes'], teachers=g['teachers'])


@schedules_bp.route('/<int:id>/delete', methods=['POST'])
def delete(id):
    """删除排课"""
    g = _get_globals()
    schedule = next((s for s in g['schedules'] if s.get('id') == id), None)
    if schedule:
        g['schedules'].remove(schedule)
        flash('排课删除成功', 'success')
    else:
        flash('排课记录不存在', 'error')
    return redirect(url_for('schedules.list'))
