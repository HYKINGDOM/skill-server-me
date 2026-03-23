# 后端 Dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 配置 pip 使用国内镜像源
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip config set install.trusted-host pypi.tuna.tsinghua.edu.cn

# 复制依赖文件
COPY pyproject.toml README.md ./

# 安装 Python 依赖（添加重试机制）
RUN pip install --no-cache-dir -e . || pip install --no-cache-dir -e . || pip install --no-cache-dir -e .

# 复制应用代码
COPY app/ ./app/

# 创建数据目录
RUN mkdir -p /app/data /app/workspace

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
