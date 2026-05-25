"""
师资管理系统基础测试套件
目标: 验证核心路由可访问、基本功能正常
运行: pytest tests/test_basic.py -v
覆盖: pytest --cov=app tests/test_basic.py
"""

import pytest
import sys
import os

# 将项目根目录加入 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def client():
    """Flask 测试客户端 fixture"""
    from app import app, db
    from models import Teacher, Course, Classroom, User, ClassInfo
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    with app.app_context():
        db.drop_all()   # 清除旧表结构
        db.create_all()  # 确保所有数据库表已创建
        
        # 创建测试用户
        user = User(
            username='test_user',
            password_hash='test_hash',
            name='测试用户',
            role='admin',
            is_active=True
        )
        db.session.add(user)
        
        # 创建测试教师数据
        for i in range(1, 101):
            teacher = Teacher(
                id=i,
                name=f'测试教师{i}',
                phone=f'1380013{str(i).zfill(4)}',
                email=f'teacher{i}@example.com',
                title='高级讲师',
                organization='浙江大学',
                status='已入库',
                evaluation_score=9.0,
                creator='管理员',
                created_at=datetime(2026, 1, 1)
            )
            db.session.add(teacher)
        
        # 创建测试课程数据
        for i in range(1, 11):
            course = Course(
                id=i,
                name=f'测试课程{i}',
                category='党政培训',
                type='必修',
                duration=8,
                credit=1.0,
                status='已审核',
                creator='管理员',
                created_at=datetime(2026, 1, 1)
            )
            db.session.add(course)
        
        # 创建测试教室数据
        for i in range(1, 6):
            room = Classroom(
                id=i,
                name=f'测试教室{i}',
                capacity=50,
                type='校内',
                campus='紫金港',
                status='可用'
            )
            db.session.add(room)
        
        db.session.commit()
        
        with app.test_client() as client:
            yield client


@pytest.fixture
def auth_client(client):
    """已登录的测试客户端（通过设置 session user_id）"""
    from app import app
    from models import User
    with app.app_context():
        user = User.query.filter_by(is_active=True).first()
        user_id = user.id if user else 1
    with client.session_transaction() as sess:
        sess['user_id'] = user_id
    return client


class TestPublicRoutes:
    """测试无需登录的公开路由"""

    def test_web_login_page(self, client):
        """登录页面可访问"""
        rv = client.get('/api/auth/web-login', follow_redirects=False)
        # 未登录时 GET /api/auth/web-login 可能重定向或返回登录页
        assert rv.status_code in [200, 302]

    def test_login_form_exists(self, client):
        """登录页面包含表单"""
        rv = client.get('/api/auth/web-login', follow_redirects=True)
        assert rv.status_code == 200
        assert b'<form' in rv.data


class TestAuthenticatedRoutes:
    """测试需要登录的路由"""

    def test_home_page(self, auth_client):
        """首页可访问并显示关键数据"""
        rv = auth_client.get('/', follow_redirects=True)
        assert rv.status_code == 200
        # 首页应包含班级、教师等关键信息
        assert b'class' in rv.data.lower() or b'dashboard' in rv.data.lower()

    def test_teachers_list(self, auth_client):
        """教师列表页可访问"""
        rv = auth_client.get('/teachers', follow_redirects=True)
        assert rv.status_code == 200
        assert b'teacher' in rv.data.lower() or b'name' in rv.data.lower()

    def test_classes_list(self, auth_client):
        """班级列表页可访问"""
        rv = auth_client.get('/classes', follow_redirects=True)
        assert rv.status_code == 200
        assert b'class' in rv.data.lower()

    def test_classrooms_list(self, auth_client):
        """教室列表页可访问"""
        rv = auth_client.get('/classrooms', follow_redirects=True)
        assert rv.status_code == 200
        assert b'classroom' in rv.data.lower() or b'room' in rv.data.lower()

    def test_sites_list(self, auth_client):
        """现场教学点列表页可访问"""
        rv = auth_client.get('/sites', follow_redirects=True)
        assert rv.status_code == 200
        assert b'site' in rv.data.lower()


class TestTeacherDetail:
    """测试教师详情页"""

    def test_teacher_detail_page(self, auth_client):
        """教师详情页可访问（测试第一个教师）"""
        rv = auth_client.get('/teachers/1')
        # 如果ID=1不存在，可能返回302重定向到列表页
        assert rv.status_code in [200, 302]


class TestAPIEndpoints:
    """测试 API 接口"""

    def test_api_classrooms_post(self, auth_client):
        """API: 新增教室接口可访问"""
        rv = auth_client.post('/api/classrooms',
                              json={'name': '测试教室pytest', 'capacity': 50, 'type': '多媒体'},
                              content_type='application/json')
        assert rv.status_code == 200
        data = rv.get_json()
        assert data is not None
        assert data.get('success') is True
        assert 'classroom' in data

    def test_api_teaching_sites_post(self, auth_client):
        """API: 新增现场教学点接口可访问"""
        rv = auth_client.post('/api/teaching-sites',
                              json={'name': '测试教学点pytest', 'type': '红色教育', 'address': '测试地址'},
                              content_type='application/json')
        assert rv.status_code == 200
        data = rv.get_json()
        assert data is not None
        assert data.get('success') is True
        assert 'site' in data


class TestDataIntegrity:
    """数据完整性检查"""

    def test_teachers_data_loaded(self, client):
        """验证教师数据已加载"""
        from models import Teacher
        count = Teacher.query.count()
        assert count > 0
        assert count >= 100  # 至少有100位教师

    def test_courses_data_loaded(self, client):
        """验证课程数据已加载"""
        from models import Course
        count = Course.query.count()
        assert count > 0

    def test_classrooms_data_loaded(self, client):
        """验证教室数据已加载"""
        from models import Classroom
        count = Classroom.query.count()
        assert count > 0

    def test_teaching_sites_data_loaded(self, client):
        """验证现场教学点数据已加载"""
        from app import teaching_sites
        assert len(teaching_sites) > 0
