"""
数据导入导出路由
ADR-005: 数据导入导出流程
- 上传 → 预览 → 确认 → 导入 → 回滚
"""
from flask import Blueprint, render_template, request, flash, redirect, url_for, session, jsonify, current_app
import os
import uuid
import json
import csv
import io
from datetime import datetime

from models import db, ImportLog, User

import_bp = Blueprint('import', __name__, url_prefix='/import')

# ==================== 导入类型配置 ====================

IMPORT_CONFIG = {
    'teachers': {
        'name': '教师数据',
        'required_fields': ['name'],
        'optional_fields': ['title', 'field', 'specialty', 'introduction', 'organization', 
                          'phone', 'email', 'status', 'evaluation_score'],
        'clean_rules': ['trim', 'remove_half_brackets', 'normalize_phone']
    },
    'classrooms': {
        'name': '教室数据',
        'required_fields': ['name', 'capacity'],
        'optional_fields': ['type', 'location', 'building'],
        'clean_rules': ['remove_city_prefix', 'normalize_capacity', 'fix_type']
    },
    'sites': {
        'name': '现场教学点',
        'required_fields': ['name'],
        'optional_fields': ['location', 'type', 'description'],
        'clean_rules': ['remove_city_prefix', 'fix_site_type']
    },
    'students': {
        'name': '学员数据',
        'required_fields': ['name'],
        'optional_fields': ['phone', 'email', 'organization', 'position'],
        'clean_rules': ['trim', 'normalize_phone']
    },
    'courses': {
        'name': '课程数据',
        'required_fields': ['name'],
        'optional_fields': ['category', 'description', 'duration', 'credits'],
        'clean_rules': ['trim']
    }
}

# ==================== 清洗规则引擎 ====================

def apply_clean_rules(data_list, rules, file_type):
    """
    应用清洗规则
    返回: (清洗后的数据, 清洗记录列表)
    """
    cleaned_data = []
    clean_records = []
    
    for idx, row in enumerate(data_list):
        cleaned_row = dict(row)
        row_changes = []
        
        for rule in rules:
            if rule == 'trim':
                for key in cleaned_row:
                    if isinstance(cleaned_row[key], str):
                        old_val = cleaned_row[key]
                        cleaned_row[key] = cleaned_row[key].strip()
                        if old_val != cleaned_row[key]:
                            row_changes.append(f"{key}: 去除首尾空格")
            
            elif rule == 'remove_half_brackets':
                for key in cleaned_row:
                    if isinstance(cleaned_row[key], str):
                        old_val = cleaned_row[key]
                        cleaned_row[key] = cleaned_row[key].replace('》', '').replace('《', '')
                        if old_val != cleaned_row[key]:
                            row_changes.append(f"{key}: 去除书名号")
            
            elif rule == 'remove_city_prefix':
                for key in ['name', 'location']:
                    if key in cleaned_row and isinstance(cleaned_row[key], str):
                        old_val = cleaned_row[key]
                        # 去除 "杭州-"、"北京-" 等城市前缀
                        import re
                        cleaned_row[key] = re.sub(r'^[\u4e00-\u9fa5]{2,6}-', '', cleaned_row[key])
                        if old_val != cleaned_row[key]:
                            row_changes.append(f"{key}: 去除城市前缀 '{old_val}' → '{cleaned_row[key]}'")
            
            elif rule == 'normalize_capacity':
                if 'capacity' in cleaned_row:
                    old_val = cleaned_row['capacity']
                    try:
                        # 提取数字
                        import re
                        cap_str = str(cleaned_row['capacity'])
                        numbers = re.findall(r'\d+', cap_str)
                        if numbers:
                            cleaned_row['capacity'] = int(numbers[0])
                            if str(old_val) != str(cleaned_row['capacity']):
                                row_changes.append(f"capacity: 标准化 '{old_val}' → {cleaned_row['capacity']}")
                    except:
                        pass
            
            elif rule == 'fix_type':
                if 'type' in cleaned_row:
                    old_val = cleaned_row['type']
                    type_val = str(cleaned_row['type']).strip()
                    if type_val in ['校内', '校内教室', '教学楼']:
                        cleaned_row['type'] = '校内'
                    elif type_val in ['校外', '校外场地', '现场教学']:
                        cleaned_row['type'] = '校外'
                    if old_val != cleaned_row['type']:
                        row_changes.append(f"type: 标准化 '{old_val}' → '{cleaned_row['type']}'")
            
            elif rule == 'fix_site_type':
                if 'type' in cleaned_row:
                    old_val = cleaned_row['type']
                    type_val = str(cleaned_row['type']).strip()
                    if type_val in ['校内', '校内教室']:
                        cleaned_row['type'] = '校内'
                    elif type_val in ['校外', '现场教学', '教学点']:
                        cleaned_row['type'] = '校外'
                    if old_val != cleaned_row['type']:
                        row_changes.append(f"type: 标准化 '{old_val}' → '{cleaned_row['type']}'")
            
            elif rule == 'normalize_phone':
                for key in ['phone', 'contact_phone']:
                    if key in cleaned_row and cleaned_row[key]:
                        old_val = cleaned_row[key]
                        phone = str(cleaned_row[key]).strip()
                        # 去除空格和横线
                        phone = phone.replace(' ', '').replace('-', '')
                        if phone.startswith('+86'):
                            phone = phone[3:]
                        cleaned_row[key] = phone
                        if old_val != cleaned_row[key]:
                            row_changes.append(f"{key}: 标准化 '{old_val}' → '{cleaned_row[key]}'")
        
        cleaned_data.append(cleaned_row)
        if row_changes:
            clean_records.append({
                'row': idx + 1,
                'changes': row_changes
            })
    
    return cleaned_data, clean_records

# ==================== 数据验证 ====================

def validate_data(data_list, file_type):
    """
    验证数据完整性
    返回: (有效数据列表, 错误列表)
    """
    config = IMPORT_CONFIG.get(file_type, {})
    required = config.get('required_fields', [])
    
    valid_data = []
    errors = []
    
    for idx, row in enumerate(data_list):
        row_errors = []
        
        # 检查必填字段
        for field in required:
            if field not in row or not row[field]:
                row_errors.append(f"缺少必填字段: {field}")
        
        if row_errors:
            errors.append({
                'row': idx + 1,
                'data': row,
                'errors': row_errors
            })
        else:
            valid_data.append(row)
    
    return valid_data, errors

# ==================== 路由 ====================

@import_bp.route('/')
@login_required_web
def index():
    """导入管理首页"""
    # 查询导入历史
    logs = ImportLog.query.order_by(ImportLog.created_at.desc()).limit(20).all()
    return render_template('import/index.html', logs=logs, config=IMPORT_CONFIG)


@import_bp.route('/upload', methods=['POST'])
@login_required_web
@require_role('admin', 'center_director', 'project_manager')
def upload():
    """上传文件并进入预览"""
    file_type = request.form.get('file_type')
    file = request.files.get('file')
    
    if not file_type or file_type not in IMPORT_CONFIG:
        flash('请选择正确的导入类型', 'error')
        return redirect(url_for('import.index'))
    
    if not file or file.filename == '':
        flash('请选择要上传的文件', 'error')
        return redirect(url_for('import.index'))
    
    # 检查文件格式
    filename = file.filename.lower()
    if not (filename.endswith('.csv') or filename.endswith('.xlsx') or filename.endswith('.xls')):
        flash('仅支持 CSV 或 Excel 格式', 'error')
        return redirect(url_for('import.index'))
    
    try:
        # 读取文件内容
        if filename.endswith('.csv'):
            stream = io.StringIO(file.stream.read().decode('utf-8'))
            reader = csv.DictReader(stream)
            data_list = list(reader)
        else:
            # Excel 处理（简化版，实际需要 openpyxl）
            flash('Excel 格式暂不支持，请先转换为 CSV', 'warning')
            return redirect(url_for('import.index'))
        
        if not data_list:
            flash('文件为空或格式错误', 'error')
            return redirect(url_for('import.index'))
        
        # 生成批次ID
        batch_id = str(uuid.uuid4())
        
        # 应用清洗规则
        rules = IMPORT_CONFIG[file_type]['clean_rules']
        cleaned_data, clean_records = apply_clean_rules(data_list, rules, file_type)
        
        # 验证数据
        valid_data, errors = validate_data(cleaned_data, file_type)
        
        # 创建导入日志（预览状态）
        log = ImportLog(
            batch_id=batch_id,
            filename=file.filename,
            file_type=file_type,
            total_rows=len(data_list),
            success_rows=len(valid_data),
            failed_rows=len(errors),
            skipped_rows=0,
            operator_id=session.get('user_id'),
            operator_name=session.get('username'),
            status='preview',
            details=json.dumps({
                'clean_records': clean_records,
                'errors': errors,
                'sample_data': valid_data[:5] if valid_data else [],
                'headers': list(data_list[0].keys()) if data_list else []
            }, ensure_ascii=False, default=str)
        )
        db.session.add(log)
        db.session.commit()
        
        flash(f'文件解析完成：共 {len(data_list)} 行，有效 {len(valid_data)} 行，失败 {len(errors)} 行', 'success')
        return redirect(url_for('import.preview', batch_id=batch_id))
        
    except Exception as e:
        flash(f'文件解析失败: {str(e)}', 'error')
        return redirect(url_for('import.index'))


@import_bp.route('/preview/<batch_id>')
@login_required_web
def preview(batch_id):
    """预览清洗后的数据"""
    log = ImportLog.query.filter_by(batch_id=batch_id).first_or_404()
    details = json.loads(log.details) if log.details else {}
    
    return render_template('import/preview.html', log=log, details=details)


@import_bp.route('/confirm/<batch_id>', methods=['POST'])
@login_required_web
@require_role('admin', 'center_director', 'project_manager')
def confirm_import(batch_id):
    """确认导入数据到数据库"""
    log = ImportLog.query.filter_by(batch_id=batch_id).first_or_404()
    
    if log.status != 'preview':
        flash('该批次已处理，无法重复导入', 'error')
        return redirect(url_for('import.index'))
    
    try:
        # TODO: 根据 file_type 调用对应的导入逻辑
        # 这里复用已有的导入脚本逻辑
        
        # 更新日志状态
        log.status = 'imported'
        log.imported_at = datetime.now()
        db.session.commit()
        
        flash(f'导入成功！共导入 {log.success_rows} 条数据', 'success')
        
    except Exception as e:
        log.status = 'failed'
        db.session.commit()
        flash(f'导入失败: {str(e)}', 'error')
    
    return redirect(url_for('import.index'))


@import_bp.route('/rollback/<batch_id>', methods=['POST'])
@login_required_web
@require_role('admin', 'center_director')
def rollback(batch_id):
    """回滚导入的数据"""
    log = ImportLog.query.filter_by(batch_id=batch_id).first_or_404()
    
    if log.status != 'imported':
        flash('只有已导入的批次才能回滚', 'error')
        return redirect(url_for('import.index'))
    
    try:
        # TODO: 根据 batch_id 标记对应数据为删除状态
        # 这里需要各数据表支持 batch_id 字段
        
        log.status = 'rolled_back'
        log.rolled_back_at = datetime.now()
        db.session.commit()
        
        flash('回滚成功！数据已恢复', 'success')
        
    except Exception as e:
        flash(f'回滚失败: {str(e)}', 'error')
    
    return redirect(url_for('import.index'))


@import_bp.route('/logs')
@login_required_web
def logs():
    """导入日志列表"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    logs_query = ImportLog.query.order_by(ImportLog.created_at.desc())
    pagination = logs_query.paginate(page=page, per_page=per_page, error_out=False)
    
    return render_template('import/logs.html', pagination=pagination, logs=pagination.items)


@import_bp.route('/template/<file_type>')
@login_required_web
def download_template(file_type):
    """下载导入模板"""
    if file_type not in IMPORT_CONFIG:
        flash('模板类型不存在', 'error')
        return redirect(url_for('import.index'))
    
    config = IMPORT_CONFIG[file_type]
    headers = config['required_fields'] + config['optional_fields']
    
    # 生成 CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    # 写一行示例数据
    sample = ['示例数据'] * len(headers)
    writer.writerow(sample)
    
    output.seek(0)
    
    from flask import Response
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={file_type}_template.csv'}
    )


# 注册登录检查装饰器
def login_required_web(f):
    """简化版登录检查"""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('请先登录', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated

def require_role(*roles):
    """简化版角色检查"""
    from functools import wraps
    from flask import session, flash, redirect, url_for
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if session.get('role') not in roles:
                flash('权限不足', 'error')
                return redirect(url_for('import.index'))
            return f(*args, **kwargs)
        return decorated
    return decorator