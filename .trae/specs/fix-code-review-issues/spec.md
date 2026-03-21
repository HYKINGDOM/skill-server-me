# 代码评审问题修复规格文档

## Why
根据代码评审报告，项目中存在多个需要修复的问题，涵盖安全性、代码质量、测试覆盖等方面。这些问题可能影响系统的安全性、可靠性和可维护性，需要系统性地进行修复。

## What Changes
- **高优先级修复**
  - 强化生产环境密钥配置验证，强制要求SECRET_KEY从环境变量读取且长度不低于32字符
  - 增加核心业务逻辑的单元测试覆盖

- **中优先级修复**
  - 改进临时文件清理机制，确保异常情况下也能正确清理
  - 统一事务边界，确保数据库操作的原子性
  - 前端API错误处理标准化
  - 前端请求取消机制
  - Git认证信息加密存储

- **低优先级修复**
  - 移除硬编码默认密码，改为环境变量配置
  - 提取魔法数字为配置常量
  - 完善前端类型定义
  - 增强文件上传路径遍历防护
  - 检查并移除敏感信息日志

## Impact
- Affected specs: 安全配置、数据库事务、文件处理、前端API层
- Affected code: 
  - `backend/app/core/config.py` - 密钥验证
  - `backend/app/api/skill_routes.py` - 临时文件清理
  - `backend/app/services/git_sync_service.py` - 事务边界
  - `backend/app/db/init_db.py` - 默认密码配置
  - `frontend/src/utils/request.ts` - API错误处理和请求取消
  - `frontend/src/types/index.ts` - 类型定义完善

## ADDED Requirements

### Requirement: 安全配置验证
系统 SHALL 在生产环境启动时验证SECRET_KEY配置的安全性。

#### Scenario: 生产环境密钥验证
- **WHEN** 系统在生产环境启动（DEBUG=False）
- **THEN** 系统验证SECRET_KEY必须从环境变量读取，且长度不低于32字符
- **AND** 如果验证失败，系统拒绝启动并输出错误信息

### Requirement: 临时文件清理
系统 SHALL 确保上传处理过程中的临时文件在任何情况下都能被正确清理。

#### Scenario: 异常情况临时文件清理
- **WHEN** 上传处理过程中发生异常
- **THEN** 系统确保临时文件被正确删除
- **AND** 不留下任何孤立文件

### Requirement: 数据库事务原子性
系统 SHALL 确保Git同步操作的数据库事务具有正确的边界。

#### Scenario: Git同步事务回滚
- **WHEN** Git同步过程中发生错误
- **THEN** 所有相关的数据库更改被回滚
- **AND** 数据库状态保持一致性

### Requirement: 前端API错误处理
前端 SHALL 统一处理API错误响应。

#### Scenario: API错误响应处理
- **WHEN** API返回错误响应
- **THEN** 前端统一解析错误信息
- **AND** 向用户显示友好的错误提示

### Requirement: 请求取消机制
前端 SHALL 在路由切换时取消未完成的API请求。

#### Scenario: 路由切换请求取消
- **WHEN** 用户切换路由
- **THEN** 前端取消当前页面未完成的API请求
- **AND** 避免内存泄漏和无效状态更新

### Requirement: 敏感信息保护
系统 SHALL 不在日志中输出敏感信息。

#### Scenario: 日志安全检查
- **WHEN** 系统记录日志
- **THEN** 日志中不包含密码、令牌、密钥等敏感信息
- **AND** 敏感字段被脱敏处理

## MODIFIED Requirements

### Requirement: 默认管理员密码配置
系统 SHALL 通过环境变量配置初始管理员密码，而非硬编码。

#### Scenario: 初始密码配置
- **WHEN** 系统初始化管理员账户
- **THEN** 从环境变量读取初始密码
- **AND** 如果未配置，生成随机密码并输出到控制台

### Requirement: 配置常量提取
系统 SHALL 将魔法数字提取为配置常量。

#### Scenario: 分页配置
- **WHEN** 系统处理分页请求
- **THEN** 使用配置文件中定义的默认分页大小
- **AND** 允许通过环境变量覆盖默认值

## REMOVED Requirements
无
