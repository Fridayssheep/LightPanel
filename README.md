# lightpanel

面向 Docker / Web 服务的智能运维诊断 Agent。基于 **MCP (Model Context Protocol)** 架构，后端通过大模型 Tool Calling 决定要调用哪些运维工具，工具层通过 MCP Server 和 Docker socket 管理宿主机容器。

```text
用户描述问题
-> LLM Agent 选择工具
-> MCP Client 调用 MCP Server (stdio)
-> 调用 Docker / 端口 / 日志 / 系统状态工具
-> 汇总证据
-> 输出诊断结论和下一步动作
-> 停止容器等高危操作需要确认
-> 按需生成结构化诊断报告
```

## 架构说明

### MCP 架构

本项目采用标准 **Model Context Protocol (MCP)** 架构：

- **MCP Server** (`app/mcp/server.py`)：通过 stdio 暴露 26 个运维工具，纯粹的工具执行器
- **MCP Client** (`app/mcp/client.py`)：策略执行层，负责 approval 和 dry_run 检查
- **AgentService**：编排层，调用 LLM 并通过 MCP Client 执行工具
- **通信方式**：stdio 子进程，每次 chat 请求复用一个 MCP session

### 前端架构

- **技术栈**：Vue 3 + TypeScript + Vite
- **设计语言**：Material / Google 风格控制台，支持用户自定义主题色、页面切换动画和操作反馈
- **功能**：总览、容器管理、Compose 管理、运行时设置、实时对话、工具调用展示、诊断报告生成与查看、历史记录

## 功能

- Docker 健康检查、容器列表、容器详情、容器日志读取
- WebUI 手动启动、停止、重启和更新 Compose 管理的容器
- WebUI 镜像拉取，支持实时显示 Docker 拉取进度
- WebUI Compose 文件编辑、Compose 启停/重启/拉取/更新和项目日志查看
- WebUI 运行时设置修改，支持调整项目扫描目录、日志目录、模型配置和 Docker CLI 代理
- 部署 Nginx 容器，直接执行
- 重启容器，直接执行
- 停止容器，需要确认
- 检查端口占用和占用进程
- 采集 CPU、内存、磁盘状态
- 读取允许目录下的日志文件
- 扫描允许项目目录下的 Docker Compose 文件，并合并运行状态
- 日志错误模式识别
- JSON 文件保存诊断历史
- **按需生成结构化诊断报告**（故障现象、排查步骤、根因、建议、严重程度）
- **Vue 3 Web UI**：总览面板、容器查看、Compose 查看、设置、实时对话、工具调用可视化、报告展示
- OpenAI-compatible LLM Tool Calling，必须配置 API

## 配置

复制配置模板：

```bash
cp .env.example .env
```

填写大模型 API：

```bash
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=你的_API_Key
LLM_MODEL=你的模型名
```

不配置 API 时 `/agent/chat` 会返回 503，因为本项目要求由大模型进行工具选择和诊断编排。

## Docker 启动

主启动方式是 Docker Compose。部署时会启动两个容器：`lightpanel-backend` 运行 FastAPI 后端并挂载宿主机 Docker socket，`lightpanel-web` 使用 Nginx 托管前端构建产物并反代后端 API：

```bash
docker compose up --build
```

启动前需要先打开 Docker Desktop 或确保 Docker daemon 正在运行。

默认只扫描后端容器内 `/app/samples` 下的 Compose 文件，并允许 WebUI 编辑这些 Compose 文件。如果要像面板工具那样发现自己的项目，把宿主机项目目录挂到后端容器内，并加入 `LIGHTPANEL_PROJECT_ROOTS`。需要 WebUI 编辑时不要使用只读挂载：

```yaml
environment:
  LIGHTPANEL_PROJECT_ROOTS: |
    /app/samples
    /projects
volumes:
  - /你的/项目目录:/projects
```

支持识别 `compose.yml`、`compose.yaml`、`docker-compose.yml`、`docker-compose.yaml`。扫描只会发生在 `LIGHTPANEL_PROJECT_ROOTS` 配置的目录内，不会全盘搜索。多个目录推荐在设置页一行一条填写；环境变量也支持英文逗号分隔。

接口文档：

```text
http://127.0.0.1:8000/docs
```

Web UI 由 Nginx 容器对外提供：

```text
http://127.0.0.1:8000/
```

健康检查：

```bash
curl http://127.0.0.1:8000/health
```

`docker_available=true` 表示后端容器已经通过 `/var/run/docker.sock` 连上宿主机 Docker。对外的 `8000` 端口在 Nginx 容器上，`/api/*`、`/health`、`/agent/*` 等路径会被反代到后端容器。

后端容器内执行的 `docker compose` 只是通过 `/var/run/docker.sock` 操作宿主机 Docker daemon，不会在容器里再启动一套 Docker-in-Docker。需要注意的是，Compose 文件里的 bind mount 路径最终由宿主机 Docker daemon 解析；如果 Compose 文件使用相对路径或只存在于 agent 容器内的路径，宿主机 daemon 未必能访问。建议把项目目录按宿主机真实绝对路径同路径挂载进 agent 容器，或者避免在被管理项目里依赖相对 bind mount。

镜像拉取进度通过 `/api/images/pull/stream` 实时推送到 WebUI。设置页的高级设置可以配置 `HTTP_PROXY`、`HTTPS_PROXY` 和 `NO_PROXY`，这些值会传给后端容器内的 `docker` / `docker compose` CLI 进程。通过 Docker socket 管理宿主机时，真正访问镜像仓库的通常仍是宿主机 Docker daemon；如果拉取仍然超时，需要同时在 Docker Desktop 或宿主机 Docker daemon 配置代理。

Docker socket 等价于宿主机 Docker 管理权限。本项目用于本地实验和课程展示，不要直接暴露到公网。WebUI 的 Compose 文件编辑和设置修改也会写入已映射目录或 `data/settings.json`。

### 接入外部 MCP

设置页高级设置支持添加外部 MCP stdio server。配置格式是 JSON 对象，key 是服务名，工具会以前缀形式暴露给 AI，例如 `web__fetch`：

```json
{
  "web": {
    "command": "uvx",
    "args": ["--from", "mcp-server-fetch", "mcp-server-fetch"],
    "description": "读取网页教程"
  }
}
```

也可以通过环境变量配置：

```bash
LIGHTPANEL_EXTERNAL_MCP_SERVERS='{"web":{"command":"uvx","args":["--from","mcp-server-fetch","mcp-server-fetch"],"description":"读取网页教程"}}'
```

配置后刷新 `/tools` 或重新发起 AI 对话即可生效。AI 可以先调用外部 MCP 读取教程、文档或网页，再结合内置 Docker / Compose MCP 工具创建容器或项目。外部 MCP 命令会在后端运行环境中启动；如果项目用 Docker 部署，命令需要存在于后端容器内。只添加可信 MCP，不要把带敏感权限的 MCP 暴露给不可信提示词。

### 暴露内置 MCP

默认情况下，本项目的内置 MCP server 只给后端内部 AI 会话使用，不对外开放。设置页高级设置可以开启“内置 MCP 暴露”，开启后外部 MCP 客户端可通过 Web 入口连接：

```text
/api/mcp
```

也可以通过环境变量启用：

```bash
LIGHTPANEL_ENABLE_PUBLIC_MCP=true
```

这个入口会暴露本项目的 Docker、Compose、镜像、网络、卷和日志工具。由于后端挂载了 Docker socket，外部 MCP 客户端等价于拿到了很高的宿主机 Docker 管理能力，只建议在本机或可信实验网络开启，不要直接放到公网。停止、删除、清理、修改设置等高危工具仍不会从公开 MCP 入口接受内部隐藏确认参数。

## MCP 工具

AI 侧通过 MCP 调用和 WebUI 相同的后端能力。当前工具覆盖：

- Docker：`docker_health`、`list_containers`、`deploy_nginx`、`inspect_container`、`get_container_logs`、`start_container`、`restart_container`、`stop_container`、`update_container`、`pull_image`
- Compose：`list_compose_projects`、`read_compose_file`、`write_compose_file`、`compose_up`、`compose_stop`、`compose_restart`、`compose_pull`、`compose_update`、`compose_down`、`get_compose_logs`
- 设置和诊断：`get_runtime_settings`、`update_runtime_settings`、`get_system_status`、`check_port`、`read_log_tail`、`analyze_log_text`
- 外部 MCP：按设置页配置动态加载，工具名格式为 `服务名__原工具名`

默认策略是：启动、重启、拉取、更新直接执行；停止容器、停止/删除 Compose 项目、写 Compose 文件、修改运行时设置需要确认；`dry_run` 会跳过所有会改变状态的工具。

## API 示例

让 Agent 检查 Docker：

```bash
curl -X POST http://127.0.0.1:8000/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"查看当前 Docker 容器状态"}'
```

部署 Nginx，直接执行：

```bash
curl -X POST http://127.0.0.1:8000/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"帮我部署一个 Nginx，映射到 8080 端口"}'
```

停止容器默认需要确认：

```bash
curl -X POST http://127.0.0.1:8000/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"停止 lightpanel-nginx 容器"}'
```

确认执行高危操作：

```bash
curl -X POST http://127.0.0.1:8000/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"停止 lightpanel-nginx 容器","approve_actions":true}'
```

## 本地开发

不用 Docker 时也可以直接本地跑后端：

```bash
conda activate py_exp
uv pip install -e ".[dev]"
bash scripts/run_api.sh
```

前端开发（热更新）：

```bash
cd frontend
npm install
npm run dev
# 访问 http://localhost:5173
```

前端构建（生产）：

```bash
cd frontend
npm run build:prod
# 静态文件输出到 frontend/dist；Docker 部署时由 frontend/Dockerfile 复制进 Nginx 镜像
```
