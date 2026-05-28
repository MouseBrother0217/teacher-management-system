"""
领域实体层 (Domain Layer)
纯 Python 类，不依赖 Flask/SQLAlchemy
对应 Clean Architecture 第三层
"""

from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime, date


@dataclass
class Teacher:
    """教师领域实体"""
    id: int
    name: str
    field: str = '无'
    description: str = ''
    phone: Optional[str] = None
    teacher_type: str = '校外'  # '校内' / '校外'
    is_in_storage: bool = False
    level: str = '普通'  # '普通' / '高级'
    lecture_fee_half_day: Optional[int] = None
    lecture_fee_full_day: Optional[int] = None
    organization: str = ''
    service_client: Optional[str] = None
    total_teaching_count: int = 0
    overall_score: float = 0.0
    total_evaluations: int = 0
    avatar_url: Optional[str] = None
    created_at: Optional[datetime] = None
    
    @property
    def phone_masked(self) -> Optional[str]:
        """手机号脱敏显示"""
        if self.phone and len(self.phone) >= 11:
            return self.phone[:3] + '****' + self.phone[-4:]
        return self.phone
    
    @property
    def status_label(self) -> str:
        """入库状态标签"""
        return '已入库' if self.is_in_storage else '未入库'


@dataclass
class Course:
    """课程领域实体"""
    id: int
    teacher_id: int
    name: str
    description: str = ''
    created_at: Optional[datetime] = None


@dataclass
class Classroom:
    """教室领域实体"""
    id: int
    name: str
    capacity: Optional[int] = None
    type: str = ''  # '校内' / '校外'
    campus: Optional[str] = None
    address: Optional[str] = None
    price: Optional[float] = None
    status: str = '可用'
    created_at: Optional[datetime] = None


@dataclass
class ClassInfo:
    """班级领域实体"""
    id: int
    name: str
    class_type: Optional[str] = None
    project_manager: Optional[str] = None
    class_teacher: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: str = '未开始'  # '进行中' / '已完成' / '未开始'
    created_at: Optional[datetime] = None


@dataclass
class TeachingRecord:
    """上课记录领域实体"""
    id: int
    teacher_id: int
    course_id: Optional[int] = None
    class_id: Optional[int] = None
    teaching_date: date = field(default_factory=date.today)
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    duration_type: str = '半天'  # '半天' / '全天'
    venue: Optional[str] = None
    student_count: int = 0
    evaluation_rate: float = 0.0
    checkin_rate: float = 0.0
    score: Optional[float] = None
    lecture_fee: Optional[int] = None
    is_paid: bool = False
    created_at: Optional[datetime] = None


@dataclass
class TeachingSite:
    """现场教学点领域实体"""
    id: int
    name: str
    type: str = ''  # '红色教育' / '美丽乡村' / etc.
    address: Optional[str] = None
    description: Optional[str] = None
    created_at: Optional[datetime] = None


@dataclass
class Evaluation:
    """评价领域实体"""
    id: int
    teacher_id: int
    teaching_record_id: Optional[int] = None
    class_id: Optional[int] = None
    
    # 评分维度 (1-10)
    content_score: Optional[float] = None
    method_score: Optional[float] = None
    effect_score: Optional[float] = None
    attitude_score: Optional[float] = None
    overall_score: Optional[float] = None
    
    # 评价内容
    content: Optional[str] = None  # 评价内容
    suggestions: Optional[str] = None  # 建议
    
    created_at: Optional[datetime] = None


@dataclass
class User:
    """用户领域实体"""
    id: int
    username: str
    name: Optional[str] = None
    role: str = 'student'  # admin/center_director/project_manager/class_advisor/finance_admin/teacher/student
    is_active: bool = True
    teacher_id: Optional[int] = None
    student_id: Optional[int] = None
    last_login: Optional[datetime] = None
    created_at: Optional[datetime] = None
    
    @property
    def role_label(self) -> str:
        """角色中文名称"""
        labels = {
            'admin': '系统管理员',
            'center_director': '中心主任',
            'project_manager': '项目主任',
            'class_advisor': '班主任',
            'finance_admin': '财务行政',
            'teacher': '教师',
            'student': '学员'
        }
        return labels.get(self.role, self.role)


@dataclass
class Student:
    """学员领域实体"""
    id: int
    name: str
    gender: Optional[str] = None  # '男' / '女'
    phone: Optional[str] = None
    company: Optional[str] = None
    job: Optional[str] = None
    province: Optional[str] = None
    city: Optional[str] = None
    class_id: Optional[int] = None
    total_attendance: int = 0
    created_at: Optional[datetime] = None


@dataclass
class EvaluationStat:
    """评价统计领域实体"""
    id: int
    teacher_id: int
    
    # 各维度平均分
    avg_content_score: float = 0.0
    avg_method_score: float = 0.0
    avg_effect_score: float = 0.0
    avg_attitude_score: float = 0.0
    avg_overall_score: float = 0.0
    
    # 点赞标签统计
    tag_case_rich: int = 0
    tag_atmosphere_active: int = 0
    tag_key_points_clear: int = 0
    tag_humor_fun: int = 0
    
    total_evaluations: int = 0
    updated_at: Optional[datetime] = None
    
    @property
    def total_likes(self) -> int:
        """总点赞数"""
        return self.tag_case_rich + self.tag_atmosphere_active + self.tag_key_points_clear + self.tag_humor_fun
