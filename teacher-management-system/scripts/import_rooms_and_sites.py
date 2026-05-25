import sqlite3
from datetime import datetime
import sys
sys.path.insert(0, '.')

from app import app

with app.app_context():
    from app import classrooms, teaching_sites
    
    print(f'📊 开始导入教室和现场教学点数据...')
    print(f'  教室: {len(classrooms)} 条')
    print(f'  现场教学点: {len(teaching_sites)} 条')
    
    conn = sqlite3.connect('instance/teacher_system.db')
    cursor = conn.cursor()
    
    # 创建 classrooms 表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS classrooms (
            id INTEGER PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            type VARCHAR(20),
            campus VARCHAR(50),
            address VARCHAR(200),
            price INTEGER,
            status VARCHAR(20),
            created_at DATETIME,
            updated_at DATETIME
        )
    ''')
    print('✅ classrooms 表已创建/存在')
    
    # 创建 teaching_sites 表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS teaching_sites (
            id INTEGER PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            type VARCHAR(50),
            supplier VARCHAR(100),
            contact_name VARCHAR(50),
            contact_phone VARCHAR(20),
            price INTEGER,
            address VARCHAR(200),
            audit_status VARCHAR(20),
            introduction TEXT,
            created_at DATETIME,
            updated_at DATETIME
        )
    ''')
    print('✅ teaching_sites 表已创建/存在')
    
    # 清空现有数据
    cursor.execute('DELETE FROM classrooms')
    cursor.execute('DELETE FROM teaching_sites')
    print('🗑️ 清空现有数据')
    
    # 导入教室
    imported_classrooms = 0
    for room in classrooms:
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO classrooms 
                (id, name, type, campus, address, price, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                room.get('id'),
                room.get('name'),
                room.get('type'),
                room.get('campus'),
                room.get('address'),
                room.get('price'),
                room.get('status'),
                room.get('created_at'),
                datetime.now()
            ))
            imported_classrooms += 1
        except Exception as e:
            print(f'  ⚠️ 教室导入错误: {room.get("name")} - {e}')
    
    # 导入现场教学点
    imported_sites = 0
    for site in teaching_sites:
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO teaching_sites 
                (id, name, type, supplier, contact_name, contact_phone, price, address, audit_status, introduction, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                site.get('id'),
                site.get('name'),
                site.get('type'),
                site.get('supplier'),
                site.get('contact_name'),
                site.get('contact_phone'),
                site.get('price'),
                site.get('address'),
                site.get('audit_status'),
                site.get('introduction'),
                site.get('created_at'),
                datetime.now()
            ))
            imported_sites += 1
        except Exception as e:
            print(f'  ⚠️ 教学点导入错误: {site.get("name")} - {e}')
    
    conn.commit()
    
    # 验证
    cursor.execute('SELECT COUNT(*) FROM classrooms')
    room_count = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM teaching_sites')
    site_count = cursor.fetchone()[0]
    
    conn.close()
    
    print(f'\n✅ 导入完成:')
    print(f'  教室: {imported_classrooms}/{len(classrooms)} 条 (数据库: {room_count})')
    print(f'  现场教学点: {imported_sites}/{len(teaching_sites)} 条 (数据库: {site_count})')
    print('🎉 教室和现场教学点数据迁移完成！')
