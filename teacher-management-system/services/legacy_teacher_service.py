"""
应用服务层 — 教师相关用例（适配现有内存数据模式）
目标：将路由中的业务逻辑抽到服务层，路由只负责 HTTP 协议处理
"""

from typing import Optional, Dict, List, Any


class LegacyTeacherService:
    """
    教师应用服务（适配当前内存数据模式）
    封装教师详情页的所有业务逻辑
    """
    
    def __init__(self, globals_dict: dict):
        """
        Args:
            globals_dict: 包含 teachers, courses, teachers_full_map 等全局数据的字典
        """
        self._g = globals_dict
    
    def get_teacher_detail(self, teacher_id: int) -> Optional[Dict]:
        """
        获取教师详情（聚合所有相关数据）
        
        Returns:
            {
                'teacher': dict,  # 教师基本信息
                'full_info': dict,  # 完整信息（来自 teachers_full_map）
                'courses': list,  # 课程列表
                'evaluations': list,  # 评价列表
                'likes': list,  # 点赞列表
                'found': bool  # 是否找到教师
            }
        """
        teachers = self._g.get('teachers', [])
        teacher = next((t for t in teachers if t.get('id') == teacher_id), None)
        
        if not teacher:
            return {'found': False}
        
        # 从完整数据中获取额外信息
        full_info = self._g.get('teachers_full_map', {}).get(teacher.get('name', ''), {})
        
        # 获取该教师的课程
        courses = [
            c for c in self._g.get('courses', [])
            if c.get('teacher_id') == teacher_id
        ]
        
        # 获取评价数据（优先使用教师对象上的结构化数据）
        evaluations = teacher.get('detailed_evaluations', [])
        likes = teacher.get('likes_data', [])
        
        # 如果没有结构化数据，回退到全局map
        if not evaluations:
            evaluations = self._g.get('teacher_evaluations_map', {}).get(teacher.get('name', ''), [])
        if not likes:
            likes = self._g.get('teacher_likes_map', {}).get(teacher.get('name', ''), [])
        
        return {
            'found': True,
            'teacher': teacher,
            'full_info': full_info,
            'courses': courses,
            'evaluations': evaluations,
            'likes': likes
        }
    
    def search_teachers(
        self,
        keyword: str = None,
        teacher_type: str = None,
        storage_status: str = None,
        field: str = None
    ) -> List[Dict]:
        """
        搜索教师（支持多条件组合过滤）
        
        Args:
            keyword: 搜索关键词（匹配姓名、专业、简介、课程名、课程简介）
            teacher_type: 教师类型筛选（校内/校外）
            storage_status: 入库状态筛选（待审核/已入库）
            field: 专业领域筛选
        """
        teachers = self._g.get('teachers', [])
        courses = self._g.get('courses', [])
        
        results = []
        for teacher in teachers:
            # 类型过滤
            if teacher_type and teacher.get('teacher_type') != teacher_type:
                continue
            
            # 入库状态过滤
            if storage_status == '待审核' and teacher.get('is_in_storage'):
                continue
            if storage_status == '已入库' and not teacher.get('is_in_storage'):
                continue
            
            # 专业领域过滤
            if field and field != '全部' and teacher.get('field') != field:
                continue
            
            # 关键词搜索（多字段匹配）
            if keyword:
                keyword_lower = keyword.lower()
                # 教师字段匹配
                teacher_fields = [
                    teacher.get('name', ''),
                    teacher.get('field', ''),
                    teacher.get('introduction', ''),
                    teacher.get('specialty', ''),
                ]
                teacher_match = any(keyword_lower in str(f).lower() for f in teacher_fields)
                
                # 课程字段匹配
                teacher_courses = [
                    c for c in courses
                    if c.get('teacher_id') == teacher.get('id')
                ]
                course_match = False
                for course in teacher_courses:
                    course_fields = [
                        course.get('name', ''),
                        course.get('description', ''),
                    ]
                    if any(keyword_lower in str(f).lower() for f in course_fields):
                        course_match = True
                        break
                
                if not teacher_match and not course_match:
                    continue
            
            results.append(teacher)
        
        return results
    
    def get_teacher_list(
        self,
        page: int = 1,
        per_page: int = 20,
        sort_by: str = 'name',
        sort_order: str = 'asc',
        keyword: str = None,
        in_stock: str = None,
        approval_status: str = None,
        status: str = None,
        title: str = None
    ) -> Dict:
        """
        获取教师列表（支持完整过滤、排序、分页）
        
        Args:
            keyword: 搜索关键词（多字段匹配）
            in_stock: 入库状态筛选（是/否）
            approval_status: 审批状态筛选（已通过/待审核）
            status: 状态筛选
            title: 职称筛选
            sort_by: 排序字段（score/count/name）
            sort_order: 排序方向（asc/desc）
            page: 页码
            per_page: 每页数量
        
        Returns:
            {
                'teachers': list,  # 当前页教师
                'filtered_teachers': list,  # 全部过滤后的教师（用于兼容旧模板）
                'total': int,
                'pages': int,
                'current_page': int,
                'has_prev': bool,
                'has_next': bool,
                'prev_num': int,
                'next_num': int,
                'pages_list': list  # 分页页码列表
            }
        """
        teachers = self._g.get('teachers', [])
        courses = self._g.get('courses', [])
        
        filtered_teachers = teachers.copy()
        
        # 综合搜索（多字段匹配）
        if keyword:
            keywords = [k.strip().lower() for k in keyword.split() if k.strip()]
            def matches_all_keywords(teacher, keywords):
                search_parts = [
                    str(teacher.get('name', '')),
                    str(teacher.get('field', '')),
                    str(teacher.get('title', '')),
                    str(teacher.get('specialty', '')),
                    str(teacher.get('introduction', '')),
                    str(teacher.get('organization', '')),
                    str(teacher.get('phone', '')),
                    str(teacher.get('contact_phone', '')),
                    str(teacher.get('course_info', '')),
                ]
                for rec in teacher.get('teaching_records', []):
                    search_parts.append(str(rec.get('课程名称', '')))
                search_text = ' '.join(search_parts).lower()
                return all(kw in search_text for kw in keywords)
            
            filtered_teachers = [t for t in filtered_teachers if matches_all_keywords(t, keywords)]
        
        # 入库状态筛选
        if in_stock:
            if in_stock == '是':
                filtered_teachers = [t for t in filtered_teachers if t.get('status') == '已入库']
            elif in_stock == '否':
                filtered_teachers = [t for t in filtered_teachers if t.get('status') != '已入库']
        
        # 审批状态筛选
        if approval_status:
            if approval_status == '已通过':
                filtered_teachers = [t for t in filtered_teachers if t.get('status') == '已入库']
            elif approval_status == '待审核':
                filtered_teachers = [t for t in filtered_teachers if t.get('status') == '待审核']
        
        # 状态筛选
        if status:
            filtered_teachers = [t for t in filtered_teachers if t.get('status') == status]
        
        # 职称筛选
        if title:
            filtered_teachers = [t for t in filtered_teachers if t.get('title') == title]
        
        # 排序
        if sort_by == 'score':
            filtered_teachers = sorted(
                filtered_teachers,
                key=lambda x: float(x.get('evaluation_score') or 0),
                reverse=True
            )
        elif sort_by == 'count':
            filtered_teachers = sorted(
                filtered_teachers,
                key=lambda x: int(x.get('teaching_count') or 0),
                reverse=True
            )
        elif sort_by == 'name':
            filtered_teachers = sorted(
                filtered_teachers,
                key=lambda x: x.get('name', '')
            )
        
        # 分页计算
        total = len(filtered_teachers)
        total_pages = (total + per_page - 1) // per_page
        page = max(1, min(page, total_pages)) if total_pages > 0 else 1
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_teachers = filtered_teachers[start_idx:end_idx]
        
        # 生成分页页码列表
        pages_list = []
        if total_pages <= 7:
            pages_list = list(range(1, total_pages + 1))
        else:
            if page <= 4:
                pages_list = list(range(1, 6)) + ['...', total_pages]
            elif page >= total_pages - 3:
                pages_list = [1, '...'] + list(range(total_pages - 4, total_pages + 1))
            else:
                pages_list = [1, '...'] + list(range(page - 1, page + 2)) + ['...', total_pages]
        
        # 查询课程数量（从 course_teachers 表）
        try:
            import sqlite3
            conn = sqlite3.connect('instance/teacher_system.db')
            c = conn.cursor()
            for teacher in paginated_teachers:
                teacher_id = teacher.get('id', 0)
                c.execute('SELECT COUNT(*) FROM course_teachers WHERE teacher_id = ?', (teacher_id,))
                teacher['course_count'] = c.fetchone()[0]
            conn.close()
        except Exception:
            for teacher in paginated_teachers:
                teacher['course_count'] = 0
        
        return {
            'teachers': paginated_teachers,
            'filtered_teachers': filtered_teachers,  # 兼容旧模板
            'total': total,
            'pages': total_pages,
            'current_page': page,
            'has_prev': page > 1,
            'has_next': page < total_pages,
            'prev_num': page - 1,
            'next_num': page + 1,
            'pages_list': pages_list
        }
    
    def create_teacher(self, form_data: dict) -> Dict:
        """
        创建新教师
        
        Args:
            form_data: 表单数据（name, title, field, specialty, introduction, organization, phone, email）
        
        Returns:
            {'success': bool, 'teacher': dict, 'error': str}
        """
        teachers = self._g.get('teachers', [])
        
        new_teacher = {
            'id': max([t.get('id', 0) for t in teachers] + [0]) + 1,
            'name': form_data.get('name'),
            'title': form_data.get('title'),
            'field': form_data.get('field'),
            'specialty': form_data.get('specialty'),
            'introduction': form_data.get('introduction'),
            'organization': form_data.get('organization'),
            'phone': form_data.get('phone'),
            'email': form_data.get('email'),
            'status': '待审核',
            'teacher_type': '校外',
            'is_in_storage': False,
            'created_at': __import__('datetime').datetime.now()
        }
        
        teachers.append(new_teacher)
        
        return {'success': True, 'teacher': new_teacher}
    
    def update_teacher(self, teacher_id: int, form_data: dict) -> Dict:
        """
        更新教师信息
        
        Returns:
            {'success': bool, 'teacher': dict, 'error': str}
        """
        teachers = self._g.get('teachers', [])
        teacher = next((t for t in teachers if t.get('id') == teacher_id), None)
        
        if not teacher:
            return {'success': False, 'error': '教师不存在'}
        
        teacher['name'] = form_data.get('name', teacher.get('name'))
        teacher['title'] = form_data.get('title', teacher.get('title'))
        teacher['field'] = form_data.get('field', teacher.get('field'))
        teacher['specialty'] = form_data.get('specialty', teacher.get('specialty'))
        teacher['introduction'] = form_data.get('introduction', teacher.get('introduction'))
        teacher['organization'] = form_data.get('organization', teacher.get('organization'))
        teacher['phone'] = form_data.get('phone', teacher.get('phone'))
        teacher['email'] = form_data.get('email', teacher.get('email'))
        
        return {'success': True, 'teacher': teacher}
    
    def delete_teacher(self, teacher_id: int) -> Dict:
        """
        删除教师
        
        Returns:
            {'success': bool, 'teacher_name': str, 'error': str}
        """
        teachers = self._g.get('teachers', [])
        teacher = next((t for t in teachers if t.get('id') == teacher_id), None)
        
        if not teacher:
            return {'success': False, 'error': '教师不存在'}
        
        teacher_name = teacher.get('name', 'unknown')
        teachers.remove(teacher)
        
        return {'success': True, 'teacher_name': teacher_name}
