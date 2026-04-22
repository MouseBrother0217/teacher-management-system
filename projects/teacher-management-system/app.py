"""
浙江大学继续教育师资管理系统
Zhejiang University Continuing Education Teacher Management System
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from models import db, Teacher, Course, ClassInfo, TeachingRecord, Evaluation, EvaluationStat, Student, User, AuditLog
import os

# 创建Flask应用
app = Flask(__name__)
app.config['SECRET_KEY'] = 'zjuedu-teacher-system-2026'

# 数据库配置（SQLite，单文件，零配置）
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///teacher_system.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 初始化数据库
db.init_app(app)

# ========== 路由定义 ==========

@app.route('/')
def index():
    """首页 - 系统概览"""
    stats = {
        'total_teachers': Teacher.query.count(),
        'total_courses': Course.query.count(),
        'total_records': TeachingRecord.query.count(),
        'total_evaluations': Evaluation.query.count()
    }
    return render_template('index.html', stats=stats)


@app.route('/teachers')
def teacher_list():
    """教师列表页"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # 搜索条件
    keyword = request.args.get('keyword', '')
    teacher_type = request.args.get('type', '')
    level = request.args.get('level', '')
    
    query = Teacher.query
    
    if keyword:
        query = query.filter(
            db.or_(
                Teacher.name.contains(keyword),
                Teacher.field.contains(keyword),
                Teacher.phone.contains(keyword)
            )
        )
    
    if teacher_type:
        query = query.filter_by(teacher_type=teacher_type)
    
    if level:
        query = query.filter_by(level=level)
    
    teachers = query.order_by(Teacher.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('teachers/list.html', teachers=teachers, 
                         keyword=keyword, type=teacher_type, level=level)


@app.route('/teachers/<int:id>')
def teacher_detail(id):
    """教师详情页"""
    teacher = Teacher.query.get_or_404(id)
    
    # 获取关联数据
    courses = teacher.courses.all()
    records = teacher.teaching_records.order_by(TeachingRecord.teaching_date.desc()).limit(10).all()
    eval_stats = teacher.evaluation_stats.first()
    
    return render_template('teachers/detail.html', 
                         teacher=teacher, 
                         courses=courses, 
                         records=records,
                         eval_stats=eval_stats)


@app.route('/api/teachers')
def api_teachers():
    """教师列表API（支持搜索）"""
    keyword = request.args.get('keyword', '')
    limit = request.args.get('limit', 20, type=int)
    
    query = Teacher.query
    
    if keyword:
        query = query.filter(
            db.or_(
                Teacher.name.contains(keyword),
                Teacher.field.contains(keyword)
            )
        )
    
    teachers = query.limit(limit).all()
    
    return jsonify({
        'total': len(teachers),
        'teachers': [{
            'id': t.id,
            'name': t.name,
            'field': t.field,
            'level': t.level,
            'score': t.overall_score,
            'phone_masked': t.phone_masked,
            'teaching_count': t.total_teaching_count,
            'avatar_url': t.avatar_url
        } for t in teachers]
    })


@app.route('/teaching-records')
def teaching_records():
    """上课记录列表"""
    page = request.args.get('page', 1, type=int)
    
    records = TeachingRecord.query.order_by(
        TeachingRecord.teaching_date.desc()
    ).paginate(page=page, per_page=20, error_out=False)
    
    return render_template('teaching/records.html', records=records)


@app.route('/api/health')
def health_check():
    """健康检查API"""
    return jsonify({
        'status': 'ok',
        'version': '0.1.0',
        'database': 'connected' if db.session.execute(db.text('SELECT 1')).scalar() else 'error'
    })


# ========== 数据库初始化命令 ==========

@app.cli.command('init-db')
def init_db():
    """初始化数据库"""
    db.create_all()
    print("✅ 数据库表创建成功！")
    
    # 创建默认管理员账号
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(
            username='admin',
            name='系统管理员',
            role='admin'
        )
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        print("✅ 默认管理员账号创建成功（admin/admin123）")
    
    print("\n数据库初始化完成！")


@app.cli.command('import-teachers')
def import_teachers():
    """导入JSON数据（从原系统提取的数据）"""
    import json
    
    json_path = '/root/.openclaw/workspace/.kimi/downloads/19d948fe-df02-8ada-8000-000048fac625_teachers_final_complete.json'
    
    if not os.path.exists(json_path):
        print(f"❌ 数据文件不存在: {json_path}")
        return
    
    print("📊 开始导入教师数据...")
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    teachers_data = data.get('teachers', [])
    total = len(teachers_data)
    imported = 0
    
    for t_data in teachers_data:
        try:
            top_info = t_data.get('top_info', {})
            basic_info = t_data.get('basic_info', {})
            
            # 解析课酬
            fee_str = basic_info.get('税前课酬', '半天:0')
            fee_half = 0
            if '半天:' in fee_str:
                try:
                    fee_half = int(fee_str.split('半天:')[1].split(',')[0].split(' ')[0])
                except:
                    pass
            
            # 检查是否已存在
            existing = Teacher.query.filter_by(
                name=top_info.get('name'),
                phone=basic_info.get('手机号', '')
            ).first()
            
            if existing:
                continue
            
            teacher = Teacher(
                name=top_info.get('name', ''),
                field=top_info.get('field', '无'),
                description=top_info.get('desc', ''),
                avatar_url=top_info.get('avatar', ''),
                lecture_fee_half_day=fee_half,
                lecture_fee_full_day=fee_half * 2 if fee_half else 0,
                id_card=basic_info.get('身份证号', ''),
                bank_name=basic_info.get('开户银行', ''),
                bank_account=basic_info.get('银行卡号', ''),
                phone=basic_info.get('手机号', ''),
                teacher_type=basic_info.get('讲师类型', '校外'),
                is_in_storage=basic_info.get('是否入库') == '是',
                level=basic_info.get('讲师级别', '普通'),
                service_client=basic_info.get('服务客户', ''),
                total_teaching_count=int(basic_info.get('上课次数', 0) or 0),
                overall_score=float(basic_info.get('综合评分', 0) or 0),
                total_evaluations=int(t_data.get('evaluation_info', {}).get('总评价数', 0) or 0)
            )
            
            db.session.add(teacher)
            db.session.flush()  # 获取ID
            
            # 导入课程信息
            course_info = basic_info.get('课程信息', '')
            if course_info:
                # 去除书名号
                course_name = course_info.strip('《》')
                course = Course(
                    teacher_id=teacher.id,
                    name=course_name
                )
                db.session.add(course)
            
            # 导入上课记录
            for record in t_data.get('teaching_records', []):
                try:
                    # 解析日期和时间
                    date_time_str = record.get('上课时间', '')
                    if date_time_str:
                        from datetime import datetime
                        dt = datetime.strptime(date_time_str.split(' ')[0], '%Y-%m-%d')
                        
                        tr = TeachingRecord(
                            teacher_id=teacher.id,
                            teaching_date=dt.date(),
                            duration_type=record.get('课时', '半天'),
                            student_count=int(record.get('上课人数', 0) or 0),
                            score=float(record.get('评分', 0) or 0) if record.get('评分') else None
                        )
                        db.session.add(tr)
                except Exception as e:
                    pass  # 跳过格式错误的记录
            
            # 导入评价统计
            likes_data = t_data.get('likes_data', [])
            if likes_data:
                stat = EvaluationStat(teacher_id=teacher.id)
                for like in likes_data:
                    content = like.get('点赞内容', '')
                    count = int(like.get('点赞次数', 0) or 0)
                    if '案例丰富' in content:
                        stat.tag_case_rich = count
                    elif '氛围活跃' in content:
                        stat.tag_atmosphere_active = count
                    elif '重点突出' in content:
                        stat.tag_key_points_clear = count
                    elif '幽默风趣' in content:
                        stat.tag_humor_fun = count
                db.session.add(stat)
            
            imported += 1
            if imported % 100 == 0:
                print(f"  已导入 {imported}/{total}...")
                db.session.commit()
                
        except Exception as e:
            print(f"  跳过一条记录: {e}")
            continue
    
    db.session.commit()
    print(f"\n✅ 导入完成！成功导入 {imported} 位教师")


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
