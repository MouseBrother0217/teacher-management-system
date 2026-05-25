from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session
from datetime import datetime, timedelta
from auth_module import login_required_web

classes_bp = Blueprint('classes', __name__, url_prefix='/classes')

# 延迟导入全局变量和辅助函数（避免循环导入）
def _get_globals():
    import sys
    app_module = sys.modules.get('app')
    return {
        'classes': getattr(app_module, 'classes', []),
        'courses': getattr(app_module, 'courses', []),
        'teachers': getattr(app_module, 'teachers', []),
        'students': getattr(app_module, 'students', []),
        'schedules': getattr(app_module, 'schedules', []),
        'classrooms': getattr(app_module, 'classrooms', []),
        'teaching_sites': getattr(app_module, 'teaching_sites', []),
        'teacher_categories': getattr(app_module, 'teacher_categories', []),
        'class_advisors_list': getattr(app_module, 'class_advisors_list', []),
        'class_checklists': getattr(app_module, 'class_checklists', {}),
        'sync_classes_from_db': getattr(app_module, 'sync_classes_from_db', lambda: None),
        'init_class_checklist': getattr(app_module, 'init_class_checklist', lambda x: None),
        'get_checklist_progress': getattr(app_module, 'get_checklist_progress', lambda x: {}),
        'smart_parse_student': getattr(app_module, 'smart_parse_student', None),
    }

# ==================== 班级列表 ====================

@classes_bp.route('/')
def classes_list():
    """班级管理列表 - 从数据库读取"""
    from models import ClassInfo
    
    keyword = request.args.get('keyword', '')
    selected_category = request.args.get('category', '')
    status = request.args.get('status', '')
    
    # 从数据库查询班级
    query = ClassInfo.query
    
    if keyword:
        query = query.filter(ClassInfo.name.contains(keyword))
    if status:
        query = query.filter(ClassInfo.status == status)
    
    # 角色权限：班主任只能看自己负责的班级
    user_role = session.get('role', '')
    user_name = session.get('name', '')
    if user_role == 'class_advisor':
        query = query.filter(ClassInfo.class_teacher == user_name)
        
    # 转换SQLAlchemy对象为字典，兼容模板
    db_classes = query.order_by(ClassInfo.id.desc()).all()
    classes_data = []
    for cls in db_classes:
        classes_data.append({
            'id': cls.id,
            'name': cls.name,
            'category_name': cls.class_type or '其他',
            'project_leader': cls.project_manager or '-',
            'class_advisor': cls.class_teacher or '-',
            'status': cls.status or '进行中',
            'start_date': cls.start_date,
            'end_date': cls.end_date,
            'course_count': 0,
            'student_count': 0,
            'sign_in_rate': None,
            'evaluation_rate': None,
            'target_audience': '党政干部',
            'created_at': cls.created_at
        })
    
    # 构建每个班级的自查进度数据
    g = _get_globals()
    checklist_progress = {}
    for cls in classes_data:
        g['init_class_checklist'](cls['id'])
        progress = g['get_checklist_progress'](cls['id'])
        checklist_progress[cls['id']] = progress
    
    # 同步到内存（确保详情页等能访问）
    import sys
    app_module = sys.modules.get('app')
    if app_module:
        app_module.classes = classes_data
    
    return render_template('classes/list.html',
                         classes=classes_data,
                         categories=g['teacher_categories'],
                         keyword=keyword,
                         selected_category=selected_category,
                         status=status,
                         now=datetime.now(),
                         checklist_progress=checklist_progress)


# ==================== 班级详情 ====================

@classes_bp.route('/<int:id>')
def detail(id):
    """班级详情页"""
    g = _get_globals()
    g['sync_classes_from_db']()
    classes = g['classes']
    schedules = g['schedules']
    students = g['students']
    teaching_sites = g['teaching_sites']
    
    class_obj = next((c for c in classes if c['id'] == id), None)
    
    # 如果内存中没有，从数据库读取
    if not class_obj:
        from models import ClassInfo
        db_class = ClassInfo.query.get(id)
        if db_class:
            class_obj = {
                'id': db_class.id,
                'name': db_class.name,
                'category_name': db_class.class_type or '未分类',
                'status': db_class.status or '未开始',
                'teacher_name': db_class.project_manager or '待定',
                'student_count': 0,
                'sign_in_rate': None,
                'evaluation_rate': None,
                'start_date': db_class.start_date,
                'end_date': db_class.end_date,
                'description': '',
                'category_id': '',
                'class_advisor': db_class.class_teacher or ''
            }
    
    if not class_obj:
        flash('班级不存在', 'error')
        return redirect(url_for('classes.classes_list'))
    
    # 权限检查：班主任只能看自己负责的班级
    user_role = session.get('role', '')
    user_name = session.get('name', '')
    if user_role == 'class_advisor' and class_obj.get('class_advisor') != user_name:
        flash('无权访问：这不是您负责的班级', 'error')
        return redirect(url_for('classes.classes_list'))
    
    # 获取该班级的课表
    class_schedules = [s for s in schedules if s['class_id'] == id]
    # 获取该班级的学员
    class_students = [st for st in students if st.get('class_id') == id]
    
    # 获取标签页参数
    active_tab = request.args.get('tab', 'schedule')
    
    return render_template('classes/detail.html',
                         class_obj=class_obj,
                         active_tab=active_tab,
                         class_schedules=class_schedules,
                         class_students=class_students,
                         sites=teaching_sites)


# ==================== 新增班级 ====================

@classes_bp.route('/new', methods=['GET', 'POST'])
@login_required_web
def new():
    """新增班级 - 支持按天独立配置上课时段"""
    g = _get_globals()
    classes = g['classes']
    
    if request.method == 'POST':
        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')
        
        # 日期逻辑校验
        if start_date_str and end_date_str:
            start = datetime.strptime(start_date_str, '%Y-%m-%d')
            end = datetime.strptime(end_date_str, '%Y-%m-%d')
            if end < start:
                flash('结束日期不能早于开始日期', 'error')
                return render_template('classes/form.html', class_obj=None, categories=g['teacher_categories'], teachers=g['teachers'], sites=g['teaching_sites'], now=datetime.now(), class_advisors=g['class_advisors_list'], current_user_name='管理员')
        
        # 收集每一天的时段选择（slot_YYYY-MM-DD 格式）
        daily_slots = {}
        for key in request.form.keys():
            if key.startswith('slot_'):
                date_str = key[5:]  # 去掉 'slot_' 前缀
                daily_slots[date_str] = request.form.getlist(key)
        
        # 收集所有使用过的时段（去重，用于存储到班级信息）
        all_used_slots = set()
        for slots in daily_slots.values():
            all_used_slots.update(slots)
        
        # 转换集合为列表（避免list内置函数被覆盖的问题）
        time_slots_list = []
        for slot in all_used_slots:
            time_slots_list.append(slot)
        
        new_class = {
            'id': len(classes) + 1,
            'name': request.form.get('name') or '未命名班级',
            'category_id': int(request.form.get('category_id', 0)),
            'category_name': next((c['name'] for c in g['teacher_categories'] if c['id'] == int(request.form.get('category_id', 0))), None),
            'time_slots': sorted(time_slots_list) if time_slots_list else ['morning', 'afternoon'],
            'start_date': datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else None,
            'end_date': datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else None,
            'status': '待开班',
            'project_leader': request.form.get('project_leader', ''),
            'class_advisor': request.form.get('class_advisor', ''),
            'sign_in_rate': 0,
            'evaluation_rate': 0,
            'student_count': 0,
            'created_at': datetime.now()
        }
        classes.append(new_class)
        
        # 同时写入数据库
        try:
            from models import ClassInfo
            db_class = ClassInfo(
                name=new_class['name'],
                class_type=new_class['category_name'] or '其他',
                project_manager=new_class['project_leader'],
                class_teacher=new_class['class_advisor'],
                start_date=new_class['start_date'],
                end_date=new_class['end_date'],
                status='未开始'
            )
            from app import db
            db.session.add(db_class)
            db.session.commit()
            new_class['db_id'] = db_class.id
        except Exception as e:
            from app import db
            db.session.rollback()
            print(f"[WARN] 班级写入数据库失败: {e}")
        
        flash('班级创建成功！请配置日程安排', 'success')
        return redirect(url_for('classes.schedule', id=new_class['id']))
    
    return render_template('classes/form.html', class_obj=None, categories=g['teacher_categories'], teachers=g['teachers'], sites=g['teaching_sites'], now=datetime.now(), class_advisors=g['class_advisors_list'], current_user_name='管理员')


# ==================== 编辑班级 ====================

@classes_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
def edit(id):
    """编辑班级"""
    g = _get_globals()
    g['sync_classes_from_db']()
    classes = g['classes']
    
    class_obj = next((c for c in classes if c['id'] == id), None)
    if not class_obj:
        flash('班级不存在', 'error')
        return redirect(url_for('classes.classes_list'))
    
    # 权限检查
    user_role = session.get('role', '')
    user_name = session.get('name', '')
    if user_role == 'class_advisor' and class_obj.get('class_advisor') != user_name:
        flash('无权编辑：这不是您负责的班级', 'error')
        return redirect(url_for('classes.classes_list'))
    
    if request.method == 'POST':
        # 日期逻辑校验
        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')
        if start_date_str and end_date_str:
            start = datetime.strptime(start_date_str, '%Y-%m-%d')
            end = datetime.strptime(end_date_str, '%Y-%m-%d')
            if end < start:
                flash('结束日期不能早于开始日期', 'error')
                return render_template('classes/form.html', class_obj=class_obj, categories=g['teacher_categories'], teachers=g['teachers'], sites=g['teaching_sites'], schedules=g['schedules'], students=g['students'], now=datetime.now(), class_advisors=g['class_advisors_list'], current_user_name='管理员')
        
        class_obj['name'] = request.form.get('name') or class_obj.get('name', '')
        class_obj['category_id'] = int(request.form.get('category_id', 0))
        class_obj['category_name'] = next((c['name'] for c in g['teacher_categories'] if c['id'] == int(request.form.get('category_id', 0))), None)
        class_obj['time_slots'] = request.form.getlist('time_slots') or ['morning', 'afternoon']
        class_obj['start_date'] = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date() if request.form.get('start_date') else class_obj.get('start_date')
        class_obj['end_date'] = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d').date() if request.form.get('end_date') else class_obj.get('end_date')
        class_obj['project_leader'] = request.form.get('project_leader', '') or class_obj.get('project_leader', '')
        class_obj['class_advisor'] = request.form.get('class_advisor', '') or class_obj.get('class_advisor', '')
        
        # 同步更新数据库
        try:
            from models import ClassInfo
            db_id = class_obj.get('db_id')
            db_class = ClassInfo.query.get(db_id) if db_id else None
            if db_class:
                db_class.name = class_obj['name']
                db_class.class_type = class_obj['category_name'] or '其他'
                db_class.project_manager = class_obj['project_leader']
                db_class.class_teacher = class_obj['class_advisor']
                db_class.start_date = class_obj['start_date']
                db_class.end_date = class_obj['end_date']
                from app import db
                db.session.commit()
            else:
                db_class = ClassInfo(
                    name=class_obj['name'],
                    class_type=class_obj['category_name'] or '其他',
                    project_manager=class_obj['project_leader'],
                    class_teacher=class_obj['class_advisor'],
                    start_date=class_obj['start_date'],
                    end_date=class_obj['end_date'],
                    status='未开始'
                )
                from app import db
                db.session.add(db_class)
                db.session.commit()
                class_obj['db_id'] = db_class.id
        except Exception as e:
            from app import db
            db.session.rollback()
            print(f"[WARN] 班级更新数据库失败: {e}")
        
        flash('班级更新成功', 'success')
        
        # 如果请求来自保存并进入自查清单按钮
        if request.form.get('form_action') == 'save_and_checklist':
            g['init_class_checklist'](id)
            return redirect(url_for('classes.checklist', id=id))
        
        # 如果请求来自确认完成按钮
        if request.form.get('form_action') == 'confirm_complete':
            class_obj['status'] = '已确认'
            try:
                from models import ClassInfo
                db_id = class_obj.get('db_id')
                db_class = ClassInfo.query.get(db_id) if db_id else None
                if db_class:
                    db_class.status = '已完成'
                    from app import db
                    db.session.commit()
            except Exception as e:
                from app import db
                db.session.rollback()
                print(f"[WARN] 确认完成时更新数据库失败: {e}")
            flash('班级已确认完成！', 'success')
            return redirect(url_for('classes.classes_list'))
        
        return redirect(url_for('classes.edit', id=id))
    
    return render_template('classes/form.html', class_obj=class_obj, categories=g['teacher_categories'], teachers=g['teachers'], sites=g['teaching_sites'], schedules=g['schedules'], students=g['students'], now=datetime.now(), class_advisors=g['class_advisors_list'], current_user_name='管理员')


# ==================== 删除班级 ====================

@classes_bp.route('/<int:id>/delete', methods=['POST'])
def delete(id):
    """删除班级"""
    g = _get_globals()
    g['sync_classes_from_db']()
    classes = g['classes']
    
    class_obj = next((c for c in classes if c['id'] == id), None)
    if class_obj:
        classes.remove(class_obj)
        flash('班级删除成功', 'success')
    else:
        flash('班级不存在', 'error')
    return redirect(url_for('classes.classes_list'))


# ==================== 生成课表 ====================

@classes_bp.route('/<int:id>/generate-schedule', methods=['POST'])
def generate_schedule(id):
    """生成课表 - 将班级状态变更为进行中"""
    g = _get_globals()
    g['sync_classes_from_db']()
    classes = g['classes']
    schedules = g['schedules']
    teaching_sites = g['teaching_sites']
    
    class_obj = next((c for c in classes if c['id'] == id), None)
    if not class_obj:
        flash('班级不存在', 'error')
        return redirect(url_for('classes.classes_list'))
    
    # 检查是否还有未安排的课程（现场教学不需要老师）
    site_names = [s['name'] for s in teaching_sites]
    class_schedules = [s for s in schedules if s['class_id'] == id]
    pending = []
    for s in class_schedules:
        is_site = s.get('location') and s['location'] in site_names
        if not s.get('teacher_id') and not is_site:
            pending.append(s)
    
    if pending:
        flash(f'还有 {len(pending)} 节课程未安排老师或课程，请完善后再生成课表', 'warning')
        return redirect(url_for('classes.schedule', id=id))
    
    # 更新班级状态为进行中
    class_obj['status'] = '进行中'
    flash('课表生成成功！班级已变更为"进行中"状态。', 'success')
    return redirect(url_for('classes.edit', id=id))


# ==================== 日程安排 ====================

@classes_bp.route('/<int:id>/schedule', methods=['GET', 'POST'])
def schedule(id):
    """班级日程安排页面 - 勾选时段生成课表"""
    g = _get_globals()
    g['sync_classes_from_db']()
    classes = g['classes']
    schedules = g['schedules']
    
    class_obj = next((c for c in classes if c['id'] == id), None)
    if not class_obj:
        flash('班级不存在', 'error')
        return redirect(url_for('classes.classes_list'))
    
    # 时段配置
    slot_config = {
        'morning': {'name': '上午', 'start': '08:30', 'end': '12:00'},
        'afternoon': {'name': '下午', 'start': '14:00', 'end': '17:30'},
        'fullday': {'name': '全天', 'start': '08:30', 'end': '17:30'},
        'evening': {'name': '晚上', 'start': '18:30', 'end': '21:00'}
    }
    
    if request.method == 'POST':
        # 收集每一天的时段选择
        daily_slots = {}
        for key in request.form.keys():
            if key.startswith('slot_'):
                date_str = key[5:]
                daily_slots[date_str] = request.form.getlist(key)
        
        # 收集所有使用过的时段
        all_used_slots = set()
        for slots in daily_slots.values():
            all_used_slots.update(slots)
        
        # 转换集合为列表（避免list内置函数被覆盖的问题）
        time_slots_list = []
        for slot in all_used_slots:
            time_slots_list.append(slot)
        
        # 更新班级的时段信息
        class_obj['time_slots'] = sorted(time_slots_list) if time_slots_list else class_obj.get('time_slots', ['morning', 'afternoon'])
        
        # 清除该班级现有的课表记录
        import sys
        app_module = sys.modules.get('app')
        if app_module:
            app_module.schedules = [s for s in schedules if s['class_id'] != id]
            schedules = app_module.schedules
        
        # 根据选择生成新的课表记录
        schedule_count = 0
        for date_str, slots in daily_slots.items():
            current_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            for slot in slots:
                if slot in slot_config:
                    config = slot_config[slot]
                    new_schedule = {
                        'id': len(schedules) + 1,
                        'class_id': id,
                        'class_name': class_obj['name'],
                        'teacher_id': None,
                        'teacher_name': None,
                        'subject': None,
                        'teaching_date': current_date,
                        'time_slot': slot,
                        'time_slot_name': config['name'],
                        'start_time': config['start'],
                        'end_time': config['end'],
                        'location': None,
                        'compensation': None,
                        'status': '待安排',
                        'courseware': None
                    }
                    schedules.append(new_schedule)
                    schedule_count += 1
        
        if schedule_count > 0:
            flash(f'已生成 {schedule_count} 个课时段，请点击"安排"按钮配置老师和课程', 'success')
        else:
            flash('未选择任何时段', 'warning')
        
        return redirect(url_for('classes.schedule', id=id))
    
    # 获取已生成的课表
    class_schedules = [s for s in schedules if s['class_id'] == id]
    
    # 按日期组织课表
    schedules_by_date = {}
    for s in class_schedules:
        date_key = s['teaching_date'].strftime('%Y-%m-%d') if s['teaching_date'] else '未安排'
        if date_key not in schedules_by_date:
            schedules_by_date[date_key] = {}
        schedules_by_date[date_key][s['time_slot']] = s
    
    # 生成日期范围列表
    date_range = []
    if class_obj.get('start_date') and class_obj.get('end_date'):
        start = class_obj['start_date']
        end = class_obj['end_date']
        current = start
        while current <= end:
            date_range.append(current.strftime('%Y-%m-%d'))
            current += timedelta(days=1)
    
    return render_template('classes/schedule.html',
                         class_obj=class_obj,
                         slot_config=slot_config,
                         schedules_by_date=schedules_by_date,
                         date_range=date_range,
                         class_schedules=class_schedules)


# ==================== 导入学员 ====================

@classes_bp.route('/<int:id>/import-students', methods=['GET', 'POST'])
def import_students(id):
    """导入学员到班级"""
    g = _get_globals()
    classes = g['classes']
    students = g['students']
    
    class_obj = next((c for c in classes if c['id'] == id), None)
    if not class_obj:
        flash('班级不存在', 'error')
        return redirect(url_for('classes.classes_list'))
    
    if request.method == 'POST':
        # 检查是否是Excel文件上传
        if 'excel_file' in request.files:
            file = request.files['excel_file']
            if file and file.filename and file.filename.endswith(('.xlsx', '.xls')):
                # Excel导入逻辑暂简化为提示
                flash('Excel导入功能已触发', 'info')
                return redirect(url_for('classes.import_students', id=id))
        
        # 批量粘贴导入（智能识别）
        batch_data = request.form.get('batch_data', '').strip()
        if not batch_data:
            flash('请输入学员数据', 'warning')
            return redirect(url_for('classes.import_students', id=id))
        
        added = 0
        errors = []
        lines = [l.strip() for l in batch_data.split('\n')]
        
        # 检测按空行分块
        blank_line_indices = [i for i, l in enumerate(lines) if not l]
        if blank_line_indices and len(blank_line_indices) >= 1:
            chunks = []
            current = []
            for l in lines:
                if l:
                    current.append(l)
                else:
                    if current:
                        chunks.append(', '.join(current))
                        current = []
            if current:
                chunks.append(', '.join(current))
        else:
            chunks = [l for l in lines if l]
        
        smart_parse = g.get('smart_parse_student')
        import re
        
        for idx, chunk in enumerate(chunks):
            if smart_parse:
                parsed = smart_parse(chunk)
            else:
                # 简化解析
                parsed = {'name': chunk, 'gender': '', 'id_type': '身份证', 'id_card': '', 'phone': '', 'company': '', 'job': '', 'province': ''}
            
            if not parsed or not parsed.get('name'):
                errors.append(f"第{idx+1}行: 无法解析")
                continue
            
            # 验证必填字段
            missing = []
            if not parsed.get('name'):
                missing.append('姓名')
            if not parsed.get('gender'):
                missing.append('性别')
            if not parsed.get('id_card'):
                missing.append('证件号码')
            if not parsed.get('phone'):
                missing.append('手机号')
            if not parsed.get('company'):
                missing.append('单位')
            if not parsed.get('job'):
                missing.append('职务')
            
            if missing:
                errors.append(f"第{idx+1}行 ({parsed.get('name', '未知')}): 缺少 {', '.join(missing)}")
                continue
            
            student = {
                'id': len(students) + 1,
                'name': parsed['name'],
                'gender': parsed['gender'],
                'id_type': parsed.get('id_type', '身份证'),
                'id_card': parsed.get('id_card', ''),
                'phone': parsed.get('phone', ''),
                'company': parsed.get('company', ''),
                'job': parsed.get('job', ''),
                'province': parsed.get('province', ''),
                'class_id': id,
                'city': '',
                'total_attendance': 0,
                'attendance_count': 0
            }
            students.append(student)
            added += 1
        
        if errors:
            flash(f'成功导入 {added} 名学员，{len(errors)} 行有误', 'success' if added > 0 else 'warning')
            for e in errors[:5]:
                flash(e, 'error')
        else:
            flash(f'成功导入 {added} 名学员', 'success')
        
        return redirect(url_for('classes.edit', id=id))
    
    # GET: 显示导入页面
    class_students = [st for st in students if st.get('class_id') == id]
    return render_template('students/import.html',
                         class_obj=class_obj,
                         class_students=class_students)


# ==================== 自查清单 ====================

@classes_bp.route('/<int:id>/checklist', methods=['GET', 'POST'])
def checklist(id):
    """班级开班前自查清单"""
    g = _get_globals()
    g['sync_classes_from_db']()
    classes = g['classes']
    class_checklists = g['class_checklists']
    
    class_obj = next((c for c in classes if c['id'] == id), None)
    
    # 如果内存中没有，从数据库读取
    if not class_obj:
        from models import ClassInfo
        db_class = ClassInfo.query.get(id)
        if db_class:
            class_obj = {
                'id': db_class.id,
                'name': db_class.name,
                'category_name': db_class.class_type or '未分类',
                'status': db_class.status or '未开始',
                'teacher_name': db_class.project_manager or '待定',
                'student_count': 0,
                'sign_in_rate': None,
                'evaluation_rate': None,
                'start_date': db_class.start_date,
                'end_date': db_class.end_date,
                'description': '',
                'category_id': '',
                'class_advisor': db_class.class_teacher or ''
            }
    
    if not class_obj:
        flash('班级不存在', 'error')
        return redirect(url_for('classes.classes_list'))
    
    # 初始化清单
    g['init_class_checklist'](id)
    checklist = class_checklists.get(id, [])
    
    if request.method == 'POST':
        # 更新清单状态
        for item in checklist:
            item_id = str(item['id'])
            if f'item_{item_id}' in request.form:
                item['checked'] = request.form.get(f'item_{item_id}') == 'on'
                item['updated_at'] = datetime.now()
        
        flash('自查清单已更新', 'success')
        return redirect(url_for('classes.checklist', id=id))
    
    return render_template('classes/checklist.html',
                         class_obj=class_obj,
                         checklist=checklist)


@classes_bp.route('/<int:id>/checklist/progress')
def checklist_progress(id):
    """获取自查清单进度（AJAX）"""
    g = _get_globals()
    g['init_class_checklist'](id)
    progress = g['get_checklist_progress'](id)
    return jsonify({
        'success': True,
        'progress': progress
    })

