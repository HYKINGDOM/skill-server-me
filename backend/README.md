# Skills Hub Backend

## 技能管理平台后端服务

### 技术栈
- FastAPI
- SQLAlchemy / SQLModel
- Pydantic
- SQLite / PostgreSQL
- JWT 认证
- Git 操作
- 搜索服务

### 快速开始

```bash
# 安装依赖
pip install -e .

# 初始化数据库
python -m app.db.init_db

# 启动服务
uvicorn app.main:app --reload
```

### 运行模式
- `login_required`: 登录开启模式（推荐生产环境）
- `readonly_anonymous`: 只读匿名模式（推荐对外展示）
- `bootstrap_admin`: 初始化管理模式（仅限初始化阶段）

### API 文档
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
