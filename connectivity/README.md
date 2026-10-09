# ReefTriage — Coral Larval Connectivity Module

生物物理珊瑚幼虫连通性模型，为 Jev 评分引擎提供 `larval_input` / `larval_output` / `connectivity_score` 特征。

## 方案选型报告

| 项目 | 结果 |
|---|---|
| Python 版本 | 3.14.7 (Windows) |
| OceanParcels 安装 | **失败**（`pip install oceanparcels` 无可用发行版；`pip install parcels` 构建 healpix 失败，无 Python 3.14 wheel） |
| 实际采用方案 | **纯 Python RK4 粒子追踪器**（自实现双线性空间插值 + 线性时间插值） |
| 流速数据源 | HYCOM GLBy0.08 expt_93.0 uv3z（全球 1/12° 海洋分析），通过 THREDDS NCSS 子集下载 |
| 数据时间窗口 | 2024-08-06 00:00 UTC → 2024-09-05 09:00 UTC（30 天，244 个 3 小时间步） |
| 深度层 | 0 m（表层）+ 15 m（深层层），用于昼夜垂直迁移 |
| 区域 | 经度 118.0–119.76°E，纬度 4.0–6.52°N |

## 模型配置

| 参数 | 值 | 说明 |
|---|---|---|
| 礁段数 | 28 | 读取 `data/output/reef_segments.geojson`（数据管线产出） |
| 每礁粒子数 | 80 | 共 2240 个粒子 |
| 模拟时长 | 30 天 | 720 个 1 小时时间步 |
| 日死亡率 | 0.05 | 指数衰减，文献常见范围 0.03–0.10 |
| 定居半径 | 5 km | 适配 1/12° (~9 km) 模型分辨率 |
| 发育期 (competency) | 5 天 | 前 5 天不计定居，避免释放点误判 |
| 垂直迁移 | 昼夜切换 | 当地时间 06:00–18:00（UTC+8）在 15 m，夜间在 0 m |
| 积分器 | RK4（4 阶 Runge-Kutta） | 向量化解，所有粒子并行推进 |

## 输出文件

```
connectivity/
├── data/
│   └── hycom_uv_30d.nc          # 下载的 HYCOM u/v 数据 (2.9 MB)
├── scripts/
│   ├── download_hycom.py        # NCSS 子集下载脚本
│   ├── reef_definitions.py       # 礁段定义（读 geojson 或占位坐标）
│   ├── run_connectivity.py       # 主粒子追踪模型
│   └── plot_connectivity.py      # 可视化
└── output/
    ├── connectivity_matrix.csv       # 28×28 连通性矩阵 C[i][j]
    ├── reef_connectivity_features.csv # 每礁段特征（Jev 引擎输入）
    ├── particle_tracks.npz           # 粒子终点（供绘图）
    ├── particle_tracks.png           # 粒子终点散点图
    ├── connectivity_heatmap.png      # 连通性矩阵热图
    └── run_log.txt                   # 运行日志与参数记录
```

## 运行结果摘要

| 指标 | 值 |
|---|---|
| 释放粒子总数 | 2240 |
| 成功定居 | 528（23.6%） |
| 死亡/流出域 | 1695（75.7%） |
| 结束时仍在漂移 | 17（0.8%） |
| 矩阵 C 范围 | [0.000, 0.813]，均值 0.008 |
| 平均自我滞留 | 0.000 |
| 平均幼虫输出 | 0.236 |
| 平均幼虫输入 | 0.236 |

### 连通性结构解读

- **源礁段（高输出）**：Sipadan/Mabul/Kapalai 群（礁 0–8），幼虫输出比例 0.36–0.81，是幼虫净输出者。
- **汇礁段（高输入）**：Timbalan Reef（礁 25）接收了 511 个定居粒子，是主要的幼虫汇。
- **Bodgaya Reef North（礁 9）**接收 17 个来自 Tetagan Reef（礁 15）的幼虫。
- 其余礁段在本 30 天窗口内无显著连通（幼虫随沿岸流流出域）。

## 生物学假设与局限（必须声明）

1. **死亡率参数**：日死亡率 0.05 为常数，未考虑年龄依赖、捕食或资源限制。30 天累积存活约 22%。
2. **垂直迁移简化**：仅两层（0 m / 15 m）昼夜切换，未模拟连续垂直迁移或物种差异。
3. **无行为差异**：除垂直迁移外，未模拟幼虫的深度选择、趋化性或游泳行为。
4. **分辨率限制**：HYCOM 1/12°（~9 km）无法解析岛礁尺度的涡旋和礁后涡流，可能高估扩散、低估滞留。
5. **礁段简化**：用多边形质心 + 5 km 圆形定居半径，未使用真实多边形边界。
6. **时间窗口单一**：仅 2024 年 8–9 月一个 30 天窗口，未覆盖季节变化或年际变化。
7. **无物种差异**：所有幼虫视为同质，未区分珊瑚物种的浮游期（PDI 20–40 天）差异。
8. **自我滞留为零**：因 5 天发育期 + 强流 (~0.3–0.8 m/s)，幼虫在可定居前已漂离原礁，属粗分辨率模型的已知局限。

## 复现方式

```powershell
cd connectivity/scripts
python download_hycom.py      # 下载 HYCOM 数据（约 2.9 MB）
python run_connectivity.py    # 运行粒子追踪（约 2 秒）
python plot_connectivity.py   # 生成图表
```

随机种子固定为 42，结果可复现。
