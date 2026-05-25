"""
API v1 路由
ADR-006: RESTful API 规范
- 统一前缀 /api/v1/
- 统一响应格式
- 支持分页、筛选、排序
"""
from flask import Blueprint, request, session, render_template
from datetime import datetime

from models import db, Teacher, ClassInfo, Course, Student, Classroom, TeachingSite, User
from utils.response import success, error, paginated, pagination_params, bad_request, unauthorized, not_found

api_v1_bp = Blueprint('api_v1', __name__, url_prefix='/api/v1')


# ==================== 认证装饰器 ====================

def api_login_required(f):
    """API 登录检查"""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return unauthorized('请先登录')
        return f(*args, **kwargs)
    return decorated


def api_role_required(*roles):
    """API 角色检查"""
    from functools import wraps
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if session.get('role') not in roles:
                from utils.response import forbidden
                return forbidden('权限不足')
            return f(*args, **kwargs)
        return decorated
    return decorator


@api_v1_bp.route('/debug')
@api_login_required
def api_debug():
    """API 调试页面"""
    return render_template('api_debug.html')


# ==================== 教师 API ====================

@api_v1_bp.route('/teachers', methods=['GET'])
@api_login_required
def get_teachers():
    """获取教师列表"""
    page, per_page = pagination_params()
    
    # 筛选参数
    keyword = request.args.get('keyword', '').strip()
    in_stock = request.args.get('in_stock', '')
    approval_status = request.args.get('approval_status', '')
    sort = request.args.get('sort', '')
    
    # 构建查询
    query = Teacher.query
    
    if keyword:
        search = f'%{keyword}%'
        query = query.filter(
            db.or_(
                Teacher.name.like(search),
                Teacher.field.like(search),
                Teacher.title.like(search),
                Teacher.organization.like(search)
            )
        )
    
    if in_stock == '是':
        query = query.filter(Teacher.is_in_storage == True)
    elif in_stock == '否':
        query = query.filter(Teacher.is_in_storage == False)
    
    if approval_status:
        query = query.filter(Teacher.approval_status == approval_status)
    
    # 排序
    if sort == 'score':
        query = query.order_by(Teacher.overall_score.desc())
    elif sort == 'count':
        query = query.order_by(Teacher.total_teaching_count.desc())
    elif sort == 'name':
        query = query.order_by(Teacher.name.asc())
    else:
        query = query.order_by(Teacher.id.desc())
    
    # 分页
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    # 序列化
    items = [teacher_to_dict(t) for t in pagination.items]
    
    return success(paginated(items, page, per_page, pagination.total))


@api_v1_bp.route('/teachers/<int:id>', methods=['GET'])
@api_login_required
def get_teacher(id):
    """获取单个教师详情"""
    teacher = Teacher.query.get(id)
    if not teacher:
        return not_found('教师不存在')
    
    return success(teacher_to_dict(teacher, detail=True))


@api_v1_bp.route('/teachers', methods=['POST'])
@api_login_required
@api_role_required('admin', 'center_director', 'project_manager')
def create_teacher():
    """创建教师"""
    data = request.get_json() or {}
    
    # 必填校验
    if not data.get('name'):
        return bad_request('缺少必填字段: name')
    
    teacher = Teacher(
        name=data.get('name'),
        title=data.get('title', ''),
        field=data.get('field', ''),
        specialty=data.get('specialty', ''),
        description=data.get('description', ''),
        organization=data.get('organization', ''),
        phone=data.get('phone', ''),
        email=data.get('email', ''),
        status='待审核'
    )
    
    db.session.add(teacher)
    db.session.commit()
    
    return success(teacher_to_dict(teacher), message='创建成功', code=201)


@api_v1_bp.route('/teachers/<int:id>', methods=['PUT'])
@api_login_required
@api_role_required('admin', 'center_director', 'project_manager')
def update_teacher(id):
    """更新教师"""
    teacher = Teacher.query.get(id)
    if not teacher:
        return not_found('教师不存在')
    
    data = request.get_json() or {}
    
    # 更新字段
    if 'name' in data:
        teacher.name = data['name']
    if 'title' in data:
        teacher.title = data['title']
    if 'field' in data:
        teacher.field = data['field']
    if 'phone' in data:
        teacher.phone = data['phone']
    if 'email' in data:
        teacher.email = data['email']
    if 'status' in data:
        teacher.status = data['status']
    
    teacher.updated_at = datetime.now()
    db.session.commit()
    
    return success(teacher_to_dict(teacher), message='更新成功')


@api_v1_bp.route('/teachers/<int:id>', methods=['DELETE'])
@api_login_required
@api_role_required('admin', 'center_director')
def delete_teacher(id):
    """删除教师"""
    teacher = Teacher.query.get(id)
    if not teacher:
        return not_found('教师不存在')
    
    db.session.delete(teacher)
    db.session.commit()
    
    return success(message='删除成功')


# ==================== 班级 API ====================

@api_v1_bp.route('/classes', methods=['GET'])
@api_login_required
def get_classes():
    """获取班级列表"""
    page, per_page = pagination_params()
    
    keyword = request.args.get('keyword', '').strip()
    category = request.args.get('category', '')
    status = request.args.get('status', '')
    
    query = ClassInfo.query
    
    if keyword:
        query = query.filter(ClassInfo.name.like(f'%{keyword}%'))
    if category:
        query = query.filter(ClassInfo.category == category)
    if status:
        query = query.filter(ClassInfo.status == status)
    
    query = query.order_by(ClassInfo.id.desc())
    
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    items = [class_to_dict(c) for c in pagination.items]
    
    return success(paginated(items, page, per_page, pagination.total))


@api_v1_bp.route('/classes/<int:id>', methods=['GET'])
@api_login_required
def get_class(id):
    """获取班级详情"""
    class_obj = ClassInfo.query.get(id)
    if not class_obj:
        return not_found('班级不存在')
    
    return success(class_to_dict(class_obj, detail=True))


# ==================== 课程 API ====================

@api_v1_bp.route('/courses', methods=['GET'])
@api_login_required
def get_courses():
    """获取课程列表"""
    page, per_page = pagination_params()
    
    keyword = request.args.get('keyword', '').strip()
    category = request.args.get('category', '')
    
    query = Course.query
    
    if keyword:
        query = query.filter(Course.name.like(f'%{keyword}%'))
    if category:
        query = query.filter(Course.category == category)
    
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    items = [course_to_dict(c) for c in pagination.items]
    
    return success(paginated(items, page, per_page, pagination.total))


# ==================== 教室/现场教学 API ====================

@api_v1_bp.route('/classrooms', methods=['GET'])
@api_login_required
def get_classrooms():
    """获取教室列表"""
    query = Classroom.query
    
    type_filter = request.args.get('type', '')
    if type_filter:
        query = query.filter(Classroom.type == type_filter)
    
    rooms = query.order_by(Classroom.id.asc()).all()
    items = [classroom_to_dict(r) for r in rooms]
    
    return success(items)


@api_v1_bp.route('/sites', methods=['GET'])
@api_login_required
def get_sites():
    """获取现场教学点列表"""
    query = TeachingSite.query
    
    type_filter = request.args.get('type', '')
    if type_filter:
        query = query.filter(TeachingSite.type == type_filter)
    
    sites = query.order_by(TeachingSite.id.asc()).all()
    items = [site_to_dict(s) for s in sites]
    
    return success(items)


# ==================== 用户 API ====================

@api_v1_bp.route('/users/me', methods=['GET'])
@api_login_required
def get_current_user():
    """获取当前登录用户信息"""
    user = User.query.get(session.get('user_id'))
    if not user:
        return unauthorized('用户不存在')
    
    return success({
        'id': user.id,
        'username': user.username,
        'name': user.name,
        'role': user.role,
        'role_label': user.role_label,
        'status': user.status
    })


# ==================== 数据序列化工具 ====================

def teacher_to_dict(teacher, detail=False):
    """教师序列化"""
    data = {
        'id': teacher.id,
        'name': teacher.name,
        'title': teacher.title,
        'field': teacher.field,
        'specialty': teacher.specialty,
        'organization': teacher.organization,
        'phone': teacher.phone,
        'email': teacher.email,
        'status': teacher.status,
        'is_in_storage': teacher.is_in_storage,
        'overall_score': float(teacher.overall_score) if teacher.overall_score else None,
        'total_teaching_count': teacher.total_teaching_count,
        'avatar_url': teacher.avatar_url,
        'created_at': teacher.created_at.strftime('%Y-%m-%d %H:%M:%S') if teacher.created_at else None
    }
    
    if detail:
        data.update({
            'description': teacher.description,
            'id_card': teacher.id_card,
            'bank_account': teacher.bank_account,
            'lecture_fee_half_day': float(teacher.lecture_fee_half_day) if teacher.lecture_fee_half_day else None,
            'lecture_fee_full_day': float(teacher.lecture_fee_full_day) if teacher.lecture_fee_full_day else None,
            'service_client': teacher.service_client,
            'updated_at': teacher.updated_at.strftime('%Y-%m-%d %H:%M:%S') if teacher.updated_at else None
        })
    
    return data


def class_to_dict(class_obj, detail=False):
    """班级序列化"""
    data = {
        'id': class_obj.id,
        'name': class_obj.name,
        'category': class_obj.category,
        'category_name': class_obj.category_name or class_obj.category,
        'status': class_obj.status,
        'start_date': class_obj.start_date.strftime('%Y-%m-%d') if class_obj.start_date else None,
        'end_date': class_obj.end_date.strftime('%Y-%m-%d') if class_obj.end_date else None,
        'student_count': class_obj.student_count,
        'created_at': class_obj.created_at.strftime('%Y-%m-%d %H:%M:%S') if class_obj.created_at else None
    }
    
    if detail:
        data.update({
            'description': class_obj.description,
            'location': class_obj.location,
            'manager': class_obj.manager,
            'updated_at': class_obj.updated_at.strftime('%Y-%m-%d %H:%M:%S') if class_obj.updated_at else None
        })
    
    return data


def course_to_dict(course):
    """课程序列化"""
    return {
        'id': course.id,
        'name': course.name,
        'category': course.category,
        'description': course.description,
        'duration': course.duration,
        'credits': float(course.credits) if course.credits else None,
        'teacher_id': course.teacher_id,
        'teacher_name': course.teacher_name if hasattr(course, 'teacher_name') else None,
        'status': course.status
    }


def classroom_to_dict(room):
    """教室序列化"""
    return {
        'id': room.id,
        'name': room.name,
        'capacity': room.capacity,
        'type': room.type,
        'location': room.location if hasattr(room, 'location') else None,
        'building': room.building if hasattr(room, 'building') else None
    }


def site_to_dict(site):
    """现场教学点序列化"""
    return {
        'id': site.id,
        'name': site.name,
        'type': site.type,
        'location': site.location if hasattr(site, 'location') else None,
        'description': site.description if hasattr(site, 'description') else None
    }
