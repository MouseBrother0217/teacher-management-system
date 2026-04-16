"""
浙江大学继续教育师资管理系统 - 数据库模型
Database Models for Teacher Management System
"""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import event
import hashlib

db = SQLAlchemy()

class Teacher(db.Model):
    """
    教师基本信息表
    对应原系统：师资管理
    """
    __tablename__ = 'teachers'
    
    id = db.Column(db.Integer, primary_key=True)  # 主键ID (1-1905)
    name = db.Column(db.String(50), nullable=False, index=True, comment='姓名')
    field = db.Column(db.String(100), default='无', comment='专业领域')
    description = db.Column(db.Text, comment='简介/描述')
    avatar_url = db.Column(db.String(500), comment='头像URL')
    
    # 财务信息
    lecture_fee_half_day = db.Column(db.Integer, comment='半天课酬(元)')
    lecture_fee_full_day = db.Column(db.Integer, comment='全天课酬(元)')
    id_card = db.Column(db.String(18), comment='身份证号')
    bank_name = db.Column(db.String(100), comment='开户银行')
    bank_account = db.Column(db.String(50), comment='银行卡号')
    
    # 联系信息
    phone = db.Column(db.String(20), comment='手机号')
    
    # 分类标签
    teacher_type = db.Column(db.Enum('校内', '校外', name='teacher_type'), default='校外', comment='讲师类型')
    is_in_storage = db.Column(db.Boolean, default=False, comment='是否入库')
    level = db.Column(db.Enum('普通', '高级', name='teacher_level'), default='普通', comment='讲师级别')
    service_client = db.Column(db.String(100), comment='服务客户')
    
    # 统计数据
    total_teaching_count = db.Column(db.Integer, default=0, comment='上课次数')
    overall_score = db.Column(db.Float, default=0.0, comment='综合评分')
    total_evaluations = db.Column(db.Integer, default=0, comment='总评价数')
    
    # 系统字段
    created_at = db.Column(db.DateTime, default=datetime.now, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), comment='创建者')
    
    # 关联关系 - 明确指定外键
    creator = db.relationship('User', foreign_keys=[created_by], backref='created_teachers')
    courses = db.relationship('Course', backref='teacher', lazy='dynamic', cascade='all, delete-orphan')
    teaching_records = db.relationship('TeachingRecord', backref='teacher', lazy='dynamic', cascade='all, delete-orphan')
    evaluation_stats = db.relationship('EvaluationStat', backref='teacher', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Teacher {self.name}>'
    
    @property
    def phone_masked(self):
        """手机号脱敏显示"""
        if self.phone and len(self.phone) >= 11:
            return self.phone[:3] + '****' + self.phone[-4:]
        return self.phone
    
    @property
    def user_account(self):
        """获取关联的用户账号"""
        return User.query.filter_by(teacher_id=self.id).first()


class Course(db.Model):
    """
    课程信息表
    一位老师可以有多个课程
    """
    __tablename__ = 'courses'
    
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'), nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False, comment='课程名称')
    description = db.Column(db.Text, comment='课程描述')
    
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    # 关联
    teaching_records = db.relationship('TeachingRecord', backref='course', lazy='dynamic')
    
    def __repr__(self):
        return f'<Course {self.name}>'


class ClassInfo(db.Model):
    """
    班级信息表
    对应原系统：班级管理
    """
    __tablename__ = 'class_info'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, comment='班级名称')
    class_type = db.Column(db.String(50), comment='班级类型')
    project_manager = db.Column(db.String(50), comment='项目主任')
    class_teacher = db.Column(db.String(50), comment='班主任')
    start_date = db.Column(db.Date, comment='开始日期')
    end_date = db.Column(db.Date, comment='结束日期')
    status = db.Column(db.Enum('进行中', '已完成', '未开始', name='class_status'), default='未开始')
    
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    # 关联
    teaching_records = db.relationship('TeachingRecord', backref='class_info', lazy='dynamic')
    
    def __repr__(self):
        return f'<ClassInfo {self.name}>'


class TeachingRecord(db.Model):
    """
    上课记录表
    对应原系统：课表管理中的每次上课记录
    """
    __tablename__ = 'teaching_records'
    
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'), nullable=False, index=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), comment='关联课程')
    class_id = db.Column(db.Integer, db.ForeignKey('class_info.id'), comment='关联班级')
    
    # 上课信息
    teaching_date = db.Column(db.Date, nullable=False, comment='上课日期')
    start_time = db.Column(db.Time, comment='开始时间')
    end_time = db.Column(db.Time, comment='结束时间')
    duration_type = db.Column(db.Enum('半天', '全天', name='duration_type'), default='半天', comment='课时类型')
    
    # 地点和人数
    venue = db.Column(db.String(200), comment='上课场所')
    student_count = db.Column(db.Integer, default=0, comment='上课人数')
    
    # 统计数据（来自评价）
    evaluation_rate = db.Column(db.Float, default=0.0, comment='评价率(%)')
    checkin_rate = db.Column(db.Float, default=0.0, comment='签到率(%)')
    score = db.Column(db.Float, comment='本次评分')
    
    # 课酬
    lecture_fee = db.Column(db.Integer, comment='本次课酬')
    is_paid = db.Column(db.Boolean, default=False, comment='是否已支付')
    
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    def __repr__(self):
        return f'<TeachingRecord {self.teacher_id}@{self.teaching_date}>'


class Evaluation(db.Model):
    """
    评价详情表
    对应原系统：教务评价 + 详细评价
    """
    __tablename__ = 'evaluations'
    
    id = db.Column(db.Integer, primary_key=True)
    teaching_record_id = db.Column(db.Integer, db.ForeignKey('teaching_records.id'), index=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'), nullable=False, index=True)
    class_id = db.Column(db.Integer, db.ForeignKey('class_info.id'))
    
    # 评价人信息
    evaluator_name = db.Column(db.String(50), comment='评价人姓名')
    evaluator_type = db.Column(db.Enum('学员', '教务', '班主任', name='evaluator_type'), default='学员')
    
    # 评分和内容
    score = db.Column(db.Float, comment='评分(10分制)')
    content = db.Column(db.Text, comment='评价内容')
    evaluation_category = db.Column(db.String(50), comment='评价类别')
    
    # 点赞标签（JSON存储）
    tags = db.Column(db.JSON, comment='点赞标签 {"案例丰富": 1, "氛围活跃": 1}')
    
    created_at = db.Column(db.DateTime, default=datetime.now, comment='评价时间')
    
    # 关联
    teacher = db.relationship('Teacher', backref='evaluations')
    teaching_record = db.relationship('TeachingRecord', backref='evaluations')
    class_info = db.relationship('ClassInfo', backref='evaluations')
    
    def __repr__(self):
        return f'<Evaluation {self.evaluator_name}:{self.score}>'


class EvaluationStat(db.Model):
    """
    评价统计表
    对应原系统：likes_data（4维度点赞统计）
    """
    __tablename__ = 'evaluation_stats'
    
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'), nullable=False, index=True)
    
    # 4个点赞维度 + 次数
    tag_case_rich = db.Column(db.Integer, default=0, comment='案例丰富，贴近实际')
    tag_atmosphere_active = db.Column(db.Integer, default=0, comment='氛围活跃，时常互动')
    tag_key_points_clear = db.Column(db.Integer, default=0, comment='重点突出，层次分明')
    tag_humor_fun = db.Column(db.Integer, default=0, comment='幽默风趣，寓教于乐')
    
    # 更新时间
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    def __repr__(self):
        return f'<EvaluationStat teacher={self.teacher_id}>'
    
    @property
    def total_likes(self):
        """总点赞数"""
        return self.tag_case_rich + self.tag_atmosphere_active + self.tag_key_points_clear + self.tag_humor_fun


class Student(db.Model):
    """
    学员信息表
    对应原系统：学员管理
    """
    __tablename__ = 'students'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, comment='姓名')
    gender = db.Column(db.Enum('男', '女', name='gender'), comment='性别')
    phone = db.Column(db.String(20), comment='手机号')
    company = db.Column(db.String(200), comment='单位')
    job = db.Column(db.String(100), comment='职业')
    province = db.Column(db.String(50), comment='省份')
    city = db.Column(db.String(50), comment='城市')
    
    # 参课统计
    total_attendance = db.Column(db.Integer, default=0, comment='参课次数')
    
    # 小程序关联
    has_mini_program = db.Column(db.Boolean, default=False, comment='是否关联小程序')
    mini_program_openid = db.Column(db.String(100), comment='小程序OpenID')
    
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    def __repr__(self):
        return f'<Student {self.name}>'


class User(db.Model):
    """
    系统用户表
    内部员工 + 老师账号
    """
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False, comment='用户名')
    password_hash = db.Column(db.String(128), comment='密码哈希')
    name = db.Column(db.String(50), comment='显示名称')
    
    # 角色：admin(管理员), staff(员工), teacher(老师)
    role = db.Column(db.Enum('admin', 'staff', 'teacher', name='user_role'), default='staff')
    
    # 老师关联（如果是老师账号）
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'), unique=True, comment='关联的教师ID')
    
    is_active = db.Column(db.Boolean, default=True, comment='是否启用')
    last_login = db.Column(db.DateTime, comment='最后登录时间')
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    # 关联
    teacher = db.relationship('Teacher', foreign_keys=[teacher_id], backref='user_link')
    
    def __repr__(self):
        return f'<User {self.username}({self.role})>'
    
    def set_password(self, password):
        """设置密码（使用SHA256哈希）"""
        self.password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    def check_password(self, password):
        """验证密码"""
        return self.password_hash == hashlib.sha256(password.encode()).hexdigest()


class AuditLog(db.Model):
    """
    审批记录表
    对应原系统：审批管理
    """
    __tablename__ = 'audit_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    target_type = db.Column(db.Enum('teacher', 'course', name='audit_target_type'), comment='审批对象类型')
    target_id = db.Column(db.Integer, comment='对象ID')
    action = db.Column(db.Enum('入库', '出库', '修改', name='audit_action'), comment='操作类型')
    
    applicant_id = db.Column(db.Integer, db.ForeignKey('users.id'), comment='申请人')
    approver_id = db.Column(db.Integer, db.ForeignKey('users.id'), comment='审批人')
    
    status = db.Column(db.Enum('pending', 'approved', 'rejected', name='audit_status'), default='pending')
    comment = db.Column(db.Text, comment='审批意见')
    
    created_at = db.Column(db.DateTime, default=datetime.now)
    processed_at = db.Column(db.DateTime, comment='处理时间')
    
    # 关联 - 明确指定外键
    applicant = db.relationship('User', foreign_keys=[applicant_id], backref='submitted_audits')
    approver = db.relationship('User', foreign_keys=[approver_id], backref='processed_audits')
