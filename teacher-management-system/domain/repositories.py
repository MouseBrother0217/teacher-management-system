"""
Repository 抽象接口 (Domain Layer)
定义数据访问契约，不依赖具体实现
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from domain.entities import Teacher, Course, Classroom, ClassInfo, TeachingRecord, TeachingSite, User, Student, Evaluation, EvaluationStat


class TeacherRepository(ABC):
    """教师仓储接口"""
    
    @abstractmethod
    def find_by_id(self, teacher_id: int) -> Optional[Teacher]:
        """按ID查找教师"""
        pass
    
    @abstractmethod
    def find_all(self, filters: dict = None) -> List[Teacher]:
        """查找所有教师，支持过滤"""
        pass
    
    @abstractmethod
    def find_by_name(self, name: str) -> List[Teacher]:
        """按姓名模糊查找"""
        pass
    
    @abstractmethod
    def save(self, teacher: Teacher) -> Teacher:
        """保存教师"""
        pass
    
    @abstractmethod
    def delete(self, teacher_id: int) -> bool:
        """删除教师"""
        pass
    
    @abstractmethod
    def count(self) -> int:
        """统计教师数量"""
        pass


class CourseRepository(ABC):
    """课程仓储接口"""
    
    @abstractmethod
    def find_by_id(self, course_id: int) -> Optional[Course]:
        pass
    
    @abstractmethod
    def find_by_teacher_id(self, teacher_id: int) -> List[Course]:
        pass
    
    @abstractmethod
    def find_all(self) -> List[Course]:
        pass
    
    @abstractmethod
    def save(self, course: Course) -> Course:
        pass


class ClassroomRepository(ABC):
    """教室仓储接口"""
    
    @abstractmethod
    def find_by_id(self, room_id: int) -> Optional[Classroom]:
        pass
    
    @abstractmethod
    def find_all(self) -> List[Classroom]:
        pass
    
    @abstractmethod
    def save(self, classroom: Classroom) -> Classroom:
        pass


class ClassInfoRepository(ABC):
    """班级仓储接口"""
    
    @abstractmethod
    def find_by_id(self, class_id: int) -> Optional[ClassInfo]:
        pass
    
    @abstractmethod
    def find_all(self, status: str = None) -> List[ClassInfo]:
        pass
    
    @abstractmethod
    def save(self, class_info: ClassInfo) -> ClassInfo:
        pass


class TeachingRecordRepository(ABC):
    """上课记录仓储接口"""
    
    @abstractmethod
    def find_by_id(self, record_id: int) -> Optional[TeachingRecord]:
        pass
    
    @abstractmethod
    def find_by_teacher_id(self, teacher_id: int) -> List[TeachingRecord]:
        pass
    
    @abstractmethod
    def find_by_class_id(self, class_id: int) -> List[TeachingRecord]:
        pass
    
    @abstractmethod
    def save(self, record: TeachingRecord) -> TeachingRecord:
        pass


class TeachingSiteRepository(ABC):
    """现场教学点仓储接口"""
    
    @abstractmethod
    def find_by_id(self, site_id: int) -> Optional[TeachingSite]:
        pass
    
    @abstractmethod
    def find_all(self) -> List[TeachingSite]:
        pass
    
    @abstractmethod
    def save(self, site: TeachingSite) -> TeachingSite:
        pass


class UserRepository(ABC):
    """用户仓储接口"""
    
    @abstractmethod
    def find_by_id(self, user_id: int) -> Optional[User]:
        pass
    
    @abstractmethod
    def find_by_username(self, username: str) -> Optional[User]:
        pass
    
    @abstractmethod
    def save(self, user: User) -> User:
        pass


class StudentRepository(ABC):
    """学员仓储接口"""
    
    @abstractmethod
    def find_by_id(self, student_id: int) -> Optional[Student]:
        pass
    
    @abstractmethod
    def find_by_class_id(self, class_id: int) -> List[Student]:
        pass


class EvaluationRepository(ABC):
    """评价仓储接口"""
    
    @abstractmethod
    def find_by_teacher_id(self, teacher_id: int) -> List[Evaluation]:
        pass
    
    @abstractmethod
    def find_by_teaching_record_id(self, record_id: int) -> List[Evaluation]:
        pass
    
    @abstractmethod
    def save(self, evaluation: Evaluation) -> Evaluation:
        pass
