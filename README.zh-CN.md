# COMP5355 Project 17：三种静态漏洞检测工具在十个开源 C 库上的比较

[English README](README.md)

我们用三个静态分析工具——**Flawfinder 2.0.20**、**Cppcheck 2.13.0**、**CodeChecker 6.29.1 + Clang Static Analyzer 18.1.3**——扫描十个固定版本的开源 C 库（共 30 次扫描），对得到的 **725 条告警**逐条对照源码核查，并比较三个工具的告警质量和运行开销。

| 关键数字 | |
| --- | --- |
| 告警总数 | 725（Flawfinder 536 / Cppcheck 116 / clangsa 73） |
| 核查结论 | 误报 648 / 有依据 62 / 无法判定 15 |
| 复现结果 | 30 组库-工具组合的告警全部与原实验一致 |

## 目录结构

```
.
├── Project17_Implementation_and_Data/   原始实验（只读）
│   ├── code/                            工具脚本、输入、结果重建脚本
│   └── data/                            原始输出、计时、725 条告警账本
├── Project17_Replication/               Docker 一键复现与结果分析
│   ├── Dockerfile                       Ubuntu 24.04 + 锁定版本的工具
│   ├── config/  replication/            固定配置、S1–S6 流程
│   ├── analysis/  human_review/         图表与分层人工复核
│   └── output/                          复现结果
├── ui/                                  Web 界面（自包含）
│   ├── data/                            UI 读取的全部数据（副本）
│   ├── vendor/                          复现解析器（解析在线运行输出）
│   ├── static/                          前端
│   ├── container/                       在复现容器内执行的辅助脚本
│   ├── tools/                           sync_data.py、build_static.py
│   ├── config.py  server.py ...         后端（FastAPI）
│   ├── runtime/                         源码缓存 + 在线运行结果（自动创建，不进 git）
│   └── Dockerfile
├── reports/                             最终报告（中英文，PDF + DOCX）
├── .github/workflows/pages.yml          GitHub Pages 自动部署
├── docker-compose.yml  .env.example     服务器部署
└── backup/                              PPT、草稿（仅本地，不进 git）
```

UI 只读取 `ui/` 里面的文件。研究数据有改动时，运行 `python ui/tools/sync_data.py` 刷新 `ui/data/`。

## 两种部署方式

| | GitHub Pages | Docker 服务器 |
| --- | --- | --- |
| 方式 | 推送到 GitHub，自动部署 | 在服务器上 `docker compose up -d --build` |
| 费用 | 免费（公开仓库） | 需要一台 Linux 服务器 |
| 库数据、工具介绍、数据看板、告警、案例、结论 | ✅ | ✅ |
| **实时运行**（在 Docker 里真跑工具） | ❌ 需要后端 | ✅ |

GitHub Pages 只能托管静态文件，不能运行 Python 后端，也不能运行 Docker。所以工作流会把所有 API 结果预先生成为 JSON，发布一个静态版界面：除了“实时运行”，其它功能都可用。

### 方式 A：GitHub Pages（推送即部署）

1. 把仓库推送到 GitHub。
2. 在仓库 **Settings → Pages → Build and deployment → Source** 中选择 **GitHub Actions**（只需设置一次）。
3. 之后每次推送到 `main`，[`.github/workflows/pages.yml`](.github/workflows/pages.yml) 会用 `ui/tools/build_static.py` 生成站点并发布到 `https://<用户名>.github.io/<仓库名>/`。进度可在 **Actions** 页查看，也可以在那里手动点 “Run workflow”。

私有仓库使用 Pages 需要付费套餐；免费账号请把仓库设为公开。

本地预览静态版：

```bash
pip install -r ui/requirements.txt
python ui/tools/build_static.py          # 生成 ui/dist/
python -m http.server -d ui/dist 8000    # 打开 http://localhost:8000
```

### 方式 B：Docker 服务器（完整功能）

需要：Linux，Docker Engine 24+ 和 Compose 插件，能访问外网。

```bash
git clone <仓库地址> project17 && cd project17
cp .env.example .env              # 按需修改 P17_RUNTIME_DIR（绝对路径）和 P17_PORT
docker compose up -d --build
```

浏览器打开 `http://<服务器地址>:8000`。会构建两个镜像：

- `project17-ui`：Web 界面和 API（数据已打包在 `ui/` 中）。
- `project17-replication:1.0`：实时运行使用的锁定版本分析工具（首次约 5–10 分钟）。

运行时数据（只有实时运行会写入）放在 `P17_RUNTIME_DIR`：

```
$P17_RUNTIME_DIR/
├── cache/downloads/   源码压缩包（校验 SHA-256）
├── cache/sources/     解压后的库源码
├── cache/build/       构建目录和编译数据库，多次运行复用
├── cache/deps/        依赖安装目录（libpng 依赖的 zlib）
├── runs/<run_id>/     每次实时运行的输出和进度日志
└── helpers/           挂载进复现容器的辅助脚本
```

**为什么必须是绝对路径：** 实时运行时，UI 容器通过 `/var/run/docker.sock` 在宿主机上启动一个**同级**复现容器。Docker 的 `-v` 路径按宿主机解析，所以 compose 把运行时目录以**完全相同的绝对路径**挂进 UI 容器，UI 交给 Docker 的每个路径在宿主机上都成立。

```bash
docker compose logs -f ui                       # 查看日志
docker compose run --rm prepare-sources         # 可选：预先下载所有库源码
git pull && docker compose up -d --build        # 更新
docker compose down                             # 停止（运行时数据保留）
```

网络慢时在 `.env` 中设置 `UBUNTU_MIRROR` / `PIP_INDEX_URL`（见 `.env.example`）。工具版本已锁定，换镜像源不影响结果。

> **安全提示：** UI 容器可以使用宿主机的 Docker socket。不要把 8000 端口直接暴露到公网，请放在带认证的反向代理之后，或用防火墙限制访问。

### UI 配置

所有路径定义在 [`ui/config.py`](ui/config.py)，均可选：

| 环境变量 | 默认值 | 作用 |
| --- | --- | --- |
| `P17_DATA_DIR` | `ui/data` | 打包的研究数据（只读） |
| `P17_RUNTIME_DIR` | `ui/runtime` | 可写的运行时数据 |
| `P17_HOST_RUNTIME_DIR` | 同 `P17_RUNTIME_DIR` | 从 Docker 宿主机看到的运行时目录 |
| `P17_IMAGE` | `project17-replication:1.0` | 实时运行使用的镜像 |

## 本地开发

```bash
pip install -r ui/requirements.txt
cd ui && uvicorn server:app --reload --port 8000
```

实时运行还需要 Docker 和镜像：`docker build -t project17-replication:1.0 Project17_Replication`。

## 命令行完整复现

```bash
cd Project17_Replication
bash run_replication.sh          # 全部十个库
bash run_replication.sh P01      # 只跑 zlib（约 2 分钟）
```

流程、数据格式、人工复核和完整分析见 [Project17_Replication/README.md](Project17_Replication/README.md)；原始实验记录见 [Project17_Implementation_and_Data/README.md](Project17_Implementation_and_Data/README.md)。

## 报告

- [reports/Project17_Report.pdf](reports/Project17_Report.pdf)（英文）
- [reports/Project17_Report_CN.pdf](reports/Project17_Report_CN.pdf)（中文）
