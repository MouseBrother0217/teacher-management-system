"""
师资管理系统 - Flask应用主文件
基于来同学社功能模块1:1复刻
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from datetime import datetime, timedelta
import calendar
import os
import sys
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-here')
app.add_template_global(datetime, 'datetime')

# 注册全局日期转换函数
app.jinja_env.globals['to_date'] = lambda d: d.date() if hasattr(d, 'date') and callable(getattr(d, 'date')) else d

# 数据库配置
from models import db, Teacher, Course, ClassInfo, TeachingRecord, Student
import os
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'instance', 'teacher_system.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# 初始化认证模块（注册蓝图、创建默认账号、注册 before_request）
from auth_module import init_auth_module, login_required_web, require_permission_web, require_role_web, ROLES, PERMISSIONS, get_role_label
init_auth_module(app, db)

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
        from teachers_full import teachers
        DATA_SOURCE = 'full'  # 完整数据含上课记录、点赞、评价
        imported_schedules = []
        imported_evaluations = []
        # full模式下也加载班级和课程数据
        try:
            from imported_courses_classes import courses as imported_courses, classes as imported_classes
            print(f"✅ 已加载完整数据文件 (teachers_full.py) + 班级课程数据")
        except ImportError:
            imported_courses = []
            imported_classes = []
            print(f"✅ 已加载完整数据文件 (teachers_full.py), 班级课程数据未找到")
    except ImportError:
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
    {'id': 1, 'name': '党政培训班', 'parent_id': None, 'parent_name': None, 'description': '面向党政干部的培训班', 'creator': '管理员', 'created_at': datetime(2026, 4, 1)},
    {'id': 2, 'name': '企业内训班', 'parent_id': None, 'parent_name': None, 'description': '面向企业内部员工的培训', 'creator': '管理员', 'created_at': datetime(2026, 4, 2)},
    {'id': 3, 'name': '公开项目班', 'parent_id': None, 'parent_name': None, 'description': '面向社会公开的培训项目', 'creator': '管理员', 'created_at': datetime(2026, 4, 3)},
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
if DATA_SOURCE in ['imported', 'full']:
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

# 启动时同步班级数据到数据库
def sync_classes_to_db():
    """将内存中的班级数据同步到数据库（如果数据库为空）"""
    try:
        from models import ClassInfo, db
        count = ClassInfo.query.count()
        if count == 0 and classes:
            print(f"📥 正在将 {len(classes)} 个班级导入数据库...")
            for c in classes:
                try:
                    start_date = None
                    end_date = None
                    if c.get('start_date'):
                        if isinstance(c['start_date'], datetime):
                            start_date = c['start_date'].date()
                        elif isinstance(c['start_date'], str):
                            try:
                                start_date = datetime.strptime(c['start_date'], '%Y-%m-%d').date()
                            except:
                                pass
                    if c.get('end_date'):
                        if isinstance(c['end_date'], datetime):
                            end_date = c['end_date'].date()
                        elif isinstance(c['end_date'], str):
                            try:
                                end_date = datetime.strptime(c['end_date'], '%Y-%m-%d').date()
                            except:
                                pass
                    
                    status = c.get('status', '未开始')
                    if status not in ['进行中', '已完成', '未开始']:
                        status = '未开始'
                    
                    cls = ClassInfo(
                        name=c.get('name', '未命名班级'),
                        class_type=c.get('category_name', c.get('class_type', '其他')),
                        project_manager=c.get('project_leader', ''),
                        class_teacher=c.get('class_advisor', ''),
                        start_date=start_date,
                        end_date=end_date,
                        status=status,
                        created_at=c.get('created_at', datetime.now())
                    )
                    db.session.add(cls)
                except Exception as e:
                    print(f"  ⚠️ 导入班级失败: {c.get('name', '未知')}: {e}")
            db.session.commit()
            print(f"✅ 班级数据导入完成")
        else:
            print(f"✅ 数据库已有 {count} 个班级，无需导入")
    except Exception as e:
        print(f"[WARN] 同步班级数据到数据库失败: {e}")

# 从数据库加载班级到内存的辅助函数
def sync_classes_from_db():
    """当内存classes为空时，从数据库加载"""
    global classes
    if not classes:
        try:
            from models import ClassInfo
            db_classes = ClassInfo.query.order_by(ClassInfo.id.desc()).all()
            for c in db_classes:
                class_dict = {
                    'id': c.id,
                    'name': c.name,
                    'category_id': 1,
                    'category_name': c.class_type or '其他',
                    'time_slots': ['morning', 'afternoon'],
                    'start_date': c.start_date or datetime.now().date(),
                    'end_date': c.end_date or datetime.now().date(),
                    'status': c.status or '待开班',
                    'project_leader': c.project_manager or '',
                    'class_advisor': c.class_teacher or '',
                    'sign_in_rate': None,
                    'evaluation_rate': None,
                    'student_count': 0,
                    'created_at': c.created_at or datetime.now(),
                    'db_id': c.id
                }
                classes.append(class_dict)
            print(f'✅ 已从数据库加载 {len(classes)} 个班级到内存')
        except Exception as e:
            print(f'[WARN] 从数据库加载班级失败: {e}')



classrooms = [
    {
        'id': 1,
        'name': '白金汉爵大酒店',
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 2,
        'name': '常州建行',
        'capacity': 100,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 3,
        'name': '铂祝香园 南湖厅',
        'capacity': 100,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 4,
        'name': '诸暨党校教室',
        'capacity': 120,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 5,
        'name': '紫金港223报告厅',
        'capacity': 100,
        'type': '校内',
        'campus': '紫金港校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 6,
        'name': '浙大森林二楼5号厅',
        'capacity': 60,
        'type': '校外',
        'campus': '主校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 7,
        'name': '海纳苑4幢101教室',
        'capacity': 50,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 8,
        'name': '海纳苑101教室',
        'capacity': 50,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 9,
        'name': '玉泉校区图书馆2楼报告厅',
        'capacity': 80,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 10,
        'name': '玉泉校区浙大控股办公楼104',
        'capacity': 80,
        'type': '校外',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 11,
        'name': '田家炳103',
        'capacity': 60,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 12,
        'name': '玉泉校区永谦活动中心',
        'capacity': 60,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 13,
        'name': '紫金港校区海纳苑4幢201教室',
        'capacity': 200,
        'type': '校外',
        'campus': '紫金港校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 14,
        'name': '浙大海宁校区',
        'capacity': 60,
        'type': '校外',
        'campus': '海宁校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 15,
        'name': '田家炳115',
        'capacity': 96,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 16,
        'name': '田家炳516',
        'capacity': 55,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 17,
        'name': '浙大华家池校区中心南楼252教室',
        'capacity': 54,
        'type': '校外',
        'campus': '华家池校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 18,
        'name': '海宁校区--圆正酒店桂雨厅',
        'capacity': 100,
        'type': '校外',
        'campus': '海宁校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 19,
        'name': '玉泉校区周亦卿大楼一楼报告厅',
        'capacity': 100,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 20,
        'name': '田家炳401',
        'capacity': 160,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 21,
        'name': '济南中欧校友产业大厦5楼会议室',
        'capacity': 100,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 22,
        'name': '济南酒店',
        'capacity': 100,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 23,
        'name': '西三324',
        'capacity': 150,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 24,
        'name': '田家炳403',
        'capacity': 70,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 25,
        'name': '瑞莱克斯大酒店',
        'capacity': 500,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 26,
        'name': '玉泉校区邵科馆211',
        'capacity': 60,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 27,
        'name': '宜必思会议室',
        'capacity': 60,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 28,
        'name': '田家炳504',
        'capacity': 60,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 29,
        'name': '西二124',
        'capacity': 50,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 30,
        'name': '3号楼101教室',
        'capacity': 64,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 31,
        'name': '艺术楼102',
        'capacity': 120,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 32,
        'name': '逸夫楼平衡中心208报告厅',
        'capacity': 100,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 33,
        'name': '西溪北园第三会议室',
        'capacity': 60,
        'type': '校外',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 34,
        'name': '田家炳216',
        'capacity': 70,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 35,
        'name': '田家炳508',
        'capacity': 60,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 36,
        'name': '灵隐开元酒店',
        'capacity': 80,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 37,
        'name': '浙大森林',
        'capacity': 40,
        'type': '校外',
        'campus': '主校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 38,
        'name': '杭州虹猫兰兔酒店',
        'capacity': 50,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 39,
        'name': '杭州百瑞运河大饭店三楼会场国际厅B区',
        'capacity': 100,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 40,
        'name': '圆正启真酒店求是厅',
        'capacity': 90,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 41,
        'name': '浙江大酒店5楼龙轩厅',
        'capacity': 60,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 42,
        'name': '田家炳411',
        'capacity': 100,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 43,
        'name': '田家炳-216教室',
        'capacity': 90,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 44,
        'name': '星程酒店3楼会议室',
        'capacity': 60,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 45,
        'name': '圆正水晶酒店15楼求智厅',
        'capacity': 90,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 46,
        'name': '新雅图酒店15楼会议室',
        'capacity': 100,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 47,
        'name': '启航国际大酒店一楼会议室',
        'capacity': 80,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 48,
        'name': '西四教学楼154教室',
        'capacity': 87,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 49,
        'name': '浙大圆正水晶酒店15楼会议室',
        'capacity': 60,
        'type': '校外',
        'campus': '主校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 50,
        'name': '浙大华家池校区教学楼313阶梯教室',
        'capacity': 160,
        'type': '校内',
        'campus': '华家池校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 51,
        'name': '田家炳408',
        'capacity': 80,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 52,
        'name': '西一教学楼606教室',
        'capacity': 31,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 53,
        'name': '紫金港启真酒店四楼舜耕厅',
        'capacity': 45,
        'type': '校外',
        'campus': '紫金港校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 54,
        'name': '西溪校区教学主楼806',
        'capacity': 66,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 55,
        'name': '马可波罗假日酒店一楼会议室',
        'capacity': 100,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 56,
        'name': '颐高数字生活厅',
        'capacity': 80,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 57,
        'name': '西溪教学主楼806',
        'capacity': 57,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 58,
        'name': '西溪校区西一405',
        'capacity': 57,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 59,
        'name': '西溪校区西一405教室',
        'capacity': 57,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 60,
        'name': '浙大西溪校区西一405',
        'capacity': 57,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 61,
        'name': '田家炳316',
        'capacity': 65,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 62,
        'name': '主楼301',
        'capacity': 60,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 63,
        'name': '博京国际酒店',
        'capacity': 110,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 64,
        'name': '田家炳311',
        'capacity': 95,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 65,
        'name': '东临401',
        'capacity': 60,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 66,
        'name': '西溪校区主楼101',
        'capacity': 50,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 67,
        'name': '田家炳315',
        'capacity': 100,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 68,
        'name': '华家池教学楼408',
        'capacity': 70,
        'type': '校内',
        'campus': '华家池校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 69,
        'name': '华家池408',
        'capacity': 70,
        'type': '校外',
        'campus': '华家池校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 70,
        'name': '西溪西区西一605',
        'capacity': 60,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 71,
        'name': '田家炳507',
        'capacity': 80,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 72,
        'name': '田家炳212',
        'capacity': 80,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 73,
        'name': '田家炳501',
        'capacity': 100,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 74,
        'name': '文源宾馆会议室',
        'capacity': 40,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 75,
        'name': '浙勤保俶饭店二楼会议室',
        'capacity': 60,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 76,
        'name': '西溪校区田家炳201',
        'capacity': 180,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 77,
        'name': '圆正水晶酒店',
        'capacity': 100,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 78,
        'name': '紫光恒越',
        'capacity': 50,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 79,
        'name': '浙大科技园',
        'capacity': 100,
        'type': '校外',
        'campus': '主校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 80,
        'name': '西三252',
        'capacity': 10,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 81,
        'name': '浙大西溪校区教学主楼802',
        'capacity': 60,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 82,
        'name': '浙江维多利亚丽嘉酒店二楼会议室',
        'capacity': 60,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 83,
        'name': '建德航空小镇开元名庭酒店',
        'capacity': 100,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 84,
        'name': '浙江维多利亚丽嘉酒店2楼大会议室',
        'capacity': 60,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 85,
        'name': '中国城戴斯酒店',
        'capacity': 50,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 86,
        'name': '杭州中维香溢酒店',
        'capacity': 129,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 87,
        'name': '浙江饭店13楼名人厅',
        'capacity': 80,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 88,
        'name': '浙大森林A楼（玉泉楼）二楼二号厅',
        'capacity': 80,
        'type': '校外',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 89,
        'name': '丽呈东谷酒店一楼会议室',
        'capacity': 60,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 90,
        'name': '浙大森林A楼玉泉楼一楼阶梯教室',
        'capacity': 140,
        'type': '校外',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 91,
        'name': '富阳瑞莱克斯大酒店',
        'capacity': 60,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 92,
        'name': '广汽研修中心202室',
        'capacity': 60,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 93,
        'name': '罗曼国际大酒店',
        'capacity': 80,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 94,
        'name': '华凯酒店',
        'capacity': 50,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 95,
        'name': '君亭设计酒店',
        'capacity': 74,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 96,
        'name': '华北饭店6楼易正厅',
        'capacity': 80,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 97,
        'name': '维多利亚丽嘉',
        'capacity': 90,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 98,
        'name': '新侨饭店二楼',
        'capacity': 50,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 99,
        'name': '仁和饭店',
        'capacity': 50,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 100,
        'name': '浙江宾馆龙井厅',
        'capacity': 70,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 101,
        'name': '浙江省委党校',
        'capacity': 80,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 102,
        'name': '田家炳211',
        'capacity': 90,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 103,
        'name': '西溪建国璞隐酒店二楼会议室',
        'capacity': 60,
        'type': '校外',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 104,
        'name': '杭州文华景澜大酒店6楼流霞厅',
        'capacity': 55,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 105,
        'name': '紫金港郁锦香酒店',
        'capacity': 80,
        'type': '校外',
        'campus': '紫金港校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 106,
        'name': '西溪田家炳516',
        'capacity': 60,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 107,
        'name': '西溪田家炳512',
        'capacity': 60,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 108,
        'name': '杭州文华景澜大酒店',
        'capacity': 100,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 109,
        'name': '绍兴鉴湖大酒店',
        'capacity': 120,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 110,
        'name': '海外海酒店',
        'capacity': 200,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 111,
        'name': '浙江宾馆',
        'capacity': 60,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 112,
        'name': '西溪校区田家炳507',
        'capacity': 60,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 113,
        'name': '田家炳512',
        'capacity': 100,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 114,
        'name': '田家炳教学楼503',
        'capacity': 54,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 115,
        'name': '东海宾馆二楼会议室',
        'capacity': 60,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 116,
        'name': '田家炳101',
        'capacity': 100,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 117,
        'name': '田家炳教学楼504',
        'capacity': 52,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 118,
        'name': '紫金港校区',
        'capacity': 70,
        'type': '校外',
        'campus': '紫金港校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 119,
        'name': '田家炳520',
        'capacity': 100,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 120,
        'name': '格雷斯精选酒店',
        'capacity': 50,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 121,
        'name': '金苑酒店会议室',
        'capacity': 130,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 122,
        'name': '田家炳301',
        'capacity': 100,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 123,
        'name': '金地大厦八楼会议室',
        'capacity': 60,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 124,
        'name': '临安党校',
        'capacity': 50,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 125,
        'name': '田家炳207',
        'capacity': 60,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 126,
        'name': '浙江中瑞大厦（精品酒店）',
        'capacity': 65,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 127,
        'name': '浙江饭店',
        'capacity': 60,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 128,
        'name': '丽呈布鲁克酒店',
        'capacity': 70,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 129,
        'name': '宁波诺丁汉',
        'capacity': 115,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 130,
        'name': '酒店会议室',
        'capacity': 60,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 131,
        'name': '华顶国际',
        'capacity': 60,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 132,
        'name': '四明山革命根据地',
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 133,
        'name': '西溪校区邵科馆211',
        'capacity': 100,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 134,
        'name': '杭州电子科技大学文一路校区磁性材料研究院三楼会议室',
        'capacity': 100,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 135,
        'name': '海华大酒店',
        'capacity': 120,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 136,
        'name': '纳德润泽园',
        'capacity': 40,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 137,
        'name': '田家炳216教室',
        'capacity': 85,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 138,
        'name': '上铁钱江酒店',
        'capacity': 60,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 139,
        'name': '亚朵酒店',
        'capacity': 66,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 140,
        'name': '帝景大酒店',
        'capacity': 110,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 141,
        'name': '金溪山庄',
        'capacity': 80,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 142,
        'name': '星都宾馆',
        'capacity': 60,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 143,
        'name': '耕读山庄',
        'capacity': 50,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 144,
        'name': '浙大圆正灵峰山庄',
        'capacity': 60,
        'type': '校外',
        'campus': '主校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 145,
        'name': '采荷酒店二楼多功能厅',
        'capacity': 100,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 146,
        'name': '圆正森林',
        'capacity': 50,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 147,
        'name': '望湖宾馆2楼蓝宝厅',
        'capacity': 100,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 148,
        'name': '望湖宾馆',
        'capacity': 1,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 149,
        'name': '教学主楼101教室',
        'capacity': 50,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 150,
        'name': '浙江大学科技园',
        'capacity': 160,
        'type': '校外',
        'campus': '主校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 151,
        'name': '宁波开元大酒店',
        'capacity': 100,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 152,
        'name': '百瑞运河大酒店',
        'capacity': 120,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 153,
        'name': '田家炳304',
        'capacity': 50,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 154,
        'name': '田家炳511',
        'capacity': 80,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 155,
        'name': '田家炳215',
        'capacity': 80,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 156,
        'name': '田家炳503',
        'capacity': 80,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 157,
        'name': '浙大森林A楼（玉泉楼）2楼三号会场',
        'capacity': 80,
        'type': '校外',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 158,
        'name': '田家炳211教室',
        'capacity': 87,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 159,
        'name': '华家池中心南楼235教室',
        'capacity': 45,
        'type': '校外',
        'campus': '华家池校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 160,
        'name': '田家炳201',
        'capacity': 100,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 161,
        'name': '华家池-中心南楼354教室',
        'capacity': 60,
        'type': '校外',
        'campus': '华家池校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 162,
        'name': '台州方远大饭店 · 三楼天禧 A 厅',
        'capacity': 100,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 163,
        'name': '田家炳203教室',
        'capacity': 100,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 164,
        'name': '田家炳207教室',
        'capacity': 114,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 165,
        'name': '华家池教学楼402',
        'capacity': 85,
        'type': '校内',
        'campus': '华家池校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 166,
        'name': '阿里',
        'capacity': 100,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 167,
        'name': '田家炳208教室',
        'capacity': 50,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 168,
        'name': '西溪-田家炳204',
        'capacity': 60,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 169,
        'name': '西溪校区西三教学楼324教室',
        'capacity': 85,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 170,
        'name': '西溪校区西三332',
        'capacity': 200,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 171,
        'name': '海康威视',
        'capacity': 55,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 172,
        'name': '浙大出版社三楼报告厅',
        'capacity': 100,
        'type': '校内',
        'campus': '主校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 173,
        'name': '西溪校区教学主楼203',
        'capacity': 60,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 174,
        'name': '紫晶酒店三楼紫霞厅',
        'capacity': 55,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 175,
        'name': '华家池校区中心南楼229教室',
        'capacity': 55,
        'type': '校外',
        'campus': '华家池校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 176,
        'name': '宁波东钱湖万金雷迪森度假酒店二楼蕙心厅',
        'capacity': 80,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 177,
        'name': '华家池校区教学楼402',
        'capacity': 45,
        'type': '校内',
        'campus': '华家池校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 178,
        'name': '田家炳308',
        'capacity': 70,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 179,
        'name': '中心南楼',
        'capacity': 645,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 180,
        'name': '华家池607',
        'capacity': 100,
        'type': '校外',
        'campus': '华家池校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 181,
        'name': '神农宾馆',
        'capacity': 80,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 182,
        'name': '西四155',
        'capacity': 82,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 183,
        'name': '田家炳305',
        'capacity': 60,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 184,
        'name': '中豪大酒店',
        'capacity': 50,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 185,
        'name': '西溪图书馆2楼报告厅',
        'capacity': 100,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 186,
        'name': '西溪校区教学主楼801',
        'capacity': 50,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 187,
        'name': '华家池602',
        'capacity': 90,
        'type': '校外',
        'campus': '华家池校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 188,
        'name': '西溪田家炳304',
        'capacity': 80,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 189,
        'name': '田家炳303',
        'capacity': 54,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 190,
        'name': '田家炳516教室',
        'capacity': 60,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 191,
        'name': '教学楼604',
        'capacity': 40,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 192,
        'name': '华家池508',
        'capacity': 100,
        'type': '校外',
        'campus': '华家池校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 193,
        'name': '华家池教学楼508',
        'capacity': 100,
        'type': '校内',
        'campus': '华家池校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 194,
        'name': '田家炳515',
        'capacity': 70,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 195,
        'name': '田家炳307',
        'capacity': 90,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 196,
        'name': '百合花酒店五楼会场',
        'capacity': 60,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 197,
        'name': '田家炳401教室',
        'capacity': 150,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 198,
        'name': '西溪校区',
        'capacity': 30,
        'type': '校外',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 199,
        'name': '西溪西三124（多）',
        'capacity': 60,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 200,
        'name': '西溪校区艺术楼D201教室',
        'capacity': 70,
        'type': '校外',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 201,
        'name': '开化党校',
        'capacity': 80,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 202,
        'name': '西溪校区西三教学楼252教室',
        'capacity': 30,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 203,
        'name': '浙江世贸君澜大饭店三楼世贸厅',
        'capacity': 400,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 204,
        'name': '西溪校区教学主楼103',
        'capacity': 56,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 205,
        'name': '西溪校区教学主楼1101',
        'capacity': 80,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 206,
        'name': '西溪西三324',
        'capacity': 156,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 207,
        'name': '西溪校区教学主楼1110',
        'capacity': 70,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 208,
        'name': '西四154',
        'capacity': 50,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 209,
        'name': '田家炳415',
        'capacity': 120,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 210,
        'name': '圆正启真酒店四楼舜水厅',
        'capacity': 60,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 211,
        'name': '锦江都城酒店-二楼会议室',
        'capacity': 70,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 212,
        'name': '浙江新世纪大酒店四楼时代广场厅',
        'capacity': 100,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 213,
        'name': '梅苑宾馆会议室',
        'capacity': 120,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 214,
        'name': '杭州开元大酒店13楼会议厅',
        'capacity': 100,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 215,
        'name': '启真水晶酒店—莫干山厅',
        'capacity': 70,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 216,
        'name': '教学主楼411教室',
        'capacity': 60,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 217,
        'name': '华家池中心南楼5楼',
        'capacity': 64,
        'type': '校外',
        'campus': '华家池校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 218,
        'name': '华家池中心南楼',
        'capacity': 64,
        'type': '校外',
        'campus': '华家池校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 219,
        'name': '杭州开元大酒店14楼会议厅',
        'capacity': 80,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 220,
        'name': '东临201教室',
        'capacity': 80,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 221,
        'name': '西溪智选',
        'capacity': 100,
        'type': '校外',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 222,
        'name': '华家池中心南楼453',
        'capacity': 60,
        'type': '校外',
        'campus': '华家池校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 223,
        'name': '西溪-田家炳411室',
        'capacity': 85,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 224,
        'name': '田家炳412',
        'capacity': 80,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 225,
        'name': '华家池中心南楼422',
        'capacity': 52,
        'type': '校外',
        'campus': '华家池校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 226,
        'name': '西四教学楼（浙大出版社3楼报告厅）',
        'capacity': 176,
        'type': '校内',
        'campus': '主校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 227,
        'name': '华家池校区403教室',
        'capacity': 40,
        'type': '校外',
        'campus': '华家池校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 228,
        'name': '华家池教学楼509',
        'capacity': 60,
        'type': '校内',
        'campus': '华家池校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 229,
        'name': '永高股份集团内（台州）',
        'capacity': 100,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 230,
        'name': '玉泉饭店2楼宴会厅',
        'capacity': 50,
        'type': '校外',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 231,
        'name': '田家炳312',
        'capacity': 60,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 232,
        'name': '西溪校区东门培训楼',
        'capacity': 70,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 233,
        'name': '田家炳404',
        'capacity': 60,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 234,
        'name': '浙江大学国家大学科技园一楼第二会议厅',
        'capacity': 60,
        'type': '校外',
        'campus': '主校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 235,
        'name': '西四101',
        'capacity': 70,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 236,
        'name': '田家炳416教室',
        'capacity': 80,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 237,
        'name': '西溪校区教学主楼1109',
        'capacity': 60,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 238,
        'name': '之江校区三号楼205',
        'capacity': 60,
        'type': '校外',
        'campus': '之江校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 239,
        'name': '西溪校区主楼806',
        'capacity': 75,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 240,
        'name': '中心南楼333教室',
        'capacity': 60,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 241,
        'name': '田家炳407',
        'capacity': 105,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 242,
        'name': '田家炳401室',
        'capacity': 150,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 243,
        'name': '田家炳311教室',
        'capacity': 120,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 244,
        'name': '浙江世贸君澜大酒店二楼文澜阁',
        'capacity': 60,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 245,
        'name': '世贸君澜大酒店二楼文澜阁',
        'capacity': 60,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 246,
        'name': '良渚博物院考察',
        'capacity': 60,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 247,
        'name': '之江校区李作权活动中心209教室',
        'capacity': 110,
        'type': '校内',
        'campus': '之江校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 248,
        'name': '西溪校区主楼426',
        'capacity': 80,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 249,
        'name': '西溪校区西四151',
        'capacity': 80,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 250,
        'name': '华家池校区中心南楼252教室',
        'capacity': 50,
        'type': '校外',
        'campus': '华家池校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 251,
        'name': '华家池教学楼401',
        'capacity': 60,
        'type': '校内',
        'campus': '华家池校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 252,
        'name': '华辰银座酒店',
        'capacity': 500,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 253,
        'name': '金都宾馆三楼多功能厅',
        'capacity': 200,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 254,
        'name': '华家池教学408',
        'capacity': 100,
        'type': '校外',
        'campus': '华家池校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 255,
        'name': '浙大出版社一楼会议室',
        'capacity': 60,
        'type': '校外',
        'campus': '主校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 256,
        'name': '瑞丰商学院',
        'capacity': 50,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 257,
        'name': '华家池中心南楼426',
        'capacity': 60,
        'type': '校外',
        'campus': '华家池校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 258,
        'name': '书香世家酒店',
        'capacity': 36,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 259,
        'name': '维也纳酒店11楼',
        'capacity': 60,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 260,
        'name': '华家池教学楼305',
        'capacity': 60,
        'type': '校内',
        'campus': '华家池校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 261,
        'name': '教学主楼802',
        'capacity': 65,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 262,
        'name': '紫金校区经济学院120会议室',
        'capacity': 100,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 263,
        'name': '舟山校区',
        'capacity': 60,
        'type': '校外',
        'campus': '舟山校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 264,
        'name': '西溪校区教学主楼303教室',
        'capacity': 70,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 265,
        'name': '灵隐宾馆负一楼会议室',
        'capacity': 70,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 266,
        'name': '教学主楼801',
        'capacity': 60,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 267,
        'name': '西二322教室',
        'capacity': 80,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 268,
        'name': '主楼806',
        'capacity': 80,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 269,
        'name': '西溪智选假日酒店',
        'capacity': 200,
        'type': '校外',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 270,
        'name': '西溪-教学主楼301室',
        'capacity': 70,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 271,
        'name': '教学主楼806教室',
        'capacity': 70,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 272,
        'name': '教学主楼806',
        'capacity': 70,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 273,
        'name': '西溪智选假日酒店会场',
        'capacity': 150,
        'type': '校外',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 274,
        'name': '玉泉饭店3楼多功能厅',
        'capacity': 100,
        'type': '校外',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 275,
        'name': '湖光饭店',
        'capacity': 60,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 276,
        'name': '紫云饭店二楼紫云厅',
        'capacity': 100,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 277,
        'name': '紫云饭店',
        'capacity': 100,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 278,
        'name': '紫荆港-圆正启真-四楼梨洲厅',
        'capacity': 60,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 279,
        'name': '伊美大酒店-17楼1号会议室',
        'capacity': 60,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 280,
        'name': '伊美大酒店',
        'capacity': 50,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 281,
        'name': '金都三楼第一会议室',
        'capacity': 70,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 282,
        'name': '浙江世贸君澜大饭店5楼国际厅',
        'capacity': 200,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 283,
        'name': '浙江金都宾馆三楼多功能厅',
        'capacity': 200,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 284,
        'name': '紫金港-圆正启真三楼启真厅',
        'capacity': 400,
        'type': '校外',
        'campus': '紫金港校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 285,
        'name': '紫金港-圆正启真三楼求是厅',
        'capacity': 120,
        'type': '校外',
        'campus': '紫金港校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 286,
        'name': '五鑫宾馆',
        'capacity': 60,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 287,
        'name': '紫金港-圆正启真四楼求是厅',
        'capacity': 120,
        'type': '校外',
        'campus': '紫金港校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 288,
        'name': '圆正西溪宾馆',
        'capacity': 80,
        'type': '校外',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 289,
        'name': '浙江世贸君澜大饭店3楼嘉禾厅',
        'capacity': 150,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 290,
        'name': '金都宾馆3楼会议室',
        'capacity': 150,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 291,
        'name': '西溪-邵科馆301室',
        'capacity': 65,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 292,
        'name': '西溪-邵科馆209室',
        'capacity': 200,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 293,
        'name': '西溪-西二101室',
        'capacity': 50,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 294,
        'name': '玉泉-生仪楼一楼报告厅',
        'capacity': 80,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 295,
        'name': '玉泉-教七604室',
        'capacity': 91,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 296,
        'name': '玉泉-教七408室',
        'capacity': 91,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 297,
        'name': '玉泉-教七404室',
        'capacity': 91,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 298,
        'name': '玉泉-教七406室',
        'capacity': 190,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 299,
        'name': '玉泉-教七402室',
        'capacity': 91,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 300,
        'name': '玉泉-教七308室',
        'capacity': 58,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 301,
        'name': '玉泉-教七306室',
        'capacity': 120,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 302,
        'name': '玉泉-教七304室',
        'capacity': 72,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 303,
        'name': '玉泉-教七302室',
        'capacity': 62,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 304,
        'name': '玉泉-教七204室',
        'capacity': 91,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 305,
        'name': '玉泉-教七202室',
        'capacity': 91,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 306,
        'name': '玉泉-教七106室',
        'capacity': 190,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 307,
        'name': '玉泉-教七104室',
        'capacity': 91,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 308,
        'name': '玉泉-教七102室',
        'capacity': 91,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 309,
        'name': '玉泉-教十一512室',
        'capacity': 54,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 310,
        'name': '玉泉-教十一517室',
        'capacity': 54,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 311,
        'name': '玉泉-教十一513室',
        'capacity': 54,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 312,
        'name': '玉泉-教十二507',
        'capacity': 60,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 313,
        'name': '玉泉-教十二505室',
        'capacity': 56,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 314,
        'name': '玉泉-教四426室',
        'capacity': 108,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 315,
        'name': '玉泉-教四410室',
        'capacity': 122,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 316,
        'name': '玉泉-教四406室',
        'capacity': 124,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 317,
        'name': '玉泉-教四404室',
        'capacity': 124,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 318,
        'name': '玉泉-教四401室',
        'capacity': 180,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 319,
        'name': '玉泉-教四301室',
        'capacity': 180,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 320,
        'name': '玉泉-教一234室',
        'capacity': 288,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 321,
        'name': '玉泉-外经贸楼601室',
        'capacity': 24,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 322,
        'name': '玉泉-外经贸楼520室',
        'capacity': 92,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 323,
        'name': '玉泉-外经贸楼101室',
        'capacity': 90,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 324,
        'name': '玉泉-外经贸楼117室',
        'capacity': 107,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 325,
        'name': '玉泉-外经贸楼115室',
        'capacity': 108,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 326,
        'name': '玉泉-外经贸楼614室',
        'capacity': 113,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 327,
        'name': '玉泉-外经贸楼606室',
        'capacity': 41,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 328,
        'name': '玉泉-外经贸楼610室',
        'capacity': 113,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 329,
        'name': '紫金港-经济学院大楼920会议室',
        'capacity': 8,
        'type': '校内',
        'campus': '紫金港校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 330,
        'name': '紫金港-经济学院大楼820会议室',
        'capacity': 16,
        'type': '校内',
        'campus': '紫金港校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 331,
        'name': '紫金港-经济学院大楼720会议室',
        'capacity': 16,
        'type': '校内',
        'campus': '紫金港校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 332,
        'name': '紫金港-经济学院大楼620会议室',
        'capacity': 16,
        'type': '校内',
        'campus': '紫金港校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 333,
        'name': '紫金港-经济学院大楼520会议室',
        'capacity': 16,
        'type': '校内',
        'campus': '紫金港校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 334,
        'name': '紫金港-经济学院大楼213会议室',
        'capacity': 35,
        'type': '校内',
        'campus': '紫金港校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 335,
        'name': '紫金港-经济学院大楼203会议室',
        'capacity': 28,
        'type': '校内',
        'campus': '紫金港校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 336,
        'name': '紫金港-经济学院大楼201会议室',
        'capacity': 83,
        'type': '校内',
        'campus': '紫金港校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 337,
        'name': '紫金港-经济学院大楼121会议室',
        'capacity': 78,
        'type': '校内',
        'campus': '紫金港校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 338,
        'name': '紫金港-经济学院大楼120会议室',
        'capacity': 126,
        'type': '校内',
        'campus': '紫金港校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 339,
        'name': '紫金港-经济学院大楼118会议室',
        'capacity': 320,
        'type': '校内',
        'campus': '紫金港校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 340,
        'name': '紫金港-经济学院大楼116会议室',
        'capacity': 27,
        'type': '校内',
        'campus': '紫金港校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 341,
        'name': '紫金港-经济学院大楼113会议室',
        'capacity': 24,
        'type': '校内',
        'campus': '紫金港校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 342,
        'name': '紫金港-经济学院大楼115会议室',
        'capacity': 28,
        'type': '校内',
        'campus': '紫金港校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 343,
        'name': '紫金港-经济学院大楼111会议室',
        'capacity': 27,
        'type': '校内',
        'campus': '紫金港校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 344,
        'name': '紫金港-经济学院大楼109会议室',
        'capacity': 28,
        'type': '校内',
        'campus': '紫金港校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 345,
        'name': '华家池-教学楼503室',
        'capacity': 50,
        'type': '校内',
        'campus': '华家池校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 346,
        'name': '华家池-教学楼403室',
        'capacity': 35,
        'type': '校内',
        'campus': '华家池校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 347,
        'name': '华家池-教学楼402室',
        'capacity': 108,
        'type': '校内',
        'campus': '华家池校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 348,
        'name': '华家池-教学楼313室',
        'capacity': 180,
        'type': '校内',
        'campus': '华家池校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 349,
        'name': '金都宾馆',
        'capacity': 100,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 350,
        'name': '思耐酒店三楼舒心厅',
        'capacity': 100,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 351,
        'name': '紫金港-圆正启真四楼梨洲厅',
        'capacity': 60,
        'type': '校外',
        'campus': '紫金港校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 352,
        'name': '紫金港-圆正启真四楼阳明厅',
        'capacity': 60,
        'type': '校外',
        'campus': '紫金港校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 353,
        'name': '杭州银星饭店2楼会议室银海厅',
        'capacity': 100,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 354,
        'name': '五鑫宾馆4楼会议室',
        'capacity': 60,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 355,
        'name': '紫金港-校友楼西溪厅',
        'capacity': 60,
        'type': '校内',
        'campus': '紫金港校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 356,
        'name': '紫金港-蒙民伟楼139室',
        'capacity': 200,
        'type': '校内',
        'campus': '紫金港校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 357,
        'name': '华家池-中心南楼353室',
        'capacity': 80,
        'type': '校内',
        'campus': '华家池校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 358,
        'name': '华家池-中心南楼251室',
        'capacity': 80,
        'type': '校内',
        'campus': '华家池校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 359,
        'name': '华家池-中心南楼229室',
        'capacity': 57,
        'type': '校内',
        'campus': '华家池校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 360,
        'name': '锦华苑宾馆518会议室',
        'capacity': 60,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 361,
        'name': '东海宾馆三号楼一楼多功能厅',
        'capacity': 50,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 362,
        'name': '玉泉-永谦活动中心三楼报告厅',
        'capacity': 100,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 363,
        'name': '西溪-西三301室',
        'capacity': 60,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 364,
        'name': '玉泉饭店三楼会议室',
        'capacity': 60,
        'type': '校外',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 365,
        'name': '西溪-教学主楼426室',
        'capacity': 64,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 366,
        'name': '玉泉-永谦活动中心二楼报告厅',
        'capacity': 80,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 367,
        'name': '西溪-邵科馆207报告厅',
        'capacity': 300,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 368,
        'name': '西溪-教学主楼539室',
        'capacity': 60,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 369,
        'name': '紫金港-蒙民伟楼138室',
        'capacity': 80,
        'type': '校内',
        'campus': '紫金港校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 370,
        'name': '华家池-教学楼504室',
        'capacity': 50,
        'type': '校内',
        'campus': '华家池校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 371,
        'name': '西溪-教学主楼203室',
        'capacity': 60,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 372,
        'name': '玉泉-邵科馆212室',
        'capacity': 60,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 373,
        'name': '华家池-教学楼508室',
        'capacity': 94,
        'type': '校内',
        'campus': '华家池校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 374,
        'name': '华家池-教学楼607室',
        'capacity': 106,
        'type': '校内',
        'campus': '华家池校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 375,
        'name': '华家池-中心南楼328室',
        'capacity': 70,
        'type': '校内',
        'campus': '华家池校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 376,
        'name': '华家池-教学楼602室',
        'capacity': 106,
        'type': '校内',
        'campus': '华家池校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 377,
        'name': '玉泉-教二204室',
        'capacity': 70,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 378,
        'name': '华家池-教学楼312室',
        'capacity': 100,
        'type': '校内',
        'campus': '华家池校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 379,
        'name': '华家池-中心南楼171室',
        'capacity': 60,
        'type': '校内',
        'campus': '华家池校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 380,
        'name': '华家池-中心南楼453室',
        'capacity': 70,
        'type': '校内',
        'campus': '华家池校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 381,
        'name': '西溪-西一405室',
        'capacity': 165,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 382,
        'name': '华家池-教学楼311室',
        'capacity': 180,
        'type': '校内',
        'campus': '华家池校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 383,
        'name': '西溪-西二322室',
        'capacity': 100,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 384,
        'name': '紫金港-建工学院多功能报告厅',
        'capacity': 100,
        'type': '校内',
        'campus': '紫金港校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 385,
        'name': '百合花酒店4楼会场',
        'capacity': 150,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 386,
        'name': '紫金港-小剧场',
        'type': '校内',
        'campus': '紫金港校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 387,
        'name': '华家池-教学楼401室',
        'capacity': 108,
        'type': '校内',
        'campus': '华家池校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 388,
        'name': '华家池-教学楼605室',
        'capacity': 70,
        'type': '校内',
        'campus': '华家池校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 389,
        'name': '华家池-教学楼608室',
        'capacity': 100,
        'type': '校内',
        'campus': '华家池校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 390,
        'name': '华家池-教学楼505室',
        'capacity': 65,
        'type': '校内',
        'campus': '华家池校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 391,
        'name': '华家池-教学楼501室',
        'capacity': 116,
        'type': '校内',
        'campus': '华家池校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 392,
        'name': '华家池-教学楼604室',
        'capacity': 60,
        'type': '校内',
        'campus': '华家池校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 393,
        'name': '华家池-教学楼408室',
        'capacity': 60,
        'type': '校内',
        'campus': '华家池校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 394,
        'name': '玉泉-周亦卿一楼报告厅',
        'capacity': 120,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 395,
        'name': '华家池-中心南楼320室',
        'capacity': 60,
        'type': '校内',
        'campus': '华家池校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 396,
        'name': '华家池-教学楼509室',
        'capacity': 80,
        'type': '校内',
        'campus': '华家池校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 397,
        'name': '华家池-教学楼502室',
        'capacity': 60,
        'type': '校内',
        'campus': '华家池校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 398,
        'name': '华家池-教学楼506室',
        'capacity': 47,
        'type': '校内',
        'campus': '华家池校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 399,
        'name': '西溪-西一505室',
        'capacity': 100,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 400,
        'name': '周亦卿科技大楼112室',
        'capacity': 100,
        'type': '校内',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 401,
        'name': '玉泉-教四412室',
        'capacity': 124,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 402,
        'name': '玉泉-教四428室',
        'capacity': 106,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 403,
        'name': '玉泉-教四304室',
        'capacity': 126,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 404,
        'name': '玉泉-教三201室',
        'capacity': 340,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 405,
        'name': '玉泉-教七楼影视厅',
        'capacity': 150,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 406,
        'name': '西溪-一源咖啡厅',
        'capacity': 50,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 407,
        'name': '玉泉-外经贸楼113室',
        'capacity': 60,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 408,
        'name': '玉泉-外经贸楼602室',
        'capacity': 60,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 409,
        'name': '玉泉-教七602室',
        'capacity': 60,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 410,
        'name': '玉泉-曹光彪二期107室',
        'capacity': 60,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 411,
        'name': '玉泉-教三301室',
        'capacity': 60,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 412,
        'name': '玉泉-教四302室',
        'capacity': 60,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 413,
        'name': '玉泉-教七208室',
        'capacity': 100,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 414,
        'name': '百瑞酒店8楼花港厅会议室',
        'capacity': 60,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 415,
        'name': '玉泉-曹光彪二期103室',
        'capacity': 130,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 416,
        'name': '西溪-西二350室',
        'capacity': 50,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 417,
        'name': '玉泉校区教4-404',
        'capacity': 65,
        'type': '校外',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 418,
        'name': '紫金港-南华园二楼会场',
        'capacity': 50,
        'type': '校内',
        'campus': '紫金港校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 419,
        'name': '玉泉-外经贸楼508室',
        'capacity': 80,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 420,
        'name': '华家池-中心南楼436室',
        'capacity': 70,
        'type': '校内',
        'campus': '华家池校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 421,
        'name': '玉泉-教七504室',
        'capacity': 65,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 422,
        'name': '华家池-教学楼601室',
        'capacity': 70,
        'type': '校内',
        'campus': '华家池校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 423,
        'name': '玉泉-教四402室',
        'capacity': 60,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 424,
        'name': '玉泉-教七502室',
        'capacity': 70,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 425,
        'name': '玉泉-教四306室',
        'capacity': 70,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 426,
        'name': '西溪-西二216室',
        'capacity': 80,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 427,
        'name': '玉泉-邵科馆211室',
        'capacity': 60,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 428,
        'name': '玉泉-外经贸楼605室',
        'capacity': 180,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 429,
        'name': '玉泉-图书馆210报告厅',
        'capacity': 200,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 430,
        'name': '玉泉-邵科馆210室',
        'capacity': 60,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 431,
        'name': '玉泉-邵科馆117报告厅',
        'capacity': 230,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 432,
        'name': '华家池-中心南楼455室',
        'capacity': 60,
        'type': '校内',
        'campus': '华家池校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 433,
        'name': '西溪-教学主楼103室',
        'capacity': 60,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 434,
        'name': '西溪-教学主楼806室',
        'capacity': 80,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 435,
        'name': '西溪-西三324室',
        'capacity': 160,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 436,
        'name': '西溪-教学主楼101室',
        'capacity': 50,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 437,
        'name': '西溪-教学主楼303室',
        'capacity': 70,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 438,
        'name': '西溪-西二332室',
        'capacity': 60,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 439,
        'name': '西溪-艺术楼D102室',
        'capacity': 200,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 440,
        'name': '西溪-教学主楼201室',
        'capacity': 60,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 441,
        'name': '瑞豪中心酒店13楼会议室',
        'capacity': 80,
        'type': '校外',
        'campus': '其他',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 442,
        'name': '西溪-西三224室',
        'capacity': 150,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 443,
        'name': '西溪-西三124室',
        'capacity': 150,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 444,
        'name': '玉泉-外经贸楼501室',
        'capacity': 50,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 445,
        'name': '玉泉-外经贸楼401室',
        'capacity': 50,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 446,
        'name': '玉泉-外经贸楼605-2室',
        'capacity': 80,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 447,
        'name': '玉泉-外经贸楼605-1室',
        'capacity': 80,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 448,
        'name': '玉泉-外经贸楼505室',
        'capacity': 60,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 449,
        'name': '玉泉-外经贸楼408室',
        'capacity': 70,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 450,
        'name': '玉泉-外经贸楼506室',
        'capacity': 80,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 451,
        'name': '西溪-邵科馆210室',
        'capacity': 82,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 452,
        'name': '西溪-邵科馆117室',
        'capacity': 102,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 453,
        'name': '西溪-教学主楼801室',
        'capacity': 56,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 454,
        'name': '西溪-教学主楼802室',
        'capacity': 64,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 455,
        'name': '西溪-艺术楼D101室',
        'capacity': 150,
        'type': '校内',
        'campus': '西溪校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 456,
        'name': '玉泉-外经贸楼340室',
        'capacity': 80,
        'type': '校内',
        'campus': '玉泉校区',
        'address': '',
        'price': None,
        'status': '可用',
        'created_at': datetime(2026, 1, 1)
    }
]

teaching_sites = [
    {
        'id': 1,
        'name': '梦想小镇＋西顾',
        'type': '美丽乡村',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '西顾视频从事DIVE，即深度沉浸式内容与技术研发制作 ，在3D VR及6DoF视频制作技术行业领先。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 2,
        'name': '龙坞茶镇',
        'type': '科技创新',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '龙坞茶镇位于杭州西南，绕城公路穿镇而过，离杭州市中心约15公里，四周群山环绕，茶园茶山连绵起伏，是西湖龙井最大产区，素有“万担茶乡”之称，初步规划用地面积217.26公顷，建筑面积78.59万平方米，主要发展茶产业+旅游业。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 3,
        'name': '浙江省国有资本运营有限公司',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '浙江省国有资本运营有限公司成立于2007年02月15日，注册地位于浙江省杭州市求是路8号公元大厦北楼25楼，法定代表人为桑均尧。包括投资与投资管理及咨询服务，资产管理与处置，股权管理，股权投资基金管理，金融信息服务。（未经金融等监管部门批准，不得从事向公众融资存款、融资担保、代客理财等金融服务）（依法须经批准的项目，经相关部门批准后方可开展经营活动）。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 4,
        'name': '杭钢集团',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '杭州钢铁集团公司是一家以钢铁为主业，多元发展的大型企业集团，是世界500强企业，有职工1.69万人，总资产290.72亿元，全资及控股子公司41家。其中杭州钢铁股份有限公司为上市公司。半山钢铁基地产铁231.01万吨、产钢331.80万吨、钢材342.24万吨、焦碳51.58万吨。杭钢大力实施“钢铁主导、适度多元、创新应变、做大做强”的发展战略，已形成以钢铁为主业，房地产、贸易流通、酒店餐饮、环境',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 5,
        'name': '浙大党建馆',
        'type': '红色教育',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '浙江大学党建馆位于学校地标建筑求是大讲堂，占地面积800余平方米，充分发挥地处浙江“三个地”和“重要窗口”的独特优势，由“红船起航主题展”和“心怀‘国之大者’ 奋力‘走在前列’——浙江大学学思践悟习近平总书记系列重要指示精神办学成果展”构成，突出思想性、紧扣主旋律、营造现场感。“红船起航主题展”与南湖革命纪念馆共建，将红船精神引入校园，是学校开展“四史”教育的重要载体。“心怀‘国之大者’ 奋力‘走',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 6,
        'name': '杭州国际博览中心',
        'type': '其他',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '杭州国际博览中心，坐落于钱塘江南岸、萧山区钱江世纪城、杭州奥体博览城核心区 [43] ；场馆设计兼具江南意蕴与现代简约 [44] ；2016年9月4-5日，为G20杭州峰会主会场。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 7,
        'name': '平湖经济技术开发区',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '国家级平湖经济技术开发区位于浙江省平湖市西北角，距离市中心仅3公里，是省级信息产业特色园区、全省唯一一个经省政府批准的日商投资区、国家（嘉兴）机电元件产业园和国家火炬计划平湖光机电产业基地核心区，也是浙江省乃至全国日资企业最集聚的开发区之一。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 8,
        'name': '绍兴退役军人事务所',
        'type': '其他',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '绍兴退役军人事务所',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 9,
        'name': '翠苑社区',
        'type': '美丽乡村',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '翠苑一区面积0.21平方公里，居民3110户，常住人口近万人。2002年5月成立杭州首家社区党委，现下设12个党支部，共有党员285名，先后荣获“全国先进基层党组织”等50余项市级以上荣誉。2003年，时任浙江省委书记的习近平同志多次亲临翠苑一区社区指导工作。长期以来，按照习近平总书记提出的“民有所呼，我有所应，民有所呼，我有所为”的要求，社区从成立老年食堂解决老年人吃饭问题，到建立社区“邻里之家',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 10,
        'name': '浙商博物馆',
        'type': '红色教育',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '浙商博物馆',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 11,
        'name': '银湖街道坑西村',
        'type': '美丽乡村',
        'supplier': '潘秀珠',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '坑西村地理位置、交通优势明显。近年来，依托村内万亩茶园、千亩石林、百亩荷花塘等丰富的自然资源、人文景观，发展美丽乡村，壮大美丽经济，在外界的知名度越来越高。坑西村与浙江永耀旅游文化发展有限公司合作正在推进的坑西温泉旅游度假区项目，总投资约16.8亿元，引起了极大的关注，将致力打造中国温泉文化第一乡、国家级旅游度假区、国家4A级景区、省级旅游风情小镇。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 12,
        'name': '桃园村',
        'type': '红色教育',
        'supplier': '潘秀珠',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '槜李产业是桃园村的特色产业，桃园村也因槜李成为第八批全国“一村一品”示范村、中国美丽乡村百家范例、浙江省美丽乡村特色精品村、省AA级景区村庄、 省级中心村、省级历史文化村、省级生态文化基地等一项项荣誉也展示出了桃园村的不懈努力。依托槜李文化与美丽乡村建设深度融合，眼下，“槜李+文化+旅游”为主导的产业框架已经形成。桃园村坚持以党建为引领，在槜李合作社的基础上成立桃园村槜李合作社支部，以党员为带动，',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 13,
        'name': '桐乡市越丰村',
        'type': '红色教育',
        'supplier': '潘秀珠',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '越丰村位于浙江桐乡开发区(高桥街道)东南部，具有高速高铁“双门户”优势，地理位置优越。全村区域面积3.33平方公里，辖26个村民小组，农户751户，总人口3071人。2020年农民人均收入3.99万元，村经常性收入313万元。2013年以来，为解决社会问题增多、矛盾纠纷多发等困扰，桐乡市坚持党建引领基层社会治理，在高桥街道越丰村率先开展自治、法治、德治融合的基层社会治理探索实践。越丰村建立“一约两',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 14,
        'name': '京杭大运河',
        'type': '文化考察',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '京杭大运河始建于春秋时期，是世界上里程最长、工程最大的古代运河，也是最古老的运河之一，与长城、坎儿井并称为中国古代的三项伟大工程，并且使用至今，是中国古代劳动人民创造的一项伟大工程，是中国文化地位的象征之一。大运河南起余杭（今杭州），北到涿郡（今北京），途经今浙江、江苏、山东、河北四省及天津、北京两市，贯通海河、黄河、淮河、长江、钱塘江五大水系，主要水源为微山湖，大运河全长约1794公里。 运河对',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 15,
        'name': '小河直街历史文化街区',
        'type': '文化考察',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '小河直街历史文化街区位于杭州市北部，地处京杭大运河、小河、余杭塘河三河交汇处。东临小河，西临和睦路，南临小河路，北临长征桥路。小河直街历史文化街区以小河直街为中心，沿运河、小河分布的民居和航运设施整体风貌和空间特征仍基本保存，具有一定的规模，在杭州市历史文化街区中应属于整体传统风貌较为完整的街区之一。街区真实地反映了清末、民国初年运河沿线下层人民的生活环境，保留着一定数量的历史建筑，其建筑特色、街',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 16,
        'name': '杭州市职工文化中心和工人文化宫',
        'type': '政务考察',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '杭州市工人文化宫，成立于1951年3月。内设机构包括文艺部、培训部、活动中心、影剧厅、办公室、行政部等。下设杭州职工艺术协会、职工摄影家协会、职工书画协会、杭州印友会及职工合唱团、京剧团、越剧团、民乐团、灯谜研究会等协会，拥有千余人业余文化艺术爱好者队伍。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 17,
        'name': '浦江新光村',
        'type': '美丽乡村',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '新光村，浙江省金华市浦江县虞宅乡下辖行政村，中国传统村落，位于金华山脉的群山之中，村域面积5平方公里。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 18,
        'name': '绍兴周恩来纪念馆',
        'type': '红色教育',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '绍兴周恩来纪念馆位于浙江省绍兴市区劳动路，截至2019年8月19日，占地面积达5500余平方米，建筑面积3200余平方米，于1984年开放，是国家AAA级景区、浙江省文物保护单位和爱国主义教育基地。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 19,
        'name': '嘉兴平湖市综合行政执法局',
        'type': '政务考察',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '嘉兴平湖市综合行政执法局“综合查一次”还将“大综合一体化”执法监管数字应用和“城市慧治”指挥协调体系协同，实现“数字指挥，一屏掌控”，实现了执法线上线下的连通指挥。在平湖市综合行政执法局的数字化城市管理指挥中心，“城市慧治”系统中实时展现执法人员的现场执法情况，指挥中心工作人员则根据现场执法情况进行指挥调度，线上线下融合，进一步提高了执法效能。平湖市将在“城市慧治”平台的基础上，将“大综合一体化”',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 20,
        'name': '新光村',
        'type': '美丽乡村',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '浙江省金华市浦江县虞宅乡下辖行政村，中国传统村落，位于金华山脉的群山之中，村域面积5平方公里。 新光村，以四进厅堂为中轴线，以中央八卦型向四周扩展，东西分裂六幢厢房，厅厢共78间，两横两纵的街巷，成为一个大井字。新光村在金华山脉的群山之中，有茜溪环绕全村，村口的金鱼山，首尾着茜溪，犹如金鱼在溪中游，金鱼头着水的地方叫雷公坎，金鱼的口在水下，当时的水深达两米左右，溪鱼有近两尺长。朱宅（新光村）境内，',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 21,
        'name': '李祖村',
        'type': '美丽乡村',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '浙江“千万工程”经验，义乌市美丽乡村建设的标杆，浙江省美丽乡村精品村、国家森林乡村、浙江省美丽宜居示范村、金华市传统村落、全国文明村镇。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 22,
        'name': '浙江文镁科技有限公司',
        'type': '科技创新',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '浙江文镁科技有限公司成立于2020年，坐落于杭州市萧山机器人小镇，是一个基于镁、铝轻金属及碳基新材料，重点围绕机器人、特种装备、日常用品领域的轻量化需求，提供从轻质材料、工业设计、产业服务、产品研发销售一站式轻量化解决方案的应用科创平台。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 23,
        'name': '传化集团+海康威视',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '传化集团+海康威视',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 24,
        'name': '海宁盐官',
        'type': '文化考察',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '海宁盐官镇是个有两千多年历史的古镇，早在我国的汉代便开始晒盐制盐，因此得名盐官镇。唐宣宗大中年间，（847年—859年）李忱在做了十四年皇帝后，终于看破了世间的滚滚红尘，自愿放弃了锦衣玉食的皇位，甘愿来在盐官镇削发为僧，他圆寂后的灵塔至今还在盐官镇上屹立。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 25,
        'name': '余杭径山',
        'type': '文化考察',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '径山云雾茶为全国名茶，享誉中外。径山与日本有着源远流长的友好史，是日本临济宗的祖庭，日本"茶道”也源于径山”茶宴。径山东南有余杭古镇，已有二千余历史，镇上有双塔、水城门、通济桥、安乐山等景点。镇西新建京航乐园，人称"小西湖”，景色宜人，其内有杨乃武与小白菜冤案资料陈列室。杨乃武墓、小白菜墓及出家处均在镇境。镇东仓前镇有章太炎故居陈列室。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 26,
        'name': '长兴县融媒体中心',
        'type': '美丽乡村',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '2021年12月18日，长兴县融媒体中心入选2021全国县级融媒体中心能力建设十大典型案例。，长兴县融媒体中心坚守融媒责任、坚定创新引领，依托现有融媒矩阵平台资源，充分将已有资源纳入应急广播体系建设中，探索多渠道、多终端、全覆盖的立体化传播路径，实现全域18个乡镇、2046个自然村（20户以上）全覆盖，推动县域应急管理能力和社会治理水平不断提升，彰显了应急广播的长兴特色。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 27,
        'name': '中共一大会址',
        'type': '红色教育',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '中共一大会址是出席中共“一大”的上海代表李汉俊之兄李书城的住所，为一座石库门式楼房。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 28,
        'name': '东信和创园',
        'type': '文化考察',
        'supplier': '李亚方',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '杭州东信和创园位于杭州市留和路，是由一片老厂房改造而成的，共有61幢房子和上千棵高大的乔木，是杭州是内一个比较文艺的地方。走进东信和创园，映入眼帘的就是改造后的厂房，极具艺术感，这里云集了文艺店铺、展厅和工作室，有着古老的建筑风格，这些建筑多为20世纪五六十年代，艺术气息浓郁，每一个细节都向人们展示着这条街区的历史文化。在园内随处可见的文艺店铺，商品琳琅满目，每家店铺都具有自己独特的魅力和思想，风',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 29,
        'name': '余杭塘栖村',
        'type': '美丽乡村',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '教学主题：塘栖村位于古镇塘栖的中东部，是塘栖镇中心区的重要组  成部分，2018 全村集体经营性收入达 700 万元，人均年收入 41860 元， 村资产总计 1.12 亿元。村区域范围内有大小企业 21 家，枇杷采摘园  区 1100 亩。村两委积极争创各类先进，已先后获得了全国民主法治村、 无邪教示范村，省级美丽宜居示范村、3A 级景区村庄、生态文化基地、 体育小康示范村、卫生村、先进妇女组织',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 30,
        'name': '杭州民生药业有限公司',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '杭州民生药业有限公司',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 31,
        'name': '吴山清风廉政+虎跑',
        'type': '红色教育',
        'supplier': '潘秀珠',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '吴山，位于杭城南部，钟灵毓秀、人文荟萃，现存有历代清官廉吏相关的历史遗迹有二十余处。作为杭州市纪委重点打造的独具杭州特色廉政文化教育基地，吴山清风廉政文化教育专线深挖以“三杰一说”为核心的吴山廉政文化资源，积极开展“有景物可看，有内容可听，有先贤可借鉴，有经验可学”形式多样的廉政文化教育。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 32,
        'name': '中共一大会址+金茂大厦',
        'type': '红色教育',
        'supplier': '潘秀珠',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '中共一大会址纪念馆（中国共产党第一次全国代表大会会址纪念馆），简称中共一大纪念馆，位于上海市黄浦区黄陂南路374号，占地面积1300余平方米，隶属上海市文物管理委员会，是一所社会科学类历史遗址专题博物馆。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 33,
        'name': '浙江中控技术股份有限公司',
        'type': '企业参访',
        'supplier': '潘秀珠',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '是中国领先的自动化与信息化技术、产品与解决方案供应商，',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 34,
        'name': '西溪湿地',
        'type': '美丽乡村',
        'supplier': '潘秀珠',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '浙江杭州西溪国家湿地公园位于浙江省杭州市西湖区和余杭区西北部，距西湖不到5千米，规划总面积11.5平方千米，湿地内河流总长100多千米，约70%的面积为河港、池塘、湖漾、沼泽等水域。湿地公园内生态资源丰富、自然景观幽雅、文化积淀深厚，与西湖、西泠并称杭州“三西”。是中国第一个集城市湿地、农耕湿地、文化湿地于一体的国家级湿地公园。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 35,
        'name': '南浔古镇+湖州新四军苏浙军区旧址',
        'type': '红色教育',
        'supplier': '潘秀珠',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '南浔古镇位于湖州市南浔区，地处江浙两省交界处。明清时期为江南蚕丝名镇，是一个人文资源充足、中西建筑合璧的江南古镇。当年的苏浙军区司令部旧址、粟裕宿舍和办公室、苏浙公学、兵工 厂等 15 处建筑旧址保存完好，全面反映了苏浙军区打击日伪顽， 建设根据地，吸收和训练进步青年，宣传抗日思想的中流砥柱作用， 全景勾勒了“江南小延安”的火热情景。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 36,
        'name': '柯岩+鲁迅故居',
        'type': '红色教育',
        'supplier': '潘秀珠',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '柯岩风景区',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 37,
        'name': '嘉兴南湖+西塘',
        'type': '红色教育',
        'supplier': '潘秀珠',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '嘉兴南湖革命纪念馆（嘉兴市） 嘉兴南湖是全国爱国主义教育示范基地，是中国共产党的诞生地。习近平同志在浙江工作期间，曾先后5次来到南湖革命纪念馆瞻仰红船。2005年6月，习近平同志在《光明日报》发表署名文章，首次提出“红船精神”，即“开天辟地、敢为人先的首创精神，坚定理想、百折不挠的奋斗精神，立党为公、忠诚为民的奉献精神”，深刻指出“红船精神”是中国革命精神之源，是党的先进性之源。2017年10月3',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 38,
        'name': '极氪智慧工厂',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '极氪智慧工厂',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 39,
        'name': '得力集团有限公司',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '得力集团有限公司',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 40,
        'name': '宁波臻至机械模具有限公司',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '宁波臻至机械模具有限公司',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 41,
        'name': '数澜科技',
        'type': '企业参访',
        'supplier': '潘秀珠',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '数澜坚持以“数据中台”作为核心战略构建和培养团队，目前成员 500+， 建成了以数据科学家、算法专家、数据产品专家、业务架构专家及数据处理专家为核心的人才队伍，核心团队成员均来自阿里、华为、金蝶等国内知名企业，是国内最早一批大数据服务创新实践者。截至目前，「数澜科技」已为万科集团、绿城服务、蓝光集团、旭辉集团、华泰证券、中国银保信、恒大人寿、大地保险、王府井、中信集团、长虹集团、宝马中国、好莱客、',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 42,
        'name': '星光未来农场',
        'type': '科技创新',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '星光农业发展有限公司位于南浔区旧馆镇港胡村，占地6000余亩，总投资2000万元，是一家综合性现代农企，致力于打造高品质粮油未来农场。农场立足机械强农、科技强农，以稳定粮食产量为前提，通过标准化种植、全程机械化作业提升粮食品质；采用“互联网+农业种植”，实现科学种植、病虫害绿色防治、农残资源化利用、农情监测和节水节肥；建立“公司+农户”模式，促进农业增产、农民增收，助力农业农村高质量发展，实现共同',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 43,
        'name': '长兴县龙溪村',
        'type': '红色教育',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '龙溪村是长兴县未来村居建设的首个试点村。2020年，龙溪村在县、乡两级政府的支持下推出了“未来乡村”数字化信息服务平台，以一图感知方式，实时掌握村庄动态。当年7月，投入40余万元完成议事协商数字化应用场景开发，“云上议事厅”上线运行。                              作为全国村级议事协商创新实验试点，龙溪村探索形成了“党建统领、靶向突破、数字赋能”的议事协商路径，打造了乡',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 44,
        'name': '桐庐法院',
        'type': '红色教育',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '用枫桥经验做法开展法院、政府部门、街道联动做好矛盾化解。桐庐法院富春江科技城人民法庭：调研人民法庭服务保障法治化营商环境相关工作及调研芦茨村共享法庭建设。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 45,
        'name': '三墩镇社会治安综合治理中心',
        'type': '红色教育',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '三墩镇综治中心以创新和发展“枫桥经验”为目标，把实现好、维护好、发展好人民群众的根本利益作为综治工作的出发点和落脚点。以“八无网格”创建为抓手，认真分析研究社会治安综合治理的薄弱方面，坚持“三必方针”，推进“五联一体”使全镇社会综合治理工作得以全面提升，社会治安形势明显好转。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 46,
        'name': '宵井村',
        'type': '美丽乡村',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '富阳市富春街道宵井村 ，位于该街道西端，东至执中亭村，南到方家井村，西南与新登镇昌东村隔岭相望，西至官山，北与春建乡上唐村隔山相望。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 47,
        'name': '菜鸟总部园区',
        'type': '科技创新',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '菜鸟成立于 2013 年，是一家客户价值驱动的全球化产业互联网公司。扎根在物流产业，把物流产业的运营、场景、设施和互联网技术做深度融合；菜鸟以科技创新为核心，在社区服务、全球物流、智慧供应链等领域建立了新赛道，为消费者和商家提供普惠优质服务，搭建了领先的全球化物流网络。长期投入为实体经济降本增效，保障民生流通，稳就业促增收，让物流更加绿色可持续；菜鸟致力于做一家服务国计民生的好公司。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 48,
        'name': '公益中学',
        'type': '文化考察',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '杭州市公益中学创办于1995年，是一所走读的公办初中，隶属于杭州市西湖区教育局。学校位于西湖区文二西路698号，西溪湿地东侧，现有28个教学班级，1300余名学生，104位教职工。学校围绕“让公益的孩子学并快乐着”的总目标开展工作。主张“先学做人，后学知识”，共建共享“相亲相爱公益人”的亲情文化，着力打造“做人第一、活教乐学” 两大品牌，倾力推重“老师开心教书，学生快乐学习，家长阳光育儿”的育人理',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 49,
        'name': '临安区行政服务中心',
        'type': '政务考察',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '临安区行政服务中心',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 50,
        'name': '安吉美丽乡村',
        'type': '美丽乡村',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '安吉余村、刘家塘村、尚书村、目莲坞村、天子湖镇南北湖村、马家弄村、高家堂村、横山坞村、鲁家村、剑山村、碧门村、夏阳村等。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 51,
        'name': '杭州市行政服务中心',
        'type': '政务考察',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '杭州市行政服务中心',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 52,
        'name': '浙江经贸职业技术学院',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '浙江经贸职业技术学院的前身是创办于1979年的浙江供销学校和创办于1984年的浙江省供销社职工学院；2002年，正式成立浙江经贸职业技术学院。2017年，毕业生职业发展状况及人才培养质量调查位居全省同类院校第三。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 53,
        'name': '浙江·中国国家版本馆杭州分馆',
        'type': '科技创新',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '杭州国家版本馆开馆展览分“潮起之江——‘重要窗口’主题版本展”、“文献之邦——江南版本文化概览”展、“盛世浙学——浙江文化研究工程成果展”、“千古风流——浙江历史文化名人展”四个主题展览，以及一个数字展厅。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 54,
        'name': '咪咕数媒',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '咪咕数媒的上级单位是中国移动旗下的咪咕文化公司。2014年，咪咕文化公司在北京成立，2015年旗下陆续设立了五大子公司，分别是咪咕视讯、咪咕互娱、咪咕音乐、咪咕数媒、咪咕动漫，其中咪咕数媒在杭州挂牌成立，其前身为2008年筹建的中国移动手机阅读基地。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 55,
        'name': '杭州市临平区新宇村',
        'type': '美丽乡村',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '杭州市临平区新宇村',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 56,
        'name': '富阳坑西村',
        'type': '美丽乡村',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '富阳坑西村，就曾遍布废弃矿山。10多年前，坑西村以开矿出名，最多时有7座矿山，还有4家沥青拌和场。整个村庄蓬头垢面，外人提到坑西村都会直摇头。近年来，在“绿水青山就是金山银山”发展理念指引下，村里关停了所有矿山，进行生态修复，“我们通过将废弃矿山、腾退厂房、周边山林、地质资源等资源集聚起来，并因地制宜开展矿山修复和矿地垦造、河道清淤，来助推坑西村全域景区化。”市规划资源局富阳分局相关负责人道，通过',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 57,
        'name': '安吉县梅溪镇',
        'type': '美丽乡村',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '“一个矿坑看看很简单，但由于历史的原因，往往主体多，产权关系复杂，在开展生态修复、安全维护时责任往往难以落实。如今，进行开发利用，呈现了发展的新机，多方主体利益平衡同样是个难题。”梅溪镇相关负责人，经过多方协调，镇里把所有矿权全部收回，既加强生态修复、安全管理，又积极创造条件加以保护利用、合理开发。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 58,
        'name': '青山村',
        'type': '美丽乡村',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '青山村的乡村建设之旅始于一个水源地保护项目，随着更多新村民的陆续加入，青山村的新旧资源得到了整合与促进，村庄焕发新生。在新老村民的众创共治下，青山村走出了一条以自然保护、生态旅游度假和文创传统手工艺为支柱的乡村振兴道路。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 59,
        'name': '绍兴市国动办（人防办）',
        'type': '其他',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '绍兴市国动办（人防办）',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 60,
        'name': '浙江省军区军史陈列馆',
        'type': '红色教育',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '浙江省军区由兵团级单位演变而来，历史厚重，英模璀璨。陈列馆展陈各类图板400余幅、革命文物200余件，详实记录了土地革命战争以来省军区部队从无到有、从小到大的发展历程，全面直观地展示省军区部队辉煌历史。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 61,
        'name': '桐乡市公安局+海宁市公安局',
        'type': '政务考察',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '桐乡市公安局+海宁市公安局（科技强警特色做法）',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 62,
        'name': '阿里云谷园',
        'type': '科技创新',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '【源起云上】讲述阿里云诞生之初对云计算的判断与思考',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 63,
        'name': '杭州市公安局滨江区分局',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '杭州市公安局滨江区分局因地制宜，创新警务管理形式，发挥科技之长弥补警力之缺，开创“警用机器人+无人机+智能岗亭”三合一巡防稳控一线智能作战单元，成为智慧警务中高端“新力量”全方位提高基层治安保障能力，全力护航辖区企业发展。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 64,
        'name': '枫桥派出所',
        'type': '红色教育',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '浙江省诸暨市枫桥派出所建立于1950年7月。“枫桥经验”源自枫桥，始于公安。自1963年11月毛泽东主席亲笔批示“枫桥经验”，到2019年11月全国首批“枫桥式公安派出所”的命名，再到2021年11月党的十九届六中全会《决议》中“坚持和发展新时代‘枫桥经验’”，58年来，在一代代枫桥人的见证下，枫桥派出所的公安民警不忘初心，砥砺前行，不断擦拭着“枫桥经验”这张金名片，扩充着“枫桥经验”的底蕴和内涵',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 65,
        'name': '杭州大捶文化发展有限公司',
        'type': '科技创新',
        'supplier': '吴如意',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '杭州大捶文化发展有限公司是一家互联网整合营销公司，是一站式新媒体多维整合数字营销服务商，字节跳动全国巨量一级代理商，抖音电商官方服务商。在直播电商、娱乐公会直播和短视频星图，品牌整案营销等多领域均具有广泛影响力。公司致力于为合作品牌提供整案服务、抖音直播建设，短视频商业化、一站式多维新媒体营销等全链路解决方案及专业服务，助力品牌布局和运营高效流量渠道，实现品牌降本增效，提升品牌知名度及市场份额。集',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 66,
        'name': '中国杭州人力资源服务产业园',
        'type': '企业参访',
        'supplier': '吴如意',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '中国杭州人力资源服务产业园是全省第一家、全国第五家国家级人力资源服务产业园。园区业态结构完善，入驻企业提供了涵盖人力资源招聘、人才派遣、高级人才寻访、人力资源外包服务、人力资源培训、人才测评、人力资源管理咨询、人力资源信息软件服务等专业化、全方位、多层次的人力资源服务，基本形成了较为完整的人力资源服务产业链。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 67,
        'name': '杭州抖音电商直播基地',
        'type': '企业参访',
        'supplier': '俞玲艳',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '参观基地园区、抖音电商直播间、选品间等，进行专题讲座，了解抖音官方授权直播基地运营模式、直播人才培养方向、直播电商趋势分析。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 68,
        'name': '余杭永安村',
        'type': '美丽乡村',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '永安村地处余杭区余杭街道东北面，2003年村规模调整由原永安村、姚村、下木桥村三村合并而成，下辖30个村民小组28个自然村，农户884户，人口3069人，拥有耕地5259亩，村域面积7.09平方公里。 　　永安村属基本农田保护区，无工业污染，绿化率达80%以上，濒临东苕溪，中苕溪穿村而行，原生态环境优美，空气清新怡人。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 69,
        'name': '杭州市公安局',
        'type': '政务考察',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '杭州市公安局是杭州市人民政府下设主管全市公安工作的职能部门，受杭州市人民政府和浙江省公安厅双重领导。各县（县级市）区设公安局（分局），在镇、乡、街道设派出所。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 70,
        'name': '海宁经济开发区',
        'type': '其他',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '海宁经济开发区成立于1992年，1997年被批准为省级开发区，2006年3月经国家审核通过。开发区管理委员会是市人民政府的派出机构，负责对开发区“统一领导、统一规划和统一管理”，并享有同级政府经济管理权限。2006年获长三角最具价值投资开发区第5位（综合实力第4位）。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 71,
        'name': '西塘古镇',
        'type': '文化考察',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '西塘古镇属浙江省嘉兴市嘉善县，地处江浙沪三省市交界处，地理位置优越。交通便捷，东距上海90公里，西距杭州110公里，北距苏州85公里。 西塘被国家文物局列入中国世界文化遗产预备名单，亦是中国首批历史文化名镇，国家AAAAA级旅游景区，获世界遗产保护杰出成就奖。西塘历史悠久，是古代吴越文化的发祥地之一。 2017年2月25日，新晋为国家5A级旅游景区。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 72,
        'name': '嘉兴物流园',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '嘉兴物流园，又称嘉兴市现代综合物流园区，由北区和南区两个物流功能区组成，规划控制面积约10000亩，其中南区约6000亩，北区约4000亩。北区背靠320国道，南区紧邻沪杭高速，申嘉湖高速和乍嘉苏高速，同时联通杭州湾跨海大桥。距乍嘉苏高速公路4号出入口、320国道、嘉兴客运中心（规划新址）约3公里；距沪杭高速公路王店出入口约6公里。拥有联接江浙沪“三纵三横三桥”便捷的高速公路网架：京杭运河、海河连',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 73,
        'name': '杭州湾大桥',
        'type': '其他',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '杭州湾跨海大桥（Hangzhou Bay Bridge），是中国浙江省境内连接嘉兴市和宁波市的跨海大桥，位于杭州湾海域之上，是沈阳—海口高速公路（国家高速G15）组成部分之一，也是浙江省东北部的城市快速路重要构成部分。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 74,
        'name': '宁波舟山港',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '宁波舟山港（Ningbo Zhoushan Port）是中国浙江省宁波市、舟山市港口，位于中国大陆海岸线中部、“长江经济带”的南翼，为中国对外开放一类口岸，中国沿海主要港口和中国国家综合运输体系的重要枢纽，中国国内重要的铁矿石中转基地、原油转运基地、液体化工储运基地和华东地区重要的煤炭、粮食储运基地；是服务长江经济带、建设舟山江海联运服务中心的核心载体，浙江海洋经济发展示范区和舟山群岛新区建设的重',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 75,
        'name': '杭州市交通运输局',
        'type': '其他',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '杭州市交通运输局是杭州市人民政府工作部门，为正局级。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 76,
        'name': '海宁红树林服饰有限公司',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '海宁红树林服饰有限公司，创立于2001年，旗下两大品牌 百味丽人 和 俏格 。位于浙江海宁市农业对外开发区。是一家集产品研发、规模生产、市场营销为一体的中型现代服装生产企业。拥有兄弟牌电脑圆头锁眼机、平头锁眼机、重机电脑套结机、重机电脑钉扣机、撬边机、双针平缝机、兄弟牌电脑平车、重机电脑平车等国内外知名生产设备500台套，公司员工600余人。旗下品牌 百味丽人 、 俏阁 产销全国各地。深受广大消费',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 77,
        'name': '杭州经济技术开发区',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '杭州经济技术开发区全年地区生产总值增长2.7%，规上工业增加值增长4.2%，服务业增加值增长0.8%。截至2020年底，累计批准设立外商投资企业1400余家，总投资超700亿美元；世界500强企业投资项目有75个。拥有全省最大的高教园区，坐落14所高校，拥有48个省部级重点实验室、82个省部级重点学科，集聚了中科院基础医学与肿瘤研究所等近30个国内外知名科研平台。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 78,
        'name': '杭州安厨电子商务有限公司',
        'type': '科技创新',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '杭州安厨电子商务有限公司创立于2013年，是农业产业服务的开创者和引领者，是一家专注于农业电商领域的互联网科技公司，致力于农业产业服务和数字乡村建设，为政府提供创新的服务产品和解决方案，帮助政府提升产业服务能力，实现数字化转型。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 79,
        'name': '萧山梅林村',
        'type': '美丽乡村',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '党山镇梅林村是党山镇规模最大的村之一，全村现有耕地1766亩，村民小组17个，人口2285人。梅林村充分利用地域经济特色和龙头带动作用，以中国包装龙头企业浙江爱迪尔包装集团公司为工业先导，带动卫浴、纺织、服装、五金等行业迅速崛起，打造具有村域经济特色的工业基地。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 80,
        'name': '桐庐县新时代文明实践中心',
        'type': '政务考察',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '在桐庐，新时代文明实践中心建设正逐渐从单向突破向系统集成深化、从阵地整合向功能拓展深化、从宣传文化系统“小循环”向融入经济社会发展和社会治理的“大循环”深化。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 81,
        'name': '安吉县新时代文明实践中心',
        'type': '其他',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '新时代文明实践中心是面向人民群众开展理论宣讲、主题教育、文化传承的有形新阵地，是提升思想觉悟、道德水平、文明素养的综合性宣传平台。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 82,
        'name': '杭州住房公积金中心',
        'type': '其他',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '杭州住房公积金中心为市政府直属的副局级事业单位，对全市住房公积金实行统一管理、统一制度、统一核算。受委托研究起草有关住房公积金管理的地方性法规、规章草案，经批准后组织实施；负责市住房公积金管理委员会有关政策和决定事项的落实工作。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 83,
        'name': '中国共产党杭州历史馆（杭州市方志馆）',
        'type': '红色教育',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '中国共产党杭州历史馆（杭州市方志馆）于2020年5月20日经过中共杭州市委机构编制委员会办公室批准正式合并，分为北山馆区和望江馆区，均为纯公益性免费场馆，隶属于中共杭州市委党史研究室（杭州市人民政府地方志办公室），规格为正处级，主要负责馆藏资料的征集、保管、展陈工作；提供党史、地方志和地情资料的咨询、查阅等公共服务工作；承担场馆展览、宣传教育和交流合作等工作。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 84,
        'name': '杭州西站',
        'type': '企业参访',
        'supplier': '吴峥',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '杭州西站位于中国浙江省杭州市，为中国铁路上海局集团有限公司管辖的铁路车站，是合杭高速铁路、杭温高速铁路的交汇车站，也是2022年杭州亚运会的配套交通保障工程。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 85,
        'name': '杭州党群服务中心',
        'type': '红色教育',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '杭州市党群服务中心是杭州党员群众“共同的家”，中心以“有困难找中心、要活动到中心、作奉献来中心”为出发点，通过与杭州智慧党建系统的线上线下联动，服务全市党员群众。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 86,
        'name': '萧山安防体验中心',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '萧山区安防体验中心区政府、区公安分局、区城投集团联合创建的，拥有“浙江最真实烟雾逃生体验”和最新前沿智慧安防技术。功能区块分为：一层是公共安全宣传体验、二层是消防安全宣传体验、三层是交通安全宣传体验和宣教室、四层是烟热通道逃生体验。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 87,
        'name': '南阳赭东村',
        'type': '科技创新',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '依托南阳young数字基层治理体系，赭东村形成了“1+4”科普工作模式，即一支科普志愿者队伍，四个科普阵地。通过数字平台信息发布、积分奖励等方式，激励群众积极参与科普活动，打通科普工作最后一公里。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 88,
        'name': '银江集团',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '银江集团是中国智慧产业领军企业，涵盖城市大脑运营、智慧产业投资、产业基地建设、创业孵化服务四大产业领域，拥有300余家成员企业及参股企业。其中登陆新三板及以上资本市场达50家以上。 目前银江集团已经获得中国服务业企业500强、中国民营企业500强、中国软件企业收入100强、中国第一批创业板上市企业、国家火炬计划重点高新技术企业、国家规划布局内重点软件企业、国家级科技企业孵化器等诸多荣誉。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 89,
        'name': '浙江博物馆',
        'type': '红色教育',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '浙江省博物馆始建于1929年，缘起于首届杭州西湖博览会，初名“浙江省西湖博物馆”，1976年更名为“浙江省博物馆”。2006年，浙江革命历史纪念馆归并浙江省博物馆管理。2009年武林馆区（包括浙江革命历史纪念馆）建成对外开放。经过九十余年的发展，浙江省博物馆（浙江革命历史纪念馆）已成为浙江省内规模最大的综合性人文科学博物馆，形成了包括孤山馆区、武林馆区、沙孟海旧居、黄宾虹纪念室、古荡文物保护科研基',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 90,
        'name': '横店影视城',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '横店影视城位于中国浙江省金华东阳市横店镇，自1996年以来，横店集团累计投入30个亿资金兴建广州街、香港街、明清宫苑、秦王宫、清明上河图、华夏文化园、明清民居博览城、梦幻谷、屏岩洞府、大智禅寺等13个跨越几千年历史时空，汇聚南北地域特色的影视拍摄基地和两座超大型的现代化摄影棚。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 91,
        'name': '杭州国家版本馆',
        'type': '其他',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '杭州国家版本馆，又名文润阁、中国国家版本馆杭州分馆，位于浙江省杭州市余杭区文润路1号，为中国国家版本馆组成部分。 总建筑面积10.31万平方米，是中国国家版本馆总馆异地灾备库、江南特色版本库，及华东地区版本资源集聚中心。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 92,
        'name': '吉利集团',
        'type': '科技创新',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '吉利控股集团致力于成为具有全球竞争力和影响力的智能电动出行和能源服务科技公司，业务涵盖汽车及上下游产业链、智能出行服务、绿色运力、数字科技等。集团总部设在杭州，旗下吉利、领克、极氪、沃尔沃、极星、路特斯、英伦电动汽车、远程新能源商用车、曹操出行等品牌各自围绕品牌定位，积极参与市场竞争。集团以汽车产业电动化和智能化转型为核心，在新能源科技、共享出行、车联网、智能驾驶、车载芯片等前沿技术领域，打造科技',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 93,
        'name': '微医集团',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '微医是国际上规模最大、最具成长力的数字健康独角兽之一，曾获得腾讯、国开金融、复星医药、晨兴资本、友邦保险、新创建集团、中投中财等知名机构投资 ，截至2018年5月估值为55亿美金。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 94,
        'name': '景溪村',
        'type': '美丽乡村',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '景溪村，隶属于浙江省湖州市安吉县报福镇，2020年3月，景溪村入选浙江第二批省级农村引领型社区名单。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 95,
        'name': '之江村',
        'type': '科技创新',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '近年来，该村按照“美丽普惠、数智赋能、未来引领”目标要求，推动山水与乡村相融、村居与田野辉映、乡土原生态与现代艺术气息兼具、乡村与城镇一体发展，其彰显江南韵味、呈现未来元素、引领乡村共富的实践，取得了良好成效；先后被评为国家级专业摄影创作基地、省级3A级景区、杭州市数字乡村样板村，是浙江省首批“未来乡村”试点村。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 96,
        'name': '母岭村',
        'type': '美丽乡村',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '母岭村先后被评为桐庐县文明村、农村信用村、“三个代表”重要思想学习教育活动先进村、杭州市先进党组织等荣誉称号。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 97,
        'name': '杭州云象网络技术有限公司',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '杭州云象网络技术有限公司成立于2014年，提供基于“区块链+人工智能+分布式”的金融数字化整体解决方案，中国最早从事区块链技术研究与商业应用、法定数字货币核心技术研究的团队。云象总部位于杭州，在北京、上海、广州、重庆、西安设有分支机构。云象在“区块链+人工智能+数字货币”等核心领域拥有200+项发明专利，70+项软件著作权，在TKDE、PAMI、INFOCOM、IJCAI、AAAI、软件学报等国际',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 98,
        'name': '新天地集团',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '新天地集团，全称杭州新天地集团有限公司，成立于2008年3月25日，位于浙江省杭州市，是一家以“城市中央活力区、城市文化名片、养生度假区”三大主力产品为引擎驱动，文、商、旅三位一体协调发展的城市复合产业运营商，董事长刘文东。[',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 99,
        'name': '杭州政协实践中心',
        'type': '其他',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '杭州市政协新时代协商民主实践中心成立于2022年，位于杭州城市阳台，是政协委员与界别群众协商议事的新平台，也是感知协商民主了解人民政协的好窗口。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 100,
        'name': '老板电器',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '杭州老板电器股份有限公司（证券代码：002508）是经过四十年市场检验的专业厨房电器生产企业。集团总部位于风景秀丽的杭州，这是一块集人文风貌与经济发展双重优势的宝地。老板集团也在这块宝地不断壮大发展，打造出“老板厨房电器”这一中国家庭熟悉与喜爱的全球畅销高端厨房电器品牌。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 101,
        'name': '杭州数字党建研习院',
        'type': '红色教育',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '数字党建研习院设在云集，由云集党委与半月谈杂志社、《非公有制企业党建》杂志、杭州市下城区委组织部等合作共同打造，实行院务委员会制，其中执行单位由云集党委兼任。研习院由研究中心、实践中心、展示中心组成。其中，展示中心占地500多平米，由数字党建云平台、党建大数据、VR和AR体验、扫码党课、党建问答游戏、党史知识滑屏等10个版块组成，以互联网为载体，充分运用数字化技术开展党建，运用数字化结果呈现党建效',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 102,
        'name': '绍兴市新闻传媒中心',
        'type': '其他',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '（全省率先整合地市级报社和广电系统）',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 103,
        'name': '安吉县融媒体中心',
        'type': '其他',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '（全国县级融媒体中心建设的先行者）',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 104,
        'name': '湖州市新闻传媒中心',
        'type': '其他',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '（浙江省的第二家跨界融合的市级媒体）',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 105,
        'name': '浙江日报报业集团',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '（推进传统媒体与新兴媒体融合发展）',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 106,
        'name': '华数集团',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '实地参观——华数集团（三网融合发展的典型）',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 107,
        'name': '中国（浙江)自由贸易试验区杭州片区',
        'type': '其他',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '中国（浙江）自由贸易试验区赋权扩区到杭州，钱塘、萧山、滨江三大区块的37.51平方公里纳入自贸试验区范围，成为引领杭州高质量发展的“试验田”。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 108,
        'name': '五四宪法馆+杭州党史馆',
        'type': '红色教育',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '“五四宪法”历史资料陈列馆，位于杭州市。2021年11月，被全国普法办公室拟表彰为2016-2020年全国普法工作先进单位。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 109,
        'name': '振宁未来社区',
        'type': '红色教育',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '振宁未来社区位于宁围街道集镇核心区块，共有11个小区，现辖区居民5429户，人口18000余人，其中户籍人口2900余人。按照党建覆盖小区、党员联系群众的思路，振宁未来社区正在努力建立资源共享、共驻共建、管理有序、服务完善、环境优美、治安良好、生活便利、人际关系和谐的现代化社区。先后获得浙江省老龄工作规范化社区、杭州市科普文明示范社区、杭州市爱国卫生先进社区、萧山区文明社区、萧山区文化社区、杭州市',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 110,
        'name': '杭钢半山数字经济小镇',
        'type': '科技创新',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '杭钢半山数字经济小镇由浙江两家世界500强企业杭钢集团 与阿里巴巴集团联合建设，总投资158亿元。浙江数字化改革重大标志性项目之一。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 111,
        'name': '桐乡越丰村（三治融合发源地）',
        'type': '美丽乡村',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '越丰村位于浙江省嘉兴市桐乡市高桥镇东面，南邻海宁市斜桥镇交界，东接屠甸镇汇丰村，北接该镇新丰村，西与镇楼下谷、范桥村相邻。桐九公路与沪杭高速公路贯穿全村。交通十分便捷。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 112,
        'name': '杭州市政协新时代协商民主实践中心',
        'type': '科技创新',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '杭州市政协新时代协商民主实践中心位于杭州市城市阳台地面一层，中心设陈列展示、协商议政、学习交流、互动体验四个区域，是市政协学习贯彻党的二十大精神，深入推进专门协商机构建设，助力打造全过程人民民主市域典范和实践高地的重要举措，是浙江省政协系统推进协商民主的创新之举。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 113,
        'name': '浙商银行',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '浙商银行是十二家全国性股份制商业银行之一，于2004年8月18日正式开业，总部设在浙江省杭州市，系全国第13家“A+H”上市银行。全称为“浙商银行股份有限公司”，英文简称“CZB”。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 114,
        'name': '杭州工运史资料陈列室工匠精神展示厅',
        'type': '其他',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '工匠精神展示厅全厅以文字、图片和影像的形式展示了 “思想引领，闪耀光芒”“工匠精神，杭州实践”“舆论反响，社会评价”等三部分内容。其中，“思想引领，闪耀光芒”展示了党的十八大以来，习近平总书记对于弘扬劳模精神、劳动精神、工匠精神的重要指示以及相关文字、图片、影像资料；“工匠精神，杭州实践”部分展示了杭州大力弘扬新时代工匠精神的实践与探索；“舆论反响，社会评价”部分展示了全国和省市媒体关于弘扬工匠精',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 115,
        'name': '河坊街',
        'type': '其他',
        'supplier': '张志豪',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '河坊街位于吴山脚下，是清河坊的一部分，属于杭州老城区，东起江城路，向西越南北向得建国南路、中河中路、中山中路、华光路、劳动路至南山路，路长1800多米，吴山广场至中山中路段为步行街，青石板路面，路宽13米，其余路宽32米。旧时，与中山中路相交得“清河坊四拐角”，自民国以来，分别为孔凤春香粉店、宓大昌旱烟、万隆火腿店、张允升帽庄四家各踞一角，成为当时远近闻名的区片。河坊街于2002年十月开街，重在突',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 116,
        'name': '杭州余杭百丈溪口村',
        'type': '科技创新',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '杭州余杭溪口村，坐落于104国道北侧，以竹文化为主题的溪口乡村，山清水秀，有着‘竹海’之称，被评为浙江省森林村庄、浙江省卫生村、杭州市体育小康村、杭州市示范村等。溪口特色文创街区，入驻多家文创企业和工作室，形成“竹➕文创”的产业发展模式。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 117,
        'name': '咸亨国际应急装备中心',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '赛孚城是咸亨国际科技股份有限公司顺应时代发展趋势而打造的一个集应急安全文化推广传播、安全技能实训、应急装备展示体验、应急装备市场推广、应急物资储备联动、应急产品科研开发推广等功能于一体的综合性、前瞻性安全服务平台。“赛孚”则是来自安全“Safe”的谐音而取，通过宣、教、体、培、练、展等形式，结合情景体验、角色植入、评估考核等手段，开创了国内应急产业发展和应急文化传播的新局面。目前杭州、南京、长沙、',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 118,
        'name': '云集（互联网电商与直销零售）',
        'type': '红色教育',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '云集是一家由社交驱动的精品会员电商平台，通过聚焦商品的极致性价比，为会员提供美妆个护、手机数码、母婴玩具、水果生鲜等全品类精选商品，服务中国家庭的消费升级。现场观摩云集智慧党建，对云集共享科技有限公司智能化、平台化、及时化、移动化非公党建模式，“四化”（工作推进标准化、工作创新品牌化、工作运行平台化、工作落实责任化）同步抓党建的工作思路，进行详细考察学习。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 119,
        'name': '钱江经济开发区',
        'type': '红色教育',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '新就业群体作为社会经济发展的新生力量，钱江经济开发区则通过党建联建形式，将新就业群体纳入基层党建格局，推动党建领“新”全面开展。此外，钱江经济开发区还设置了新就业群体综合服务站，为快递员、外卖配送员和网约车司机等新就业群体提供便捷、全面而温暖的服务，打造新就业群体的精神家园和活动平台。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 120,
        'name': '富通集团（电子信息）',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '富通集团是国家重点高新技术企业、全国民营百强企业、全国电子信息百强企业和国家创新型企业。其产业、技术和规模等综合竞争力居全球领先地位，是全球知名的光通信企业。富通集团有限公司党委，曾被中共中央组织部授予“全国创先争优先进基层党组织”、“全国先进基层党组织”等光荣称号。富通集团在全体党员中开展了“党员创先争优”“红旗班组”“党员先锋岗”“党员责任区”“党员示范岗”等系列活动，开展“我为企业献一计”活',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 121,
        'name': '南湖区新时代文明实践中心',
        'type': '红色教育',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '南湖区新时代文明实践中心坐落于嘉兴国际创意文化产业园105号，与南湖新区新时代文明实践所共建共享，于2019年7月6日正式启用，分为三层，面积达1500平米，集文明驿站、新时代文明实践展示展陈、志愿服务指导中心、志愿者之家、红船实践书苑、有声“学习”书柜、文创产品展区、融直播大讲堂等功能于一体。南湖区新时代文明实践中心于2018年12月被列为省级试点，并于2019年10月荣升为全国试点。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 122,
        'name': '桐乡智慧警务',
        'type': '政务考察',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '应用互联网理念探索公安工作新模式，为推动现代警务机制改革提供支撑，最大限度地为人民群众安居乐业提供服务。针对理念最先进、技术最先进、平台最先进、工具最先进的目标，搭建中国最智慧警务，并形成智慧警务建设的桐乡模式。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 123,
        'name': '拱墅区上塘街道综合执法指挥中心',
        'type': '政务考察',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '拱墅区上塘街道综合执法指挥中心占地4200平方米，上下五层楼，一站式办事窗口都位于一楼，二楼有数字化指挥中心，是拱墅区体量最大的街道综合执法大楼，位于拱墅区重点打造的智慧网谷产业核心区内。中心内还设有办案联动区、法制审核区等功能区块，并配有谈心谈话、宣传教育等文化阵地，为办事的老百姓提供了更加舒适的服务环境。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 124,
        'name': '杭州缤纷未来社区',
        'type': '科技创新',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '缤纷未来社区创建以来，西兴街道围绕“治理一体化”核心，打破条块分割、单部门内循环模式，构建“一体化、大综合”的治理体系，实施“缤纷管家、缤纷执法、缤纷掌柜、缤纷数智、缤纷服务”五大项目，实现一体化物业管理、一体化综合执法、一体化社区运营、一体化数字平台、一体化惠民服务。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 125,
        'name': '葛巷社区',
        'type': '科技创新',
        'supplier': '付娟',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '葛巷社区地处杭州未来科技城核心区块，是杭州城市新中心当之无愧的心脏部位，毗邻杭州西站，是典型的回迁混居型社区。区域面积0.56平方公里，下辖4个小区，2个回迁安置小区，2个商品房小区，1个商住体，17个网格。近年来，葛巷社区优化网格划分，精化网格力量配比，有效统筹党员、楼道长、居民代表、驻社干部等力量，一网导览治理神经末梢，实现线上线下响应闭环，让社区治理更智慧更高效。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 126,
        'name': '湖滨街道晴雨工作室',
        'type': '美丽乡村',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '杭州市上城区湖滨街道“湖滨晴雨”工作室于2009年12月28日成立,是全国首个“民生促民生”社区互动平台。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 127,
        'name': '数秦科技',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '数秦科技成立于2016年5月，总部位于杭州，是中国产业区块链赛道的头部企业。数秦科技运用区块链、大数据、人工智能技术，自主研发分布式商业技术引擎“氚平台”，深耕司法、金融、政务三大业务领域， 是中国领先的全流程可信数据技术与服务提供商。数秦科技的核心竞争力是能在跨行业、跨组织、跨平台等多跨应用场景中，满足政府、企业、智能网络进行大规模可信数据交换的需求，并进一步为用户提供更加优质的数字化服务。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 128,
        'name': '盘石集团',
        'type': '红色教育',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '盘石集团2004年于杭州创立。 盘石全球数字经济平台致力于大数据技术革命驱动的全球数字经济建设与发展。盘石深度挖掘“盘石云”大数据，通过“盘石全球数字经济平台”旗下的商业群智协同云、元宇宙出海数娱云、直播电商云、全球数字经济产业园云、数字人才教育云、数字科技云、新消费云七朵云系核心服务，打造基于盘石大数据为基础而交互链接的商业生态平台。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 129,
        'name': '杭州奥能电力设备制造有限公司',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '杭州奥能电力设备制造有限公司地处于浙江省省会杭州的高新技术开发区，是一家从事电力用交、直流电源及电能质量控制的公司。公司自年成立至今，经过奥能人的艰苦创业、奋发图强，经营规模不断扩大，已经形成了一个完善的经营服务体系，目前奥能公司已在北京、太原、成都、呼和浩特、新疆等省会城市设立办事机构，是集科研、生产、销售、服务为一体的集团公司。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 130,
        'name': '杭州市数字经济党群服务中心',
        'type': '红色教育',
        'supplier': '潘秀珠',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '杭州市数字经济党群服务中心位于杭州市数字经济高地——未来科技城核心区 的浙江海外高层次人才创新园 4 号楼，该中心共两层，建筑面积达 2600 平方米，是 一个集展示窗口、服务阵地、赋能高地和交流平台为一体的党建阵地。中心一层为展 示学习体验区，设置了数字化序厅、党建云馆、数字经济党建五大中心等“一厅一馆 五中心”，集中展示和杭州数字经济发展总体概况和数字经济党建工作的经验做 法，综合应用了人工智',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 131,
        'name': '佛山村',
        'type': '红色教育',
        'supplier': '潘秀珠',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '地处萧山区西南，山水生态资源独具特色，地理环境优越，交通便利，有着得天独厚的发展潜力与优势。村庄总面积3.93平方公里，有农户374户，人口1303人，是浙江省首批气候康养乡村、省3A级景区村庄，杭州市首批共富村和数字乡村试点村。 坚持党建引领，统筹乡村自治，全面实施映山红数字治理计划，推出“工分宝”小程序，为村庄数字赋能，激活了村民自治意识，村民已通过“工分宝”参与志愿服务活动1200余人次，节',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 132,
        'name': '中国杭州低碳科技馆',
        'type': '科技创新',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '中国杭州低碳科技馆是全球第一家以低碳为主题的大型科技馆，是集低碳科技普及、绿色建筑展示、低碳学术交流和低碳信息传播等职能为一体的公益性科普教育机构。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 133,
        'name': '传化集团',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '传化集团，即传化集团有限公司，是一家涵盖化工、投资等五大事业板块，横跨一、二、三产业的多元化现代企业集团，创立于1986年，总部位于杭州。1992年，企业更名为“杭州传化化学制品有限公司”，开始了在纺织化学品领域的全面开拓。2004年“传化股份”（002010）在深交所上市交易。[2]旗下业务包括化工、科技城、物流等。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 134,
        'name': '乌镇大数据高新技术产业园',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '乌镇大数据高新技术产业区以大数据、云计算、物联网为代表的新一代信息技术产业；以航空航天、高端装备为代表的特色产业以及以新能源、生物医药等为代表的新兴产业已经形成产业集群。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 135,
        'name': '安吉孝丰镇横溪邬村',
        'type': '美丽乡村',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '横溪坞村域面积8.5平方公里，位于“千年古镇，孝子之乡”浙江安吉孝丰镇，该镇是24孝中 “郭巨埋儿得金”、“孟宗哭竹”故事发源地。作为安吉美丽乡村精品示范村，横溪坞生态环境优美，民风淳朴，正致力将“青山绿水”打造成宜居、宜业、宜游、宜康养的安吉生态旅居目的地。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 136,
        'name': '浙江省法纪教育基地',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '浙江省法纪教育基地由省、市、区三级纪委、检察、司法等十家单位联合共建，杭州市萧山区法纪教育中心[浙江省法纪教育基地（萧山）管理中心]具体负责管理。基地占地面积13亩，建筑面积4000平方米。基地前身为2003年12月成立的萧山区警示教育基地；2005年7月，杭州市党员干部法纪教育基地在此成立；2006年8月，浙江省法纪教育基地挂牌成立；2009年7月基地二期扩建投入运行；2015年4月基地三期场馆',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 137,
        'name': '鸬鸟蜜梨小镇',
        'type': '美丽乡村',
        'supplier': '王梦思',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '杭州余杭的鸬鸟镇有蜜梨之乡之称。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 138,
        'name': '小古城村',
        'type': '美丽乡村',
        'supplier': '高香明',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '小古城村位于杭州市余杭区径山镇东北部，是余杭区级文明村、生态村、文化村、安全村。小古城村系 2003 年 9 月由吴山、钱家滩、俞家堰三村合并而成，因省级文物保护单位小古城遗址坐落本村而得村名。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 139,
        'name': '仓前街道社会治理综合服务中心',
        'type': '美丽乡村',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '仓前街道社会治理综合服务中心：街道根据省市区基层社会治理和最多跑一次改革精神，融合了仓前属地资源、特色打造的一站式、窗口化服务大厅。整个一楼大厅共设有13个服务窗口，共包含42项+一窗受理便民服务项目和全辖区矛盾纠纷多元处置化解工作；二楼司法所是我们的大调解中心：金牌调解室、领导接访室、解铃工作室、社区矫正教育室等形成多功能区域；三楼为安全生产综合执法中队、消防应急管理站，是杭州市首批示范化站所，',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 140,
        'name': '中国财税博物馆',
        'type': '红色教育',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '国财税博物馆隶属于财政部和国家税务总局，坐落于钱江之滨，西湖之畔，吴山之麓，占地面积27亩，建筑面积12000平方米，收藏各类财税历史相关文物和文献资料近万件，是国家级的专业博物馆。博物馆现有财富中国、中国古代财税历史、中国近现代财税历史、中国当代财税历史、中国会计历史五个展厅和摇钱树与理财家展区。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 141,
        'name': '蚂蚁链产业创新中心',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '蚂蚁链产业创新中心是蚂蚁集团倾力打造，基于阿里经济体及生 态伙伴等各个领域优势资源，实现产业链上下游企业集聚、新兴 产业培育、产业赋能、产业投资、人才引进等发展要素于一体的 创新服务平台，共享新技术，共创新价值，构建数字经济时代价 值互联网体系。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 142,
        'name': '梦想小镇',
        'type': '科技创新',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '“梦想小镇”涵盖了互联网创业小镇和天使小镇两大内容，其中，互联网创业小镇重点鼓励和支持“泛大学生”群体创办电子商务、软件设计、信息服务、集成电路、大数据、云计算、网络安全、动漫设计等互联网相关领域产品研发、生产、经营和技术(工程)服务的企业；天使小镇重点培育和发展科技金融、互联网金融，集聚天使投资基金、股权投资机构、财富管理机构，着力构建覆盖企业发展初创期、成长期、成熟期等各个不同发展阶段的金融服',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 143,
        'name': '文晖街道',
        'type': '红色教育',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '拱墅区文晖街道区域面积5.48平方公里，下辖8个社区和2个经合社。文晖街道聚焦“全类别”住宅小区矛盾隐患多、需求差异大、治理难度高等现状，在推动小区由乱到治、由差变好，让居民群众更幸福、更满意上下功夫，打出“创新、夯基、补短”组合拳，以党建统领三方协同治理助力现代社区建设，初步呈现出“党旗红、治理优、生活美”的文晖实景。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 144,
        'name': '采荷青荷苑社区',
        'type': '美丽乡村',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '建于2001年的青荷苑社区，属于采荷街道荷花塘未来社区范围，是全省首批未来社区试点单元。近年来，坚持“同步改造提升、同步服务提升”，推进老旧小区综合改造提升项目；嵌入式打造幸福邻里坊社区共富综合体，集成设置养老、幼托、医疗、教育等普惠性服务，形成“十分优享”服务体系。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 145,
        'name': '杭州城市规划展览馆',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '杭州市城市规划展览馆位于杭州市市民中心裙楼L座，以“规划构筑品质生活,梦想点亮美丽杭州”为展示主题，定位为亲民、互动、前瞻的“城市窗口”，是爱国、爱家乡的教育基地，阳光规划公众参与的重要平台。展馆主要杭州古都文化名城的悠久历史，宣传当今城市规划建设的伟大成就，展示生活品质之城的灿烂明天。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 146,
        'name': '良渚文化村未来社区',
        'type': '科技创新',
        'supplier': '王梦思',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '自启动未来社区试点工作以来，良渚文化村社区以领跑姿态奋战奋进，按照“政府主导、企业共建、居民参与”的运作模式，立足九大场景打造，坚持“线上+线下”一体化推进，多跨应用推动数字改革，积极打造“城市更新”与“数字治理”高度融合的国际化未来社区示范样板。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 147,
        'name': '浙江省档案馆',
        'type': '红色教育',
        'supplier': '王梦思',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '浙江省档案馆为国家一级档案馆，现有馆藏224个全宗，档案近54万卷（件），其中清代档案3353卷（件），民国时期档案约12万卷（件），革命历史档案1000多卷（件），建国后档案约41万卷（件）；照片、声像等特种载体档案近44万张，资料约9万册。开放档案约19万卷（件），开放目录60万条。通过拓展收集范围，加大征集力度，馆藏结构日益丰富，形成纸质、声像、书画、印章、电子文件等多载体和文书档案、科技档',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 148,
        'name': '乌镇雅园',
        'type': '文化考察',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '绿城乌镇雅园位于桐乡市乌镇是以独栋别墅，多层的普通住宅，别墅建筑。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 149,
        'name': '天目里',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '天目里坐落于杭州市西湖区文新单元，紧邻国家湿地公园——西溪湿地。项目占地面积43395平方米，总建筑面积23.4万平方米，地下3层，地上共17幢7—11层单体建筑，通过连廊贯通，形成一个围合式建筑群。它不仅是江南布衣和GOA的总部，也是一个集合了办公、美术、艺术中心、百货以及商业等多元的开放性综合园区。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 150,
        'name': '青山湖科技城',
        'type': '科技创新',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '青山湖科技城是浙江建设科技强省和创新型省份的重大工程，也是杭州城西科创产业集聚区的核心组成部分。规划面积115平方公里，分为四大功能区，其中：研发区面积5平方公里，启动区块面积2.07平方公里，是科技城的核心，集聚了大批科研机构和研发人才；产业化区面积40平方公里，是高端产业和高新企业的集聚地；现代服务和综合生活配套区面积25平方公里，是企业总部、中介机构、现代服务的集聚地；生态休闲区面积45平方',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 151,
        'name': '小营街道小营巷社区',
        'type': '美丽乡村',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '杭州市上城区小营街道小营巷社区建于2001年，位于杭州市上城区的东北角，占地面积0.3平方公里。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 152,
        'name': '杭州城市大脑',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '杭州城市大脑有限公司成立于2019年4月，是国内首家专注于城市大脑建设和运营的国有控股混合所有制科技企业。核心技术团队具有浙江政务服务网和浙里办APP建设运营成熟经验，公司自成立以来，深度参与市域城市大脑和省域数字化改革建设运营，致力于用科技推动城市治理体系和治理能力现代化。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 153,
        'name': '杭州汽轮动力集团',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '杭州汽轮动力集团有限公司的前身为杭州汽轮机厂，成立于1958年。1995年6月，作为国务院百家建立现代企业制度试点，首批改制为政府授权经营的国有独资企业；是杭州市六家国有资产授权经营大集团之一。是中国最大企业500强之一、中国制造业500强之一、中国竞争力100强之一、全国创和谐劳动关系模范企业、中国机械百强企业列第19位。2016年8月，杭州汽轮动力集团在"2016中国企业500强"中排名第23',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 154,
        'name': '六和律师事务所',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '浙江六和律师事务所成立于1998年11月，是以公司和投融资业务为特色的大型综合性律师事务所，系全国优秀律师事务所，在业务总量、人员规模、律师素质，还是综合考评、社会知名度等均名列前茅。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 155,
        'name': '新华三集团',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '新华三集团（H3C）作为数字化解决方案领导者，致力于成为客户业务创新、数字化转型值得信赖的合作伙伴。作为紫光集团旗下的核心企业，新华三通过深度布局“芯-云-网-边-端”全产业链，不断提升数字化和智能化赋能水平。新华三拥有芯片、计算、存储、网络、5G、安全、终端等全方位的数字化基础设施整体能力，提供云计算、大数据、人工智能、工业互联网、信息安全、智能联接、边缘计算等在内的一站式数字化解决方案，以及端',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 156,
        'name': '昆山之路成果展',
        'type': '红色教育',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '“与时俱进的昆山之路”成果展位于昆山市科技文化博览中心，占地面积3000平方米。展厅分为序厅、“峥嵘岁月”“春华秋实”“走进新时代”“党建引领”“2035城市规划”六个部分，充分运用声、光、电以及场景复原、LED天幕、纱幕影院等现代展示技术和手法，所有多媒体设备均纳入智能化操作系统，凸显科技和环保理念。这是外界了解认识昆山的重要窗口，也是昆山广大干部群众重温奋斗历程、坚定发展信心的重要场所。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 157,
        'name': '昆山深化两岸产业合作试验区展示馆',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '深化两岸产业合作试验区（以下简称:昆山试验区）位于富春江路西侧、前进路北侧的光电产业园内，展馆建筑面积1000多平方米。展示馆分为“序章”“谋双赢，同筑中国梦”“承善政，美玉在昆冈”“创荣业，转型再出发”和“融两岸，建设心家园”五个篇章，利用声光电手段，结合文字资料、图表数据和模型实物等表现形式，真实记录了昆台两地经贸文化交流交往的历史时刻，生动再现了在昆台资企业成长轨迹，全面展示了昆山深试验区获',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 158,
        'name': '昆山市行政服务中心',
        'type': '政务考察',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '昆山市行政服务中心位于江苏省昆山市前进中路219号，为江苏省昆山市政府派出机构，正科级建制，履行对进驻部门集中审批、收费事项的组织协调、管理监督和指导服务的职能。为了规范行政审批行为，简化审批程序，提高行政效率，对行政审批事项、收费事项和服务项目实行“一个门受理、一座楼办事、一个窗收费、一条龙服务”的运作模式。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 159,
        'name': '米果果小镇',
        'type': '美丽乡村',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '米果果小镇创建于2013年，总面积3152亩，是一个集种养殖、农产品深加工、休闲旅游、教育培训、创新创意发展为一体的综合性农业园区,第一期投资已超5亿元。米果果小镇的发展核心目标是让土地活起来，让农民富起来，让乡村美起来，通过“土地保底收益+赠送10%股权+利润分红”的土地流转模式，已成为中国农业园区带动当地农民共同发展的典范。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 160,
        'name': '云栖小镇',
        'type': '科技创新',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '云栖小镇位于杭州西湖区的西南部，规划面积13.8平方公里核心规划面积3.5平方公里：是在原来传统工业园区（转塘经济科技园）的基础上，实施“腾笼换鸟、筑巢引凤”打造而成。2014年时任浙江省省长李强到访云栖小镇，首次肯定并提出特色小镇的发展理念。云栖小镇至此成为浙江省特色小镇的发源地，云栖小镇专注于吸引大企业开放核心能力，搭建服务平台，为广大的中小微企业供创新创业服务，打造四大产业生态，大力引进以云',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 161,
        'name': '海康威视',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '海康威视成立于2001年，是一家专注技术创新的科技公司。秉承“专业、厚实、诚信”的经营理念，践行“成就客户、价值为本、诚信务实、追求卓越”的核心价值观，海康威视致力于将物联感知、人工智能、大数据技术服务于千行百业，引领智能物联新未来：以全面的感知技术，帮助人、物更好地链接，构筑智能世界的基础；以丰富的智能产品，洞察和满足多样化需求，让智能触手可及；以创新的智能物联应用，建设便捷、高效、安心的智能世',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 162,
        'name': '嘉兴潘家浜村',
        'type': '美丽乡村',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '潘家浜村，位于浙江省嘉兴市秀洲区新塍镇。2020年3月，潘家浜村被浙江省乡村振兴领导小组办公室认定为2019年度浙江省善治示范村。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 163,
        'name': '万事利集团',
        'type': '红色教育',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '2013年，万事利丝绸文化博物馆正式获得杭州市园文局、杭州市民政局的批准，成为省内首家民间丝绸文化博物馆。万事利集团董事局主席屠红燕担任万事利丝绸文化博物馆馆长，国家级丝绸专家、世界非物质文化遗产宋锦传承人钱小萍为万事利丝绸文化博物馆名誉馆长。博物馆内收藏众多现当代作品，主要为刺绣、缂丝精品，以及万事利建厂以来各个时期的精品，共600多件。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 164,
        'name': '上城区行政服务中心',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '上城区行政服务中心人是杭州市的一个政府工作部门，为市民、企业提供受理、咨询、审批、收费、投诉等“一站式”服务。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 165,
        'name': '杭州市财政局',
        'type': '其他',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '杭州市财政局是杭州市人民政府工作部门，为正局级。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 166,
        'name': '德清新农村',
        'type': '美丽乡村',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '德清五四村、德清庾村',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 167,
        'name': '浙江革命烈士纪念馆',
        'type': '红色教育',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '浙江革命烈士纪念馆位于杭州西子湖畔的云居山上，北连吴山天风，南邻万松书院；东眺钱江浩荡, 西瞰湖光山色。为了缅怀先烈，激励后人，1985年中共浙江省委、省政府作出决定建造本馆。1987年12月浙江革命烈士纪念碑奠基，1990年3月落成，1991年9月浙江革命烈士纪念馆主馆建成并对外开放，2003年10月建立浙江革命烈士纪念馆网站。为了更好地宣传烈士事迹，弘扬烈士精神，浙江革命烈士纪念馆主馆主体建筑',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 168,
        'name': '余杭区行政服务中心',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '余杭区行政服务中心位于杭州余杭区临平南大街265号，共进驻37个审批服务部门，4家银行，13家中介机构，2家商务中心，300余名工作人员，200余个办事窗口，集中办理400余个审批和服务类事项。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 169,
        'name': '桐庐县行政服务中心',
        'type': '红色教育',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '桐庐县行政服务中心（招管办）作为全县“放管服”改革主窗口，围绕数字化改革组织流程再造要求，创新“党建+改革”关键绩效指标考核，先后完成二轮次支部换届和“党建+”KPI考核，推动党建和业务深度融合，为高效落实政务“一网通办”奠定了良好的组织保障。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 170,
        'name': '半淞园路街道耀江花园居委会',
        'type': '美丽乡村',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '耀江花园社区为第七批全国民主法治示范村（社区）',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 171,
        'name': '半淞园路街道保屯居民区',
        'type': '美丽乡村',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '保屯社区归属于上海市,黄浦区,半淞园路街道。天蓝水清,历史悠久,四季分明,气候温和。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 172,
        'name': '漕河泾街道华富片区',
        'type': '红色教育',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '华富街区位于漕河泾最北端，毗连徐家汇城市副中心，是未来龙吴路快速路的北出口，周边分布有徐家汇体育公园、龙华烈士陵园、区应急指挥中心等单位，区位优势明显。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 173,
        'name': '徐家汇街道社区党建服务中心',
        'type': '红色教育',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '徐家汇社区党建服务中心为适应年轻群体的需求和特点，以“建设素质优良的专业化社工队伍”为目标，依托“党建+社工”的工作模式，积极为社工的成长成才创造条件、搭建平台，有效激发了年轻人干事创业、服务基层的热情和动力，为社区工作的良性开展提供了人才保障。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 174,
        'name': '萧山区南阳街道潮都社区',
        'type': '红色教育',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '潮都社区位于南阳核心区，是省级第四批未来社区、市级第一批未来社区。包含商品房小区、安置小区和老旧小区三大类型的小区，是典型都市圈有机更新多村安置混合型城市社区。按照加快形成一批具有萧山辨识度的城乡现代社区建设样板的要求，潮都社区克服不同家庭、宗族和浓厚的原有村籍观念的居民融合难题，探索出“党建引领、七式治理”社区治理新模式，并作为示范样板在全区全面复制推广。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 175,
        'name': '拱墅区上塘街道瓜山社区',
        'type': '科技创新',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '瓜山未来社区是为年轻人打造的宜居社区，更是杭州“数智化”“数治化”应用的集结地。数字化设施全方位渗透到瓜山未来社区的各个角落，一改瓜山曾经城中村的老旧面貌。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 176,
        'name': '五四宪法历史资料陈列馆',
        'type': '红色教育',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '杭州是中华人民共和国第一部宪法“五四宪法”起草地。“五四宪法”历史资料陈列馆收藏了大量珍贵文物、文献资料和历史档案。“五四宪法”历史资料陈列馆坚持党的领导、人民当家作主、依法治国有机统一，努力为普及宪法知识、增强宪法意识、弘扬宪法精神、推动宪法实施作出贡献。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 177,
        'name': '人大代表联络站',
        'type': '科技创新',
        'supplier': '戴佳宇',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '人大代表联络站建设是浙江省人大数字化改革“1512”体系构架的重要组成部分。凯旋街道金秋花园人大代表联络站是杭州市首批最美人大代表联络站、全省首批人大践行全过程人民民主基层单元培育对象之一。上城区人大常委会会同凯旋街道，将街道居民议事组织作为小切口进行数字化改革探索，开发建设了“街道人大工作”特色场景。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 178,
        'name': '西湖区绕城村',
        'type': '美丽乡村',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '浙江省杭州市西湖区三墩镇绕城村概况。绕城村面积2.27平方公里，占有耕地1937亩；共有住户510户，1970人，在册党员87名，三副班子成员7人。2006年该村集体可分配收入72.91万元，人均年收入10269元。先后获得浙江省卫生村，市级计划生育先进集体、示范村、区级五好村党支部、安全文明村、西湖区三星级民主法治村等荣誉称号。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 179,
        'name': '嘉兴电子商务产业园',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '浙江嘉兴电子商务产业园以大数据、云计算、物联网为代表的新一代信息技术产业；以航空航天、高端装备为代表的特色产业以及以新能源、生物医药等为代表的新兴产业已经形成产业集群，重点发展电子信息、生物医药、智能装备、汽车零部件、新材料等主导产业。成为推动高质量发展的创新能极。园区加快特色转型，融入了新一代信息技术发展的时代浪潮。面对高质量发展中遇到的困难挑战， 浙江嘉兴电子商务产业园 敢想敢闯敢试，园区自成',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 180,
        'name': '富阳黄公望村',
        'type': '美丽乡村',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '黄公望村，是浙江省杭州市富阳区东洲街道下辖村，位于浙江省杭州市富阳区，是2007年将原有的华墅村、白鹤村、株林坞村、横山村四村合并而成，称为“黄公望村”。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 181,
        'name': '吴山清风廉政教育基地',
        'type': '红色教育',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '吴山清风廉政文化教育专线以“周新祠——阮公祠——三茅观于谦读书处”三个参观点为核心，结合新建的吴山文化名人导览石碑、名家撰写的《五瘴说》石刻、廉政文化教育展示厅，通过听、说、读、写等多种互动方式让参观者在感受吴山悠久文化积淀和优美自然风光的同时，接受廉洁文化熏陶，90分钟。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 182,
        'name': '杭州经济技术开发区（张学宁）',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '杭州经济技术开发区是1993年4月经国务院批准设立的国家级开发区，是全国唯一集工业园区、高教园区、出口加工区于一体的国家级开发区，委托管理下沙和白杨两个街道，辖区人口约45万人。杭州经济技术开发区是中国唯一的集产业园区、出口加工区、高教园区于一体的国家级开发区，拥有浙江省最大的高教园区。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 183,
        'name': '滨江海创基地',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '海外高层次人才创新创业基地，位于杭州高新开发区(滨江)之江科技工业园区，为省、市重点工程，座落在风景秀丽的杭州钱塘江南岸六和路368号，北临钱塘江，与对岸六和塔遥遥相望，东侧为著名的钱塘江大桥（一桥）及浙赣铁路线，交通便捷、地理位置十分优越。园区总占地面积304亩，总建筑面积24万平方米，其中地上建筑面积208806.3平方米，地下31838.8平方米，园区绿化率超过50%，环境大气，视野开阔。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 184,
        'name': '杭州滨江高新区智慧e谷',
        'type': '科技创新',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '滨江是一座智慧e谷、创新之城。20年来，始终坚持“高”“新”产业发展方向，围绕自主创新、网络安全和中国智造，打造网络信息技术产业的完整产业链，已形成千亿级智慧经济产业。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 185,
        'name': '嘉兴南湖',
        'type': '红色教育',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '嘉兴南湖革命纪念馆（嘉兴市） 嘉兴南湖是全国爱国主义教育示范基地，是中国共产党的诞生地。习近平同志在浙江工作期间，曾先后5次来到南湖革命纪念馆瞻仰红船。2005年6月，习近平同志在《光明日报》发表署名文章，首次提出“红船精神”，即“开天辟地、敢为人先的首创精神，坚定理想、百折不挠的奋斗精神，立党为公、忠诚为民的奉献精神”，深刻指出“红船精神”是中国革命精神之源，是党的先进性之源。2017年10月3',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 186,
        'name': '莫干山民国风情小镇',
        'type': '美丽乡村',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '庾村，莫干山下的一个民国风情小镇，面积不大，但颇有一番趣味，很适合散步转悠。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 187,
        'name': '临安白牛村',
        'type': '科技创新',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '杭州临安白牛村是全国首批淘宝村，是农村电商发展的样板村。白牛村建立“村民主体、市场主导、政府支持”的“农村淘宝”白牛模式，切实解决农户销售农产品缺市场、成本高、渠道少等问题，初步形成了“网店自主经营、公共服务配套”的集聚化、有序化农村电商发展格局，以坚实电商底子和优越的自然环境为基础，打造农村电商和休闲旅游相结合的电商特色小镇。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 188,
        'name': '运河(国际)跨境电子商务园',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '运河（国际）跨境电子商务园深入学习贯彻党的二十大精神，以数字品牌出海定位为着力点，进一步做强平台产业孵化能级、提升园区核心数字产业集聚度，奋力开创园区品牌出海高质量发展新局面。充分发挥拱墅区的产业优势、拱墅区政府、上塘街道的政策优势、浙江工程师学院、浙大城市学院、浙江树人大学的高校人才优势，园区联合浙大城市学院，共建全球跨境电商品牌与设计中心，以跨境产品品牌研究、工业设计和界面设计研究为核心，开展',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 189,
        'name': '云裳城直播中心',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '云裳城是直播供应链企业颖上传媒与阿里巴巴淘宝直播打造的直播电商产业园，是余杭区重大项目，淘宝直播示范中心、拥有完善的电商直播产业链条。入驻品牌包括红蜻蜓、意尔康、老板电器、炊大皇、芭蒂娜、卡拉佛、阿依莲、奥康、MO&Co等在内的众多知名品牌，涵盖女装、男装、电器、食品、化妆品等品类，可满足800+品牌商入驻。 云裳城作为首批淘宝直播官方授权基地，全国首家 [4-5]  家淘宝直播示范中心，享受淘宝',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 190,
        'name': '义乌国际商贸城',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '义乌是全国改革开放一面旗帜。义乌国际商贸城是国际性的小商品流通、信息、展示中心，是中国最大的小商品出口基地之一。义乌公路港主要面向国内物流业务，是一个集零担快运、仓储配送、集货中转、智能停车、餐饮住宿、信息与金融服务等功能于一体的现代综合物流园区。义乌保税物流中心主要开展跨境电商保税进口（1210）、保税存储、一日游、简单加工、转口贸易、国际中转、全球采购拼箱等业务，推出公共保税仓储业务，拓展分类',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 191,
        'name': '萧山农业电商孵化园',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '萧山农产品电子商务发展将以“孵化园+协会+公司”的运作模式，积极推行分销体系建设，以孵化园为支撑，“两化”结合通过社会化和市场化相结合，促进全区农产品电子商务的发展。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 192,
        'name': '中国社区建设展示中心',
        'type': '美丽乡村',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '中国社区建设展示中心位于浙江省杭州市上城区金钗袋巷。紧邻“胡雪岩故居”。是一家展示我国社区建设成果的专题性陈列馆。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 193,
        'name': '馒头山社区',
        'type': '美丽乡村',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '馒头山社区位于浙江省杭州市上城区南星街道南宋皇城遗址凤凰山脚路，南靠浙赣线，西至凤凰山，北上万松岭，2021年，司法部、民政部，命名馒头山社区为第八批“全国民主法治示范村（社区）”。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 194,
        'name': '潮都未来社区',
        'type': '美丽乡村',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '潮都未来社区位于南阳街道核心区，是浙江省第四批旧改类城镇未来社区创建项目。社区规划单元面积63公顷，实施单元面积26公顷，受益居民8593人。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 195,
        'name': '富阳东梓关村',
        'type': '美丽乡村',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '东梓关村是杭州市富阳区场口镇一个村庄，富阳区场口镇东梓关村位于场口镇西部，地理位置独特，面临富春江，背靠小山群，文化底蕴深厚，因郁达夫同名小说而著名，是两府、两县、两镇的中心点。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 196,
        'name': '杭州丁兰街道便民服务中心',
        'type': '政务考察',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '杭州丁兰街道便民服务中心紧抓政务服务数字化改革先发优势，积极推进区街一体化的政务服务体系建设，通过优化服务环境、拓展服务事项、推行特色服务，全面构筑政务服务智能办、线上线下融合办、便民快捷掌上办新格局，打造具有丁兰特色“系统优”“服务优”双优办事大厅。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 197,
        'name': '外桐坞村',
        'type': '美丽乡村',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '外桐坞村位于浙江省杭州市西湖区转塘街道东北面3km，置于素有“万担茶乡”之称的龙坞茶叶基地之中，是西湖龙井茶的主要产地。整个村东面面山，南与唐家桥相邻，西与里桐坞相对，北与大清相挨，绕城高速穿村而过。从2006 年开始，外桐坞村与艺术结缘，逐渐成为艺术家聚集地。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 198,
        'name': '凤凰村',
        'type': '美丽乡村',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '凤凰村先后获得“全国敬老模范村”、“浙江省文明村”、“浙江全面小康建设示范村”、“浙江省村务公开民主管理示范村”、“杭州市先进基层党组织”、“杭州市园林绿化村”、“杭州市四星级民主法治村”等荣誉。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 199,
        'name': '航民村',
        'type': '美丽乡村',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '航民村地处长江三角洲钱塘江南岸，是浙江省杭州市萧山区瓜沥镇辖下的一个行政村。多年来，航民村以科学发展观统揽全局，不断创新发展集体经济的新思路新举措，有效地推动全村经济社会的协调发展，走出了一条建设富裕和谐新农村的成功路子。先后荣获了浙江省“全面建设小康示范村”、“首届魅力新农村”和全国“村镇建设文明村”、“十大特色村”、“全国先进基层党组织”、“全国创建文明工作先进村”等光荣称号。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 200,
        'name': '绿城中国',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '绿城房地产集团有限公司位于中国浙江省杭州市，是中国著名的房地产开发商，创始人是宋卫平。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 201,
        'name': '浙医二院',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '浙江大学医学院附属第二医院（简称“浙大二院”）创建于1869年，是浙江省西医发源地，全国首家三级甲等医院、首批国家疑难病症诊治能力提升工程项目单位、首批国家区域医疗中心建设单位(心血管病、创伤、骨科(培育)、神经疾病(培育) )、首批国家紧急医学救援基地，连续四年位居三级公立医院绩效考核全国前十，“自然指数”全球50强，是G20杭州峰会医疗保障定点单位及驻点单位，众多海外医师首选的中国培训基地之一',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 202,
        'name': '古荡街道社区卫生服务中心',
        'type': '美丽乡村',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '杭州市西湖区古荡街道社区卫生服务中心，成立于2000年，建筑面积3080㎡。中心设有全科、妇科、儿科、口腔科、中医科、针灸推拿科、预防接种科、儿童保健科、围产期保健科、社服科、输液室、药剂、检验、影像等科室，开展基本医疗和公共卫生服务以及家庭医生签约服务。下辖莲花、古墩、益乐、文华、嘉绿苑、嘉荷六个社区卫生服务站。现有中高级职称卫技人员70人。口腔科为西湖区重点学科，配备达到省市级水平的口腔器械消',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 203,
        'name': '邵逸夫医院',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '浙江大学医学院附属邵逸夫医院是由香港知名实业家邵逸夫爵士捐资、浙江省人民政府配套建设，集医疗、教学和科研为一体的公立综合性三级甲等医院。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 204,
        'name': '桐庐健康小镇',
        'type': '美丽乡村',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '桐庐健康小镇背靠大奇山国家森林公园，三面环山、一面临着富春江，宛如世外桃源。整个区域环境优势明显，森林覆盖率超过80%，有39座天然形成的一级水质水库，全年空气质量优良天数在340天以上，PM2.5浓度年均值低于21，空气中富含丰富的负氧离子，每立方厘米达到10000个，温湿度适宜。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 205,
        'name': '腾讯大浙网',
        'type': '其他',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '大浙网定位为浙江城市生活门户,把握城市脉搏,创造快乐生活,以杭州为核心,覆盖整个浙江省,传播本地资讯和文化,为浙江省互联网用户提供最本地化的新闻行业资讯和生活娱乐产品,打造一站式在线生活服务。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 206,
        'name': 'G20主会场',
        'type': '其他',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '杭州国际博览中心(G20峰会主会场)在萧山区钱江世纪城(奔竞大道353号),从空中看,它和钱江新城的杭州大剧院、大金球组成的“日月同辉”在同一条中轴线上。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 207,
        'name': '白沙泉并购金融街区',
        'type': '科技创新',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '浙江省首个并购金融主题特色街区，白沙泉致力于打造并购金融全要素聚集生态圈，为企业并购重组和浙江经济转型升级提供一站式服务，成为全球并购价值链的浙江高地。2020 年 1 月，获得了中国证券监督管理委员会授予的“国家级投资者教育基地”称号，成为浙江省内唯一一家以券商为主体的国家级投资者教育基地。2020 年 5 月喜获浙江省公安厅授予的“浙江省防范经济犯罪教育基地”称号，此外，基地在运营初期就获得了',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 208,
        'name': '枫桥经验',
        'type': '红色教育',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '“枫桥经验”是全国政法战线一面高扬的旗帜，一直引领我国基层社会治理创新。半个世纪后的今天，习近平总书记提出，全力推进平安中国、法治中国建设。在催人奋进的新号角吹响之际，回顾“枫桥经验”的诞生与演进，我们可以发现，它依然是一面必须高举的鲜明旗帜，一笔不可多得的精神财富。有了这面旗帜，将使我们更加坚定地走好“为了群众、依靠群众、发动群众”的路线，让群众真正成为维护社会稳定、促进平安和谐的中流砥柱。有了',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 209,
        'name': '淳安县博物馆',
        'type': '红色教育',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '淳安县博物馆总建筑面积约5700平方米，由淳安县政府投资建设，总投资约8000万元，2018年5月18日正式对外开放。博物馆场馆分为四层，分别是序厅、历史厅、移民厅、非遗厅，以淳安文化为主轴，讲述淳安从“湖底江（新安江）”时代到“江上湖（千岛湖）”时代的历史故事，致力于打造一座回得去的文化故乡和放不下的精神家园。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 210,
        'name': '千岛湖下姜村',
        'type': '红色教育',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '下姜村，隶属浙江省杭州市淳安县枫树岭镇，原来是当地出了名的贫困村，近年来，下姜村坚持生态优先、绿色发展，依托红色旅游资源，形成以乡村旅游产业为支柱，规模效益农业为补充的生态产业集群，探索出了一条可持续和可复制的乡村振兴之路。如今的下姜村青山相伴、绿水环绕，农居错落有致，现代化休闲农业产业园区整齐有序。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 211,
        'name': '西湖跨境电商产业实验区',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '西湖区跨境电商产业园以跨境出口业务为主，帮国内制造企业去除中间环节，在海外建品牌，推动自主品牌商品出口。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 212,
        'name': '智慧E谷',
        'type': '科技创新',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '滨江是一座智慧e谷、创新之城。20年来，始终坚持“高”“新”产业发展方向，围绕自主创新、网络安全和中国智造，打造网络信息技术产业的完整产业链，已形成千亿级智慧经济产业。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 213,
        'name': '之江文化创意园',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '杭州之江文化创意园由西湖区委、区政府，之江国家旅游度假区党工委、管委会共同打造，是杭州市首批命名的十大文化创意产业园之一。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 214,
        'name': '白马湖文化创意园',
        'type': '科技创新',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '创意城相关负责人，白马湖生态创意城当前正处在国家级文化产业示范园区样板区和全省数字文化产业高地建设的高速发展期，白马湖文化创意产业研究基地将有力助推创意城产业发展定位更加清晰，园区产业赋能和营商环境更加成熟，数字文化产业发展更加高质量。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 215,
        'name': '西溪文化创意产业园',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '西溪创意产业园是西溪国家湿地公园的重要组成部分，园区隶属于西湖区委、区政府和西溪国家湿地公园管委会,是西湖区倾力打造“全省文创第一区”的重要基地之一。西溪创意产业园是杭州市首批“十大文化创意园区”，是省级影视创作拍摄示范园区，是国家影视产业“走出去”的重要窗口。开园以来，创意园区先后获“北京电影学院教育创作实践基地”“浙江省影视创作拍摄示范基地”“浙江省电影审查中心”、浙江122工程首批示范文化产',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 216,
        'name': '杭州颐高电子商务产业园',
        'type': '科技创新',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '颐高电子商务产业园，是由颐高集团打造的城市电子商务产业综合体，集特色产业园、商贸物流、电子商务于一体的大型现代服务业平台，构建了当地最大的网商群体生态链和电子商务产业链。园区涵盖电商总部基地、网商创业中心、电商服务中心、电子商务学院、网货博览城与物流基地六大功能板块，引进阿里巴巴中国产业带、特色中国淘宝馆和淘宝大学，吸纳各类电子商务企业入驻，培育近千名网商创业就业，直接带动当地综合产值，创造就业岗',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 217,
        'name': '新塘跨境电商产业园',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '新塘跨境电商产业园由原华隆羽绒公司旧厂房改建而成，总建筑面积约2.4万平方米，通过集聚城区跨境电商企业、引进外来优质企业，着力构建跨境电商研发、销售和展示环节，形成产业与人才集聚效应，与空港保税物流园区形成错位协调发展。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 218,
        'name': '东方电子商务园',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '东方电子商务园位于杭州江干科技经济园内，2010年11月被市委、市政府认定为杭州市文化创意产业园。占地面积129.62亩，目标是打造成17万平方米的全国领先现代服务产业集聚区。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 219,
        'name': '杭州跨境贸易电子商务产业园',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '中国（杭州）跨境贸易电子商务产业园位于下城区石桥路长城街南侧，一期建筑面积近4万平方米。园区利用信息化手段实现园区内海关、国检、国税、外管、电商企业、物流企业等之间的流程优化，特别是通过“定期申报”的业务模式，大大降低跨境电商企业货品通关成本。园区内的跨境电商企业出口货物的外汇可通过外管实现即时结汇；充分享受国家出口退税政策，进一步降低出口成本。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 220,
        'name': '杭州电子商务产业园',
        'type': '科技创新',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '杭州电子商务产业园位于西湖区翠柏路7号，2010年正式开园，总占地面积28亩，建筑面积约6万平方米。配套拥有报告厅、商务会议室、健身中心、党员活动中心、小型图书馆、员工餐厅、便利超市、地下车库等公共设施。园区现有电子商务企业96家，就业人数4600人，构建了良好的电子商务生态圈。 先后取得四项国家级荣誉：国家电子商务示范基地、国家级科技企业孵化器、国家软件产业基地拓展区、中国电子商务示范基地。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 221,
        'name': '绿科秀',
        'type': '科技创新',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '绿科秀农业公园，占地168亩，以农业体验为特色，设有兰花馆、绿植馆、盆栽馆、蔬果馆、体验教学馆、露天体验区等6大农业主题体验区，在紧凑的空间里，融合了农业生物技术、智慧农业技术、节能环保技术、农业创意设计，以及富有特色的水果、蔬菜、花卉、绿植等，是立足体验经济、“互联网+”和创客精神的新型农业技术、农业产品体验中心，同时也是一个服务于青少年、市民的农业科学公园。经过多年的努力，获得多方肯定，先后获',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 222,
        'name': '乌镇互联网小镇',
        'type': '科技创新',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '乌镇互联网小镇是指按照走集约、智能、绿色、低碳的新型城镇化道路的总体要求，以打造浙江省互联网经济特色小镇为目标，以世界互联网大会永久落户乌镇为契机，充分利用云计算、移动互联网、物联网和大数据等新一代信息技术的“互联网会务会展小镇、互联感知体验小镇、智慧应用示范小镇、互联网产业特色小镇”。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 223,
        'name': '黄公望金融小镇',
        'type': '科技创新',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '黄公望金融小镇是根据钱塘江金融港湾总体建设规划要求，依托黄公望区块独特的自然环境、人文特色和高端配套优势，吸引私募股权投资机构集聚的特色金融小镇。目前，黄公望金融小镇是富阳区作为吸引区内外金融资本的集聚平台，2016年-2021年期间，钱塘江金融港湾规划明确的“1+X”重点发展的特色小镇，小镇在历年省级特色小镇考核中考评良好。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 224,
        'name': '巧克力小镇',
        'type': '美丽乡村',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '歌斐颂巧克力小镇是由歌斐颂集团投资打造的省级重点项目、是国内首家集巧克力生产、研发、展示、体验、休闲度假于一体的巧克力工业旅游与主题乐园相结合的特色旅游产品。一幢幢欧式建筑充满着浪漫、清新的异国情调，让人身在国内却犹如游览于“异国他乡”；一件件先进设备构成的国际顶尖巧克力流水线，观赏到巧克力生产的神奇奥秘；一粒粒可可豆讲述一段奇妙的巧克力故事，让人感受到可可豆的神奇魅力。一个个家庭携子进入儿童DI',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 225,
        'name': '临安云制造小镇',
        'type': '科技创新',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '云制造小镇依托于青山湖科技城，尽享传统制造业雄厚基础、科研院所强大科技支撑和众多创客无限创造力。在3.17平方公里的云制造小镇里，核心区众创空间就有1364亩，包括众创服务中心、创智天地、科技创意园、创客工厂等创业创新平台。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 226,
        'name': '天子岭静脉小镇',
        'type': '科技创新',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '天子岭静脉小镇坐落于杭州市北郊，毗邻半山国家森林公园，面积3.8平方公里。小镇以杭州天子岭循环经济产业园为基础，践行“绿水青山就是金山银山”环保理念，打造以绿色为主题，环保产业为核心，旅游和文化协同发展的城市“最美出口”。天子岭始终站在保障城市出口、提高环境质量第一线，并以此为基点构建了清洁直运解决方案、城市垃圾绿色处置、固体废弃物资利用、生态文明环保教育、环境设计价值输出五大业务板块，业务涵盖垃',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 227,
        'name': '萧山信息港小镇',
        'type': '科技创新',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '信息港小镇，位于浙江省杭州市萧山区，国家级经济技术开发区萧山经济技术开发区内，规划面积3.12平方公里。小镇依托杭州湾信息港为主要载体，以新一代信息技术为主导，以“互联网+”为特色，重点引进软件和信息服务、互联网及互联网+产业，围绕“信息改变生活”这一主题，将小镇打造为萧山两化深度融合的主平台、科技创新驱动的新引擎，杭州互联网经济的新硅谷、大众创业的新空间、跨境电商的先行区。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 228,
        'name': '艺尚小镇',
        'type': '科技创新',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '艺尚小镇位于临平区临平新城核心区，东连桐乡、海宁，北接德清，南与杭州主城、下沙副城相连，位于长三角城市群发展的核心位置。中国纺织工业联合会、中国服装协会、中国服装设计师协会与余杭区政府签署合作协议，将艺尚小镇建设成为文化创意推动、科技创新聚集、可持续发展导向的数字时尚高地，推动艺尚小镇“中国时尚风向地、中国奢侈品海淘地、中国网红直播引领地、中国潮流文化集聚地、中国数字时尚融合地”等“五地”的打造，',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 229,
        'name': '萧山机器人小镇',
        'type': '科技创新',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '机器人小镇主力发展工业机器人，鼓励发展服务机器人，积极发展机器人关键零部件，打造集机器人研发设计、孵化放大、生产制造、终端应用等功能于一体的机器人全产业链特色小镇。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 230,
        'name': '未来科技城',
        'type': '红色教育',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '杭州未来科技城（海创园）总面积113平方公里，北至杭长高速公路，东至杭州绕城高速公路，南至杭徽高速公路（02省道），西至南湖。在此基础上，划定了未来科技城（海创园）35平方公里重点建设区，具体范围为北至宣杭铁路，东至杭州绕城高速公路，南至和睦水乡，西至东西大道（含永乐区块）。已落户阿里巴巴淘宝城、中国移动4G研究院、南方水泥、奥克斯研究院、浙江福彩等项目。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 231,
        'name': '玉皇山南基金小镇',
        'type': '科技创新',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '玉皇山南基金小镇是一个类似于美国对冲基金天堂格林尼治的基金小镇，位于杭州上城区，于2015年05月17日揭牌创建。该小镇以金融产业为主，截止2016年底，入驻企业超1000家，管理资产规模超5900亿元，实现税收超10亿元。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 232,
        'name': '嘉兴嘉佑农业',
        'type': '美丽乡村',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '浙江嘉佑农业发展有限公司于2017年07月07日成立。法定代表人吴忠泉，公司经营范围包括：一般项目：谷物种植；油料种植；豆类种植；蔬菜种植；水果种植；花卉种植；园艺产品种植；农业园艺服务；农业机械服务；农作物病虫害防治服务；智能农业管理；农业机械租赁；食用农产品初加工；食用农产品零售；食用农产品批发；农副产品销售；林业产品销售；日用品销售；农业科学研究和试验发展；农业生产托管服务；与农业生产经营有',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 233,
        'name': '阿里巴巴园区',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '阿里巴巴是以曾担任英语教师的马云为首的18人于1999年在浙江省杭州市创立的公司。2014年9月19日，阿里巴巴集团在纽约证券交易所正式挂牌上市，创造了史上最大IPO记录，股票代码“BABA”。现阿里巴巴集团之下，设立阿里云智能、淘宝天猫商业、国际数字商业、本地生活、菜鸟、大文娱等6大业务集团和多家业务公司。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 234,
        'name': '绍兴鲁迅纪念馆',
        'type': '红色教育',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '绍兴鲁迅纪念馆（Lu Xun Memorial Museum），始建于1973年，位于浙江省绍兴市越城区鲁迅中路235号，总占地面积达6000平方米，总建筑面积达5000平方米。绍兴鲁迅纪念馆是建国后浙江省最早建立的纪念性人物博物馆。主展厅共两层，分为南、北展厅两个大空间形式，同时又与序厅紧密相连。南展厅二层为中庭式回廊展场，主要展出鲁迅的生平事迹。 1994年，绍兴鲁迅纪念馆获批为全国优秀社会教',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 235,
        'name': '华立集团',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '华立创立于1970年9月28日，是以华立集团股份有限公司为母体，以医药为核心主业、多元化投资发展的企业集团。业务涉及医药、电能计量仪表及电力自动化系统、电子材料、房地产、现代农业、石油化工、矿产开发等领域。全球员工超过10000人。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 236,
        'name': '桐庐美丽乡村',
        'type': '美丽乡村',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '桐庐美丽乡村-东梓关村、荻浦村、环溪村、深奥村、芦茨村',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 237,
        'name': '良渚博物院',
        'type': '红色教育',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '良渚文化距今约5300——4300年，院内共展出良渚文化时期玉器、石器、陶器和漆木器等各类珍贵文物600多件（组）。展览力求创新陈列理念、合理运用先进的展示方法和手段，努力实现传播方式多元化，将博物馆传统展示与数字化展示等手段相结合，合理使用大型油画、场景复原、数字多媒体及3D打印等新技术，加强观众在实体文物中参观的感受，扩展了博物馆的有限展示空间，为观众提供个性化的数字化展示服务。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 238,
        'name': '跨湖桥遗址博物馆',
        'type': '红色教育',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '跨湖桥遗址是全国重点文物保护单位，是我省继河姆渡之后史前考古工作的又一重大发现，把浙江的文明史提前到了8000年前，被评为“2001年度全国考古十大新发现”，2004年被正式命名为“跨湖桥文化”，2006年被国务院公布为第六批全国重点文物保护单位。遗址出土的世界第一舟及相关遗迹在全国乃至世界具有重大影响。时任浙江省委书记习近平同志曾于2005年和2006年两次亲临视察并作出重要指示，要求研究好、保',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 239,
        'name': '九阳工厂',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '九阳股份有限公司成立于1994年，是一家专注于健康饮食电器研发、生产和销售的现代企业。2014年，九阳诞生了第1亿个豆浆机用户。了解企业发展历程、品牌文化、历史产品等，参观智能制造工厂参观、园区参观等。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 240,
        'name': '萧山瓜沥七彩社区',
        'type': '美丽乡村',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '瓜沥七彩未来社区是浙江省首批24个未来社区试点创建项目之一。社区地处瓜沥镇新区核心地块，是新建与改造结合的未来社区，总投资44亿，规划单元面积约79.21公顷，实施单元面积约40.34公顷。区块内功能配套完善，交通区位优势明显，距杭州市主城区车程30分钟，距杭州萧山国际机场车程15分钟，距杭甬高速瓜沥出口车程5分钟。瓜沥镇是全国综合实力百强行列，排名全区、全市最靠前，位列全国第35位，蝉联“杭州第',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 241,
        'name': '安恒信息',
        'type': '企业参访',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '杭州安恒信息技术股份有限公司国内总部设在杭州及北京，并在上海、南京、广州、深圳、成都、重庆、济南、西安等多个城市设有分支机构。安恒信息多次入选全球网络安全500强，曾先后为北京奥运会、国庆60周年庆典、上海世博会、广州亚运会、抗战七十周年、连续三届世界互联网大会、G20杭州峰会、厦门金砖峰会等众多活动提供网络信息安全保障。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 242,
        'name': '安吉大竹园村',
        'type': '美丽乡村',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '安吉大竹园村位于灵峰旅游度假区西南部是度假区的南大门，东南邻天荒坪镇白水湾村，西与刘家塘村接壤，北与孝丰镇交界，东与灵峰景区相连，距县城10公里，区域位置明显。行政区域面积8.7平方公里，共有山林6500亩，耕地3325.5亩。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 243,
        'name': '东阳花园村',
        'type': '美丽乡村',
        'supplier': '徐燕',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '花园村先后被授予全国先进基层党组织、全国新农村建设A级学习考察点，中国村官培训基地、全国文明村、全国模范村、中国十大国际名村等一百多项省级以上荣誉称号。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 244,
        'name': '大华股份',
        'type': '企业参访',
        'supplier': '袁园',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '全球领先的以视频为核心的智慧物联解决方案提供商和运营服务商。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 245,
        'name': '湘湖金融小镇',
        'type': '科技创新',
        'supplier': '章子莹',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '以国家旅游度假区和5A景区建设为契机，充分发挥人文环境优势，吸引私募基金、企业直投机构、金融投资公司等机构，重点发展私募金融，集聚股权投资、风险投资、天使投资、上市企业投融资总部等业态，建设中国版“苏黎世湖区”。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 246,
        'name': '许梦逸（多兰）',
        'type': '企业参访',
        'supplier': '超级管理员',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '阿里钉钉资深部署专家，帮助超1200家企业实现数字化管理及数字化组织打造，阿里钉钉服务转化率最高的90后专家。',
        'created_at': datetime(2026, 1, 1)
    },
    {
        'id': 247,
        'name': '娃哈哈集团',
        'type': '企业参访',
        'supplier': '超级管理员',
        'contact_name': '',
        'contact_phone': '',
        'price': None,
        'address': '',
        'audit_status': '已通过',
        'introduction': '杭州娃哈哈集团有限公司创建于1987年，为中国最大，全球第五的食品饮料生产企业。是在销售收入、利润、利税等指标上已连续11年位居中国饮料行业首位，成为中国最大、效益最好、最具发展潜力的食品饮料企业。',
        'created_at': datetime(2026, 1, 1)
    }
]


# 班主任候选列表（后续从权限系统读取）
class_advisors_list = ['朱倩倩', '高芳荣']

# 班级开班前自查清单模板（5阶段32项）
CHECKLIST_TEMPLATE = [
    {
        'stage': '确定培训班',
        'items': [
            '申报合同（3个附件：委托函、申报表、现场教学备案表）',
            '申报项目',
            '初算费用（培训费、住宿费、用餐分别多少）',
            '订好酒店'
        ]
    },
    {
        'stage': '确定培训',
        'items': [
            '确定课表（提前约好老师）',
            '确定现场教学（提前约好现场教学）',
            '确定用餐（食堂85-60元；七舍提前预定100元；酒店用餐；现场教学用餐）',
            '确定航班高铁',
            '接机牌',
            '确定合同（申报合同未确认可修改一次，已确认或已修改一次再次修改需找xx。PDF版打印三份，每份盖章、手写签字、骑缝章，合同需提前签好快递或者开班当天给xx）',
            '学员名单（浙大班6项：姓名、性别、身份证号、单位、职务、联系方式）',
            '对方开学领导',
            '我方开学领导（提前7-10天以上预约）',
            '结业领导（一般无结业，单位要求结业即自己联系中心开学领导结业）'
        ]
    },
    {
        'stage': '临近开班',
        'items': [
            '安排用车（提前5-7天以上预约）',
            '订好水果',
            '申领物资',
            '预约拍照',
            '老师、学员、大巴车进校报备',
            '老师课件（索要课件即可再次确认老师上课时间，并确定老师时间是否安排冲突）',
            '打印手册--制作横幅--桌牌（学员-老师-领导），备查手册防督导检查',
            '开学典礼流程-主持稿-开学PPT'
        ]
    },
    {
        'stage': '开班',
        'items': [
            '提醒老师（每天一早发信息第二天上课老师）',
            '提醒领导（提前一天）',
            '布置教室（红绒布-音响、无线话筒、电脑检测-U盘备份课件-翻页笔）',
            '交课表（开班当天及更早）',
            '做证书（开班当天及更早）',
            '打印预案和签承诺书（收集好后给赵老师备案）'
        ]
    },
    {
        'stage': '结束',
        'items': [
            '归还物资',
            '课酬结算',
            '各类报销',
            '结算表'
        ]
    }
]

# 班级自查清单存储 {class_id: [ checklist_items ]}
class_checklists = {}

def init_class_checklist(class_id):
    """为班级初始化自查清单"""
    if class_id in class_checklists:
        return
    checklist = []
    for stage_data in CHECKLIST_TEMPLATE:
        for idx, item in enumerate(stage_data['items']):
            checklist.append({
                'id': len(checklist) + 1,
                'stage': stage_data['stage'],
                'item_index': idx + 1,
                'content': item,
                'is_checked': False,
                'checked_at': None,
                'checked_by': None
            })
    class_checklists[class_id] = checklist

def get_checklist_progress(class_id):
    """获取班级自查清单进度"""
    if class_id not in class_checklists:
        init_class_checklist(class_id)
    checklist = class_checklists[class_id]
    total = len(checklist)
    checked = sum(1 for item in checklist if item['is_checked'])
    percentage = round((checked / total * 100), 1) if total > 0 else 0
    return {
        'total': total,
        'checked': checked,
        'percentage': percentage,
        'by_stage': {}
    }
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


# ==================== 用户权限管理 ====================
@app.route('/users/api/list', methods=['GET'])
@login_required_web
@require_role_web('admin', 'center_director')
def users_api_list():
    """获取用户列表API"""
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


@app.route('/users/api/create', methods=['POST'])
@login_required_web
@require_role_web('admin', 'center_director')
def users_api_create():
    """创建用户API"""
    from models import User, db
    from werkzeug.security import generate_password_hash
    
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


@app.route('/users/api/<int:user_id>/update', methods=['POST'])
@login_required_web
@require_role_web('admin', 'center_director')
def users_api_update(user_id):
    """更新用户API"""
    from models import User, db
    from werkzeug.security import generate_password_hash
    
    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'message': '用户不存在'}), 404
    
    # 不能修改自己
    if user.id == session.get('user_id'):
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


@app.route('/users/api/<int:user_id>/toggle', methods=['POST'])
@login_required_web
@require_role_web('admin', 'center_director')
def users_api_toggle(user_id):
    """启用/禁用用户API"""
    from models import User, db
    
    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'message': '用户不存在'}), 404
    
    # 不能禁用自己
    if user.id == session.get('user_id'):
        return jsonify({'success': False, 'message': '不能禁用自己'}), 400
    
    user.is_active = not user.is_active
    db.session.commit()
    
    status = '启用' if user.is_active else '禁用'
    return jsonify({
        'success': True,
        'message': f'用户已{status}',
        'is_active': user.is_active
    })


@app.route('/users/api/<int:user_id>/delete', methods=['POST'])
@login_required_web
@require_role_web('admin', 'center_director')
def users_api_delete(user_id):
    """删除用户API"""
    from models import User, db
    
    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'message': '用户不存在'}), 404
    
    # 不能删除自己
    if user.id == session.get('user_id'):
        return jsonify({'success': False, 'message': '不能删除自己'}), 400
    
    db.session.delete(user)
    db.session.commit()
    
    return jsonify({'success': True, 'message': '用户已删除'})


# ==================== 首页仪表盘 ====================
# ==================== 班级分类 ====================
# ==================== 教室管理 ====================
# ==================== API 路由：排课页面新增教室/现场教学点 ====================
# ==================== 现场教学 ====================
# ==================== 师资管理 ====================
@app.route('/teachers/export')
@require_role_web('admin', 'center_director')
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

# ==================== 学员导出 ====================
@app.route('/students/export')
@require_role_web('admin', 'center_director')
def students_export():
    """导出学员列表为CSV"""
    import csv
    import io
    from models import Student
    
    keyword = request.args.get('keyword', '')
    
    query = Student.query
    if keyword:
        query = query.filter(
            db.or_(
                Student.name.contains(keyword),
                Student.phone.contains(keyword),
                Student.company.contains(keyword)
            )
        )
    
    students_list = query.order_by(Student.created_at.desc()).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # 表头
    writer.writerow(['ID', '姓名', '性别', '手机号', '单位', '职务', '省份', '证件类型', '证件号码', '上课次数', '创建时间'])
    
    # 数据行
    for s in students_list:
        writer.writerow([
            s.id,
            s.name or '',
            s.gender or '',
            s.phone or '',
            s.company or '',
            s.job or '',
            s.province or '',
            s.id_type or '',
            s.id_card or '',
            s.total_attendance or 0,
            s.created_at.strftime('%Y-%m-%d') if s.created_at else ''
        ])
    
    output.seek(0)
    
    from flask import Response
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename=students_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv',
            'Content-Type': 'text/csv; charset=utf-8-sig'
        }
    )


# ==================== 班级导出 ====================
@app.route('/classes/export')
@require_role_web('admin', 'center_director')
def classes_export():
    """导出班级列表为CSV"""
    import csv
    import io
    from models import ClassInfo
    
    keyword = request.args.get('keyword', '')
    status = request.args.get('status', '')
    
    query = ClassInfo.query
    if keyword:
        query = query.filter(ClassInfo.name.contains(keyword))
    if status:
        query = query.filter(ClassInfo.status == status)
    
    classes_list = query.order_by(ClassInfo.id.desc()).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # 表头
    writer.writerow(['ID', '班级名称', '班级类型', '项目主任', '班主任', '开始日期', '结束日期', '状态', '创建时间'])
    
    # 数据行
    for c in classes_list:
        writer.writerow([
            c.id,
            c.name or '',
            c.class_type or '',
            c.project_manager or '',
            c.class_teacher or '',
            c.start_date.strftime('%Y-%m-%d') if c.start_date else '',
            c.end_date.strftime('%Y-%m-%d') if c.end_date else '',
            c.status or '',
            c.created_at.strftime('%Y-%m-%d') if c.created_at else ''
        ])
    
    output.seek(0)
    
    from flask import Response
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename=classes_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv',
            'Content-Type': 'text/csv; charset=utf-8-sig'
        }
    )


# ==================== 现场教学导出 ====================
@app.route('/sites/export')
@require_role_web('admin', 'center_director')
def sites_export():
    """导出现场教学点列表为CSV"""
    import csv
    import io
    
    keyword = request.args.get('keyword', '')
    site_type = request.args.get('type', '')
    audit_status = request.args.get('audit_status', '')
    
    filtered_sites = teaching_sites.copy()
    if keyword:
        filtered_sites = [s for s in filtered_sites if keyword in s['name']]
    if site_type:
        filtered_sites = [s for s in filtered_sites if s['type'] == site_type]
    if audit_status:
        filtered_sites = [s for s in filtered_sites if s['audit_status'] == audit_status]
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # 表头
    writer.writerow(['ID', '名称', '类型', '供应商', '联系人', '联系电话', '价格(元/人)', '地址', '审核状态'])
    
    # 数据行
    for s in filtered_sites:
        writer.writerow([
            s['id'],
            s['name'],
            s['type'],
            s['supplier'],
            s['contact_name'],
            s['contact_phone'],
            s['price'],
            s['address'],
            s['audit_status']
        ])
    
    output.seek(0)
    
    from flask import Response
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename=sites_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv',
            'Content-Type': 'text/csv; charset=utf-8-sig'
        }
    )


# ==================== 教室导出 ====================
@app.route('/classrooms/export')
@require_role_web('admin', 'center_director')
def classrooms_export():
    """导出教室列表为CSV"""
    import csv
    import io
    
    keyword = request.args.get('keyword', '')
    room_type = request.args.get('type', '')
    
    filtered_rooms = classrooms.copy()
    if keyword:
        filtered_rooms = [r for r in filtered_rooms if keyword in r['name']]
    if room_type:
        filtered_rooms = [r for r in filtered_rooms if r['type'] == room_type]
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # 表头
    writer.writerow(['ID', '名称', '类型', '校区', '容量', '地址', '价格(元)', '状态'])
    
    # 数据行
    for r in filtered_rooms:
        writer.writerow([
            r['id'],
            r['name'],
            r['type'],
            r['campus'],
            r['capacity'],
            r['address'],
            r['price'],
            r['status']
        ])
    
    output.seek(0)
    
    from flask import Response
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename=classrooms_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv',
            'Content-Type': 'text/csv; charset=utf-8-sig'
        }
    )


# ==================== 分类导出 ====================
@app.route('/categories/export')
@require_role_web('admin', 'center_director')
def categories_export():
    """导出分类列表为CSV"""
    import csv
    import io
    
    keyword = request.args.get('keyword', '')
    
    filtered_categories = teacher_categories.copy()
    if keyword:
        filtered_categories = [c for c in filtered_categories if keyword in c['name']]
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # 表头
    writer.writerow(['ID', '名称', '层级', '父级ID', '父级名称', '排序', '描述'])
    
    # 数据行
    for c in filtered_categories:
        writer.writerow([
            c['id'],
            c['name'],
            c.get('level', 1),
            c.get('parent_id', ''),
            c.get('parent_name', ''),
            c.get('sort', 0),
            c.get('description', '')
        ])
    
    output.seek(0)
    
    from flask import Response
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename=categories_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv',
            'Content-Type': 'text/csv; charset=utf-8-sig'
        }
    )


# ==================== 班级管理 ====================
import re

# 智能识别学员字段
def smart_parse_student(text):
    """
    智能解析学员信息，不依赖字段顺序和分隔符。
    支持：逗号、空格、制表符、换行、分号、竖线等分隔符。
    返回: {'name':..., 'gender':..., 'id_type':..., 'id_card':..., 
           'phone':..., 'company':..., 'job':..., 'province':...} 或 None
    """
    text = text.strip()
    if not text:
        return None
    
    # 统一分隔符：把常见分隔符都换成逗号，然后拆分
    # 支持：逗号、中文逗号、空格、制表符、分号、竖线、换行、全角空格
    normalized = text.replace('，', ',').replace('\t', ',').replace(';', ',').replace('|', ',').replace('\u3000', ',')
    # 把多个连续空格/逗号合并为一个逗号
    import re
    normalized = re.sub(r'[,\s]+', ',', normalized)
    # 去掉开头和结尾的逗号
    normalized = normalized.strip(',')
    parts = [p.strip() for p in normalized.split(',') if p.strip()]
    
    result = {
        'name': '', 'gender': '', 'id_type': '身份证', 'id_card': '',
        'phone': '', 'company': '', 'job': '', 'province': ''
    }
    
    # 已分配的片段索引
    used = set()
    
    # 1. 识别性别（最简单，先识别）
    for i, p in enumerate(parts):
        if i in used:
            continue
        if p in ['男', '女']:
            result['gender'] = p
            used.add(i)
            break
    
    # 2. 识别证件类型
    for i, p in enumerate(parts):
        if i in used:
            continue
        if p in ['身份证', '护照', '其他']:
            result['id_type'] = p
            used.add(i)
            break
    
    # 3. 识别手机号（11位，1开头）
    for i, p in enumerate(parts):
        if i in used:
            continue
        if re.match(r'^1[3-9]\d{9}$', p):
            result['phone'] = p
            used.add(i)
            break
    
    # 4. 识别身份证号（18位）
    for i, p in enumerate(parts):
        if i in used:
            continue
        if re.match(r'^\d{17}[\dXx]$', p):
            result['id_card'] = p
            result['id_type'] = '身份证'
            used.add(i)
            break
    
    # 5. 识别护照号（字母+数字，不含中文）
    if not result['id_card']:
        for i, p in enumerate(parts):
            if i in used:
                continue
            if re.match(r'^[A-Za-z]\d{7,9}$', p):
                result['id_card'] = p
                result['id_type'] = '护照'
                used.add(i)
                break
    
    # 6. 识别省份（以省/市/自治区结尾）
    for i, p in enumerate(parts):
        if i in used:
            continue
        if re.search(r'(省|市|自治区|特别行政区)$', p):
            result['province'] = p
            used.add(i)
            break
    
    # 7. 识别职务（关键词匹配）
    job_keywords = ['工程师', '经理', '主任', '教授', '处长', '局长', '部长', '科长', '科员',
                   '总监', '主管', '专员', '助理', '顾问', '讲师', '研究员', '秘书',
                   '书记', '校长', '院长', '所长', '厂长', '店长', '组长', '班长',
                   '总裁', '副总裁', '总经理', '副总经理', '董事长', '副董事长', '监事长',
                   '教师', '医生', '护士', '律师', '会计师', '经济师', '医师']
    for i, p in enumerate(parts):
        if i in used:
            continue
        if any(kw in p for kw in job_keywords) and len(p) <= 15:
            result['job'] = p
            used.add(i)
            break
    
    # 8. 识别单位（含单位关键词，或较长字符串）
    company_keywords = ['大学', '学院', '公司', '集团', '研究院', '研究所', '中心', '医院',
                       '学校', '银行', '局', '厅', '部', '委', '办', '公社', '协会',
                       '工厂', '企业', '机关', '政府', '报社', '电视台', '出版社',
                       '科技', '技术', '咨询', '管理', '服务', '贸易', '实业', '文化',
                       '教育', '培训', '传媒', '网络', '软件', '信息', '智能', '数据']
    for i, p in enumerate(parts):
        if i in used:
            continue
        if any(kw in p for kw in company_keywords) and len(p) >= 4:
            result['company'] = p
            used.add(i)
            break
    
    # 9. 识别姓名（剩余中文字符，2-4个字）
    for i, p in enumerate(parts):
        if i in used:
            continue
        if re.match(r'^[\u4e00-\u9fa5·]{2,5}$', p):
            result['name'] = p
            used.add(i)
            break
    
    # 10. 如果还有未分配，尝试补充
    remaining = [parts[i] for i in range(len(parts)) if i not in used]
    
    # 如果缺少姓名，从剩余里找一个最像人名的（2-4个中文字符）
    if not result['name']:
        for p in remaining:
            if re.match(r'^[\u4e00-\u9fa5]{2,4}$', p):
                result['name'] = p
                remaining.remove(p)
                break
    
    # 如果缺少单位，从剩余里找最长的作为单位
    if not result['company'] and remaining:
        longest = max(remaining, key=len)
        if len(longest) >= 4:
            result['company'] = longest
            remaining.remove(longest)
    
    # 如果缺少职务，从剩余里找一个较短的作为职务
    if not result['job'] and remaining:
        shortest = min(remaining, key=len)
        if len(shortest) <= 10:
            result['job'] = shortest
    
    return result


# ==================== 班级自查清单 ====================
# ==================== 课表管理 ====================
# ==================== 学员管理 ====================
@app.route('/students/<int:id>/evaluate', methods=['POST'])
@login_required_web
def student_evaluate(id):
    """学员提交评价"""
    if session.get('role') != 'student':
        flash('只有学员可以提交评价', 'error')
        return redirect(url_for('student_detail', id=id))
    
    student = Student.query.get(id)
    if not student:
        flash('学员不存在', 'error')
        return redirect(url_for('students_list'))
    
    score = request.form.get('score', type=float)
    content = request.form.get('content', '').strip()
    
    if not score or score < 1 or score > 10:
        flash('评分必须在1-10分之间', 'error')
        return redirect(url_for('student_detail', id=id))
    
    if not content:
        flash('评价内容不能为空', 'error')
        return redirect(url_for('student_detail', id=id))
    
    # 创建评价记录（简化版：关联到第一个可用的教师）
    from models import Evaluation
    eval_record = Evaluation(
        teacher_id=1,  # 简化处理，关联到第一个教师
        evaluator_name=student.name,
        evaluator_type='学员',
        score=score,
        content=content
    )
    db.session.add(eval_record)
    db.session.commit()
    
    flash('评价提交成功！', 'success')
    return redirect(url_for('student_detail', id=id))
def student_new():
    """新增学员"""
    if request.method == 'POST':
        # 必填字段验证
        name = request.form.get('name', '').strip()
        gender = request.form.get('gender', '').strip()
        id_type = request.form.get('id_type', '身份证').strip()
        id_card = request.form.get('id_card', '').strip()
        phone = request.form.get('phone', '').strip()
        company = request.form.get('company', '').strip()
        job = request.form.get('job', '').strip()
        
        errors = []
        if not name:
            errors.append('姓名不能为空')
        if not gender:
            errors.append('性别不能为空')
        if not id_card:
            errors.append('证件号码不能为空')
        if not phone:
            errors.append('手机号不能为空')
        if not company:
            errors.append('单位不能为空')
        if not job:
            errors.append('职务不能为空')
        
        if errors:
            for e in errors:
                flash(e, 'error')
            return render_template('students/form.html', classes=classes)
        
        new_student = Student(
            name=name,
            gender=gender,
            id_type=id_type,
            id_card=id_card,
            phone=phone,
            company=company,
            job=job,
            province=request.form.get('province', '').strip(),
            class_id=int(request.form.get('class_id', 0)) if request.form.get('class_id') else None
        )
        db.session.add(new_student)
        db.session.commit()
        flash('学员添加成功', 'success')
        
        # 如果从班级页面添加，返回班级编辑页面
        return_class_id = request.form.get('return_class_id')
        if return_class_id:
            return redirect(url_for('class_edit', id=int(return_class_id)))
        
        return redirect(url_for('students_list'))
    return render_template('students/form.html', classes=classes)


# ==================== 课程管理 ====================
# ==================== 课酬管理 ====================
# ==================== 审批管理 ====================
# ==================== API接口 ====================
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


# ==================== Excel学员导入辅助函数 ====================
def _import_students_from_excel(class_id, file):
    """从Excel文件导入学员到班级"""
    import pandas as pd
    from io import BytesIO
    
    try:
        df = pd.read_excel(BytesIO(file.read()))
    except Exception as e:
        flash(f'Excel解析失败: {str(e)}', 'error')
        return redirect(url_for('import_students', id=class_id))
    
    # 列名映射（支持中文和英文）
    column_mapping = {
        '姓名': 'name', 'name': 'name',
        '性别': 'gender', 'gender': 'gender',
        '证件类型': 'id_type', 'id_type': 'id_type',
        '证件号码': 'id_card', 'id_card': 'id_card', '身份证号': 'id_card',
        '手机号': 'phone', 'phone': 'phone', '联系电话': 'phone',
        '单位': 'company', 'company': 'company', '工作单位': 'company',
        '职位': 'job', 'job': 'job', '职务': 'job',
        '省份': 'province', 'province': 'province'
    }
    
    # 重命名列
    renamed = {}
    for col in df.columns:
        col_str = str(col).strip()
        if col_str in column_mapping:
            renamed[col_str] = column_mapping[col_str]
    
    df = df.rename(columns=renamed)
    
    # 确保必要列存在
    if 'name' not in df.columns:
        flash('Excel中未找到"姓名"列，请使用正确的模板', 'error')
        return redirect(url_for('import_students', id=class_id))
    
    added = 0
    errors = []
    
    for idx, row in df.iterrows():
        name = str(row.get('name', '')).strip()
        if not name or name == 'nan':
            continue
        
        gender = str(row.get('gender', '男')).strip()
        id_type = str(row.get('id_type', '身份证')).strip()
        id_card = str(row.get('id_card', '')).strip()
        phone = str(row.get('phone', '')).strip()
        company = str(row.get('company', '')).strip()
        job = str(row.get('job', '')).strip()
        province = str(row.get('province', '')).strip()
        
        # 验证必填字段
        missing = []
        if not name:
            missing.append('姓名')
        if not id_card:
            missing.append('证件号码')
        if not phone:
            missing.append('手机号')
        if not company:
            missing.append('单位')
        if not job:
            missing.append('职务')
        
        if missing:
            errors.append(f"第{idx+1}行 ({name or '未知'}): 缺少 {', '.join(missing)}")
            continue
        
        # 验证手机号
        if not re.match(r'^1[3-9]\d{9}$', phone):
            errors.append(f"第{idx+1}行 ({name}): 手机号格式不正确")
            continue
        
        # 验证性别
        if gender not in ['男', '女']:
            gender = '男'  # 默认男
        
        # 检查是否已存在
        existing = Student.query.filter_by(phone=phone).first()
        if existing:
            # 更新班级关联
            existing.class_id = class_id
            db.session.commit()
            added += 1
            continue
        
        student = Student(
            name=name,
            gender=gender,
            id_type=id_type or '身份证',
            id_card=id_card,
            phone=phone,
            company=company,
            job=job,
            province=province or '',
            class_id=class_id
        )
        db.session.add(student)
        added += 1
    
    db.session.commit()
    
    if errors:
        flash(f'成功导入 {added} 名学员，{len(errors)} 行有误', 'success' if added > 0 else 'warning')
        for e in errors[:5]:
            flash(e, 'error')
    else:
        flash(f'成功导入 {added} 名学员', 'success')
    
    return redirect(url_for('class_edit', id=class_id))

# ==================== 启动应用 ====================
with app.app_context():
    db.create_all()
    sync_classes_to_db()
    
    # 自动检测并导入基础数据
    import sqlite3
    db_path = os.path.join(basedir, 'instance', 'teacher_system.db')
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 检查教师数据
        cursor.execute('SELECT COUNT(*) FROM teachers')
        teacher_count = cursor.fetchone()[0]
        if teacher_count == 0:
            print('🔄 数据库教师数据为空，自动导入中...')
            try:
                import subprocess
                result = subprocess.run(['python3', 'scripts/import_teachers_to_db.py'], 
                                      cwd=basedir, capture_output=True, text=True)
                if result.returncode == 0:
                    print('✅ 教师数据自动导入完成')
                else:
                    print(f'⚠️ 教师数据导入输出: {result.stdout[-200:]}')
            except Exception as e:
                print(f'⚠️ 教师数据自动导入失败: {e}')
        else:
            print(f'✅ 教师数据已存在: {teacher_count} 条')
        
        # 检查教室数据
        cursor.execute('SELECT COUNT(*) FROM classrooms')
        room_count = cursor.fetchone()[0]
        if room_count == 0:
            print('🔄 数据库教室数据为空，自动导入中...')
            try:
                import subprocess
                result = subprocess.run(['python3', 'scripts/import_rooms_and_sites.py'], 
                                      cwd=basedir, capture_output=True, text=True)
                if result.returncode == 0:
                    print('✅ 教室和现场教学点数据自动导入完成')
                else:
                    print(f'⚠️ 教室导入输出: {result.stdout[-200:]}')
            except Exception as e:
                print(f'⚠️ 教室数据自动导入失败: {e}')
        else:
            print(f'✅ 教室数据已存在: {room_count} 条')
        
        conn.close()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

# ==================== 学员签到功能 ====================
@app.route('/attendance/sign-in', methods=['GET', 'POST'])
@login_required_web
def attendance_sign_in():
    """学员签到/签退页面"""
    from models import Student, AttendanceRecord, ClassInfo
    
    # 如果是学员账号，找到自己的学员记录
    user_role = session.get('role', '')
    user_id = session.get('user_id')
    
    if user_role == 'student':
        # 学员只能签到自己
        student = Student.query.filter_by(user_id=user_id).first()
        if not student:
            flash('未找到您的学员信息', 'error')
            return redirect(url_for('index'))
        
        if request.method == 'POST':
            action = request.form.get('action', 'sign_in')  # sign_in 或 sign_out
            class_id = request.form.get('class_id', type=int)
            
            if not class_id:
                flash('请选择班级', 'error')
                return redirect(url_for('attendance_sign_in'))
            
            # 检查今天是否已签到
            today = datetime.now().date()
            existing = AttendanceRecord.query.filter(
                db.func.date(AttendanceRecord.sign_in_time) == today,
                AttendanceRecord.student_id == student.id,
                AttendanceRecord.class_id == class_id
            ).first()
            
            if action == 'sign_in':
                if existing and existing.sign_in_time:
                    flash('今天已经签到过了', 'warning')
                else:
                    record = AttendanceRecord(
                        student_id=student.id,
                        class_id=class_id,
                        sign_in_time=datetime.now(),
                        sign_method='手动'
                    )
                    db.session.add(record)
                    db.session.commit()
                    flash('签到成功！', 'success')
            
            elif action == 'sign_out':
                if not existing:
                    flash('今天还未签到，无法签退', 'error')
                elif existing.sign_out_time:
                    flash('今天已经签退过了', 'warning')
                else:
                    existing.sign_out_time = datetime.now()
                    db.session.commit()
                    flash('签退成功！', 'success')
            
            return redirect(url_for('attendance_sign_in'))
        
        # 学员：显示自己的签到记录和可签到班级
        my_classes = []
        if student.class_id:
            cls = ClassInfo.query.get(student.class_id)
            if cls:
                my_classes = [cls]
        
        records = AttendanceRecord.query.filter_by(student_id=student.id).order_by(AttendanceRecord.created_at.desc()).limit(30).all()
        
        return render_template('attendance/sign_in.html',
                             student=student,
                             my_classes=my_classes,
                             records=records,
                             is_student=True)
    
    else:
        # 老师/班主任/管理员：管理签到
        selected_class = request.args.get('class_id', '')
        selected_date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
        
        query = AttendanceRecord.query
        if selected_class:
            query = query.filter(AttendanceRecord.class_id == int(selected_class))
        if selected_date:
            date_obj = datetime.strptime(selected_date, '%Y-%m-%d')
            query = query.filter(db.func.date(AttendanceRecord.sign_in_time) == date_obj.date())
        
        records = query.order_by(AttendanceRecord.sign_in_time.desc()).all()
        
        return render_template('attendance/sign_in.html',
                             records=records,
                             classes=ClassInfo.query.all(),
                             selected_class=selected_class,
                             selected_date=selected_date,
                             is_student=False)


@app.route('/attendance/sign-in-admin', methods=['GET', 'POST'])
@login_required_web
def attendance_admin():
    """签到管理后台 - 管理员/班主任"""
    from models import Student, AttendanceRecord, ClassInfo
    
    user_role = session.get('role', '')
    user_name = session.get('name', '')
    
    selected_class = request.args.get('class_id', '')
    selected_date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    
    # 查询班级列表
    class_query = ClassInfo.query
    if user_role == 'class_advisor':
        class_query = class_query.filter(ClassInfo.class_teacher == user_name)
    classes_list = class_query.all()
    
    # 查询签到记录
    query = AttendanceRecord.query
    if selected_class:
        query = query.filter(AttendanceRecord.class_id == int(selected_class))
    if selected_date:
        date_obj = datetime.strptime(selected_date, '%Y-%m-%d')
        query = query.filter(db.func.date(AttendanceRecord.sign_in_time) == date_obj.date())
    
    records = query.order_by(AttendanceRecord.sign_in_time.desc()).all()
    
    if request.method == 'POST':
        # 批量签到/签退操作
        student_id = request.form.get('student_id', type=int)
        class_id = request.form.get('class_id', type=int)
        action = request.form.get('action', 'sign_in')
        
        if student_id and class_id:
            record = AttendanceRecord.query.filter_by(
                student_id=student_id,
                class_id=class_id
            ).filter(db.func.date(AttendanceRecord.sign_in_time) == datetime.now().date()).first()
            
            if action == 'sign_in':
                if not record:
                    record = AttendanceRecord(
                        student_id=student_id,
                        class_id=class_id,
                        sign_in_time=datetime.now(),
                        sign_method='手动'
                    )
                    db.session.add(record)
                    db.session.commit()
                    flash('签到成功', 'success')
                else:
                    flash('该学员今天已签到', 'warning')
            
            elif action == 'sign_out':
                if record and not record.sign_out_time:
                    record.sign_out_time = datetime.now()
                    db.session.commit()
                    flash('签退成功', 'success')
                else:
                    flash('该学员今天未签到或已签退', 'warning')
        
        return redirect(url_for('attendance_admin', class_id=selected_class, date=selected_date))
    
    return render_template('attendance/admin.html',
                         records=records,
                         classes=classes_list,
                         selected_class=selected_class,
                         selected_date=selected_date,
                         user_role=user_role)

# 注册蓝图（Clean Architecture 渐进式拆分）
try:
    from routes import (classrooms_bp, sites_bp, api_bp, teachers_bp, classes_bp,
                       courses_bp, students_bp, schedules_bp,
                       users_bp, categories_bp, compensations_bp, approvals_bp, home_bp)
    app.register_blueprint(classrooms_bp)
    app.register_blueprint(sites_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(teachers_bp)
    app.register_blueprint(classes_bp)
    app.register_blueprint(courses_bp)
    app.register_blueprint(students_bp)
    app.register_blueprint(schedules_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(categories_bp)
    app.register_blueprint(compensations_bp)
    app.register_blueprint(approvals_bp)
    app.register_blueprint(home_bp)
    
    # 注册导入导出蓝图 (ADR-005)
    try:
        from routes.import import import_bp
        app.register_blueprint(import_bp)
        print('✅ 导入导出蓝图注册成功')
    except Exception as e:
        print(f'⚠️ 导入导出蓝图注册失败: {e}')
    
    print('✅ 蓝图注册成功 (14个蓝图: classrooms, sites, api, teachers, classes, courses, students, schedules, users, categories, compensations, approvals, home, import)')
except Exception as e:
    print(f'⚠️ 蓝图注册失败: {e}')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
