# Git 认证信息加密存储功能说明

## 功能概述

本功能实现了 Git 仓库认证信息的加密存储，确保敏感数据（如 GitHub Token、SSH 密钥等）在数据库中以加密形式保存，防止数据泄露。

## 技术实现

### 1. 加密算法

使用 `cryptography` 库的 Fernet 对称加密算法：

- **算法**: AES-128-CBC
- **填充**: PKCS7
- **完整性**: HMAC-SHA256
- **特性**: 
  - 自动添加时间戳防止重放攻击
  - 每次加密生成不同的密文
  - 密文包含版本信息

### 2. 核心文件

#### 2.1 加密服务模块

**文件**: [backend/app/core/encryption.py](file:///Users/bingbing/Documents/project/skill-server-me/backend/app/core/encryption.py)

**主要功能**:
- `encrypt(plaintext: str) -> str`: 加密字符串
- `decrypt(ciphertext: str) -> str`: 解密字符串
- `generate_key() -> str`: 生成新的加密密钥

**使用示例**:
```python
from app.core.encryption import get_encryption_service

# 获取加密服务实例
encryption_service = get_encryption_service()

# 加密
encrypted_token = encryption_service.encrypt("ghp_xxxxxxxxxxxx")

# 解密
decrypted_token = encryption_service.decrypt(encrypted_token)
```

#### 2.2 配置模块

**文件**: [backend/app/core/config.py](file:///Users/bingbing/Documents/project/skill-server-me/backend/app/core/config.py)

**新增配置项**:
```python
# 加密配置
encryption_key: Optional[str] = None  # Fernet 加密密钥
```

**配置验证**:
- 生产环境强制要求设置 `ENCRYPTION_KEY` 环境变量
- 自动验证密钥格式是否为有效的 Fernet 密钥
- 开发环境未配置时给出警告

#### 2.3 Git 同步服务

**文件**: [backend/app/services/git_sync_service.py](file:///Users/bingbing/Documents/project/skill-server-me/backend/app/services/git_sync_service.py)

**修改内容**:
1. **导入仓库时加密存储**:
   ```python
   # 加密认证信息
   if auth_secret_ref:
       encrypted_auth_secret = self.encryption_service.encrypt(auth_secret_ref)
   ```

2. **同步仓库时解密使用**:
   ```python
   # 解密认证信息
   if repo.auth_secret_ref:
       auth_secret = self.encryption_service.decrypt(repo.auth_secret_ref)
   ```

3. **构建认证 URL**:
   - 支持 Token 认证
   - 支持用户名密码认证
   - 支持 SSH 密钥认证

## 部署配置

### 1. 生成加密密钥

使用以下方法之一生成加密密钥：

**方法一：使用 Python 脚本**
```bash
cd backend
python -c "from app.core.encryption import EncryptionService; print(EncryptionService.generate_key())"
```

**方法二：使用测试脚本**
```bash
cd backend
python test_encryption.py
```

### 2. 配置环境变量

在 `.env` 文件中添加：

```bash
# 加密密钥（必须设置）
ENCRYPTION_KEY=your-generated-encryption-key-here

# JWT 密钥（生产环境必须设置）
SECRET_KEY=your-secret-key-at-least-32-characters-long

# 调试模式（生产环境设置为 False）
DEBUG=false
```

**重要提示**:
- 加密密钥一旦设置，不要随意更改，否则已加密的数据将无法解密
- 生产环境必须通过环境变量设置密钥
- 密钥长度至少为 32 个字符

### 3. 安装依赖

确保 `pyproject.toml` 中包含 `cryptography` 依赖：

```bash
pip install cryptography>=41.0.0
```

## 使用流程

### 1. 导入带认证的 Git 仓库

```python
# API 调用示例
POST /api/repos/import
{
    "name": "my-private-repo",
    "url": "https://github.com/user/private-repo.git",
    "branch": "main",
    "auth_type": "token",
    "auth_secret_ref": "ghp_xxxxxxxxxxxxxxxxxxxx"
}
```

**处理流程**:
1. 接收认证信息
2. 使用加密服务加密 `auth_secret_ref`
3. 将加密后的数据存入数据库
4. 返回仓库信息（不包含认证信息）

### 2. 同步 Git 仓库

```python
# API 调用示例
POST /api/repos/{repo_id}/sync
```

**处理流程**:
1. 从数据库读取加密的认证信息
2. 使用加密服务解密
3. 构建带认证的 Git URL
4. 执行 Git 操作
5. 认证信息在内存中使用后立即销毁

## 安全特性

### 1. 数据加密

- 所有认证信息在存储前自动加密
- 使用 AES-128-CBC 算法，安全性高
- 每次加密生成不同的密文，防止模式分析

### 2. 密钥管理

- 密钥从环境变量读取，不硬编码
- 生产环境强制验证密钥配置
- 支持密钥格式验证

### 3. 访问控制

- 认证信息仅在需要时解密
- 解密后的数据仅在内存中存在
- API 响应不返回认证信息

### 4. 审计日志

- 加密/解密操作记录日志
- 异常情况详细记录
- 便于安全审计和问题排查

## 异常处理

### 1. 加密异常

```python
from app.core.exceptions import EncryptionError

try:
    encrypted = encryption_service.encrypt(data)
except EncryptionError as e:
    # 处理加密失败
    logger.error(f"加密失败: {e}")
```

### 2. 解密异常

```python
try:
    decrypted = encryption_service.decrypt(encrypted_data)
except EncryptionError as e:
    # 处理解密失败（密钥不匹配或数据被篡改）
    logger.error(f"解密失败: {e}")
```

## 测试验证

### 1. 运行测试脚本

```bash
cd backend
python test_encryption.py
```

### 2. 测试内容

- ✅ 密钥生成
- ✅ 字符串加密
- ✅ 字符串解密
- ✅ 空值处理
- ✅ 密钥验证
- ✅ 异常处理

### 3. 预期输出

```
============================================================
Git 认证信息加密存储功能测试
============================================================

1. 生成加密密钥:
   密钥: wcdwviLMbJfhza9zDJ-5zLEYqBetBtZCCHpBQj5xFKw=

2. 设置环境变量 ENCRYPTION_KEY 和 SECRET_KEY

3. 创建加密服务实例成功

4. 测试加密功能:
   ✓ 验证成功: 加密解密一致

5. 测试空值处理:
   ✓ 空字符串处理正确

============================================================
测试完成！所有功能正常
============================================================
```

## 最佳实践

### 1. 密钥管理

- ✅ 使用强随机密钥生成器
- ✅ 密钥存储在安全的环境变量中
- ✅ 定期轮换密钥（需要重新加密所有数据）
- ❌ 不要在代码中硬编码密钥
- ❌ 不要将密钥提交到版本控制

### 2. 数据处理

- ✅ 仅在需要时解密数据
- ✅ 解密后立即使用，不长期保存
- ✅ 使用 HTTPS 传输数据
- ❌ 不要在日志中记录明文认证信息
- ❌ 不要在 API 响应中返回认证信息

### 3. 错误处理

- ✅ 捕获并记录加密/解密异常
- ✅ 提供友好的错误提示
- ✅ 区分不同类型的错误
- ❌ 不要暴露详细的加密细节

## 常见问题

### Q1: 如何更换加密密钥？

**A**: 更换密钥需要重新加密所有已存储的数据：

1. 生成新密钥
2. 使用旧密钥解密所有数据
3. 使用新密钥重新加密
4. 更新环境变量

### Q2: 忘记密钥怎么办？

**A**: 密钥丢失后，已加密的数据无法恢复。建议：
- 安全备份密钥
- 使用密钥管理系统
- 定期测试密钥恢复流程

### Q3: 加密会影响性能吗？

**A**: 加密操作非常快速：
- 加密/解密操作通常在毫秒级完成
- 对整体性能影响可忽略不计
- 安全收益远大于性能损耗

### Q4: 支持哪些认证类型？

**A**: 当前支持：
- Token 认证（GitHub Token、GitLab Token 等）
- 用户名密码认证
- SSH 密钥认证（通过 SSH 配置文件）

## 相关文件

- [加密服务模块](file:///Users/bingbing/Documents/project/skill-server-me/backend/app/core/encryption.py)
- [配置模块](file:///Users/bingbing/Documents/project/skill-server-me/backend/app/core/config.py)
- [异常定义](file:///Users/bingbing/Documents/project/skill-server-me/backend/app/core/exceptions.py)
- [Git 同步服务](file:///Users/bingbing/Documents/project/skill-server-me/backend/app/services/git_sync_service.py)
- [测试脚本](file:///Users/bingbing/Documents/project/skill-server-me/backend/test_encryption.py)

## 更新日志

### v1.0.0 (2024-03-21)

- ✅ 实现基于 Fernet 的加密服务
- ✅ 添加加密密钥配置和验证
- ✅ 修改 Git 同步服务支持加密存储
- ✅ 添加异常处理和日志记录
- ✅ 编写测试脚本验证功能
- ✅ 编写使用文档
