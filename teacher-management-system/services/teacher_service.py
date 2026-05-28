"""
应用服务层 (Application Layer)
编排领域对象完成用例，协调多个领域服务
"""

from typing import Optional, Dict, List
from domain.entities import Teacher, Course, TeachingRecord, Evaluation
from domain.repositories import (
    TeacherRepository, CourseRepository, TeachingRecordRepository,
    EvaluationRepository
)


class TeacherService:
    """教师应用服务"""
    
    def __init__(
        self,
        teacher_repo: TeacherRepository,
        course_repo: CourseRepository,
        record_repo: TeachingRecordRepository,
        eval_repo: EvaluationRepository
    ):
        self._teacher_repo = teacher_repo
        self._course_repo = course_repo
        self._record_repo = record_repo
        self._eval_repo = eval_repo
    
    def get_teacher_detail(self, teacher_id: int) -> Optional[Dict]:
        """
        获取教师详情（聚合数据）
        返回: {
            'teacher': Teacher,
            'courses': List[Course],
            'teaching_records': List[TeachingRecord],
            'evaluations': List[Evaluation],
            'stats': {
                'total_courses': int,
                'total_records': int,
                'avg_score': float
            }
        }
        """
        teacher = self._teacher_repo.find_by_id(teacher_id)
        if teacher is None:
            return None
        
        # 查询关联数据
        courses = self._course_repo.find_by_teacher_id(teacher_id)
        records = self._record_repo.find_by_teacher_id(teacher_id)
        evaluations = self._eval_repo.find_by_teacher_id(teacher_id)
        
        # 计算统计
        avg_score = 0.0
        if evaluations:
            scores = [e.overall_score for e in evaluations if e.overall_score is not None]
            if scores:
                avg_score = sum(scores) / len(scores)
        
        return {
            'teacher': teacher,
            'courses': courses,
            'teaching_records': records,
            'evaluations': evaluations,
            'stats': {
                'total_courses': len(courses),
                'total_records': len(records),
                'avg_score': round(avg_score, 2)
            }
        }
    
    def search_teachers(self, keyword: str, filters: dict = None) -> List[Teacher]:
        """搜索教师（按姓名/专业领域）"""
        # 先按姓名搜索
        teachers = self._teacher_repo.find_by_name(keyword)
        
        # 如果 filters 有额外条件，再过滤
        if filters:
            # 简化处理：重新用 find_all 带 filters
            all_teachers = self._teacher_repo.find_all(filters)
            # 取交集（名字匹配 + filters 匹配）
            teacher_ids = {t.id for t in teachers}
            teachers = [t for t in all_teachers if t.id in teacher_ids]
        
        return teachers
    
    def get_teacher_list(self, filters: dict = None) -> List[Teacher]:
        """获取教师列表"""
        return self._teacher_repo.find_all(filters)


class ClassroomService:
    """教室应用服务"""
    
    def __init__(self, classroom_repo):
        self._classroom_repo = classroom_repo
    
    def get_classroom_list(self) -> List:
        """获取教室列表"""
        return self._classroom_repo.find_all()


class ClassInfoService:
    """班级应用服务"""
    
    def __init__(self, class_info_repo, record_repo):
        self._class_info_repo = class_info_repo
        self._record_repo = record_repo
    
    def get_class_list(self, status: str = None) -> List:
        """获取班级列表"""
        return self._class_info_repo.find_all(status)
    
    def get_class_detail(self, class_id: int) -> Optional[Dict]:
        """获取班级详情（含上课记录）"""
        class_info = self._class_info_repo.find_by_id(class_id)
        if class_info is None:
            return None
        
        records = self._record_repo.find_by_class_id(class_id)
        
        return {
            'class_info': class_info,
            'teaching_records': records,
            'total_records': len(records)
        }
