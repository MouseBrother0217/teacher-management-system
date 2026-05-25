"""
API 统一响应封装
ADR-006: RESTful API 规范
- 统一响应格式
- 统一错误处理
- 分页封装
"""
from flask import jsonify, request


def success(data=None, message='success', code=200):
    """
    成功响应
    
    示例:
        return success({'teachers': [...]})
        return success({'teachers': [...]}, message='查询成功')
    """
    response = {
        'code': code,
        'message': message,
        'data': data
    }
    return jsonify(response), code


def error(message='操作失败', code=400, data=None):
    """
    错误响应
    
    示例:
        return error('教师不存在', code=404)
        return error('参数错误：缺少必填字段 name', code=400)
    """
    response = {
        'code': code,
        'message': message,
        'data': data
    }
    return jsonify(response), code


def paginated(items, page=1, per_page=20, total=None):
    """
    分页响应封装
    
    示例:
        teachers = Teacher.query.paginate(page=page, per_page=per_page)
        return success(paginated(teachers.items, page, per_page, teachers.total))
    """
    total = total or len(items)
    total_pages = (total + per_page - 1) // per_page if per_page > 0 else 1
    
    return {
        'items': items,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': total,
            'total_pages': total_pages
        }
    }


def pagination_params():
    """
    从请求中获取分页参数
    
    示例:
        page, per_page = pagination_params()
    """
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    # 限制最大值
    if per_page > 100:
        per_page = 100
    if per_page < 1:
        per_page = 20
    
    return page, per_page


# 常用错误快捷方法

def bad_request(message='参数错误'):
    return error(message, code=400)


def unauthorized(message='未授权，请先登录'):
    return error(message, code=401)


def forbidden(message='权限不足'):
    return error(message, code=403)


def not_found(message='资源不存在'):
    return error(message, code=404)


def server_error(message='服务器内部错误'):
    return error(message, code=500)
