# 浙江大学继续教育师资管理系统

## 项目概述
基于Flask + SQLite开发的师资管理Web应用，包含1853位教师数据。

## 功能模块
- 师资管理：教师档案、搜索筛选、入库状态
- 课表管理：排课、上课记录、评价率统计
- 评价系统：4维度点赞统计（案例丰富、氛围活跃、重点突出、幽默风趣）

## 技术栈
- Python 3.12 + Flask 3.1
- Flask-SQLAlchemy 3.1
- SQLite数据库
- HTML/CSS/JS原生前端

## 快速启动

### 1. 安装依赖
```bash
cd teacher-management-system
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install flask flask-sqlalchemy
```

### 2. 初始化数据库
```bash
flask init-db
```

### 3. 导入教师数据
```bash
flask import-teachers
```

### 4. 启动应用
```bash
python app.py
```

### 5. 访问
浏览器打开：http://localhost:5000

## 默认账号
- 用户名：admin
- 密码：admin123

## 目录结构
```
teacher-management-system/
├── app.py                 # 应用入口
├── models.py              # 数据库模型
├── templates/             # HTML模板
│   ├── base.html
│   ├── index.html
│   └── teachers/
├── data/                  # 数据文件
│   └── teachers_data.json # 1853位教师数据
└── venv/                  # 虚拟环境
```

## 数据说明
teachers_data.json包含1905位教师的完整信息（已导入1853位），包括：
- 基本信息（姓名、头像、简介）
- 财务信息（课酬、银行卡）
- 课程信息
- 上课记录
- 评价数据

## 开发状态
第一阶段完成：基础框架 + 师资管理
第二阶段待开发：学员小程序、评价系统完善

---
生成时间：2026-04-16
