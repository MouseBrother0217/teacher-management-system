#!/usr/bin/env python3
"""
Clean Architecture 路由拆分脚本
自动将 app.py 中的路由按功能分组拆分到 routes/ 目录下的蓝图文件
"""

import re
import os
from collections import defaultdict

APP_FILE = '/root/.openclaw/workspace/teacher-management-system/app.py'
ROUTES_DIR = '/root/.openclaw/workspace/teacher-management-system/routes'

def analyze_routes():
    """分析 app.py 中的路由结构"""
    with open(APP_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 找到所有路由装饰器和对应的函数
    route_pattern = r'^(@app\.route\([^)]+\).*(?:\n@app\.[a-z_]+\([^)]+\))*\n)def ([a-z_]+)\([^)]*\):'
    
    routes = []
    for match in re.finditer(route_pattern, content, re.MULTILINE):
        decorators = match.group(1).strip()
        func_name = match.group(2)
        
        # 提取 URL
        url_match = re.search(r"@app\.route\('([^']+)'", decorators)
        if url_match:
            url = url_match.group(1)
            # 确定功能组
            group = determine_group(url)
            routes.append({
                'url': url,
                'func_name': func_name,
                'decorators': decorators,
                'group': group
            })
    
    return routes

def determine_group(url):
    """根据 URL 确定功能组"""
    url = url.lower()
    if url.startswith('/classrooms') or url.startswith('/api/classrooms'):
        return 'classrooms'
    elif url.startswith('/sites') or url.startswith('/api/teaching-sites'):
        return 'sites'
    elif url.startswith('/teachers') or url.startswith('/api/teachers'):
        return 'teachers'
    elif url.startswith('/classes') or url.startswith('/api/classes'):
        return 'classes'
    elif url.startswith('/courses') or url.startswith('/api/courses'):
        return 'courses'
    elif url.startswith('/students') or url.startswith('/api/students'):
        return 'students'
    elif url.startswith('/schedules') or url.startswith('/api/schedules'):
        return 'schedules'
    elif url.startswith('/users') or url.startswith('/api/users'):
        return 'users'
    elif url.startswith('/categories'):
        return 'categories'
    elif url.startswith('/compensations'):
        return 'compensations'
    elif url.startswith('/approvals'):
        return 'approvals'
    elif url.startswith('/attendance'):
        return 'attendance'
    elif url.startswith('/api/stats'):
        return 'home'
    elif url == '/':
        return 'home'
    else:
        return 'other'

if __name__ == '__main__':
    routes = analyze_routes()
    
    # 按组统计
    groups = defaultdict(list)
    for route in routes:
        groups[route['group']].append(route)
    
    print("=== 路由分组统计 ===")
    for group, items in sorted(groups.items(), key=lambda x: -len(x[1])):
        print(f"\n{group}: {len(items)} 个路由")
        for item in items:
            print(f"  - {item['url']} → {item['func_name']}")
