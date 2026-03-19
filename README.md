# Skills Hub

私有化部署的技能管理平台

## 功能特性

- 📦 **Skill 包管理**：上传、创建、编辑、删除
- 🔄 **Git 仓库同步**：自动同步 Git 仓库中的 Skills
- 🔍 **混合检索**：全文检索 + 向量检索 + RRF 融合
- 📚 **版本管理**：完整的版本历史和回滚
- ⏱️ **时间线追踪**：记录所有变更事件
- ⭐ **收藏功能**：收藏常用 Skills
- 🔔 **消息通知**：系统通知和事件提醒
- 🔐 **权限控制**：RBAC 权限系统

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- SQLite / PostgreSQL

### 后端启动

```bash
cd backend

# 安装依赖
pip install -e .

# 初始化数据库
python -m app.db.init_db

# 启动服务
uvicorn app.main:app --reload
```

### 前端启动

```bash
cd frontend

# 安装依赖
npm install

# 开发模式
npm run dev

# 生产构建
npm run build
```

### Docker 部署

```bash
# 复制环境配置
cp .env.example .env

# 启动服务
docker-compose up -d
```

## 运行模式

系统支持三种运行模式：

1. **登录开启模式**（推荐生产环境）
   - 完整用户体系和权限控制
   - 支持收藏、通知等功能

2. **只读匿名模式**（推荐对外展示）
   - 仅允许查看和下载
   - 禁止所有修改操作

3. **初始化管理模式**（仅限初始化阶段）
   - 单管理员入口
   - 初始化完成后必须切换

## API 文档

启动后端服务后访问：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 目录结构

```
skills-hub/
├── backend/                 # 后端代码
│   ├── app/
│   │   ├── api/            # API 路由
│   │   ├── auth/           # 认证授权
│   │   ├── core/           # 核心配置
│   │   ├── db/             # 数据库
│   │   ├── services/       # 业务服务
│   │   └── main.py         # 应用入口
│   └── pyproject.toml
├── frontend/               # 前端代码
│   ├── src/
│   │   ├── layouts/       # 布局组件
│   │   ├── views/         # 页面组件
│   │   ├── stores/        # 状态管理
│   │   ├── router/        # 路由配置
│   │   └── utils/         # 工具函数
│   └── package.json
├── deploy/                 # 部署配置
│   └── docker-compose.yml
├── data/                   # 数据目录
└── workspace/              # 工作区
```

## 许可证

MIT License
