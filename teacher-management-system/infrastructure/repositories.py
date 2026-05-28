"""
SQLAlchemy Repository 实现 (Infrastructure Layer)
将 SQLAlchemy ORM 模型映射到领域实体
"""

from typing import List, Optional
from domain.entities import Teacher, Course, Classroom, ClassInfo, TeachingRecord, TeachingSite, User, Student, Evaluation
from domain.repositories import (
    TeacherRepository, CourseRepository, ClassroomRepository,
    ClassInfoRepository, TeachingRecordRepository, TeachingSiteRepository,
    UserRepository, StudentRepository, EvaluationRepository
)
from models import (
    Teacher as TeacherModel, Course as CourseModel, Classroom as ClassroomModel,
    ClassInfo as ClassInfoModel, TeachingRecord as TeachingRecordModel,
    User as UserModel, Student as StudentModel, Evaluation as EvaluationModel
)


class SQLAlchemyTeacherRepository(TeacherRepository):
    """教师仓储 SQLAlchemy 实现"""
    
    def __init__(self, db_session):
        self._session = db_session
    
    def _to_entity(self, model) -> Teacher:
        """将 SQLAlchemy 模型转为领域实体"""
        if model is None:
            return None
        return Teacher(
            id=model.id,
            name=model.name,
            field=model.field or '无',
            description=model.description or '',
            phone=model.phone,
            teacher_type=model.teacher_type or '校外',
            is_in_storage=model.is_in_storage or False,
            level=model.level or '普通',
            lecture_fee_half_day=model.lecture_fee_half_day,
            lecture_fee_full_day=model.lecture_fee_full_day,
            organization='',
            service_client=model.service_client,
            total_teaching_count=model.total_teaching_count or 0,
            overall_score=model.overall_score or 0.0,
            total_evaluations=model.total_evaluations or 0,
            avatar_url=model.avatar_url,
            created_at=model.created_at
        )
    
    def find_by_id(self, teacher_id: int) -> Optional[Teacher]:
        model = self._session.query(TeacherModel).get(teacher_id)
        return self._to_entity(model)
    
    def find_all(self, filters: dict = None) -> List[Teacher]:
        query = self._session.query(TeacherModel)
        
        if filters:
            if 'teacher_type' in filters:
                query = query.filter(TeacherModel.teacher_type == filters['teacher_type'])
            if 'is_in_storage' in filters:
                query = query.filter(TeacherModel.is_in_storage == filters['is_in_storage'])
            if 'level' in filters:
                query = query.filter(TeacherModel.level == filters['level'])
        
        models = query.all()
        return [self._to_entity(m) for m in models]
    
    def find_by_name(self, name: str) -> List[Teacher]:
        models = self._session.query(TeacherModel).filter(
            TeacherModel.name.like(f'%{name}%')
        ).all()
        return [self._to_entity(m) for m in models]
    
    def save(self, teacher: Teacher) -> Teacher:
        # 暂不实现完整 save（需要处理关联关系）
        # 简化版：仅支持查询
        raise NotImplementedError("save 方法在迁移阶段暂不实现")
    
    def delete(self, teacher_id: int) -> bool:
        raise NotImplementedError("delete 方法在迁移阶段暂不实现")
    
    def count(self) -> int:
        return self._session.query(TeacherModel).count()


class SQLAlchemyCourseRepository(CourseRepository):
    """课程仓储 SQLAlchemy 实现"""
    
    def __init__(self, db_session):
        self._session = db_session
    
    def _to_entity(self, model) -> Course:
        if model is None:
            return None
        return Course(
            id=model.id,
            teacher_id=model.teacher_id,
            name=model.name,
            description=model.description or '',
            created_at=model.created_at
        )
    
    def find_by_id(self, course_id: int) -> Optional[Course]:
        model = self._session.query(CourseModel).get(course_id)
        return self._to_entity(model)
    
    def find_by_teacher_id(self, teacher_id: int) -> List[Course]:
        models = self._session.query(CourseModel).filter(
            CourseModel.teacher_id == teacher_id
        ).all()
        return [self._to_entity(m) for m in models]
    
    def find_all(self) -> List[Course]:
        models = self._session.query(CourseModel).all()
        return [self._to_entity(m) for m in models]
    
    def save(self, course: Course) -> Course:
        raise NotImplementedError("save 方法在迁移阶段暂不实现")


class SQLAlchemyClassroomRepository(ClassroomRepository):
    """教室仓储 SQLAlchemy 实现"""
    
    def __init__(self, db_session):
        self._session = db_session
    
    def _to_entity(self, model) -> Classroom:
        if model is None:
            return None
        return Classroom(
            id=model.id,
            name=model.name,
            capacity=model.capacity,
            type=model.type or '',
            campus=model.campus,
            address=model.address,
            price=model.price,
            status=model.status or '可用',
            created_at=model.created_at
        )
    
    def find_by_id(self, room_id: int) -> Optional[Classroom]:
        model = self._session.query(ClassroomModel).get(room_id)
        return self._to_entity(model)
    
    def find_all(self) -> List[Classroom]:
        models = self._session.query(ClassroomModel).all()
        return [self._to_entity(m) for m in models]
    
    def save(self, classroom: Classroom) -> Classroom:
        raise NotImplementedError("save 方法在迁移阶段暂不实现")


class SQLAlchemyClassInfoRepository(ClassInfoRepository):
    """班级仓储 SQLAlchemy 实现"""
    
    def __init__(self, db_session):
        self._session = db_session
    
    def _to_entity(self, model) -> ClassInfo:
        if model is None:
            return None
        return ClassInfo(
            id=model.id,
            name=model.name,
            class_type=model.class_type,
            project_manager=model.project_manager,
            class_teacher=model.class_teacher,
            start_date=model.start_date,
            end_date=model.end_date,
            status=model.status or '未开始',
            created_at=model.created_at
        )
    
    def find_by_id(self, class_id: int) -> Optional[ClassInfo]:
        model = self._session.query(ClassInfoModel).get(class_id)
        return self._to_entity(model)
    
    def find_all(self, status: str = None) -> List[ClassInfo]:
        query = self._session.query(ClassInfoModel)
        if status:
            query = query.filter(ClassInfoModel.status == status)
        models = query.all()
        return [self._to_entity(m) for m in models]
    
    def save(self, class_info: ClassInfo) -> ClassInfo:
        raise NotImplementedError("save 方法在迁移阶段暂不实现")


class SQLAlchemyTeachingRecordRepository(TeachingRecordRepository):
    """上课记录仓储 SQLAlchemy 实现"""
    
    def __init__(self, db_session):
        self._session = db_session
    
    def _to_entity(self, model) -> TeachingRecord:
        if model is None:
            return None
        return TeachingRecord(
            id=model.id,
            teacher_id=model.teacher_id,
            course_id=model.course_id,
            class_id=model.class_id,
            teaching_date=model.teaching_date,
            start_time=model.start_time.strftime('%H:%M') if model.start_time else None,
            end_time=model.end_time.strftime('%H:%M') if model.end_time else None,
            duration_type=model.duration_type or '半天',
            venue=model.venue,
            student_count=model.student_count or 0,
            evaluation_rate=model.evaluation_rate or 0.0,
            checkin_rate=model.checkin_rate or 0.0,
            score=model.score,
            lecture_fee=model.lecture_fee,
            is_paid=model.is_paid or False,
            created_at=model.created_at
        )
    
    def find_by_id(self, record_id: int) -> Optional[TeachingRecord]:
        model = self._session.query(TeachingRecordModel).get(record_id)
        return self._to_entity(model)
    
    def find_by_teacher_id(self, teacher_id: int) -> List[TeachingRecord]:
        models = self._session.query(TeachingRecordModel).filter(
            TeachingRecordModel.teacher_id == teacher_id
        ).order_by(TeachingRecordModel.teaching_date.desc()).all()
        return [self._to_entity(m) for m in models]
    
    def find_by_class_id(self, class_id: int) -> List[TeachingRecord]:
        models = self._session.query(TeachingRecordModel).filter(
            TeachingRecordModel.class_id == class_id
        ).all()
        return [self._to_entity(m) for m in models]
    
    def save(self, record: TeachingRecord) -> TeachingRecord:
        raise NotImplementedError("save 方法在迁移阶段暂不实现")


class SQLAlchemyTeachingSiteRepository(TeachingSiteRepository):
    """现场教学点仓储 SQLAlchemy 实现"""
    
    def __init__(self, db_session):
        self._session = db_session
    
    def _to_entity(self, model) -> TeachingSite:
        if model is None:
            return None
        return TeachingSite(
            id=model.id,
            name=model.name,
            type=model.type or '',
            address=model.address,
            description=model.description,
            created_at=model.created_at
        )
    
    def find_by_id(self, site_id: int) -> Optional[TeachingSite]:
        # 现场教学点目前存储在 teaching_sites 内存列表中
        # 需要适配
        raise NotImplementedError("现场教学点需要从内存列表迁移到数据库")
    
    def find_all(self) -> List[TeachingSite]:
        raise NotImplementedError("现场教学点需要从内存列表迁移到数据库")
    
    def save(self, site: TeachingSite) -> TeachingSite:
        raise NotImplementedError("现场教学点需要从内存列表迁移到数据库")


class SQLAlchemyUserRepository(UserRepository):
    """用户仓储 SQLAlchemy 实现"""
    
    def __init__(self, db_session):
        self._session = db_session
    
    def _to_entity(self, model) -> User:
        if model is None:
            return None
        return User(
            id=model.id,
            username=model.username,
            name=model.name,
            role=model.role or 'student',
            is_active=model.is_active if model.is_active is not None else True,
            teacher_id=model.teacher_id,
            student_id=model.student_id,
            last_login=model.last_login,
            created_at=model.created_at
        )
    
    def find_by_id(self, user_id: int) -> Optional[User]:
        model = self._session.query(UserModel).get(user_id)
        return self._to_entity(model)
    
    def find_by_username(self, username: str) -> Optional[User]:
        model = self._session.query(UserModel).filter(
            UserModel.username == username
        ).first()
        return self._to_entity(model)
    
    def save(self, user: User) -> User:
        raise NotImplementedError("save 方法在迁移阶段暂不实现")


class SQLAlchemyStudentRepository(StudentRepository):
    """学员仓储 SQLAlchemy 实现"""
    
    def __init__(self, db_session):
        self._session = db_session
    
    def _to_entity(self, model) -> Student:
        if model is None:
            return None
        return Student(
            id=model.id,
            name=model.name,
            gender=model.gender,
            phone=model.phone,
            company=model.company,
            job=model.job,
            province=model.province,
            city=model.city,
            class_id=model.class_id,
            total_attendance=model.total_attendance or 0,
            created_at=model.created_at
        )
    
    def find_by_id(self, student_id: int) -> Optional[Student]:
        model = self._session.query(StudentModel).get(student_id)
        return self._to_entity(model)
    
    def find_by_class_id(self, class_id: int) -> List[Student]:
        models = self._session.query(StudentModel).filter(
            StudentModel.class_id == class_id
        ).all()
        return [self._to_entity(m) for m in models]


class SQLAlchemyEvaluationRepository(EvaluationRepository):
    """评价仓储 SQLAlchemy 实现"""
    
    def __init__(self, db_session):
        self._session = db_session
    
    def _to_entity(self, model) -> Evaluation:
        if model is None:
            return None
        return Evaluation(
            id=model.id,
            teacher_id=model.teacher_id,
            teaching_record_id=model.teaching_record_id,
            class_id=model.class_id,
            content_score=model.content_score,
            method_score=model.method_score,
            effect_score=model.effect_score,
            attitude_score=model.attitude_score,
            overall_score=model.overall_score,
            content=model.content,
            suggestions=model.suggestions,
            created_at=model.created_at
        )
    
    def find_by_teacher_id(self, teacher_id: int) -> List[Evaluation]:
        models = self._session.query(EvaluationModel).filter(
            EvaluationModel.teacher_id == teacher_id
        ).all()
        return [self._to_entity(m) for m in models]
    
    def find_by_teaching_record_id(self, record_id: int) -> List[Evaluation]:
        models = self._session.query(EvaluationModel).filter(
            EvaluationModel.teaching_record_id == record_id
        ).all()
        return [self._to_entity(m) for m in models]
    
    def save(self, evaluation: Evaluation) -> Evaluation:
        raise NotImplementedError("save 方法在迁移阶段暂不实现")
