FROM mcr.microsoft.com/devcontainers/base:ubuntu-22.04

# 安装系统依赖（按需调整）
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    build-essential \
    pkg-config \
    git \
    curl \
    ca-certificates \
    libssl-dev \
    libffi-dev \
    zlib1g-dev \
    fonts-dejavu-core \
    fonts-noto-cjk \
 && rm -rf /var/lib/apt/lists/*

# 切换到非 root 用户并设置工作目录
USER vscode
WORKDIR /workspace
