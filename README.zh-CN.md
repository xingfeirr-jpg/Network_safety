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
│   ├── config/libraries.json            十个库的固定配置
│   ├── replication/                     流程 S1–S5、解析器、比对 S6
│   ├── analysis/  human_review/         图表与分层人工复核
│   └── output/                          复现结果（UI 读取）
├── ui/                                  Web 界面（FastAPI + Plotly）
│   ├── config.py                        所有路径集中定义，可用环境变量覆盖
│   ├── server.py                        API 与在线运行
│   ├── container/                       在复现容器内执行的辅助脚本
│   ├── static/                          前端
│   └── Dockerfile
├── reports/                             最终报告（中英文，PDF + DOCX）
├── docker-compose.yml                   部署文件
├── .env.example                         部署配置模板
└── data/                                运行时数据，自动创建（不进 git）
```

`backup/`（PPT、报告草稿、原始压缩包）只保留在本地，不纳入 git。

## 部署（Docker，推荐）

需要：Linux 服务器，安装 Docker Engine 24+ 和 Compose 插件，能访问外网（Ubuntu/PyPI 软件源以及 GitHub 上的库源码）。

```bash
git clone <你的仓库地址> project17 && cd project17
cp .env.example .env              # 按需修改 P17_DATA_DIR（绝对路径）和 P17_PORT
docker compose up -d --build
```

浏览器打开 `http://<服务器地址>:8000`。

`docker compose up` 会做两件事：

1. **构建 `project17-replication:1.0`**（锁定工具版本的分析镜像，首次约 5–10 分钟），并运行一次 `prepare-sources`：把十个库的固定版本源码下载并解压到 `$P17_DATA_DIR/cache/sources` 后退出。UI 用这些源码显示每条告警所在的代码行。之后再启动时，已有的库会跳过。
2. **构建并启动 `project17-ui`**，在 8000 端口提供界面和 API。

### 数据路径设计

UI 的所有路径都在 [`ui/config.py`](ui/config.py) 中定义：

| 环境变量 | 默认值（本地） | 作用 |
| --- | --- | --- |
| `P17_IMPL_DIR` | `<仓库>/Project17_Implementation_and_Data` | 原始实验数据，只读（已打包进镜像） |
| `P17_REPL_DIR` | `<仓库>/Project17_Replication` | 复现包，只读（已打包进镜像） |
| `P17_DATA_DIR` | `<仓库>/data` | 可写的运行时数据 |
| `P17_HOST_DATA_DIR` | 同 `P17_DATA_DIR` | 从 Docker 宿主机看到的数据目录 |
| `P17_IMAGE` | `project17-replication:1.0` | 在线运行使用的镜像 |

运行时数据目录：

```
$P17_DATA_DIR/
├── cache/
│   ├── downloads/   源码压缩包（校验 SHA-256）
│   ├── sources/     解压后的库源码
│   ├── build/       构建目录和编译数据库（多次运行复用）
│   └── deps/        依赖安装目录（libpng 依赖的 zlib）
├── runs/<run_id>/   每次在线运行的输出和进度日志
└── runtime/         挂载进复现容器的辅助脚本
```

**为什么 `P17_DATA_DIR` 必须是绝对路径：** 在 UI 里发起在线运行时，UI 容器通过 `/var/run/docker.sock` 在宿主机上启动一个**同级**的复现容器。Docker 的 `-v` 路径是按宿主机解析的，所以 compose 把数据目录以**完全相同的绝对路径**挂载进 UI 容器，这样 UI 交给 Docker 的每个路径在宿主机上都成立。

### 常用运维命令

```bash
docker compose logs -f ui                              # 查看 UI 日志
docker compose run --rm prepare-sources P01 P08        # 重新获取指定库的源码
docker compose up -d --build                           # git pull 之后更新
docker compose down                                    # 停止（P17_DATA_DIR 中的数据保留）
```

网络慢时，在 `.env` 中设置 `UBUNTU_MIRROR` 和 `PIP_INDEX_URL`（示例见 `.env.example`）。工具版本已锁定，换镜像源不影响结果。

> **安全提示：** UI 容器可以访问宿主机的 Docker socket（用于启动分析容器）。不要把 8000 端口直接暴露到公网，请放在带认证的反向代理之后，或用防火墙限制访问来源。

## 本地开发（UI 不用 Docker）

```bash
pip install -r ui/requirements.txt
cd ui && uvicorn server:app --reload --port 8000
```

运行时数据写入 `<仓库>/data`。在线运行仍需要 Docker 和复现镜像：`docker build -t project17-replication:1.0 Project17_Replication`。

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
