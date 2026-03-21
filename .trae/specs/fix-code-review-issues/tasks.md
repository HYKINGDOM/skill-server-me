# Tasks

## 高优先级任务

- [x] Task 1: 强化生产环境密钥配置验证
  - [x] Task 1.1: 修改 `backend/app/core/config.py`，添加生产环境SECRET_KEY验证逻辑
  - [x] Task 1.2: 验证SECRET_KEY长度不低于32字符
  - [x] Task 1.3: 生产环境强制要求SECRET_KEY从环境变量读取
  - [x] Task 1.4: 添加启动时验证失败的错误处理

- [x] Task 2: 改进临时文件清理机制
  - [x] Task 2.1: 重构 `backend/app/api/skill_routes.py` 中的上传处理逻辑
  - [x] Task 2.2: 使用上下文管理器确保临时文件清理
  - [x] Task 2.3: 添加临时文件清理的单元测试

- [x] Task 3: 统一数据库事务边界
  - [x] Task 3.1: 分析 `backend/app/services/git_sync_service.py` 中的事务边界
  - [x] Task 3.2: 重构sync_repo方法，使用事务上下文管理器
  - [x] Task 3.3: 确保所有数据库操作在同一事务中
  - [x] Task 3.4: 添加事务回滚测试

## 中优先级任务

- [x] Task 4: 移除硬编码默认密码
  - [x] Task 4.1: 修改 `backend/app/db/init_db.py`，支持环境变量配置初始密码
  - [x] Task 4.2: 添加随机密码生成逻辑
  - [x] Task 4.3: 更新配置文档

- [x] Task 5: 提取魔法数字为配置常量
  - [x] Task 5.1: 在 `backend/app/core/config.py` 中添加分页相关配置
  - [x] Task 5.2: 更新所有使用硬编码分页值的地方
  - [x] Task 5.3: 添加配置验证

- [x] Task 6: 前端API错误处理标准化
  - [x] Task 6.1: 检查前端API请求封装文件位置
  - [x] Task 6.2: 创建或修改统一的错误处理拦截器
  - [x] Task 6.3: 标准化错误响应格式处理
  - [x] Task 6.4: 添加用户友好的错误提示组件

- [x] Task 7: 前端请求取消机制
  - [x] Task 7.1: 实现请求取消管理器
  - [x] Task 7.2: 在路由切换时取消未完成请求
  - [x] Task 7.3: 使用AbortController实现请求取消

- [x] Task 8: Git认证信息加密存储
  - [x] Task 8.1: 添加认证信息加密服务
  - [x] Task 8.2: 修改Git同步服务使用加密存储
  - [x] Task 8.3: 添加密钥管理配置

## 低优先级任务

- [x] Task 9: 完善前端类型定义
  - [x] Task 9.1: 检查 `frontend/src/types/index.ts` 中的类型定义
  - [x] Task 9.2: 添加缺失的API响应类型
  - [x] Task 9.3: 确保类型定义与后端一致

- [x] Task 10: 增强文件上传路径遍历防护
  - [x] Task 10.1: 审查 `backend/app/services/skill_service.py` 中的ZIP解压逻辑
  - [x] Task 10.2: 添加多层路径验证
  - [x] Task 10.3: 添加安全测试用例

- [x] Task 11: 检查并移除敏感信息日志
  - [x] Task 11.1: 扫描所有日志输出点
  - [x] Task 11.2: 识别可能输出敏感信息的位置
  - [x] Task 11.3: 实现敏感信息脱敏处理
  - [x] Task 11.4: 添加日志安全审计测试

# Task Dependencies
- Task 2 依赖 Task 1（配置验证完成后才能确保安全配置生效）
- Task 3 独立
- Task 4 独立
- Task 5 独立
- Task 6 和 Task 7 可以并行执行
- Task 8 独立
- Task 9 独立
- Task 10 依赖 Task 2（文件处理相关）
- Task 11 独立
