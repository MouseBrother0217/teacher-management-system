"""
routes 包初始化
注册所有 Flask Blueprint
"""
from .classrooms_sites import classrooms_bp, sites_bp, api_bp
from .teachers import teachers_bp
from .classes import classes_bp
from .courses_students_schedules import courses_bp, students_bp, schedules_bp
from .misc import users_bp, categories_bp, compensations_bp, approvals_bp, home_bp

__all__ = ['classrooms_bp', 'sites_bp', 'api_bp', 'teachers_bp', 'classes_bp',
           'courses_bp', 'students_bp', 'schedules_bp',
           'users_bp', 'categories_bp', 'compensations_bp', 'approvals_bp', 'home_bp']
