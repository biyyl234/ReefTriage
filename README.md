# 🪸 ReefTriage — Semporna Reef Restoration Prioritization

> 仙本那珊瑚礁恢复优先级实时决策系统
> AI4Climate 赛道 04・马来西亚沙巴仙本那珊瑚礁气候韧性

ReefTriage 把珊瑚礁保护从"年度巡查 + 经验判断"升级为**周级实时决策工具**：每周接入 NOAA DHW 热压力数据，结合 Copernicus Marine 真实温盐氧叶绿素、ETOPO 水深、HYCOM 海流粒子追踪、CoralCore RHI 和旅游潜点距离，通过**三层决策引擎**（ML 白化预测 + 熵权 TOPSIS + Laya/Jev 结构化判断）对仙本那海域 28 个礁段打出 0-100 恢复优先级分数，并在有限预算下用整数规划输出"先救哪几段"的可执行名单。

集成 NocoBase 作为后台管理系统，支持双向数据同步和统一管理面板。

---

## 架构图

```
┌──────────────────────────────────────────────────────────┐
│                    NocoBase (:13000)                      │
│  礁段管理 / 数据编辑 / 图表 / 用户权限 / 菜单导航          │
│  (PostgreSQL :5432 存储)                                  │
└────────────────────┬─────────────────────────────────────┘
                     │ 双向同步 (REST API)
                     ▼
┌──────────────────────────────────────────────────────────┐
│              ReefTriage FastAPI (:8000)                   │
│  ┌────────────┐  ┌────────────┐  ┌───────────────────┐   │
│  │ 前端 Leaflet │  │  REST API   │  │  统一管理面板      │   │
│  │ 地图+列表    │  │ /api/*      │  │  /admin-panel    │   │
│  └────────────┘  └─────┬──────┘  └───────────────────┘   │
│                        │                                  │
│              ┌─────────▼──────────┐                       │
│              │  评分引擎 engine.py  │                       │
│              │  批量评分 + 缓存     │                       │
│              └─────────┬──────────┘                       │
└────────────────────────┼──────────────────────────────────┘
                         │ POST /v1/systemone
                         ▼
              ┌─────────────────────┐
              │  Laya/Jev (:5000)   │  可选，未启动时自动 mock
              │  真实 AI 评分引擎     │
              └─────────────────────┘
```

---

## 评分模型架构（三层）

ReefTriage 使用三层架构评分模型（`app/scoring/`），不依赖 Laya 也能独立运行。

### 第一层：特征增强

| 模型 | 文件 | 说明 |
|------|------|------|
| **模型C — ML白化预测器** | `ml_predictor.py` | 逻辑回归，用 2020/2024 历史 DHW + 12维特征训练，输出 bleaching_probability (0-1)。AUC=0.99，系数可解释。 |
| **模型D — 贝叶斯不确定性** | `bayesian.py` | 蒙特卡洛模拟（1000次），对水深/RHI/连通性等不确定特征加噪声，输出 score 均值和 95% 置信区间。 |

### 第二层：双引擎评分融合

| 模型 | 文件 | 说明 |
|------|------|------|
| **模型A — 熵权TOPSIS** | `mcdm.py` | 熵权法客观赋权（12+1维特征）+ TOPSIS 相对接近度 → mcdm_score (0-100)。权重可展示。 |
| **Laya rubric v2** | `rubric_v2.py` | 结构化分维度判断标准（热压力/脆弱性/恢复潜力/旅游价值/成本效益），输出 laya_score。 |
| **融合引擎** | `fusion.py` | `final_score = α × mcdm_score + (1-α) × laya_score`，α=0.30（walk-forward回测优化，限制[0.3,0.7]）。 |

### 第三层：决策优化

| 模型 | 文件 | 说明 |
|------|------|------|
| **阈值优化** | `threshold.py` | ROC + Youden's J 确定最优阈值（invest≥37.6，bootstrap 95% CI [37.4, 37.9]），替代硬编码 55/40。 |
| **模型B — 预算整数规划** | `optimizer.py` | 0-1 整数规划：最大化 Σ expected_gain × connectivity_amplifier，约束 Σ cost ≤ budget。PuLP 求解，失败回退贪心。 |

### 回测验证

- **Walk-forward**：2020训练→2024验证，2024训练→2020验证
- **ROC AUC**：新模型 0.989 vs 旧模型 0.889（2020）/ 0.947（2024）
- **白化峰命中率**：2020 事件 61.1%，2024 事件 64.7%（Invest 段命中高 DHW 异常的比例）
- **Bootstrap**：1000次，命中率 100% (32/32)
- 详细报告：`docs/model_optimization_report.md`
- 回测脚本：`scripts/run_backtest.py`（可重复运行，种子42）
- ⚠️ 标签来自 DHW 阈值而非实测白化，以上为方向性验证，非预测精度声明

### 模型 API

| 端点 | 说明 |
|------|------|
| `GET /api/model/weights` | 熵权法特征权重 |
| `GET /api/model/compare` | 新旧模型评分对比 + α |
| `GET /api/model/ml-info` | ML模型指标 + 系数 |
| `GET /api/optimize?budget=&unit_cost=` | 预算约束整数规划结果 |

---


## Reef Lab 微观页面（micro.html）

除宏观地图外，系统为每个礁段提供一个**微观诊断页面** `app/frontend/micro.html`，从宏观列表的详情抽屉点击 **🔬 Enter Reef Lab** 打开（URL: `/static/micro.html?segment=R01`）。

页面分四个面板，中英双语切换（右上角按钮）：

| 面板 | 内容 |
|------|------|
| 🌡️ 物理环境 | 当前 SST / DHW / BAA 白化预警等级；ECharts 月均 SST 气候态曲线 + DHW 累积历史柱状图；海流流速/流向罗盘 |
| 🧪 化学环境 | pH、文石饱和度 Ωarag、溶解氧 DO、盐度、叶绿素-a 五张指标卡，带 [范围] 与 OK/CAUTION/DANGER 阈值徽标 |
| 🪸 白化监测 | 4 张参考珊瑚图像（健康/轻度/中度/重度）+ 在端 HSV 白化分析器（上传照片输出 White/Pale/Pigmented 占比）；CoralCore RHI 8 维条形图；珊瑚覆盖度趋势曲线；历史白化事件时间线 |
| 💰 修复成本核算 | 方法下拉（珊瑚园艺/直接移植/幼虫培育/人工鱼礁）+ 面积/存活率滑块 + 密度输入；实时计算总成本、存活珊瑚数、单株成本与五项成本明细；💾 Save 持久化 |

**双向联动**：微观页面保存的修复成本会写入 `scored_segments.json` 的 `restoration_plan` 字段，宏观优化器（模型B `/api/optimize`）在预算规划时优先使用该实际成本（`cost_source=saved_plan`），否则回退到面积×水深的估算值（`cost_source=estimated`）。

---

## 连通性模型（纯 Python RK4 粒子追踪）

因 `oceanparcels` 在 Windows Python 3.14 无预编译 wheel，ReefTriage 实现了自包含的纯 Python RK4 粒子追踪模型（`app/scoring/connectivity.py`）：

| 参数 | 值 |
|------|------|
| 礁段数 | 28 |
| 每段释放粒子 | 80（共 2240） |
| 模拟时长 | 30 天（720 步） |
| 日死亡率 | 0.05（指数衰减，文献范围 0.03–0.10） |
| 定居半径 | 5 km |
| competency period | 5 天（前 5 天不定居） |
| 垂直迁移 | 昼夜：白天 15 m / 夜间 0 m（UTC+8） |
| 积分器 | 4 阶 Runge–Kutta，向量化 |
| 随机种子 | 42（可复现） |
| 海流强迫 | HYCOM GLBy0.08 1/12° 3小时再分析 |

**结果**：528 粒子定居（23.6%），1695 死亡或离开域（75.7%），17 漂浮（0.8%）。Sipadan/Mabul/Kapalai 为净幼虫源（输出系数 0.36–0.81），Timbalan Reef 为主要汇。前端通过 `/static/connectivity.html` 以 ECharts 力导向图展示 28 节点幼虫流向网络。

---

## Layui 综合管理系统（admin.html）

除 `/admin-panel`（供 NocoBase 嵌入的旧面板）外，系统提供一个独立的 **Layui 2.9.16 综合管理控制台**，作为前端统一入口。

**访问方式**：
- 根路径 http://127.0.0.1:8000/ 自动重定向到 `/static/admin.html`
- 直接打开 http://127.0.0.1:8000/static/admin.html
- 顶栏右上角 "↗" 按钮可在新标签页打开当前 iframe 内容

**布局**：深色科技风（`--bg:#0a1628`），顶栏（Logo + 居中页标题 + 服务状态徽章 + 语言切换）+ 左侧 200px **可拖动宽度、可收缩展开**侧边栏（拖动边缘调整宽度，点击箭头折叠，状态持久化到 localStorage）+ 右侧 iframe 内容区。侧边栏宽度在窄屏（<768px）自动折叠为 60px 图标栏。首次访问自动弹出 **Intro.js Product Tour**（8 步中英双语新手指引），可通过 Help 按钮重新触发。

**前端路由表**（所有页面均通过 `/static/` 前缀访问）：

| 路径 | 文件 | 用途 |
|------|------|------|
| `/` | — | 重定向到 `/static/admin.html` |
| `/static/admin.html` | `admin.html` | Layui 综合管理控制台（统一入口） |
| `/static/index.html` | `index.html` | Leaflet 宏观决策地图（默认首页） |
| `/static/filter.html` | `filter.html` | 空间筛选（DHW/水深/连通性/评分多维筛选） |
| `/static/draw.html` | `draw.html` | 区域绘制与报告（Leaflet Draw 圈选礁段） |
| `/static/micro.html?segment=R01` | `micro.html` | Reef Lab 微观实验室（4 面板诊断） |
| `/static/report.html` | `report.html` | 报告中心（单段/区域报告渲染） |
| `/static/services.html` | `services.html` | 服务监控（4 服务卡片 + ECharts 仪表盘） |
| `/static/api.html` | `api.html` | API 控制台（端点列表 + Test 调用） |
| `/static/model.html` | `model.html` | 模型面板（三层架构/权重/对比/ML 指标） |
| `/static/connectivity.html` | `connectivity.html` | 连通性网络（ECharts 力导向图） |
| `/static/metadata.html` | `metadata.html` | 数据来源（数据层元数据展示） |
| `/static/feedback.html` | `feedback.html` | 用户反馈表单（功能建议/Bug/数据问题） |
| `/static/settings.html` | `settings.html` | 设置（语言/底图/模型参数） |
| `/admin-panel` | `admin/panel.html` | NocoBase iframe 嵌入用旧管理面板 |

**侧边栏菜单项**（iframe 加载对应页面，页标题随菜单切换）：

| 菜单 | iframe src | 内容 |
|------|------|------|
| 🗺️ 宏观决策地图 | `/static/index.html` | Leaflet 决策地图（默认首页） |
| 🎯 空间筛选 | `/static/filter.html` | 多维空间筛选面板 |
| ✏️ 区域绘制 | `/static/draw.html` | 圈选区域 → 相交礁段 + 汇总报告 |
| 🔬 微观实验室 | `/static/micro.html?segment=R01` | Reef Lab 微观诊断 |
| 📄 报告中心 | `/static/report.html` | 单段/区域报告渲染 |
| 📊 服务监控 | `/static/services.html` | 4 个服务卡片 + ECharts 仪表盘 |
| 🔧 API 管理 | `/static/api.html` | 端点列表 + Test 按钮 + JSON 面板 |
| 🧮 模型面板 | `/static/model.html` | 三层工作流/权重/对比/ML 指标 |
| 🌐 连通性网络 | `/static/connectivity.html` | ECharts force graph 28 节点 |
| 📚 数据来源 | `/static/metadata.html` | 数据层元数据展示 |
| 💬 用户反馈 | `/static/feedback.html` | 反馈表单（中英双语，复制提交） |
| ⚙️ 设置 | `/static/settings.html` | 语言/底图选择 + 模型参数 |

**顶栏服务状态徽章**：RT / LYA / PG / NB 四色点，每 30s 轮询 `/api/services-status` 更新（ReefTriage 自身恒为在线，其余按端口探测）。

**i18n 统一**：语言偏好存于 `localStorage['reeftriage_lang']`（`en`/`zh`）。admin.html 切换语言时写入 localStorage 并 reload iframe；各子页面加载时读取该 key 应用字典。macro/micro 与 admin 共享同一 key，跨页面语言一致。

---

## 底图配置与响应式布局

### 底图切换

宏观地图（`index.html`）默认使用 **ESRI World Imagery（卫星图）**，右上角 "🛰️ 卫星 / 🗺️ 地形" 按钮在以下两层间切换：

| 底图 | URL 模板 | 说明 |
|------|---------|------|
| 卫星（默认） | `server.arcgisonline.com/.../World_Imagery/tile/{z}/{y}/{x}` | ESRI World Imagery，真彩色影像 |
| 地形 | `server.arcgisonline.com/.../World_Topo_Map/tile/{z}/{y}/{x}` | ESRI World Topo Map，晕渲地形 |

> 早期版本曾用 ESRI Ocean 底图，第六轮起改为 World Topo Map。底图选择亦会写入 `localStorage['reeftriage_basemap']`，可在设置页切换。

### 响应式断点

| 断点 | 布局 |
|------|------|
| 桌面 >1200px | 完整侧边栏 + 全宽面板 + ECharts 全尺寸 |
| 平板 768–1200px | 侧边栏收窄，图表自动 resize |
| 移动 <768px | 侧边栏折叠为图标栏，面板抽屉化，ECharts 监听 window resize 自适应 |

所有 ECharts 图表（services 仪表盘 / model 权重与对比 / connectivity 力导向图）均注册 `window.resize` 事件，窗口或侧边栏折叠时自动重绘。

---

## 环境数据（Reef Lab 数据源）

微观页面的环境与监测数据位于 `data/output/environmental/R01-R28.json` 与 `data/output/monitoring/R01-R28.json`，每个礁段一个文件。

| 变量 | 来源 | 说明 |
|------|------|------|
| DHW 时间序列 | **NOAA Coral Reef Watch v3.1** 5km 逐日（ERDDAP 实测/再分析） | 2020-2026 逐月，来自 ERDDAP netCDF，是**实测**热压力记录 |
| SST / 盐度 / 溶解氧 DO / 叶绿素-a | **Copernicus Marine Service** PHY + BGC 再分析（2026年9月接入，已替换文献值） | 仙本那观测值：SST 29.88°C、盐度 32.84 PSU、DO 4.49 ml/L、叶绿素 0.135 mg/m³；按 28 礁段质心采样 |
| pH / Ωarag（文石饱和度） | **文献典型值**（热带大洋珊瑚礁） | Copernicus BGC 数据集**不含 pH 变量**，保留文献值并在 UI 中标注 |
| 海流流速/流向 | **HYCOM GLBy0.08** 1/12° 3小时再分析 | 用于粒子追踪连通性模型（2240 粒子 × 30 天 RK4） |
| RHI 8 维与覆盖度趋势 | **文献锚定估计**（非现场调查） | 引用 Reef Check Malaysia 2024、NOAA CRW 及已发表马来西亚白化文献 |
| 珊瑚参考图 | `app/frontend/img/coral/` | 4 张示意图，署名见 `img/coral/SOURCES.md` |

> ✅ **Copernicus Marine 已接入**（2026年9月）：通过 `copernicusmarine` Python 工具包下载 PHY（`cmems_mod_glo_phy_my_0.083deg_P1D-m`）和 BGC（`cmems_mod_glo_bgc_my_0.25deg_P1D-m`）再分析数据，采样 28 礁段质心（表层 0.5–10 m 平均），替换了此前的文献占位值。观测值：SST 29.88°C、盐度 32.84 PSU、DO 4.49 ml/L、叶绿素 0.135 mg/m³。
>
> ⚠️ **已知降级**：BGC 数据集不含 pH 和文石饱和度（Ωarag），这两个参数仍为文献典型值，UI 中明确标注。DO 原始单位 mmol/m³，已按 0.022391 换算为 ml/L。
>
> 原始 `.nc` 文件已通过 `.gitignore` 排除（`data/raw/` 与 `*.nc`），入库的是采样后的 JSON。下载脚本见 `scripts/probe_cmems.py`，下载日志见 `docs/copernicus_download_log.md`。

---

## AI 白化识别（降级算法 + 模型调研）

微观页面内置一个**在端（on-device）HSV 白化分析器** `app/frontend/lib/color_analyzer.js`：

- 上传珊瑚照片后，在浏览器内把图像像素从 RGB 转到 HSV 色域；
- 按色相/饱和度/明度阈值把像素分成 **White（白化）/ Pale（褪色）/ Pigmented（色素正常）/ Water（水体）** 四类，输出各占百分比；
- 这是一个**轻量降级算法**，不是深度学习检测器——用于演示"图像辅助白化评估"的交互，不替代水下调查。

**NOAA YOLO11n 模型调研**：我们调研了 NOAA 珊瑚礁监测所用的 YOLO11n 实例分割模型（用于自动化珊瑚/藻类/死亡骨架像素分割），完整选型对比、数据增强、训练代价与部署方案见 `docs/ai_model_research.md`。当前 demo 未集成真实权重（需 GPU 训练 + 标注数据集），HSV 降级算法可在无网络/GPU 时运行。

---

## 修复成本核算方法

成本计算器（micro.html 第 4 面板）按文献锚定的单价实时估算：

- `surviving = area_m² × coral_density × survival_rate`
- 总成本按方法单价（USD/m²，`coral_gardening=2.0` 等）× 面积，并拆分为 Materials / Labor / Equipment / Monitoring(3yr) / Maintenance(3yr) 五项；
- 单价区间锚定 **Bayraktarov et al. 2016**（全球珊瑚修复成本综述）：社区低成本约 $9,200/ha，发展中国家常规约 $160,000/ha，单株 $0.15–$178，南海单株 ¥100–500。
- 保存后由 `/api/segments/{id}/restoration-cost` 写入，供模型B预算优化使用。

---

## 环境要求

| 组件 | 最低版本 | 说明 |
|------|---------|------|
| Python | 3.12+ (开发用 3.14) | 后端运行时 |
| Node.js | 18+ (开发用 22) | NocoBase 运行时 |
| yarn | 1.22+ | NocoBase 包管理 (`npm install -g yarn`) |
| PostgreSQL | 14+ (开发用 17) | NocoBase 数据库 |
| Laya/Jev | 可选 | 真实 AI 评分，不装则自动 mock 降级 |

**端口占用**：8000 (ReefTriage)、13000 (NocoBase)、5432 (PostgreSQL)、5000 (Laya，可选)

---

## 快速开始（三步启动）

### 1. 克隆仓库

```bash
git clone https://github.com/biyyl234/ReefTriage.git
cd ReefTriage
```

### 2. 运行部署脚本

```bat
setup.bat
```

脚本会自动完成：创建 Python venv → 安装依赖 → 检查/安装 PostgreSQL → 创建数据库 → 安装 NocoBase 依赖 → 初始化 NocoBase → 同步数据。

> ⚠️ `yarn install` 可能需要 10-20 分钟，请耐心等待。如遇网络问题，脚本已自动切换 npmmirror 镜像。

### 3. 启动所有服务

```bat
start_all.bat
```

访问：
- **ReefTriage 地图**: http://127.0.0.1:8000
- **综合管理控制台**: http://127.0.0.1:8000/static/admin.html （Layui 12 菜单统一入口，首次访问自动弹出 Product Tour 新手指引）
- **管理面板**: http://127.0.0.1:8000/admin-panel （NocoBase 嵌入用旧面板）
- **NocoBase 后台**: http://127.0.0.1:13000 (admin@nocobase.com / admin123)

---

## 详细部署步骤

如果 setup.bat 失败或需要手动部署，按以下步骤操作。

### A. ReefTriage 后端

```bash
# 1. 创建虚拟环境
python -m venv .venv

# 2. 激活 (Windows)
.venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 启动后端
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

验证：浏览器打开 http://127.0.0.1:8000 应看到 Leaflet 地图。

### B. PostgreSQL

#### 方式一：便携版（推荐，无需管理员权限）

```bash
# 1. 下载 PostgreSQL 17 便携版
#    访问 https://www.enterprisedb.com/download-postgresql-binaries
#    下载 postgresql-17.x-windows-x64-binaries.zip

# 2. 解压到 %USERPROFILE%\pg17\
#    解压后结构: %USERPROFILE%\pg17\pgsql\bin\

# 3. 初始化数据库集群 (首次)
set PGPASSWORD=postgres
"%USERPROFILE%\pg17\pgsql\bin\initdb.exe" -D "%USERPROFILE%\pg17\data" -U postgres -W

# 4. 启动
"%USERPROFILE%\pg17\pgsql\bin\pg_ctl.exe" -D "%USERPROFILE%\pg17\data" -l "%USERPROFILE%\pg17\pg.log" -o "-p 5432" start

# 5. 创建 nocobase 数据库
"%USERPROFILE%\pg17\pgsql\bin\psql.exe" -h 127.0.0.1 -p 5432 -U postgres -c "CREATE DATABASE nocobase;"
```

#### 方式二：正式安装

1. 从 https://www.postgresql.org/download/windows/ 下载安装包
2. 安装时设置 superuser 密码为 `postgres`，端口 5432
3. 安装完成后服务自动启动
4. 创建数据库：`psql -U postgres -c "CREATE DATABASE nocobase;"`

### C. NocoBase

```bash
cd nocobase

# 1. 配置环境变量
copy .env.example .env
# 编辑 .env，确认数据库连接信息:
#   DB_DIALECT=postgres
#   DB_HOST=127.0.0.1
#   DB_PORT=5432
#   DB_DATABASE=nocobase
#   DB_USER=postgres
#   DB_PASSWORD=postgres
#   APP_PORT=13000

# 2. 安装依赖 (10-20 分钟)
yarn config set registry https://registry.npmmirror.com
yarn install

# 3. 初始化数据库和管理员
yarn nocobase install

# 4. 启动 (开发模式)
yarn dev
```

验证：浏览器打开 http://127.0.0.1:13000，用 admin@nocobase.com / admin123 登录。

### D. 数据同步

```bash
# 确保 ReefTriage (:8000) 和 NocoBase (:13000) 都在运行

# 1. 创建 reefs collection (首次)
.venv\Scripts\python.exe scripts\setup_nocobase_collection.py

# 2. 同步礁段数据到 NocoBase
.venv\Scripts\python.exe scripts\sync_to_nocobase.py

# 3. 配置 NocoBase 导航菜单
.venv\Scripts\python.exe scripts\setup_nocobase_menu.py
```

### E. Laya/Jev（可选）

不安装 Laya 时系统自动使用 mock 模式，前端可完整演示。

```bash
pip install "laya[serve]"
set LAYA_PORT=5000
set LAYA_PRELOAD=1
laya-serve
```

启动后 ReefTriage 前端右上角徽章从 "Laya: MOCK" 变为 "Laya: LIVE"。

---

## 配置说明

### 端口

| 服务 | 端口 | 可修改 |
|------|------|--------|
| ReefTriage | 8000 | uvicorn --port 参数 |
| NocoBase | 13000 | nocobase/.env 中 APP_PORT |
| PostgreSQL | 5432 | postgresql.conf / 启动参数 |
| Laya | 5000 | LAYA_PORT 环境变量 |

### NocoBase .env 变量

见 `nocobase/.env.example`：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| APP_KEY | 应用加密密钥（必须修改） | 随机生成 |
| APP_PORT | NocoBase 端口 | 13000 |
| DB_DIALECT | 数据库类型 | postgres |
| DB_HOST / DB_PORT | 数据库地址 | 127.0.0.1:5432 |
| DB_DATABASE | 数据库名 | nocobase |
| DB_USER / DB_PASSWORD | 数据库凭据 | postgres / postgres |
| INIT_ROOT_EMAIL | 初始管理员邮箱 | admin@nocobase.com |
| INIT_ROOT_PASSWORD | 初始管理员密码 | admin123 |

### 默认账号

- **NocoBase 管理员**: admin@nocobase.com / admin123
- **PostgreSQL superuser**: postgres / postgres

---

## 服务说明

### 四个服务

| 服务 | 端口 | 健康检查 | 说明 |
|------|------|---------|------|
| ReefTriage | 8000 | `GET /api/health` | FastAPI 后端 + 前端 + 管理面板 |
| NocoBase | 13000 | `GET /api/health` | 后台管理系统 |
| PostgreSQL | 5432 | TCP 连接探测 | NocoBase 数据库 |
| Laya/Jev | 5000 | `GET /api/status` | AI 评分引擎（可选） |

### 统一管理面板

访问 http://127.0.0.1:8000/admin-panel：

- **服务状态总览**：四个服务实时状态，每 30 秒自动刷新
- **API 操控面板**：一键触发重新评分、查看状态、数据同步等
- **可扩展架构**：在 `app/main.py` 添加端点，在 `app/admin/panel.html` 添加按钮

### 单独启动/停止

```bat
REM 仅启动 ReefTriage
run.bat

REM 启动所有服务
start_all.bat

REM 停止所有服务
stop_all.bat
```

---

## 数据同步

### 双向同步机制

```
ReefTriage (:8000)  <--双向同步-->  NocoBase (:13000)
       |                                    |
       ▼                                    ▼
 scored_segments.json                PostgreSQL (:5432)
```

- **ReefTriage → NocoBase**: `scripts/sync_to_nocobase.py`（全量 upsert，幂等）
- **NocoBase → ReefTriage**: `scripts/sync_from_nocobase.py`（仅同步 manual_override=true 的记录）
- 在 NocoBase 修改 score/choice 时自动标记 `manual_override=true`，避免下次 recalc 覆盖

### 同步命令

```bash
# ReefTriage -> NocoBase
.venv\Scripts\python.exe scripts\sync_to_nocobase.py

# NocoBase -> ReefTriage (仅人工修改)
.venv\Scripts\python.exe scripts\sync_from_nocobase.py

# 强制同步所有记录
set SYNC_ALL=1 && .venv\Scripts\python.exe scripts\sync_from_nocobase.py
```

也可通过管理面板的按钮触发，或调用 API：
- `POST /api/sync-to-nocobase`
- `POST /api/sync-from-nocobase`

### ReefTriage API 端点

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | /api/health | 健康检查 |
| GET | /api/stats | 统计数据 |
| GET | /api/segments | 所有礁段列表 |
| GET | /api/segments/{id} | 单个礁段详情 (含 bleaching_probability, mcdm_score, laya_score, final_score, confidence_interval) |
| GET | /api/priority?budget=&unit_cost= | 预算约束下的优先名单 (旧版 top-N) |
| GET | /api/optimize?budget=&unit_cost= | 预算约束整数规划优化 (模型B; 优先读取 Reef Lab 保存的 restoration_plan) |
| GET | /api/segments/{id}/environmental | 该礁段物理化学环境数据 (data/output/environmental/{id}.json) |
| GET | /api/segments/{id}/restoration-cost | 该礁段修复成本配置 (已保存则返回 saved_plan, 否则返回默认值) |
| POST | /api/segments/{id}/restoration-cost | 保存修复成本配置到 scored_segments.json 的 restoration_plan 字段 |
| GET | /api/segments/{id}/bleaching-monitoring | 白化监测数据 (RHI 8 维 + 覆盖度趋势 + 历史白化事件) |
| GET | /api/environmental/summary | 28 个礁段环境摘要 (SST/DHW/pH 均值 + 区域统计) |
| GET | /api/model/weights | 熵权法特征权重 (模型A) |
| GET | /api/model/compare | 新旧模型评分对比 + α |
| GET | /api/model/ml-info | ML白化预测器指标 + 系数 (模型C) |
| POST | /api/recalc | 触发重新评分 |
| PUT | /api/segments/{id} | 更新礁段（修改 score/choice 自动标记 manual_override） |
| POST | /api/sync-to-nocobase | 触发同步到 NocoBase |
| POST | /api/sync-from-nocobase | 触发从 NocoBase 回写 |
| GET | /api/services-status | 聚合四服务状态 |
| GET | /api/laya-status | Laya 服务状态 |
| GET | /admin-panel | 统一管理面板页面 |

---

## NocoBase 管理界面

### 导航菜单

NocoBase 顶部导航已配置两个 Link 菜单项（点击新标签页打开）：
- **ReefTriage 演示** → 管理面板
- **ReefTriage 地图** → 原始地图页面

重新配置菜单：`.venv\Scripts\python.exe scripts/setup_nocobase_menu.py`

### reefs Collection 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| segment_id | string (主键) | 礁段编号 |
| name / name_zh | string | 英文名 / 中文名 |
| lat / lon | float | 经纬度 |
| current_dhw | float | 当前热压力 |
| max_dhw_5yr | float | 5年最大热压力 |
| mean_depth | float | 平均深度 |
| distance_to_dive_site | float | 距潜点距离 |
| connectivity_score | float | 连通性评分 (1-5) |
| rhi_score | float | RHI 评分 (0-100) |
| reef_area | float | 礁区面积 |
| score | integer | 优先级评分 (0-100) |
| choice | select | invest / monitor / deprioritize |
| laya_choice | select | Laya 建议分类 |
| confidence | float | 置信度 |
| model | string | 使用模型 |
| manual_override | boolean | 人工覆盖标记 |

### 内嵌 iframe（手动配置）

NocoBase 内置 `@nocobase/plugin-block-iframe` 插件，如需在 NocoBase 内内嵌页面：

1. 进入 NocoBase → 右上角铅笔图标（UI 编辑器）
2. "+ Add page" → "Page"（Classic page v1）
3. "+ Add block" → 搜索 "Iframe"
4. 填 URL：`http://127.0.0.1:8000/admin-panel` 或 `http://127.0.0.1:8000/`
5. 高度设为 "Full height"
6. 保存退出

---

## 项目结构

```
ReefTriage/
├── app/
│   ├── main.py              # FastAPI 入口 (含同步触发、服务状态等端点)
│   ├── admin/
│   │   └── panel.html       # 统一管理面板 (服务状态 + API 按钮)
│   ├── scoring/
│   │   ├── engine.py        # 评分引擎 + 缓存 + update_segment()
│   │   ├── config.py        # 模型配置 (特征/α/阈值/成本)
│   │   ├── fusion.py        # 三层融合引擎 (MCDM+Laya→final_score)
│   │   ├── mcdm.py          # 模型A: 熵权法 + TOPSIS
│   │   ├── ml_predictor.py  # 模型C: ML白化预测器 (逻辑回归)
│   │   ├── bayesian.py      # 模型D: 贝叶斯蒙特卡洛不确定性
│   │   ├── optimizer.py     # 模型B: 预算约束整数规划
│   │   ├── threshold.py     # ROC/Youden's J 阈值优化
│   │   ├── rubric.py        # Laya v1 rubric (兼容)
│   │   ├── rubric_v2.py     # Laya v2 结构化分维度 rubric
│   │   ├── laya_client.py   # Laya HTTP 客户端 + mock 降级
│   │   ├── data_loader.py   # 数据加载 + 历史DHW提取
│   │   └── rhi.py           # CoralCore RHI 8 参数
│   ├── models/
│   │   └── reef.py          # Pydantic 模型
│   ├── frontend/            # Layui 前端（12 页面 + 管理控制台）
│   │   ├── admin.html      # Layui 综合管理控制台 (顶栏+侧边栏+iframe, 12 菜单 + Product Tour)
│   │   ├── index.html      # 宏观决策地图 (Leaflet + ESRI 卫星/地形切换 + 预算滑块 + i18n)
│   │   ├── filter.html      # 空间筛选 (12 参数实时过滤)
│   │   ├── draw.html       # 区域绘制报告 (leaflet-draw 圈选 → 相交礁段)
│   │   ├── micro.html      # Reef Lab 微观诊断页 (物理/化学/白化/成本 4 面板)
│   │   ├── report.html      # 报告中心 (A4 打印 + PDF 导出)
│   │   ├── services.html   # 服务监控页 (4 服务卡片 + ECharts 仪表盘)
│   │   ├── api.html        # API 控制台 (20+ 端点 + Test 按钮 + JSON 面板)
│   │   ├── model.html      # 模型面板 (三层工作流/权重/对比/ML 指标/回测)
│   │   ├── connectivity.html # 连通性力导向网络图 (ECharts graph 28 节点)
│   │   ├── metadata.html   # 数据来源元数据 (10 数据层溯源)
│   │   ├── feedback.html   # 用户反馈表单 (中英双语)
│   │   ├── settings.html   # 设置页 (语言/底图/参数)
│   │   ├── app.js / style.css
│   │   ├── lib/color_analyzer.js  # 在端 HSV 白化分析
│   │   └── img/coral/      # 4 张珊瑚白化参考图
│   └── ...
├── nocobase/                # NocoBase 后台管理 (子项目)
│   ├── .env.example         # 环境变量模板
│   ├── package.json
│   └── yarn.lock
├── scripts/
│   ├── sync_to_nocobase.py      # ReefTriage -> NocoBase 同步
│   ├── sync_from_nocobase.py    # NocoBase -> ReefTriage 回写
│   ├── setup_nocobase_collection.py  # 创建 reefs collection
│   ├── setup_nocobase_menu.py        # 配置导航菜单
│   ├── setup_nocobase_pages.py       # 创建管理页面
│   ├── setup_nocobase_iframes.py     # 创建 iframe 页面
│   ├── probe_cmems.py                # Copernicus Marine 数据下载与礁段采样
│   └── run_backtest.py              # Walk-forward 回测（种子42，可重复）
├── data/
│   └── output/              # 评分结果 (已提交, 28个礁段)
├── docs/                    # API 文档 / 回测报告 / Copernicus 下载日志 (copernicus_download_log.md)
├── submission/              # 参赛提交材料
├── setup.bat                # 一键部署脚本
├── start_all.bat            # 一键启动所有服务
├── stop_all.bat             # 一键停止所有服务
├── run.bat                  # 仅启动 ReefTriage
├── requirements.txt
├── .gitignore
└── README.md
```

---

## 常见问题

### Q: 端口被占用怎么办？

```bash
# 查看占用端口的进程
netstat -ano | findstr :8000
netstat -ano | findstr :13000

# 结束进程 (替换 PID)
taskkill /PID <PID> /F
```

或修改端口：ReefTriage 用 `--port` 参数，NocoBase 改 `.env` 中 `APP_PORT`。

### Q: Laya 没启动会怎样？

系统自动降级到 mock 模式，前端右上角显示 "Laya: MOCK"。所有功能正常演示，评分使用模拟数据。安装真实 Laya 后自动切换。

### Q: NocoBase 连不上数据库？

1. 确认 PostgreSQL 在运行：`pg_ctl status` 或检查服务
2. 确认 `nocobase/.env` 中数据库连接信息正确
3. 确认 nocobase 数据库已创建：`psql -U postgres -c "\l"`
4. 测试连接：`psql -h 127.0.0.1 -p 5432 -U postgres -d nocobase`

### Q: 数据同步失败？

1. 确认 ReefTriage (:8000) 和 NocoBase (:13000) 都在运行
2. 确认 reefs collection 已创建：运行 `scripts/setup_nocobase_collection.py`
3. 查看同步脚本输出的错误信息
4. NocoBase dev 模式下 API 可能较慢，重试即可

### Q: yarn install 很慢或失败？

```bash
# 切换国内镜像
yarn config set registry https://registry.npmmirror.com
yarn install
```

如仍失败，删除 `nocobase/node_modules` 和 `yarn.lock` 后重试。

### Q: NocoBase 页面空白？

NocoBase dev 模式首次启动需要 1-2 分钟编译。等待编译完成后刷新页面。如仍空白，检查浏览器控制台错误。

### Q: 如何重置 NocoBase？

```bash
# 删除数据库重建
psql -U postgres -c "DROP DATABASE nocobase;"
psql -U postgres -c "CREATE DATABASE nocobase;"
cd nocobase && yarn nocobase install
```

---

## 技术栈

- **后端**: Python 3.14 / FastAPI / Uvicorn（8 个 service 模块，20+ API 端点）
- **评分引擎**: 三层架构 — ML 逻辑回归白化预测（AUC=0.994）+ 贝叶斯蒙特卡洛不确定性（1000 次采样）+ 熵权 TOPSIS（mcdm_score）+ Laya/Jev 结构化判断（laya_score），α=0.30 融合；ROC/Youden's J 阈值优化（invest≥37.6）；PuLP 预算整数规划（贪心回退）
- **宏观前端**: **Layui 2.9.16** + Leaflet + ESRI 卫星图（12 菜单侧边栏，可拖动宽度、收缩展开，localStorage 持久化）+ Intro.js Product Tour 中英双语新手指引
- **微观前端**: Reef Lab `micro.html`（ECharts 图表 + 原生 HSV 白化分析 `lib/color_analyzer.js`，物理/化学/白化监测/成本核算 4 面板，中英双语）
- **连通性模型**: 纯 Python RK4 粒子追踪（HYCOM 1/12° 海流强迫，2240 粒子 × 30 天，定居率 23.6%）
- **管理后台**: NocoBase 2.2.18（Node.js / React / PostgreSQL 17，双向数据同步）
- **AI 评分**: Laya（Jev 开源平替）+ mock 降级；白化图像分析为 HSV 降级算法（NOAA YOLO11n 见 docs/ai_model_research.md）
- **数据**: NOAA CRW v3.1 DHW/SST（5km 逐日，ERDDAP）+ **Copernicus Marine PHY/BGC 真实再分析**（SST/盐度/DO/叶绿素，已替换文献值）+ ETOPO 2022 水深 + OSM 潜点 POI + HYCOM 海流 + CoralCore RHI（8 参数代理）；pH/Ωarag 保留文献值（BGC 无此变量）

---

## 参考

- [NocoBase 文档](https://docs.nocobase.com/)
- [Laya (Jev)](https://github.com/NandhaKishorM/laya)
- [CoralCore RHI](https://github.com/gitdeeper8/coralcore)
- [NOAA Coral Reef Watch](https://coralreefwatch.noaa.gov/)
- [Reef Check Malaysia 2024 白化报告](https://reefcheck.org.my/)
