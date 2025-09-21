# OpenAI API 代理服务

![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python: 3.9-3.12](https://img.shields.io/badge/python-3.9--3.12-green.svg)
![FastAPI](https://img.shields.io/badge/framework-FastAPI-009688.svg)

基于 FastAPI 的高性能 OpenAI API 兼容代理服务，采用多提供商架构设计，支持 GLM-4.5 系列、K2Think、LongCat 等多种 AI 模型的完整功能。

## ✨ 核心特性

- 🔌 **完全兼容 OpenAI API** - 无缝集成现有应用
- 🏗️ **多提供商架构** - 支持 Z.AI、K2Think、LongCat 等多个 AI 提供商
- 🤖 **Claude Code 支持** - 通过 Claude Code Router 接入 Claude Code (**CCR 工具请升级到 v1.0.47 以上**)
- 🍒 **Cherry Studio支持** - Cherry Studio 中可以直接调用 MCP 工具
- 🚀 **高性能流式响应** - Server-Sent Events (SSE) 支持
- 🛠️ **增强工具调用** - 改进的 Function Call 实现，支持复杂工具链
- 🧠 **思考模式支持** - 智能处理模型推理过程
- 🐳 **Docker 部署** - 一键容器化部署(环境变量请参考`.env.example`)
- 🛡️ **会话隔离** - 匿名模式保护隐私
- 🔧 **灵活配置** - 环境变量灵活配置
- 🔄 **Token 池管理** - 自动轮询、容错恢复、动态更新
- 🛡️ **错误处理** - 完善的异常捕获和重试机制

## 🚀 快速开始

### 环境要求

- Python 3.9-3.12
- pip 或 uv (推荐)

### 安装运行

```bash
# 克隆项目
git clone https://github.com/ZyphrZero/z.ai2api_python.git
cd z.ai2api_python

# 使用 uv (推荐)
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync
uv run python main.py

# 或使用 pip (推荐使用清华源)
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
python main.py
```

> 🍋‍🟩 服务启动后访问接口文档：http://localhost:8080/docs  
> 💡 **提示**：默认端口为 8080，可通过环境变量 `LISTEN_PORT` 修改  
> ⚠️ **注意**：请勿将 `AUTH_TOKEN` 泄露给其他人，请使用 `AUTH_TOKENS` 配置多个认证令牌  

### 基础使用

服务启动后，可以通过标准的 OpenAI API 客户端进行调用。详细的 API 使用方法请参考 [OpenAI API 文档](https://platform.openai.com/docs/api-reference)。

### Docker 部署

#### 方式一：使用预构建镜像（推荐）

从 Docker Hub 拉取最新镜像：

```bash
# 拉取最新版本
docker pull zyphrzero/z-ai2api-python:latest

# 或拉取指定版本
docker pull zyphrzero/z-ai2api-python:v0.1.0
```

**快速启动**：

```bash
# 基础启动（使用默认配置）
docker run -d \
  --name z-ai2api \
  -p 8080:8080 \
  -e AUTH_TOKEN="sk-your-api-key" \
  zyphrzero/z-ai2api-python:latest

# 完整配置启动
docker run -d \
  --name z-ai2api \
  -p 8080:8080 \
  -e AUTH_TOKEN="sk-your-api-key" \
  -e ANONYMOUS_MODE="true" \
  -e DEBUG_LOGGING="true" \
  -e TOOL_SUPPORT="true" \
  -v $(pwd)/tokens.txt:/app/tokens.txt \
  -v $(pwd)/logs:/app/logs \
  zyphrzero/z-ai2api-python:latest
```

**使用 Docker Compose**：

创建 `docker-compose.yml` 文件：

```yaml
version: '3.8'

services:
  z-ai2api:
    image: zyphrzero/z-ai2api-python:latest
    container_name: z-ai2api
    ports:
      - "8080:8080"
    environment:
      - AUTH_TOKEN=sk-your-api-key
      - ANONYMOUS_MODE=true
      - DEBUG_LOGGING=true
      - TOOL_SUPPORT=true
      - LISTEN_PORT=8080
    volumes:
      - ./tokens.txt:/app/tokens.txt
      - ./logs:/app/logs
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

然后启动：

```bash
docker-compose up -d
```

#### 方式二：本地构建

```bash
cd deploy
docker-compose up -d
```

#### Docker 镜像信息

- **镜像地址**: [https://hub.docker.com/r/zyphrzero/z-ai2api-python](https://hub.docker.com/r/zyphrzero/z-ai2api-python)
- **支持架构**: `linux/amd64`, `linux/arm64`
- **基础镜像**: `python:3.11-slim`

#### 数据持久化

为了保持日志和配置文件的持久化，建议挂载以下目录：

```bash
# 启动时挂载数据目录
docker run -d \
  --name z-ai2api \
  -p 8080:8080 \
  -e AUTH_TOKEN="sk-your-api-key" \
  -v $(pwd)/tokens.txt:/app/tokens.txt \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/.env:/app/.env \
  zyphrzero/z-ai2api-python:latest
```

## 📖 详细指南

### 支持的模型

#### Z.AI 提供商
| 模型               | 上游 ID       | 描述        | 特性                   |
| ------------------ | ------------- | ----------- | ---------------------- |
| `GLM-4.5`          | 0727-360B-API | 标准模型    | 通用对话，平衡性能     |
| `GLM-4.5-Thinking` | 0727-360B-API | 思考模型    | 显示推理过程，透明度高 |
| `GLM-4.5-Search`   | 0727-360B-API | 搜索模型    | 实时网络搜索，信息更新 |
| `GLM-4.5-Air`      | 0727-106B-API | 轻量模型    | 快速响应，高效推理     |

#### K2Think 提供商
| 模型                    | 描述           | 特性                     |
| ----------------------- | -------------- | ------------------------ |
| `MBZUAI-IFM/K2-Think`   | K2Think 模型   | 快速的高质量推理 |

#### LongCat 提供商
| 模型               | 描述           | 特性                     |
| ------------------ | -------------- | ------------------------ |
| `LongCat-Flash`    | 快速响应模型   | 高速处理，适合实时对话   |
| `LongCat`          | 标准模型       | 平衡性能，通用场景       |
| `LongCat-Search`   | 搜索增强模型   | 集成搜索功能，信息检索   |

## ⚙️ 配置说明

### 环境变量配置

#### 基础配置
| 变量名                | 默认值                                    | 说明                   |
| --------------------- | ----------------------------------------- | ---------------------- |
| `AUTH_TOKEN`          | `sk-your-api-key`                         | 客户端认证密钥         |
| `LISTEN_PORT`         | `8080`                                    | 服务监听端口           |
| `DEBUG_LOGGING`       | `true`                                    | 调试日志开关           |
| `ANONYMOUS_MODE`      | `true`                                    | 匿名用户模式开关           |
| `TOOL_SUPPORT`        | `true`                                    | Function Call 功能开关 |
| `SKIP_AUTH_TOKEN`     | `false`                                   | 跳过认证令牌验证       |
| `SCAN_LIMIT`          | `200000`                                  | 扫描限制               |
| `AUTH_TOKENS_FILE`    | `tokens.txt`                              | Z.AI 认证token文件路径 |
| `USE_REQUEST_API_KEY` | `false`                                   | 是否使用请求体中的 ApiKey 作为认证令牌 |

#### 提供商配置
| 变量名                    | 默认值    | 说明                        |
| ------------------------- | --------- | --------------------------- |
| `LONGCAT_PASSPORT_TOKEN`  | -         | LongCat 单个认证token       |
| `LONGCAT_TOKENS_FILE`     | -         | LongCat 多个token文件路径   |

> 💡 详细配置请查看 `.env.example` 文件

## 🏗️ 多提供商架构

### Z.AI 提供商
```bash
# Z.AI 认证配置
AUTH_TOKENS_FILE=tokens.txt
ANONYMOUS_MODE=true
```

### LongCat 提供商

```bash
# LongCat 认证配置
LONGCAT_PASSPORT_TOKEN=your_passport_token
# 或使用多个token文件
LONGCAT_TOKENS_FILE=longcat_tokens.txt
```

### K2Think 提供商
```bash
# K2Think 自动处理认证，无需额外配置
```

## 🔄 Token池机制

### 功能特性

- **负载均衡**：轮询使用多个auth token，分散请求负载
- **自动容错**：token失败时自动切换到下一个可用token
- **健康监控**：基于Z.AI API的role字段精确验证token类型
- **自动恢复**：失败token在超时后自动重新尝试
- **动态管理**：支持运行时更新token池
- **智能去重**：自动检测和去除重复token
- **类型验证**：只接受认证用户token (role: "user")，拒绝匿名token (role: "guest")
- **回退机制**：认证模式失败时自动回退到匿名模式，*匿名模式无法回退到认证模式*

## 监控API

> 仅有基础功能，暂未完善

```bash
# 查看token池状态
curl http://localhost:8080/v1/token-pool/status

# 手动健康检查
curl -X POST http://localhost:8080/v1/token-pool/health-check

# 动态更新token池
curl -X POST http://localhost:8080/v1/token-pool/update \
  -H "Content-Type: application/json" \
  -d '["new_token1", "new_token2"]'
```

## 🎯 使用场景

### 1. AI 应用开发
- **智能客服系统**：集成到现有客服平台，提供 24/7 智能问答服务
- **内容生成工具**：自动生成文章、摘要、翻译等内容
- **代码助手**：提供代码补全、解释、优化建议等功能

### 2. 工具调用集成
- **外部 API 集成**：连接天气、搜索、数据库等外部服务
- **自动化工作流**：构建复杂的多步骤自动化任务
- **智能决策系统**：基于实时数据进行智能分析和决策

## ❓ 常见问题

**Q: 如何获取 AUTH_TOKEN？**  
A: `AUTH_TOKEN` 为自己自定义的 api key，在环境变量中配置，需要保证客户端与服务端一致。

**Q: 启动时提示"服务已在运行"怎么办？**  
A: 这是服务唯一性验证功能，防止重复启动。解决方法：
- 检查是否已有服务实例在运行：`ps aux | grep z-ai2api-server`
- 停止现有实例后再启动新的
- 如果确认没有实例运行，删除 PID 文件：`rm z-ai2api-server.pid`
- 可通过环境变量 `SERVICE_NAME` 自定义服务名称避免冲突

**Q: 如何通过 Claude Code 使用本服务？**

A: 创建 [zai.js](https://gist.githubusercontent.com/musistudio/b35402d6f9c95c64269c7666b8405348/raw/f108d66fa050f308387938f149a2b14a295d29e9/gistfile1.txt) 这个 ccr 插件放在`./.claude-code-router/plugins`目录下，配置 `./.claude-code-router/config.json` 指向本服务地址，使用 `AUTH_TOKEN` 进行认证。

示例配置：

```json
{
  "LOG": false,
  "LOG_LEVEL": "debug",
  "CLAUDE_PATH": "",
  "HOST": "127.0.0.1",
  "PORT": 3456,
  "APIKEY": "",
  "API_TIMEOUT_MS": "600000",
  "PROXY_URL": "",
  "transformers": [
    {
      "name": "zai",
      "path": "C:\\Users\\Administrator\\.claude-code-router\\plugins\\zai.js",
      "options": {}
    }
  ],
  "Providers": [
    {
      "name": "GLM",
      "api_base_url": "http://127.0.0.1:8080/v1/chat/completions",
      "api_key": "sk-your-api-key",
      "models": ["GLM-4.5", "GLM-4.5-Air"],
      "transformers": {
        "use": ["zai"]
      }
    }
  ],
  "StatusLine": {
    "enabled": false,
    "currentStyle": "default",
    "default": {
      "modules": []
    },
    "powerline": {
      "modules": []
    }
  },
  "Router": {
    "default": "GLM,GLM-4.5",
    "background": "GLM,GLM-4.5",
    "think": "GLM,GLM-4.5",
    "longContext": "GLM,GLM-4.5",
    "longContextThreshold": 60000,
    "webSearch": "GLM,GLM-4.5",
    "image": "GLM,GLM-4.5"
  },
  "CUSTOM_ROUTER_PATH": ""
}
```

**Q: 匿名模式是什么？**  
A: 匿名模式使用临时 token，避免对话历史共享，保护隐私。

**Q: 如何自定义配置？**  
A: 通过环境变量配置，推荐使用 `.env` 文件。  

**Q: 如何配置 LongCat 认证？**  
A: 有两种方式配置 LongCat 认证：  
1. 单个 token：设置 `LONGCAT_PASSPORT_TOKEN` 环境变量  
2. 多个 token：创建 token 文件并设置 `LONGCAT_TOKENS_FILE` 环境变量  


## 🔑 获取 Z.ai API Token

要使用完整的多模态功能，需要获取正式的 Z.ai API Token：

1. 打开 [Z.ai 聊天界面](https://chat.z.ai)，然后登录账号
2. 按 F12 打开开发者工具
3. 切换到 "Application" -> "Local Storage" -> "Cookie"列表中找到名为`token`的值
4. 复制 `token` 值设置为环境变量，也可以使用官方个人账号下设置的 API Key

> ❗ **重要提示**: 获取的 token 可能有时效性，多模态模型需要**官方 Z.ai API 非匿名 Token**，匿名 token 不支持多媒体处理  

## 🔑 获取 LongCat API Token

获取 LongCat API Token 才能正常使用该服务（官网匿名对话次数仅有一次）：

1. 打开 [LongCat 官网](https://longcat.chat/)，登录自己的美团账号
2. 按 F12 打开开发者工具
3. 切换到 "Application" -> "Local Storage" -> "Cookie"列表中找到名为`passport_token_key`的值
4. 复制 `passport_token_key` 值设置为环境变量


## 🛠️ 技术栈

| 组件            | 技术                                                                              | 版本    | 说明                                       |
| --------------- | --------------------------------------------------------------------------------- | ------- | ------------------------------------------ |
| **Web 框架**    | [FastAPI](https://fastapi.tiangolo.com/)                                          | 0.116.1 | 高性能异步 Web 框架，支持自动 API 文档生成 |
| **ASGI 服务器** | [Granian](https://github.com/emmett-framework/granian)                            | 2.5.2   | 基于 Rust 的高性能 ASGI 服务器，支持热重载 |
| **HTTP 客户端** | [HTTPX](https://www.python-httpx.org/) / [Requests](https://requests.readthedocs.io/) | 0.27.0 / 2.32.5 | 异步/同步 HTTP 库，用于上游 API 调用      |
| **数据验证**    | [Pydantic](https://pydantic.dev/)                                                 | 2.11.7  | 类型安全的数据验证与序列化                 |
| **配置管理**    | [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) | 2.10.1  | 基于 Pydantic 的配置管理                   |
| **日志系统**    | [Loguru](https://loguru.readthedocs.io/)                                          | 0.7.3   | 高性能结构化日志库                         |
| **用户代理**    | [Fake UserAgent](https://pypi.org/project/fake-useragent/)                        | 2.2.0   | 动态用户代理生成                           |

## 🏗️ 技术架构

```
┌──────────────┐      ┌─────────────────────────────────────┐      ┌─────────────────┐
│   OpenAI     │      │                                     │      │                 │
│  Client      │────▶│         FastAPI Server             │────▶│   Z.AI API      │
└──────────────┘      │                                     │      │                 │
┌──────────────┐      │ ┌─────────────────────────────────┐ │      │ ┌─────────────┐ │
│ Claude Code  │      │ │      Provider Router            │ │      │ │0727-360B-API│ │
│   Router     │────▶│ │  ┌─────────┬─────────┬─────────┐ │ │      │ └─────────────┘ │
└──────────────┘      │ │  │Z.AI     │K2Think  │LongCat  │ │ │      │ ┌─────────────┐ │
                      │ │  │Provider │Provider │Provider │ │ │────▶│ │0727-106B-API│ │
                      │ │  └─────────┴─────────┴─────────┘ │ │      │ └─────────────┘ │
                      │ └─────────────────────────────────┘ │      │                 │
                      │ ┌─────────────────────────────────┐ │      └─────────────────┘
                      │ │     /v1/chat/completions        │ │      ┌─────────────────┐
                      │ │     /v1/models                  │ │      │  K2Think API    │
                      │ │     Enhanced Tools              │ │────▶│                 │
                      │ └─────────────────────────────────┘ │      └─────────────────┘
                      └─────────────────────────────────────┘      ┌─────────────────┐
                               OpenAI Compatible API               │  LongCat API    │
                                                                   │                 │
                                                                   └─────────────────┘
```

## ⭐ Star History

If you like this project, please give it a star ⭐  

[![Star History Chart](https://api.star-history.com/svg?repos=ZyphrZero/z.ai2api_python&type=Date)](https://star-history.com/#ZyphrZero/z.ai2api_python&Date)


## 🤝 贡献指南

我们欢迎所有形式的贡献！
请确保代码符合 PEP 8 规范，并更新相关文档。

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## ⚠️ 免责声明

- 本项目与 Z.AI、K2Think、LongCat 等 AI 提供商官方无关
- 使用前请确保遵守各提供商的服务条款
- 请勿用于商业用途或违反使用条款的场景
- 项目仅供学习和研究使用
- 用户需自行承担使用风险

---

<div align="center">
Made with ❤️ by the community
</div>
