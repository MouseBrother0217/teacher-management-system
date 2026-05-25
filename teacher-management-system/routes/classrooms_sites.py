from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from datetime import datetime
from auth_module import login_required_web
from app import classrooms, schedules, teaching_sites

classrooms_bp = Blueprint('classrooms', __name__, url_prefix='/classrooms')
sites_bp = Blueprint('sites', __name__, url_prefix='/sites')
api_bp = Blueprint('api', __name__, url_prefix='/api')

# ==================== 教室管理 ====================

@classrooms_bp.route('/')
def list():
    """教室管理列表"""
    keyword = request.args.get('keyword', '')
    room_type = request.args.get('type', '')
    campus = request.args.get('campus', '')
    
    filtered_rooms = classrooms
    if keyword:
        filtered_rooms = [r for r in filtered_rooms if keyword in r['name']]
    if room_type:
        filtered_rooms = [r for r in filtered_rooms if r['type'] == room_type]
    if campus:
        filtered_rooms = [r for r in filtered_rooms if r['campus'] == campus]
    
    return render_template('classrooms/list.html',
                         classrooms=filtered_rooms,
                         keyword=keyword,
                         room_type=room_type,
                         campus=campus)


@classrooms_bp.route('/<int:id>')
def detail(id):
    """教室详情页"""
    classroom = next((r for r in classrooms if r['id'] == id), None)
    if not classroom:
        flash('教室不存在', 'error')
        return redirect(url_for('classrooms.list'))
    
    # 获取该教室的使用记录
    usage_records = [s for s in schedules if s.get('classroom_id') == id]
    
    return render_template('classrooms/detail.html',
                         classroom=classroom,
                         usage_records=usage_records)


@classrooms_bp.route('/new', methods=['GET', 'POST'])
def new():
    """新增教室"""
    if request.method == 'POST':
        new_room = {
            'id': len(classrooms) + 1,
            'name': request.form.get('name'),
            'type': request.form.get('type'),
            'campus': request.form.get('campus'),
            'capacity': int(request.form.get('capacity', 0)) if request.form.get('capacity') else None,
            'price': float(request.form.get('price', 0)) if request.form.get('price') else None,
            'address': request.form.get('address'),
            'description': request.form.get('description'),
            'status': request.form.get('status', '可用'),
            'created_at': datetime.now()
        }
        classrooms.append(new_room)
        flash('教室添加成功', 'success')
        return redirect(url_for('classrooms.list'))
    return render_template('classrooms/form.html')


@classrooms_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
def edit(id):
    """编辑教室"""
    classroom = next((r for r in classrooms if r['id'] == id), None)
    if not classroom:
        flash('教室不存在', 'error')
        return redirect(url_for('classrooms.list'))
    if request.method == 'POST':
        classroom['name'] = request.form.get('name')
        classroom['type'] = request.form.get('type')
        classroom['campus'] = request.form.get('campus')
        classroom['capacity'] = int(request.form.get('capacity', 0)) if request.form.get('capacity') else None
        classroom['price'] = float(request.form.get('price', 0)) if request.form.get('price') else None
        classroom['address'] = request.form.get('address')
        classroom['description'] = request.form.get('description')
        classroom['status'] = request.form.get('status')
        flash('教室更新成功', 'success')
        return redirect(url_for('classrooms.detail', id=id))
    return render_template('classrooms/form.html', classroom=classroom)


@classrooms_bp.route('/<int:id>/delete', methods=['POST'])
def delete(id):
    """删除教室"""
    classroom = next((r for r in classrooms if r['id'] == id), None)
    if classroom:
        # 检查是否有课表使用该教室
        used_in_schedule = any(s.get('classroom_id') == id for s in schedules)
        if used_in_schedule:
            flash('该教室已被课表使用，不能删除', 'error')
            return redirect(url_for('classrooms.list'))
        classrooms.remove(classroom)
        flash('教室删除成功', 'success')
    else:
        flash('教室不存在', 'error')
    return redirect(url_for('classrooms.list'))


# ==================== 现场教学点 ====================

@sites_bp.route('/')
def sites_list():
    """现场教学点列表"""
    keyword = request.args.get('keyword', '')
    site_type = request.args.get('type', '')
    supplier = request.args.get('supplier', '')
    audit_status = request.args.get('audit_status', '')
    
    filtered_sites = teaching_sites
    if keyword:
        filtered_sites = [s for s in filtered_sites if keyword in s['name']]
    if site_type:
        filtered_sites = [s for s in filtered_sites if s['type'] == site_type]
    if supplier:
        filtered_sites = [s for s in filtered_sites if s['supplier'] == supplier]
    if audit_status:
        filtered_sites = [s for s in filtered_sites if s['audit_status'] == audit_status]
    
    return render_template('sites/list.html',
                         sites=filtered_sites,
                         keyword=keyword,
                         site_type=site_type,
                         supplier=supplier,
                         audit_status=audit_status)


@sites_bp.route('/<int:id>')
def site_detail(id):
    """现场教学点详情页"""
    site = next((s for s in teaching_sites if s['id'] == id), None)
    if not site:
        flash('现场教学点不存在', 'error')
        return redirect(url_for('sites.sites_list'))
    return render_template('sites/detail.html', site=site)


@sites_bp.route('/new', methods=['GET', 'POST'])
def site_new():
    """新增现场教学点"""
    if request.method == 'POST':
        new_site = {
            'id': len(teaching_sites) + 1,
            'name': request.form.get('name'),
            'type': request.form.get('type'),
            'supplier': request.form.get('supplier'),
            'contact_name': request.form.get('contact_name'),
            'contact_phone': request.form.get('contact_phone'),
            'price': float(request.form.get('price', 0)),
            'address': request.form.get('address'),
            'price_note': request.form.get('price_note'),
            'description': request.form.get('description'),
            'audit_status': '待审核',
            'created_at': datetime.now()
        }
        teaching_sites.append(new_site)
        flash('现场教学点添加成功', 'success')
        return redirect(url_for('sites.sites_list'))
    return render_template('sites/form.html')


@sites_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
def site_edit(id):
    """编辑现场教学点"""
    site = next((s for s in teaching_sites if s['id'] == id), None)
    if not site:
        flash('现场教学点不存在', 'error')
        return redirect(url_for('sites.sites_list'))
    if request.method == 'POST':
        site['name'] = request.form.get('name')
        site['type'] = request.form.get('type')
        site['supplier'] = request.form.get('supplier')
        site['contact_name'] = request.form.get('contact_name')
        site['contact_phone'] = request.form.get('contact_phone')
        site['price'] = float(request.form.get('price', 0))
        site['address'] = request.form.get('address')
        site['price_note'] = request.form.get('price_note')
        site['description'] = request.form.get('description')
        flash('现场教学点更新成功', 'success')
        return redirect(url_for('sites.site_detail', id=id))
    return render_template('sites/form.html', site=site)


@sites_bp.route('/<int:id>/delete', methods=['POST'])
def site_delete(id):
    """删除现场教学点"""
    site = next((s for s in teaching_sites if s['id'] == id), None)
    if site:
        teaching_sites.remove(site)
        flash('现场教学点删除成功', 'success')
    else:
        flash('现场教学点不存在', 'error')
    return redirect(url_for('sites.sites_list'))


# ==================== API 路由 ====================

@api_bp.route('/classrooms', methods=['POST'])
@login_required_web
def api_add_classroom():
    """AJAX新增教室"""
    try:
        data = request.get_json()
        if not data or not data.get('name'):
            return jsonify({'success': False, 'error': '教室名称不能为空'}), 400
        
        new_room = {
            'id': len(classrooms) + 1,
            'name': data.get('name'),
            'type': data.get('type', '多媒体教室'),
            'campus': data.get('campus', '主校区'),
            'capacity': data.get('capacity', 50),
            'price': None,
            'address': '',
            'description': '',
            'status': '可用',
            'created_at': datetime.now()
        }
        classrooms.append(new_room)
        return jsonify({
            'success': True,
            'classroom': {
                'id': new_room['id'],
                'name': new_room['name'],
                'type': new_room['type'],
                'campus': new_room['campus'],
                'capacity': new_room['capacity']
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/teaching-sites', methods=['POST'])
@login_required_web
def api_add_teaching_site():
    """AJAX新增现场教学点"""
    try:
        data = request.get_json()
        if not data or not data.get('name'):
            return jsonify({'success': False, 'error': '教学点名称不能为空'}), 400
        
        new_site = {
            'id': len(teaching_sites) + 1,
            'name': data.get('name'),
            'type': data.get('type', '红色教育基地'),
            'supplier': '',
            'contact_name': '',
            'contact_phone': '',
            'price': None,
            'address': data.get('address', ''),
            'price_note': '',
            'description': data.get('introduction', ''),
            'audit_status': '待审核',
            'created_at': datetime.now()
        }
        teaching_sites.append(new_site)
        return jsonify({
            'success': True,
            'site': {
                'id': new_site['id'],
                'name': new_site['name'],
                'address': new_site['address'],
                'type': new_site['type']
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
