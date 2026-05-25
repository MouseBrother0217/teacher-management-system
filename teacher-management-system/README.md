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
├── app.py                 # 主应用入口
├── routes/                # 蓝图路由（13个功能模块）
│   ├── teachers.py        # 师资管理
│   ├── classes.py         # 班级管理
│   ├── courses.py         # 课程管理
│   ├── schedules.py       # 课表管理
│   └── ...
├── models.py              # 数据库模型
├── templates/             # HTML模板
├── static/                # 静态资源
├── tests/                 # 测试文件
├── Dockerfile             # Docker构建
├── docker-compose.yml     # 本地Docker编排
├── docker-compose.prod.yml # 生产Docker编排
└── .github/workflows/ci.yml # GitHub Actions CI/CD
```

## CI/CD 配置

本项目已配置 GitHub Actions 自动构建：

- **自动测试**：每次 push 自动运行 pytest
- **Docker 镜像**：push 到 main 分支时自动构建并推送 Docker 镜像到 Docker Hub
- **部署文件**：`docker-compose.prod.yml` 用于生产环境部署

构建状态：[![CI](https://github.com/MouseBrother0217/teacher-management-system/actions/workflows/ci.yml/badge.svg)](https://github.com/MouseBrother0217/teacher-management-system/actions/workflows/ci.yml)

## 测试

```bash
# 运行测试
cd teacher-management-system
pytest tests/test_basic.py -v
```

---
生成时间：2026-04-16
更新：2026-05-25 已配置 CI/CD + Docker 部署 + Clean Architecture 重构 + pytest测试
