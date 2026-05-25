"""
师资管理系统 - Flask应用主文件
基于来同学社功能模块1:1复刻
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from datetime import datetime, timedelta
import calendar
import os
import sys
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'

# 加载真实学员评价数据
def load_real_evaluations():
    """加载真实学员评价数据从real_evaluations.py"""
    try:
        eval_file = os.path.join(os.path.dirname(__file__), 'data', 'real_evaluations.py')
        with open(eval_file, 'r', encoding='utf-8') as f:
            content = f.read()
            # 找到teacher_evaluations_map JSON
            import re
            match = re.search(r'teacher_evaluations_map = ({.*?})\n\n# 点赞', content, re.DOTALL)
            if match:
                evals_json = match.group(1)
                evaluations_map = json.loads(evals_json)
                # 转换日期字符串为datetime对象
                for name, evals in evaluations_map.items():
                    for e in evals:
                        if isinstance(e.get('created_at'), str):
                            try:
                                e['created_at'] = datetime.strptime(e['created_at'], '%Y-%m-%d %H:%M:%S')
                            except:
                                e['created_at'] = datetime.now()
            else:
                evaluations_map = {}
            
            # 找到teacher_likes_map JSON
            match2 = re.search(r'teacher_likes_map = ({.*?})$', content, re.DOTALL)
            if match2:
                likes_json = match2.group(1)
                likes_map = json.loads(likes_json)
            else:
                likes_map = {}
            
            return evaluations_map, likes_map
    except Exception as e:
        print(f"加载真实评价数据失败: {e}")
        return {}, {}

# 全局真实评价数据
teacher_evaluations_map, teacher_likes_map = load_real_evaluations()
print(f"✅ 已加载 {len(teacher_evaluations_map)} 位教师的真实评价数据")

# 加载导入的真实数据
try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'data'))
    # 优先加载完整数据文件
    try:
        from teachers_full import teachers, teacher_map, teacher_name_map
        # 数据集成：同时加载课表/评价/课程/班级数据
        from imported_teachers import schedules as imported_schedules, evaluations as imported_evaluations
        from imported_courses_classes import courses as imported_courses, classes as imported_classes
        DATA_SOURCE = 'full'  # 完整数据含上课记录、点赞、评价
        print(f"✅ 已加载完整数据文件 (teachers_full.py)")
        print(f"✅ 数据集成完成 - 课表: {len(imported_schedules)}条, 评价: {len(imported_evaluations)}条")
        print(f"✅ 数据集成完成 - 课程: {len(imported_courses)}门, 班级: {len(imported_classes)}个")
    except ImportError as e2:
        print(f"⚠️ 数据集成部分失败: {e2}, 回退到基础导入")
        from imported_teachers import teachers, schedules as imported_schedules, evaluations as imported_evaluations
        from imported_courses_classes import courses as imported_courses, classes as imported_classes
        DATA_SOURCE = 'imported'  # 1905条真实数据
    
    # 转换日期字符串为datetime对象
    def parse_date_str(dt_str):
        if not dt_str:
            return None
        if isinstance(dt_str, datetime):
            return dt_str
        try:
            return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        except:
            try:
                return datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
            except:
                try:
                    return datetime.strptime(dt_str, '%Y-%m-%d')
                except:
                    return None
    
    # 转换教师数据中的日期，并修复ID为0的问题
    next_id = 1
    for t in teachers:
        if t.get('created_at') and isinstance(t['created_at'], str):
            t['created_at'] = parse_date_str(t['created_at'])
        # 修复ID为0的问题：重新分配唯一ID
        if not t.get('id') or t.get('id') == 0:
            t['id'] = next_id
        next_id = max(next_id, t.get('id', 0)) + 1
    
    # 转换课表数据中的日期
    for s in imported_schedules:
        if s.get('teaching_date') and isinstance(s['teaching_date'], str):
            s['teaching_date'] = parse_date_str(s['teaching_date'])
        if s.get('created_at') and isinstance(s['created_at'], str):
            s['created_at'] = parse_date_str(s['created_at'])
    
    # 转换评价数据中的日期
    for e in imported_evaluations:
        if e.get('created_at') and isinstance(e['created_at'], str):
            e['created_at'] = parse_date_str(e['created_at'])
    
    # 转换班级数据中的日期
    for c in imported_classes:
        if c.get('created_at') and isinstance(c['created_at'], str):
            c['created_at'] = parse_date_str(c['created_at'])
        if c.get('start_date') and isinstance(c['start_date'], str):
            c['start_date'] = parse_date_str(c['start_date'])
        if c.get('end_date') and isinstance(c['end_date'], str):
            c['end_date'] = parse_date_str(c['end_date'])
    
    print(f"✅ 已加载真实数据:")
    print(f"  - 教师: {len(teachers)}位")
    print(f"  - 上课记录: {len(imported_schedules)}条")
    print(f"  - 评价: {len(imported_evaluations)}条")
    print(f"  - 课程: {len(imported_courses)}门")
    print(f"  - 班级: {len(imported_classes)}个")
    
    # ID修复后，重新构建 teacher_map 和 teacher_name_map
    teacher_map = {t['id']: t for t in teachers}
    teacher_name_map = {t['name']: t for t in teachers}
    print(f"  - 已重建索引: {len(teacher_map)}个唯一ID")
    
    # 初始化老师的擅长课程字段（如果没有）
    for t in teachers:
        if 'courses' not in t:
            t['courses'] = []  # 默认为空列表，后续可通过老师编辑页面添加
except ImportError as e:
    print(f"⚠️ 无法加载导入的数据: {e}, 使用模拟数据")
    teachers = []
    imported_schedules = []
    imported_evaluations = []
    imported_courses = []
    imported_classes = []
    DATA_SOURCE = 'mock'

# 模拟数据存储（实际项目中使用数据库）
teacher_categories = [
    {'id': 1, 'name': '管理类', 'parent_id': None, 'parent_name': None, 'description': '企业管理、领导力培训', 'creator': '管理员', 'created_at': datetime(2026, 4, 1)},
    {'id': 2, 'name': '技术类', 'parent_id': None, 'parent_name': None, 'description': 'IT技术、编程开发', 'creator': '管理员', 'created_at': datetime(2026, 4, 2)},
    {'id': 3, 'name': '金融类', 'parent_id': None, 'parent_name': None, 'description': '金融投资、财务管理', 'creator': '管理员', 'created_at': datetime(2026, 4, 3)},
    {'id': 4, 'name': '财税系统', 'parent_id': None, 'parent_name': None, 'description': '税务稽查、财务管理', 'creator': '管理员', 'created_at': datetime(2026, 4, 4)},
    {'id': 5, 'name': '经济学', 'parent_id': None, 'parent_name': None, 'description': '宏观经济、产业经济', 'creator': '管理员', 'created_at': datetime(2026, 4, 5)},
    {'id': 6, 'name': '法律法规', 'parent_id': None, 'parent_name': None, 'description': '法律知识、合规管理', 'creator': '管理员', 'created_at': datetime(2026, 4, 6)},
]

# 使用导入的真实师资数据（如果导入失败则保持为空列表）
if DATA_SOURCE == 'mock':
    # 仅在无法加载导入数据时使用最小模拟数据
    teachers = [
        {
            'id': 1,
            'name': '张老师',
            'phone': '13800138001',
            'email': 'zhang@example.com',
            'avatar_url': 'https://api.dicebear.com/7.x/avataaars/svg?seed=1',
            'gender': '男',
            'title': '高级讲师',
            'organization': '浙江大学',
            'education': '博士',
            'major': '管理学',
            'specialty': '企业管理、领导力、团队建设',
            'introduction': '拥有10年企业培训经验，服务过华为、阿里等知名企业',
            'status': '已入库',
            'evaluation_score': 9.8,
            'creator': '管理员',
            'created_at': datetime(2026, 1, 15)
        },
    ]
    imported_schedules = []
    imported_evaluations = []

# 根据数据加载方式设置变量
schedules = imported_schedules
evaluations_data = imported_evaluations

# 设置课程和班级数据（从导入文件加载）
if DATA_SOURCE in ('imported', 'full'):
    courses = imported_courses
    classes = imported_classes
    # 确保日期字段存在
    for c in classes:
        if not c.get('created_at'):
            c['created_at'] = datetime(2026, 1, 1)
        if not c.get('category_id'):
            cat_name = c.get('category_name', '其他')
            cat = next((cat for cat in teacher_categories if cat['name'] == cat_name), None)
            c['category_id'] = cat['id'] if cat else 1
    for c in courses:
        if not c.get('created_at'):
            c['created_at'] = datetime(2026, 1, 1)
        if not c.get('category_id'):
            c['category_id'] = 1
else:
    # 如果导入失败，使用空列表
    courses = []
    classes = []

students = []

classrooms = [
    {
        'id': 1,
        'name': 'A101多媒体教室',
        'capacity': 50,
        'type': '多媒体教室',
        'campus': '主校区',
        'address': '教学楼A栋1层',
        'price': 500.00,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 2,
        'name': 'B201会议室',
        'capacity': 30,
        'type': '会议室',
        'campus': '分校区',
        'address': '行政楼2层',
        'price': 300.00,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 3,
        'name': '阶梯报告厅',
        'capacity': 200,
        'type': '报告厅',
        'campus': '主校区',
        'address': '图书馆1层',
        'price': 1000.00,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 4,
        'name': 'C301实验室',
        'capacity': 40,
        'type': '实验室',
        'campus': '主校区',
        'address': '实验楼3层',
        'price': 600.00,
        'status': '占用',
        'created_at': datetime(2026, 2, 1)
    }
]

teaching_sites = [
    {
        'id': 1,
        'name': '阿里巴巴集团总部',
        'type': '企业参访',
        'supplier': '阿里培训部',
        'contact_name': '陈经理',
        'contact_phone': '13900139001',
        'price': 5000.00,
        'address': '杭州市余杭区文一西路969号',
        'audit_status': '已通过',
        'created_at': datetime(2026, 1, 15)
    },
    {
        'id': 2,
        'name': '华为深圳研究所',
        'type': '技术考察',
        'supplier': '华为大学',
        'contact_name': '刘经理',
        'contact_phone': '13900139002',
        'price': 8000.00,
        'address': '深圳市龙岗区坂田华为基地',
        'audit_status': '已通过',
        'created_at': datetime(2026, 2, 10)
    },
    {
        'id': 3,
        'name': '中共一大会址',
        'type': '红色教育',
        'supplier': '上海红色教育中心',
        'contact_name': '周主任',
        'contact_phone': '13900139003',
        'price': 2000.00,
        'address': '上海市黄浦区黄陂南路374号',
        'audit_status': '已通过',
        'created_at': datetime(2026, 3, 1)
    },
    {
        'id': 4,
        'name': '腾讯滨海大厦',
        'type': '企业参访',
        'supplier': '腾讯学院',
        'contact_name': '吴经理',
        'contact_phone': '13900139004',
        'price': 6000.00,
        'address': '深圳市南山区海天二路33号',
        'audit_status': '待审核',
        'created_at': datetime(2026, 4, 10)
    }
]

# 注意：classes/courses变量在文件开头根据数据加载方式设置
# 如果使用导入数据，变量将指向 imported_courses 和 imported_classes

compensations = [
    {
        'id': 1,
        'teacher_id': 1,
        'teacher_name': '张老师',
        'class_id': 1,
        'class_name': '企业领导力提升研修班',
        'schedule_id': 1,
        'subject': '领导力基础理论',
        'teaching_date': datetime(2026, 4, 17),
        'amount': 2000.00,
        'status': '待审批',
        'requester_name': '管理员',
        'approver_name': None,
        'approved_at': None,
        'created_at': datetime(2026, 4, 17)
    },
    {
        'id': 2,
        'teacher_id': 1,
        'teacher_name': '张老师',
        'class_id': 1,
        'class_name': '企业领导力提升研修班',
        'schedule_id': 3,
        'subject': '组织行为学导论',
        'teaching_date': datetime(2026, 4, 16),
        'amount': 2000.00,
        'status': '已通过',
        'requester_name': '管理员',
        'approver_name': '审批人',
        'approved_at': datetime(2026, 4, 16),
        'created_at': datetime(2026, 4, 16)
    },
    {
        'id': 3,
        'teacher_id': 4,
        'teacher_name': '刘老师',
        'class_id': 1,
        'class_name': '企业领导力提升研修班',
        'schedule_id': 3,
        'subject': '组织行为学导论',
        'teaching_date': datetime(2026, 4, 16),
        'amount': 1500.00,
        'status': '已发放',
        'requester_name': '管理员',
        'approver_name': '审批人',
        'approved_at': datetime(2026, 4, 16),
        'created_at': datetime(2026, 4, 15)
    }
]


# ==================== 首页仪表盘 ====================
@app.route('/')
def index():
    """首页仪表盘 - 截图风格"""
    # 统计数据 - 待办事项
    stats = {
        'today_todo': 3,
        'compensation_pending': len([c for c in compensations if c['status'] == '待审批']),
        'teacher_pending': len([t for t in teachers if t.get('status') == '待审核']),
        'site_pending': len([s for s in teaching_sites if s.get('audit_status') == '待审核']),
    }
    
    # 今日课表
    today = datetime.now()
    today_schedules = [s for s in schedules if s['teaching_date'].date() == today.date()]
    
    # 日历数据
    current_month = today.strftime('%Y年%m月')
    cal = calendar.Calendar()
    calendar_days = []
    
    for week in cal.monthdayscalendar(today.year, today.month):
        for day in week:
            if day != 0:
                day_date = datetime(today.year, today.month, day)
                has_event = any(s['teaching_date'].date() == day_date.date() for s in schedules)
                calendar_days.append({
                    'date': day,
                    'is_today': day == today.day,
                    'has_event': has_event
                })
    
    return render_template('index.html',
                         today=today.strftime('%Y年%m月%d日'),
                         total_classes=len(classes),
                         stats=stats,
                         today_schedules=today_schedules,
                         current_month=current_month,
                         calendar_days=calendar_days)


# ==================== 班级分类 ====================
@app.route('/categories')
def categories_list():
    """班级分类列表"""
    keyword = request.args.get('keyword', '')
    parent_id = request.args.get('parent_id', '')
    
    filtered_categories = teacher_categories
    if keyword:
        filtered_categories = [c for c in filtered_categories if keyword in c['name']]
    if parent_id:
        filtered_categories = [c for c in filtered_categories if str(c['parent_id']) == parent_id]
    
    return render_template('categories/list.html',
                         categories=filtered_categories,
                         all_categories=teacher_categories,
                         keyword=keyword,
                         parent_id=parent_id)


@app.route('/categories/new', methods=['GET', 'POST'])
def category_new():
    """新增分类"""
    if request.method == 'POST':
        parent_id = int(request.form.get('parent_id', 0)) if request.form.get('parent_id') else None
        new_category = {
            'id': len(teacher_categories) + 1,
            'name': request.form.get('name'),
            'parent_id': parent_id,
            'parent_name': next((c['name'] for c in teacher_categories if c['id'] == parent_id), None) if parent_id else None,
            'description': request.form.get('description'),
            'creator': '管理员',
            'created_at': datetime.now()
        }
        teacher_categories.append(new_category)
        flash('分类添加成功', 'success')
        return redirect(url_for('categories_list'))
    return render_template('categories/form.html', all_categories=teacher_categories)


@app.route('/categories/<int:id>/edit', methods=['GET', 'POST'])
def category_edit(id):
    """编辑分类"""
    category = next((c for c in teacher_categories if c['id'] == id), None)
    if not category:
        flash('分类不存在', 'error')
        return redirect(url_for('categories_list'))
    if request.method == 'POST':
        parent_id = int(request.form.get('parent_id', 0)) if request.form.get('parent_id') else None
        category['name'] = request.form.get('name')
        category['parent_id'] = parent_id
        category['parent_name'] = next((c['name'] for c in teacher_categories if c['id'] == parent_id), None) if parent_id else None
        category['description'] = request.form.get('description')
        flash('分类更新成功', 'success')
        return redirect(url_for('categories_list'))
    return render_template('categories/form.html', category=category, all_categories=teacher_categories)


@app.route('/categories/<int:id>/delete', methods=['POST'])
def category_delete(id):
    """删除分类"""
    category = next((c for c in teacher_categories if c['id'] == id), None)
    if category:
        # 检查是否有子分类
        has_children = any(c.get('parent_id') == id for c in teacher_categories)
        if has_children:
            flash('该分类下有子分类，不能删除', 'error')
            return redirect(url_for('categories_list'))
        # 检查是否有班级使用该分类
        used_in_class = any(c.get('category_id') == id for c in classes)
        if used_in_class:
            flash('该分类已被班级使用，不能删除', 'error')
            return redirect(url_for('categories_list'))
        teacher_categories.remove(category)
        flash('分类删除成功', 'success')
    else:
        flash('分类不存在', 'error')
    return redirect(url_for('categories_list'))


# ==================== 教室管理 ====================
@app.route('/classrooms')
def classrooms_list():
    """教室管理列表"""
    keyword = request.args.get('keyword', '')
    room_type = request.args.get('type', '')
    campus = request.args.get('campus', '')
    
    filtered_rooms = classrooms
    if keyword:
        filtered_rooms = [r for r in filtered_rooms if keyword in r['name']]
    if room_type:
        filtered_rooms = [r for r in filtered_rooms if r['type'] == room_type]
    if campus:
        filtered_rooms = [r for r in filtered_rooms if r['campus'] == campus]
    
    return render_template('classrooms/list.html',
                         classrooms=filtered_rooms,
                         keyword=keyword,
                         room_type=room_type,
                         campus=campus)


@app.route('/classrooms/<int:id>')
def classroom_detail(id):
    """教室详情页"""
    classroom = next((r for r in classrooms if r['id'] == id), None)
    if not classroom:
        flash('教室不存在', 'error')
        return redirect(url_for('classrooms_list'))
    
    # 获取该教室的使用记录
    usage_records = [s for s in schedules if s.get('classroom_id') == id]
    
    return render_template('classrooms/detail.html',
                         classroom=classroom,
                         usage_records=usage_records)


@app.route('/classrooms/new', methods=['GET', 'POST'])
def classroom_new():
    """新增教室"""
    if request.method == 'POST':
        new_room = {
            'id': len(classrooms) + 1,
            'name': request.form.get('name'),
            'type': request.form.get('type'),
            'campus': request.form.get('campus'),
            'capacity': int(request.form.get('capacity', 0)) if request.form.get('capacity') else None,
            'price': float(request.form.get('price', 0)) if request.form.get('price') else None,
            'address': request.form.get('address'),
            'description': request.form.get('description'),
            'status': request.form.get('status', '可用'),
            'created_at': datetime.now()
        }
        classrooms.append(new_room)
        flash('教室添加成功', 'success')
        return redirect(url_for('classrooms_list'))
    return render_template('classrooms/form.html')


@app.route('/classrooms/<int:id>/edit', methods=['GET', 'POST'])
def classroom_edit(id):
    """编辑教室"""
    classroom = next((r for r in classrooms if r['id'] == id), None)
    if not classroom:
        flash('教室不存在', 'error')
        return redirect(url_for('classrooms_list'))
    if request.method == 'POST':
        classroom['name'] = request.form.get('name')
        classroom['type'] = request.form.get('type')
        classroom['campus'] = request.form.get('campus')
        classroom['capacity'] = int(request.form.get('capacity', 0)) if request.form.get('capacity') else None
        classroom['price'] = float(request.form.get('price', 0)) if request.form.get('price') else None
        classroom['address'] = request.form.get('address')
        classroom['description'] = request.form.get('description')
        classroom['status'] = request.form.get('status')
        flash('教室更新成功', 'success')
        return redirect(url_for('classroom_detail', id=id))
    return render_template('classrooms/form.html', classroom=classroom)


@app.route('/classrooms/<int:id>/delete', methods=['POST'])
def classroom_delete(id):
    """删除教室"""
    classroom = next((r for r in classrooms if r['id'] == id), None)
    if classroom:
        # 检查是否有课表使用该教室
        used_in_schedule = any(s.get('classroom_id') == id for s in schedules)
        if used_in_schedule:
            flash('该教室已被课表使用，不能删除', 'error')
            return redirect(url_for('classrooms_list'))
        classrooms.remove(classroom)
        flash('教室删除成功', 'success')
    else:
        flash('教室不存在', 'error')
    return redirect(url_for('classrooms_list'))


# ==================== 现场教学 ====================
@app.route('/sites')
def sites_list():
    """现场教学点列表"""
    keyword = request.args.get('keyword', '')
    site_type = request.args.get('type', '')
    supplier = request.args.get('supplier', '')
    audit_status = request.args.get('audit_status', '')
    
    filtered_sites = teaching_sites
    if keyword:
        filtered_sites = [s for s in filtered_sites if keyword in s['name']]
    if site_type:
        filtered_sites = [s for s in filtered_sites if s['type'] == site_type]
    if supplier:
        filtered_sites = [s for s in filtered_sites if s['supplier'] == supplier]
    if audit_status:
        filtered_sites = [s for s in filtered_sites if s['audit_status'] == audit_status]
    
    return render_template('sites/list.html',
                         sites=filtered_sites,
                         keyword=keyword,
                         site_type=site_type,
                         supplier=supplier,
                         audit_status=audit_status)


@app.route('/sites/<int:id>')
def site_detail(id):
    """现场教学点详情页"""
    site = next((s for s in teaching_sites if s['id'] == id), None)
    if not site:
        flash('现场教学点不存在', 'error')
        return redirect(url_for('sites_list'))
    return render_template('sites/detail.html', site=site)


@app.route('/sites/new', methods=['GET', 'POST'])
def site_new():
    """新增现场教学点"""
    if request.method == 'POST':
        new_site = {
            'id': len(teaching_sites) + 1,
            'name': request.form.get('name'),
            'type': request.form.get('type'),
            'supplier': request.form.get('supplier'),
            'contact_name': request.form.get('contact_name'),
            'contact_phone': request.form.get('contact_phone'),
            'price': float(request.form.get('price', 0)),
            'address': request.form.get('address'),
            'price_note': request.form.get('price_note'),
            'description': request.form.get('description'),
            'audit_status': '待审核',
            'created_at': datetime.now()
        }
        teaching_sites.append(new_site)
        flash('现场教学点添加成功', 'success')
        return redirect(url_for('sites_list'))
    return render_template('sites/form.html')


@app.route('/sites/<int:id>/edit', methods=['GET', 'POST'])
def site_edit(id):
    """编辑现场教学点"""
    site = next((s for s in teaching_sites if s['id'] == id), None)
    if not site:
        flash('现场教学点不存在', 'error')
        return redirect(url_for('sites_list'))
    if request.method == 'POST':
        site['name'] = request.form.get('name')
        site['type'] = request.form.get('type')
        site['supplier'] = request.form.get('supplier')
        site['contact_name'] = request.form.get('contact_name')
        site['contact_phone'] = request.form.get('contact_phone')
        site['price'] = float(request.form.get('price', 0))
        site['address'] = request.form.get('address')
        site['price_note'] = request.form.get('price_note')
        site['description'] = request.form.get('description')
        flash('现场教学点更新成功', 'success')
        return redirect(url_for('site_detail', id=id))
    return render_template('sites/form.html', site=site)


@app.route('/sites/<int:id>/delete', methods=['POST'])
def site_delete(id):
    """删除现场教学点"""
    site = next((s for s in teaching_sites if s['id'] == id), None)
    if site:
        teaching_sites.remove(site)
        flash('现场教学点删除成功', 'success')
    else:
        flash('现场教学点不存在', 'error')
    return redirect(url_for('sites_list'))


# ==================== 师资管理 ====================
@app.route('/teachers')
def teachers_list():
    """师资管理列表（卡片式布局）- 支持分页、排序、跳转"""
    keyword = request.args.get('keyword', '')
    status = request.args.get('status', '')
    title = request.args.get('title', '')
    sort_by = request.args.get('sort', '')  # score:评分, count:上课次数, name:姓名
    page = request.args.get('page', 1, type=int)
    per_page = 20  # 每页20位
    
    filtered_teachers = teachers.copy()
    
    # 多关键词搜索（空格分隔，匹配所有关键词）
    if keyword:
        keywords = [k.strip().lower() for k in keyword.split() if k.strip()]
        def matches_all_keywords(teacher, keywords):
            search_text = ' '.join([
                str(teacher.get('name', '')),
                str(teacher.get('field', '')),
                str(teacher.get('title', '')),
                str(teacher.get('specialty', '')),
                str(teacher.get('introduction', '')),
                str(teacher.get('organization', ''))
            ]).lower()
            return all(kw in search_text for kw in keywords)
        filtered_teachers = [t for t in filtered_teachers if matches_all_keywords(t, keywords)]
    if status:
        filtered_teachers = [t for t in filtered_teachers if t.get('status') == status]
    if title:
        filtered_teachers = [t for t in filtered_teachers if t.get('title') == title]
    
    # 排序
    if sort_by == 'score':
        # 按评分从高到低
        filtered_teachers = sorted(filtered_teachers, 
                                  key=lambda x: float(x.get('evaluation_score') or 0), 
                                  reverse=True)
    elif sort_by == 'count':
        # 按上课次数从高到低
        filtered_teachers = sorted(filtered_teachers, 
                                  key=lambda x: int(x.get('teaching_count') or 0), 
                                  reverse=True)
    elif sort_by == 'name':
        # 按姓名排序
        filtered_teachers = sorted(filtered_teachers, 
                                  key=lambda x: x.get('name', ''))
    
    # 分页计算
    total = len(filtered_teachers)
    total_pages = (total + per_page - 1) // per_page
    page = max(1, min(page, total_pages)) if total_pages > 0 else 1
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    paginated_teachers = filtered_teachers[start_idx:end_idx]
    
    # 生成分页页码列表（显示前后2页+首页+末页+省略号）
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
    
    return render_template('teachers/list.html',
                         teachers=paginated_teachers,
                         pagination=pagination,
                         keyword=keyword,
                         status=status,
                         title=title,
                         sort=sort_by)


@app.route('/teachers/<int:id>')
def teacher_detail(id):
    """教师详情页 - 使用完整真实数据"""
    teacher = next((t for t in teachers if t['id'] == id), None)
    if not teacher:
        flash('教师不存在', 'error')
        return redirect(url_for('teachers_list'))
    
    # 获取教师的上课记录（从完整数据）
    teaching_records = teacher.get('teaching_records', [])
    
    # 获取点赞统计数据
    likes_data = teacher.get('likes_data', [])
    
    # 获取详细评价数据
    detailed_evaluations = teacher.get('detailed_evaluations', [])
    
    return render_template('teachers/detail.html',
                         teacher=teacher,
                         teaching_records=teaching_records,
                         likes_data=likes_data,
                         detailed_evaluations=detailed_evaluations)


@app.route('/teachers/new', methods=['GET', 'POST'])
def teacher_new():
    """新增讲师"""
    if request.method == 'POST':
        new_teacher = {
            'id': len(teachers) + 1,
            'name': request.form.get('name'),
            'phone': request.form.get('phone'),
            'email': request.form.get('email'),
            'gender': request.form.get('gender'),
            'title': request.form.get('title'),
            'organization': request.form.get('organization'),
            'education': request.form.get('education'),
            'major': request.form.get('major'),
            'specialty': request.form.get('specialty'),
            'introduction': request.form.get('introduction'),
            'compensation_before_tax': float(request.form.get('compensation_before_tax', 0)) if request.form.get('compensation_before_tax') else None,
            'compensation_after_tax': float(request.form.get('compensation_after_tax', 0)) if request.form.get('compensation_after_tax') else None,
            'level': request.form.get('level'),
            'bank_name': request.form.get('bank_name'),
            'bank_card': request.form.get('bank_card'),
            'id_card': request.form.get('id_card'),
            'service_customers': request.form.get('service_customers'),
            'status': '待审核',
            'evaluation_score': 0,
            'creator': '管理员',
            'created_at': datetime.now()
        }
        teachers.append(new_teacher)
        flash('讲师添加成功', 'success')
        return redirect(url_for('teachers_list'))
    return render_template('teachers/form.html')


@app.route('/teachers/<int:id>/edit', methods=['GET', 'POST'])
def teacher_edit(id):
    """编辑讲师"""
    teacher = next((t for t in teachers if t['id'] == id), None)
    if not teacher:
        flash('讲师不存在', 'error')
        return redirect(url_for('teachers_list'))
    if request.method == 'POST':
        teacher['name'] = request.form.get('name')
        teacher['phone'] = request.form.get('phone')
        teacher['email'] = request.form.get('email')
        teacher['gender'] = request.form.get('gender')
        teacher['title'] = request.form.get('title')
        teacher['organization'] = request.form.get('organization')
        teacher['education'] = request.form.get('education')
        teacher['major'] = request.form.get('major')
        teacher['specialty'] = request.form.get('specialty')
        teacher['introduction'] = request.form.get('introduction')
        teacher['compensation_before_tax'] = float(request.form.get('compensation_before_tax', 0)) if request.form.get('compensation_before_tax') else None
        teacher['compensation_after_tax'] = float(request.form.get('compensation_after_tax', 0)) if request.form.get('compensation_after_tax') else None
        teacher['level'] = request.form.get('level')
        teacher['bank_name'] = request.form.get('bank_name')
        teacher['bank_card'] = request.form.get('bank_card')
        teacher['id_card'] = request.form.get('id_card')
        teacher['service_customers'] = request.form.get('service_customers')
        flash('讲师更新成功', 'success')
        return redirect(url_for('teacher_detail', id=id))
    return render_template('teachers/form.html', teacher=teacher)


@app.route('/teachers/<int:id>/delete', methods=['POST'])
def teacher_delete(id):
    """删除讲师"""
    teacher = next((t for t in teachers if t['id'] == id), None)
    if teacher:
        # 检查是否有课表使用该讲师
        used_in_schedule = any(s.get('teacher_id') == id for s in schedules)
        if used_in_schedule:
            flash('该讲师已有授课记录，不能删除', 'error')
            return redirect(url_for('teachers_list'))
        teachers.remove(teacher)
        flash('讲师删除成功', 'success')
    else:
        flash('讲师不存在', 'error')
    return redirect(url_for('teachers_list'))


@app.route('/teachers/export')
def teachers_export():
    """导出师资列表为CSV"""
    import csv
    import io
    
    keyword = request.args.get('keyword', '')
    sort_by = request.args.get('sort', '')
    
    filtered_teachers = teachers.copy()
    
    # 多关键词搜索
    if keyword:
        keywords = [k.strip().lower() for k in keyword.split() if k.strip()]
        def matches_all_keywords(teacher, keywords):
            search_text = ' '.join([
                str(teacher.get('name', '')),
                str(teacher.get('field', '')),
                str(teacher.get('title', '')),
                str(teacher.get('specialty', '')),
                str(teacher.get('introduction', '')),
                str(teacher.get('organization', ''))
            ]).lower()
            return all(kw in search_text for kw in keywords)
        filtered_teachers = [t for t in filtered_teachers if matches_all_keywords(t, keywords)]
    
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
    
    # 生成CSV
    output = io.StringIO()
    writer = csv.writer(output)
    
    # 表头
    writer.writerow(['ID', '姓名', '所属领域', '讲师类型', '级别', '税前课酬', '税后课酬', 
                     '上课次数', '综合评分', '服务客户', '手机号', '状态', '个人简介'])
    
    # 数据行
    for t in filtered_teachers:
        writer.writerow([
            t.get('id', ''),
            t.get('name', ''),
            t.get('field', ''),
            t.get('teacher_type', ''),
            t.get('level', ''),
            t.get('compensation_before_tax', ''),
            t.get('compensation_after_tax', ''),
            t.get('teaching_count', 0),
            t.get('evaluation_score', 0),
            t.get('service_customers', ''),
            t.get('phone', ''),
            t.get('status', ''),
            (t.get('introduction', '') or '')[:100] + '...' if (t.get('introduction', '') or '') else ''
        ])
    
    output.seek(0)
    
    # 返回CSV文件
    from flask import Response
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename=teachers_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv',
            'Content-Type': 'text/csv; charset=utf-8-sig'
        }
    )


# ==================== 班级管理 ====================
@app.route('/classes')
def classes_list():
    """班级管理列表"""
    keyword = request.args.get('keyword', '')
    selected_category = request.args.get('category', '')
    selected_teacher = request.args.get('teacher', '')
    status = request.args.get('status', '')
    
    filtered_classes = classes
    if keyword:
        filtered_classes = [c for c in filtered_classes if keyword in c['name']]
    if selected_category:
        filtered_classes = [c for c in filtered_classes if str(c['category_id']) == selected_category]
    if selected_teacher:
        filtered_classes = [c for c in filtered_classes if str(c['teacher_id']) == selected_teacher]
    if status:
        filtered_classes = [c for c in filtered_classes if c['status'] == status]
    
    return render_template('classes/list.html',
                         classes=filtered_classes,
                         categories=teacher_categories,
                         teachers=teachers,
                         keyword=keyword,
                         selected_category=selected_category,
                         selected_teacher=selected_teacher,
                         status=status)


@app.route('/classes/<int:id>')
def class_detail(id):
    """班级详情页"""
    class_obj = next((c for c in classes if c['id'] == id), None)
    if not class_obj:
        flash('班级不存在', 'error')
        return redirect(url_for('classes_list'))
    
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
                         class_students=class_students)


@app.route('/classes/new', methods=['GET', 'POST'])
def class_new():
    """新增班级 - 支持批量生成课表"""
    if request.method == 'POST':
        # 获取上课时段（可多选）
        time_slots = request.form.getlist('time_slots') or ['morning', 'afternoon']
        
        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')
        
        new_class = {
            'id': len(classes) + 1,
            'name': request.form.get('name'),
            'category_id': int(request.form.get('category_id', 0)),
            'category_name': next((c['name'] for c in teacher_categories if c['id'] == int(request.form.get('category_id', 0))), None),
            'time_slots': time_slots,  # 存储上课时段 ['morning', 'afternoon', 'evening']
            'start_date': datetime.strptime(start_date_str, '%Y-%m-%d') if start_date_str else None,
            'end_date': datetime.strptime(end_date_str, '%Y-%m-%d') if end_date_str else None,
            'status': request.form.get('status', '招生中'),
            'description': request.form.get('description'),
            'sign_in_rate': 0,
            'evaluation_rate': 0,
            'student_count': 0,
            'created_at': datetime.now()
        }
        classes.append(new_class)
        
        # 根据日期范围和时段批量生成课表
        if start_date_str and end_date_str:
            from datetime import timedelta
            start = datetime.strptime(start_date_str, '%Y-%m-%d')
            end = datetime.strptime(end_date_str, '%Y-%m-%d')
            
            # 时段配置
            slot_config = {
                'morning': {'name': '上午', 'start': '08:30', 'end': '12:00'},
                'afternoon': {'name': '下午', 'start': '14:00', 'end': '17:30'},
                'evening': {'name': '晚上', 'start': '18:30', 'end': '21:00'},
                'fullday': {'name': '全天', 'start': '08:30', 'end': '17:30'}
            }
            
            current_date = start
            schedule_count = 0
            while current_date <= end:
                for slot in time_slots:
                    if slot in slot_config:
                        config = slot_config[slot]
                        new_schedule = {
                            'id': len(schedules) + 1,
                            'class_id': new_class['id'],
                            'class_name': new_class['name'],
                            'teacher_id': None,  # 待安排
                            'teacher_name': None,
                            'subject': None,  # 待安排
                            'teaching_date': current_date,
                            'time_slot': slot,  # 时段标记
                            'time_slot_name': config['name'],
                            'start_time': config['start'],
                            'end_time': config['end'],
                            'location': None,
                            'compensation': None,
                            'status': '待安排',  # 待安排老师
                            'courseware': None
                        }
                        schedules.append(new_schedule)
                        schedule_count += 1
                current_date += timedelta(days=1)
            
            flash(f'班级添加成功！已自动生成 {schedule_count} 个课时段，请在课表管理中安排老师和课程', 'success')
        else:
            flash('班级添加成功！', 'success')
        
        return redirect(url_for('class_detail', id=new_class['id']))
    return render_template('classes/form.html', categories=teacher_categories, teachers=teachers)


@app.route('/classes/<int:id>/edit', methods=['GET', 'POST'])
def class_edit(id):
    """编辑班级"""
    class_obj = next((c for c in classes if c['id'] == id), None)
    if not class_obj:
        flash('班级不存在', 'error')
        return redirect(url_for('classes_list'))
    if request.method == 'POST':
        class_obj['name'] = request.form.get('name')
        class_obj['category_id'] = int(request.form.get('category_id', 0))
        class_obj['category_name'] = next((c['name'] for c in teacher_categories if c['id'] == int(request.form.get('category_id', 0))), None)
        class_obj['time_slots'] = request.form.getlist('time_slots') or ['morning', 'afternoon']
        class_obj['start_date'] = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d') if request.form.get('start_date') else None
        class_obj['end_date'] = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d') if request.form.get('end_date') else None
        class_obj['status'] = request.form.get('status')
        class_obj['description'] = request.form.get('description')
        flash('班级更新成功', 'success')
        return redirect(url_for('class_detail', id=id))
    return render_template('classes/form.html', class_obj=class_obj, categories=teacher_categories, teachers=teachers)


@app.route('/classes/<int:id>/delete', methods=['POST'])
def class_delete(id):
    """删除班级"""
    class_obj = next((c for c in classes if c['id'] == id), None)
    if class_obj:
        classes.remove(class_obj)
        flash('班级删除成功', 'success')
    else:
        flash('班级不存在', 'error')
    return redirect(url_for('classes_list'))


@app.route('/classes/export')
def classes_export():
    """导出班级列表为CSV"""
    import csv
    import io
    
    keyword = request.args.get('keyword', '')
    
    filtered_classes = classes.copy()
    if keyword:
        filtered_classes = [c for c in filtered_classes if keyword in c.get('name', '')]
    
    # 生成CSV
    output = io.StringIO()
    writer = csv.writer(output)
    
    # 表头
    writer.writerow(['ID', '班级名称', '班级分类', '课程数量', '学员数量', '项目主任', '班主任', 
                     '授课人群', '签到率', '评价率', '班级状态', '开班时间', '结束时间'])
    
    # 数据行
    for c in filtered_classes:
        writer.writerow([
            c.get('id', ''),
            c.get('name', ''),
            c.get('category_name', ''),
            c.get('course_count', 0),
            c.get('student_count', 0),
            c.get('project_leader', ''),
            c.get('class_advisor', ''),
            c.get('target_audience', '党政干部'),
            c.get('sign_in_rate', '92.89%'),
            c.get('evaluation_rate', '96.89%'),
            c.get('status', ''),
            c.get('start_date', '').strftime('%Y-%m-%d') if c.get('start_date') else '',
            c.get('end_date', '').strftime('%Y-%m-%d') if c.get('end_date') else ''
        ])
    
    output.seek(0)
    
    # 返回CSV文件
    from flask import Response
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename=classes_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv',
            'Content-Type': 'text/csv; charset=utf-8-sig'
        }
    )


# ==================== 课表管理 ====================
@app.route('/schedules')
def schedules_list():
    """课表管理列表"""
    selected_class = request.args.get('class_id', '')
    selected_teacher = request.args.get('teacher_id', '')
    selected_date = request.args.get('date', '')
    
    filtered_schedules = schedules
    if selected_class:
        filtered_schedules = [s for s in filtered_schedules if str(s['class_id']) == selected_class]
    if selected_teacher:
        filtered_schedules = [s for s in filtered_schedules if str(s['teacher_id']) == selected_teacher]
    if selected_date:
        try:
            date_obj = datetime.strptime(selected_date, '%Y-%m-%d')
            filtered_schedules = [s for s in filtered_schedules if s['teaching_date'].date() == date_obj.date()]
        except:
            pass
    
    return render_template('schedules/list.html',
                         schedules=filtered_schedules,
                         classes=classes,
                         teachers=teachers,
                         selected_class=selected_class,
                         selected_teacher=selected_teacher,
                         selected_date=selected_date)


@app.route('/schedules/<int:id>')
def schedule_detail(id):
    """课表详情页"""
    schedule = next((s for s in schedules if s['id'] == id), None)
    if not schedule:
        flash('课表不存在', 'error')
        return redirect(url_for('schedules_list'))
    
    # 模拟签到记录
    sign_records = [
        {
            'student_id': 1,
            'student_name': '张三',
            'student_phone': '13700137001',
            'student_company': '阿里巴巴',
            'status': '已签到',
            'sign_time': datetime(2026, 4, 17, 8, 55)
        },
        {
            'student_id': 2,
            'student_name': '李四',
            'student_phone': '13700137002',
            'student_company': '腾讯科技',
            'status': '未签到',
            'sign_time': None
        }
    ]
    
    # 模拟评价记录
    evaluations = [
        {
            'id': 1,
            'created_at': datetime(2026, 4, 17, 14, 30),
            'student_name': '张三',
            'class_name': '企业领导力提升研修班',
            'score': 9.5,
            'content': '老师讲得非常好，受益匪浅！'
        }
    ]
    
    return render_template('schedules/detail.html',
                         schedule=schedule,
                         sign_records=sign_records,
                         evaluations=evaluations,
                         total_students=len(sign_records),
                         signed_count=len([r for r in sign_records if r['status'] == '已签到']),
                         unsigned_count=len([r for r in sign_records if r['status'] != '已签到']),
                         evaluated_count=len(evaluations),
                         commented_count=len([e for e in evaluations if e['content']]))


@app.route('/schedules/new', methods=['GET', 'POST'])
def schedule_new():
    """新增/安排课表"""
    preselected_class_id = request.args.get('class_id')
    preselected_date = request.args.get('date')
    preselected_slot = request.args.get('slot')
    
    if request.method == 'POST':
        class_id = int(request.form.get('class_id', 0))
        teacher_id = int(request.form.get('teacher_id', 0)) if request.form.get('teacher_id') else None
        time_slot = request.form.get('time_slot', 'morning')
        
        # 时段配置
        slot_config = {
            'morning': {'name': '上午', 'start': '08:30', 'end': '12:00'},
            'afternoon': {'name': '下午', 'start': '14:00', 'end': '17:30'},
            'evening': {'name': '晚上', 'start': '18:30', 'end': '21:00'},
                'fullday': {'name': '全天', 'start': '08:30', 'end': '17:30'}
        }
        config = slot_config.get(time_slot, slot_config['morning'])
        
        # 如果是安排现有课表（已有class_id和date/slot的组合）
        existing_schedule = None
        teaching_date_str = request.form.get('teaching_date')
        if class_id and teaching_date_str:
            teaching_date = datetime.strptime(teaching_date_str, '%Y-%m-%d')
            existing_schedule = next((s for s in schedules 
                                      if s['class_id'] == class_id 
                                      and s['teaching_date'].date() == teaching_date.date()
                                      and s.get('time_slot') == time_slot), None)
        
        if existing_schedule:
            # 更新现有课表
            existing_schedule['teacher_id'] = teacher_id
            existing_schedule['teacher_name'] = next((t['name'] for t in teachers if t['id'] == teacher_id), None) if teacher_id else None
            existing_schedule['subject'] = request.form.get('subject')
            existing_schedule['location'] = request.form.get('location')
            existing_schedule['compensation'] = float(request.form.get('compensation', 0)) if request.form.get('compensation') else None
            existing_schedule['status'] = request.form.get('status', '待上课')
            flash('课程安排成功！', 'success')
            return redirect(url_for('class_detail', id=class_id))
        else:
            # 创建新课表
            new_schedule = {
                'id': len(schedules) + 1,
                'class_id': class_id,
                'class_name': next((c['name'] for c in classes if c['id'] == class_id), None),
                'teacher_id': teacher_id,
                'teacher_name': next((t['name'] for t in teachers if t['id'] == teacher_id), None) if teacher_id else None,
                'subject': request.form.get('subject'),
                'teaching_date': datetime.strptime(teaching_date_str, '%Y-%m-%d') if teaching_date_str else None,
                'time_slot': time_slot,
                'time_slot_name': config['name'],
                'start_time': request.form.get('start_time') or config['start'],
                'end_time': request.form.get('end_time') or config['end'],
                'location': request.form.get('location'),
                'compensation': float(request.form.get('compensation', 0)) if request.form.get('compensation') else None,
                'status': request.form.get('status', '待上课'),
                'courseware': None
            }
            schedules.append(new_schedule)
            flash('课表添加成功！', 'success')
            return redirect(url_for('schedules_list'))
    
    # 获取预选班级的信息
    class_name = None
    if preselected_class_id:
        class_obj = next((c for c in classes if c['id'] == int(preselected_class_id)), None)
        if class_obj:
            class_name = class_obj['name']
    
    return render_template('schedules/form.html', 
                         classes=classes, 
                         teachers=teachers, 
                         classrooms=classrooms, 
                         sites=teaching_sites,
                         courses=courses,
                         preselected_class_id=preselected_class_id,
                         preselected_date=preselected_date,
                         preselected_slot=preselected_slot,
                         class_name=class_name)


@app.route('/schedules/<int:id>/edit', methods=['GET', 'POST'])
def schedule_edit(id):
    """编辑课表/安排老师课程"""
    schedule = next((s for s in schedules if s['id'] == id), None)
    if not schedule:
        flash('课表不存在', 'error')
        return redirect(url_for('schedules_list'))
    
    if request.method == 'POST':
        teacher_id = int(request.form.get('teacher_id', 0)) if request.form.get('teacher_id') else None
        time_slot = request.form.get('time_slot', schedule.get('time_slot', 'morning'))
        
        # 时段配置
        slot_config = {
            'morning': {'name': '上午', 'start': '08:30', 'end': '12:00'},
            'afternoon': {'name': '下午', 'start': '14:00', 'end': '17:30'},
            'evening': {'name': '晚上', 'start': '18:30', 'end': '21:00'},
                'fullday': {'name': '全天', 'start': '08:30', 'end': '17:30'}
        }
        config = slot_config.get(time_slot, slot_config['morning'])
        
        schedule['teacher_id'] = teacher_id
        schedule['teacher_name'] = next((t['name'] for t in teachers if t['id'] == teacher_id), None) if teacher_id else None
        schedule['subject'] = request.form.get('subject')
        schedule['teaching_date'] = datetime.strptime(request.form.get('teaching_date'), '%Y-%m-%d') if request.form.get('teaching_date') else None
        schedule['time_slot'] = time_slot
        schedule['time_slot_name'] = config['name']
        schedule['start_time'] = request.form.get('start_time') or config['start']
        schedule['end_time'] = request.form.get('end_time') or config['end']
        schedule['location'] = request.form.get('location')
        schedule['compensation'] = float(request.form.get('compensation', 0)) if request.form.get('compensation') else None
        schedule['status'] = request.form.get('status', '待上课')
        flash('课程安排更新成功！', 'success')
        
        # 如果是从班级详情页来的，返回班级详情页
        if schedule.get('class_id'):
            return redirect(url_for('class_detail', id=schedule['class_id']))
        return redirect(url_for('schedules_list'))
    
    # 获取班级名称
    class_name = None
    if schedule.get('class_id'):
        class_obj = next((c for c in classes if c['id'] == schedule['class_id']), None)
        if class_obj:
            class_name = class_obj['name']
    
    return render_template('schedules/form.html', 
                         schedule=schedule, 
                         classes=classes, 
                         teachers=teachers, 
                         classrooms=classrooms, 
                         sites=teaching_sites,
                         courses=courses,
                         class_name=class_name,
                         preselected_class_id=schedule.get('class_id'))


@app.route('/schedules/<int:id>/delete', methods=['POST'])
def schedule_delete(id):
    """删除课表"""
    schedule = next((s for s in schedules if s['id'] == id), None)
    if schedule:
        schedules.remove(schedule)
        flash('课表删除成功', 'success')
    else:
        flash('课表不存在', 'error')
    return redirect(url_for('schedules_list'))


@app.route('/schedules/export')
def schedules_export():
    """导出课表列表为CSV"""
    import csv
    import io
    
    selected_class = request.args.get('class_id', '')
    selected_teacher = request.args.get('teacher_id', '')
    selected_date = request.args.get('date', '')
    
    filtered_schedules = schedules.copy()
    if selected_class:
        filtered_schedules = [s for s in filtered_schedules if str(s.get('class_id')) == selected_class]
    if selected_teacher:
        filtered_schedules = [s for s in filtered_schedules if str(s.get('teacher_id')) == selected_teacher]
    if selected_date:
        filtered_schedules = [s for s in filtered_schedules if s.get('teaching_date') and s['teaching_date'].strftime('%Y-%m-%d') == selected_date]
    
    # 生成CSV
    output = io.StringIO()
    writer = csv.writer(output)
    
    # 表头
    writer.writerow(['ID', '上课时间', '课程名称', '课程类型', '所属班级', '授课老师', '教室/教学点', 
                     '上课人数', '签到率', '评价率', '课酬', '状态'])
    
    # 数据行
    for s in filtered_schedules:
        writer.writerow([
            s.get('id', ''),
            f"{s.get('teaching_date', '').strftime('%Y-%m-%d') if s.get('teaching_date') else ''} {s.get('start_time', '')}-{s.get('end_time', '')}",
            s.get('subject', ''),
            s.get('course_type', '理论课程'),
            s.get('class_name', ''),
            s.get('teacher_name', ''),
            s.get('location', ''),
            s.get('student_count', 0),
            s.get('sign_rate', '100.00%'),
            s.get('eval_rate', '35.90%'),
            s.get('compensation', 0),
            s.get('status', '')
        ])
    
    output.seek(0)
    
    # 返回CSV文件
    from flask import Response
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename=schedules_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv',
            'Content-Type': 'text/csv; charset=utf-8-sig'
        }
    )


# ==================== 学员管理 ====================
@app.route('/students')
def students_list():
    """学员管理列表"""
    keyword = request.args.get('keyword', '')
    selected_class = request.args.get('class_id', '')
    province = request.args.get('province', '')
    
    filtered_students = students
    if keyword:
        filtered_students = [s for s in filtered_students 
                           if keyword in s['name'] or 
                              keyword in (s['phone'] or '') or 
                              keyword in (s['company'] or '')]
    if selected_class:
        filtered_students = [s for s in filtered_students if s.get('class_id') == int(selected_class)]
    if province:
        filtered_students = [s for s in filtered_students if s.get('province') == province]
    
    return render_template('students/list.html',
                         students=filtered_students,
                         classes=classes,
                         keyword=keyword,
                         selected_class=selected_class,
                         province=province)


@app.route('/students/<int:id>')
def student_detail(id):
    """学员详情页"""
    student = next((s for s in students if s['id'] == id), None)
    if not student:
        flash('学员不存在', 'error')
        return redirect(url_for('students_list'))
    
    # 模拟上课记录
    attendance_records = [
        {
            'teaching_date': datetime(2026, 4, 17),
            'duration': '3小时',
            'subject': '领导力基础理论',
            'class_name': '企业领导力提升研修班',
            'director': '张主任',
            'teacher_manager': '王老师',
            'evaluation_score': 9.5,
            'evaluation_comment': '老师讲得非常好，受益匪浅！'
        },
        {
            'teaching_date': datetime(2026, 4, 16),
            'duration': '3小时',
            'subject': '组织行为学导论',
            'class_name': '企业领导力提升研修班',
            'director': '张主任',
            'teacher_manager': '李老师',
            'evaluation_score': None,
            'evaluation_comment': None
        }
    ]
    
    return render_template('students/detail.html',
                         student=student,
                         attendance_records=attendance_records)


@app.route('/students/new', methods=['GET', 'POST'])
def student_new():
    """新增学员"""
    if request.method == 'POST':
        new_student = {
            'id': len(students) + 1,
            'name': request.form.get('name'),
            'gender': request.form.get('gender'),
            'phone': request.form.get('phone'),
            'email': request.form.get('email'),
            'company': request.form.get('company'),
            'position': request.form.get('position'),
            'province': request.form.get('province'),
            'city': request.form.get('city'),
            'class_id': int(request.form.get('class_id', 0)) if request.form.get('class_id') else None,
            'class_name': next((c['name'] for c in classes if c['id'] == int(request.form.get('class_id', 0))), None) if request.form.get('class_id') else None,
            'student_no': request.form.get('student_no') or f'S{len(students)+1:04d}',
            'remark': request.form.get('remark'),
            'attendance_count': 0,
            'created_at': datetime.now()
        }
        students.append(new_student)
        flash('学员添加成功', 'success')
        return redirect(url_for('students_list'))
    return render_template('students/form.html', classes=classes)


@app.route('/students/<int:id>/edit', methods=['GET', 'POST'])
def student_edit(id):
    """编辑学员"""
    student = next((s for s in students if s['id'] == id), None)
    if not student:
        flash('学员不存在', 'error')
        return redirect(url_for('students_list'))
    if request.method == 'POST':
        student['name'] = request.form.get('name')
        student['gender'] = request.form.get('gender')
        student['phone'] = request.form.get('phone')
        student['email'] = request.form.get('email')
        student['company'] = request.form.get('company')
        student['position'] = request.form.get('position')
        student['province'] = request.form.get('province')
        student['city'] = request.form.get('city')
        student['class_id'] = int(request.form.get('class_id', 0)) if request.form.get('class_id') else None
        student['class_name'] = next((c['name'] for c in classes if c['id'] == int(request.form.get('class_id', 0))), None) if request.form.get('class_id') else None
        student['student_no'] = request.form.get('student_no')
        student['remark'] = request.form.get('remark')
        flash('学员更新成功', 'success')
        return redirect(url_for('student_detail', id=id))
    return render_template('students/form.html', student=student, classes=classes)


@app.route('/students/<int:id>/delete', methods=['POST'])
def student_delete(id):
    """删除学员"""
    student = next((s for s in students if s['id'] == id), None)
    if student:
        students.remove(student)
        flash('学员删除成功', 'success')
    else:
        flash('学员不存在', 'error')
    return redirect(url_for('students_list'))


# ==================== 课程管理 ====================
@app.route('/courses')
def courses_list():
    """课程管理列表"""
    keyword = request.args.get('keyword', '')
    selected_category = request.args.get('category_id', '')
    
    filtered_courses = courses
    if keyword:
        filtered_courses = [c for c in filtered_courses if keyword in c['name']]
    if selected_category:
        filtered_courses = [c for c in filtered_courses if str(c['category_id']) == selected_category]
    
    return render_template('courses/list.html',
                         courses=filtered_courses,
                         categories=teacher_categories,
                         keyword=keyword,
                         selected_category=selected_category)


@app.route('/courses/<int:id>')
def course_detail(id):
    """课程详情页"""
    course = next((c for c in courses if c['id'] == id), None)
    if not course:
        flash('课程不存在', 'error')
        return redirect(url_for('courses_list'))
    
    # 获取教授该课程的讲师
    course_teachers = [t for t in teachers if any(id == c['id'] for c in t.get('courses', []))]
    # 模拟上课记录
    course_schedules = [s for s in schedules if s['subject'] == course['name']]
    
    return render_template('courses/detail.html',
                         course=course,
                         teachers=course_teachers,
                         schedules=course_schedules)


@app.route('/courses/new', methods=['GET', 'POST'])
def course_new():
    """新增课程"""
    if request.method == 'POST':
        category_id = int(request.form.get('category_id', 0))
        new_course = {
            'id': len(courses) + 1,
            'name': request.form.get('name'),
            'category_id': category_id,
            'category_name': next((c['name'] for c in teacher_categories if c['id'] == category_id), None),
            'duration': int(request.form.get('duration', 0)) if request.form.get('duration') else None,
            'description': request.form.get('description'),
            'created_at': datetime.now()
        }
        courses.append(new_course)
        flash('课程添加成功', 'success')
        return redirect(url_for('courses_list'))
    return render_template('courses/form.html', categories=teacher_categories)


@app.route('/courses/<int:id>/edit', methods=['GET', 'POST'])
def course_edit(id):
    """编辑课程"""
    course = next((c for c in courses if c['id'] == id), None)
    if not course:
        flash('课程不存在', 'error')
        return redirect(url_for('courses_list'))
    if request.method == 'POST':
        category_id = int(request.form.get('category_id', 0))
        course['name'] = request.form.get('name')
        course['category_id'] = category_id
        course['category_name'] = next((c['name'] for c in teacher_categories if c['id'] == category_id), None)
        course['duration'] = int(request.form.get('duration', 0)) if request.form.get('duration') else None
        course['description'] = request.form.get('description')
        flash('课程更新成功', 'success')
        return redirect(url_for('course_detail', id=id))
    return render_template('courses/form.html', course=course, categories=teacher_categories)


@app.route('/courses/<int:id>/delete', methods=['POST'])
def course_delete(id):
    """删除课程"""
    course = next((c for c in courses if c['id'] == id), None)
    if course:
        courses.remove(course)
        flash('课程删除成功', 'success')
    else:
        flash('课程不存在', 'error')
    return redirect(url_for('courses_list'))


# ==================== 课酬管理 ====================
@app.route('/compensations')
def compensations_list():
    """课酬管理列表"""
    keyword = request.args.get('keyword', '')
    selected_teacher = request.args.get('teacher_id', '')
    status = request.args.get('status', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    
    filtered_compensations = compensations
    if keyword:
        filtered_compensations = [c for c in filtered_compensations 
                                if keyword in (c['class_name'] or '') or 
                                   keyword in (c['teacher_name'] or '')]
    if selected_teacher:
        filtered_compensations = [c for c in filtered_compensations if str(c['teacher_id']) == selected_teacher]
    if status:
        filtered_compensations = [c for c in filtered_compensations if c['status'] == status]
    
    return render_template('compensations/list.html',
                         compensations=filtered_compensations,
                         teachers=teachers,
                         keyword=keyword,
                         selected_teacher=selected_teacher,
                         status=status,
                         start_date=start_date,
                         end_date=end_date)


@app.route('/compensations/<int:id>')
def compensation_detail(id):
    """课酬详情页"""
    compensation = next((c for c in compensations if c['id'] == id), None)
    if not compensation:
        flash('课酬记录不存在', 'error')
        return redirect(url_for('compensations_list'))
    
    # 模拟审批记录
    approval_records = [
        {
            'action': '发起审批',
            'operator': compensation.get('requester_name', '管理员'),
            'time': compensation.get('created_at'),
            'comment': '申请发放课酬'
        }
    ]
    if compensation.get('status') in ['已通过', '已发放']:
        approval_records.append({
            'action': '审批通过',
            'operator': compensation.get('approver_name', '审批人'),
            'time': compensation.get('approved_at'),
            'comment': '同意发放'
        })
    
    return render_template('compensations/detail.html',
                         compensation=compensation,
                         approval_records=approval_records)


@app.route('/compensations/new', methods=['GET', 'POST'])
def compensation_new():
    """新增课酬"""
    if request.method == 'POST':
        teacher_id = int(request.form.get('teacher_id', 0))
        class_id = int(request.form.get('class_id', 0))
        new_compensation = {
            'id': len(compensations) + 1,
            'teacher_id': teacher_id,
            'teacher_name': next((t['name'] for t in teachers if t['id'] == teacher_id), None),
            'class_id': class_id,
            'class_name': next((c['name'] for c in classes if c['id'] == class_id), None),
            'subject': request.form.get('subject'),
            'teaching_date': datetime.strptime(request.form.get('teaching_date'), '%Y-%m-%d') if request.form.get('teaching_date') else None,
            'amount': float(request.form.get('amount', 0)),
            'status': '待审批',
            'requester_name': '管理员',
            'approver_name': None,
            'approved_at': None,
            'created_at': datetime.now()
        }
        compensations.append(new_compensation)
        flash('课酬申请提交成功', 'success')
        return redirect(url_for('compensations_list'))
    return render_template('compensations/form.html', teachers=teachers, classes=classes, schedules=schedules)


@app.route('/compensations/<int:id>/edit', methods=['GET', 'POST'])
def compensation_edit(id):
    """编辑课酬"""
    compensation = next((c for c in compensations if c['id'] == id), None)
    if not compensation:
        flash('课酬记录不存在', 'error')
        return redirect(url_for('compensations_list'))
    if compensation.get('status') not in ['待审批', '草稿']:
        flash('已审批或已发放的课酬不能编辑', 'error')
        return redirect(url_for('compensation_detail', id=id))
    if request.method == 'POST':
        teacher_id = int(request.form.get('teacher_id', 0))
        class_id = int(request.form.get('class_id', 0))
        compensation['teacher_id'] = teacher_id
        compensation['teacher_name'] = next((t['name'] for t in teachers if t['id'] == teacher_id), None)
        compensation['class_id'] = class_id
        compensation['class_name'] = next((c['name'] for c in classes if c['id'] == class_id), None)
        compensation['subject'] = request.form.get('subject')
        compensation['teaching_date'] = datetime.strptime(request.form.get('teaching_date'), '%Y-%m-%d') if request.form.get('teaching_date') else None
        compensation['amount'] = float(request.form.get('amount', 0))
        flash('课酬更新成功', 'success')
        return redirect(url_for('compensation_detail', id=id))
    return render_template('compensations/form.html', compensation=compensation, teachers=teachers, classes=classes, schedules=schedules)


@app.route('/compensations/<int:id>/delete', methods=['POST'])
def compensation_delete(id):
    """删除课酬"""
    compensation = next((c for c in compensations if c['id'] == id), None)
    if compensation:
        if compensation.get('status') not in ['待审批', '草稿']:
            flash('已审批或已发放的课酬不能删除', 'error')
            return redirect(url_for('compensations_list'))
        compensations.remove(compensation)
        flash('课酬记录删除成功', 'success')
    else:
        flash('课酬记录不存在', 'error')
    return redirect(url_for('compensations_list'))


# ==================== 审批管理 ====================
@app.route('/approvals/compensation')
def approvals_compensation():
    """课酬审批"""
    pending_compensations = [c for c in compensations if c['status'] == '待审批']
    return render_template('approvals/compensation.html',
                         pending_compensations=pending_compensations)


@app.route('/approvals/teacher')
def approvals_teacher():
    """讲师审批"""
    pending_teachers = [t for t in teachers if t['status'] == '待审核']
    return render_template('approvals/teacher.html',
                         pending_teachers=pending_teachers)


@app.route('/approvals/site')
def approvals_site():
    """现场教学审批"""
    keyword = request.args.get('keyword', '')
    supplier = request.args.get('supplier', '')
    phone = request.args.get('phone', '')
    site_type = request.args.get('type', '')
    create_date = request.args.get('create_date', '')
    
    # 获取待审核的现场教学点
    pending_sites = [s for s in teaching_sites if s['audit_status'] == '待审核']
    
    if keyword:
        pending_sites = [s for s in pending_sites if keyword in s['name']]
    if supplier:
        pending_sites = [s for s in pending_sites if supplier in (s['supplier'] or '')]
    if phone:
        pending_sites = [s for s in pending_sites if phone in (s['contact_phone'] or '')]
    if site_type:
        pending_sites = [s for s in pending_sites if s['type'] == site_type]
    
    return render_template('approvals/site.html',
                         pending_sites=pending_sites,
                         keyword=keyword,
                         supplier=supplier,
                         phone=phone,
                         site_type=site_type,
                         create_date=create_date)


# ==================== API接口 ====================
@app.route('/api/stats')
def api_stats():
    """统计数据API"""
    return jsonify({
        'teachers': len(teachers),
        'classes': len(classes),
        'students': len(students),
        'schedules': len(schedules),
        'pending_approvals': len([c for c in compensations if c['status'] == '待审批']) + 
                            len([t for t in teachers if t['status'] == '待审核']) +
                            len([s for s in teaching_sites if s['audit_status'] == '待审核'])
    })


@app.route('/api/teachers')
def api_teachers():
    """师资列表API"""
    return jsonify(teachers)


@app.route('/api/classes')
def api_classes():
    """班级列表API"""
    return jsonify(classes)


# ==================== 错误处理 ====================
@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500


# ==================== 启动应用 ====================
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)