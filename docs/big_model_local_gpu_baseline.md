# 本机大模型性能基线与已知陷阱

- 分支：`friend-integ`（Jetson AGX Orin，集成 CUDA GPU）
- 记录日期：2026-10-13
- 适用范围：`openpilot/selfdrive/modeld/` 下的模型运行与编译

本文档里的数字全部是 **2026-10-13 当天在 TGC 大模型上的一次实测**，换模型后必须重测。
真正可复用的是**测量口径**和**陷阱**，不是数字。

---

## 一、性能基线

### 1.1 引擎本体（停栈、独占 GPU）

`trtexec --loadEngine=<plan> --iterations=400 --warmUp=200 --avgRuns=400`

| 大模型 | GPU latency | 吞吐 |
|---|---|---|
| TGC（`big_driving_supercombo.onnx`，1791d594） | 11.87 ms | **83.93 qps** |
| BigCombo（`big_driving_supercombo.onnx`，1791d594 的旧编译） | 21.95 ms | **45.45 qps** |

TGC 比 BigCombo 快 **1.85 倍**，尽管它的输出维度大 7 倍（18452 vs 2580）、hidden_state 宽 32 倍
（16384 vs 512）。

### 1.2 经 modeld（TGC，单实例 25 秒采样）

```
road / wide 相机     20.00 Hz
模型输出              20.00 Hz
CAN                  53.48 Hz

推理耗时   avg 22.50 ms   p50 21.86   p90 26.08   p99 36.63   max 49.44
```

### 1.3 分层耗时（TGC，`modeld_bigcombo.ModelState.run` 单点采样）

```
TOTAL        21.67 ms
├─ runner     16.64 ms  77%   TRT 调用（含 uint8→fp16 转换 + H2D）
├─ temporal    2.72 ms  13%   features_buffer 整体移位
├─ parse       0.54 ms   2%   18452 维按 output_slices 切片 + Parser
├─ inputs      0.12 ms   1%
└─ warp+d2h    1.65 ms   8%   残差 = TOTAL - 上述各项
```

对照引擎本体的 11.87 ms，**modeld 侧多出约 10 ms，其中约 4.8 ms 是 runner 相对引擎 GPU 时间的额外开销**
（ctypes 传参 + fp16 转换 + H2D），已知其中 0.79 ms 是 uint8→fp16 转换。

**这 ~10 ms 基本是管线固定成本，与具体模型无关**（只有 `temporal` 和 `parse` 随模型宽度变化）。
换模型后可以先用「引擎时间 + 10 ms」预估端到端耗时。

### 1.4 20 Hz 是调度上限，不是模型能力

`openpilot/selfdrive/modeld/constants.py`：

```python
MODEL_RUN_FREQ = 20        # 每 50 ms 取一次结果发出去
MODEL_CONTEXT_FREQ = 5
```

引擎有 4.2 倍余量但从未用上。**看到 20 fps 不要判断成「模型慢」**——那是调度值。
改动 `MODEL_RUN_FREQ` 会牵连 controls / planner / selfdrived 的时序假设，不是改个数的事。

---

## 二、测量时必须分开的三个口径

混在一起会得出「引擎 84 fps 但系统只有 44 fps」这种无法解释的结论。

| 口径 | 怎么测 | 用途 |
|---|---|---|
| 引擎本体 | `trtexec --loadEngine`，**必须停栈** | 判断这张图本身行不行 |
| 经 modeld | 订阅 `modelV2`，读 `modelExecutionTime` | 管线的真实代价 |
| 实际输出 | `modelV2` 到达频率 | 被 `MODEL_RUN_FREQ` 卡住的上限 |

停栈时至少要杀掉 manager（`python3 ./manager.py`，**cmdline 不含 openpilot**）和全部
setproctitle 守护进程，见下节。

---

## 三、已知陷阱

### 3.1 setproctitle 守护进程杀不掉 —— 会毁掉所有性能测量

`modeld` 等守护进程启动时会 `setproctitle`，cmdline 被改写成：

```
selfdrive.modeld.modeld_bigcombo
openpilot.tools.webcam.camerad
selfdrive.selfdrive.ui.ui
```

**这些名字里不含 `openpilot` 字样。** 用 `pgrep -f "openpilot"` 清理时：

- 带 `openpilot.` 的（camerad、ui）能杀到
- 被改过名的一个都杀不到

manager 被 kill 后子进程会被 re-parent 到 `systemd --user` 存活。下次启动 manager 又拉起新的
modeld，于是**两个 modeld 抢同一路 visionipc**，谁也跑不满。

典型症状：被抢占的那个进程 `run()` 只耗 0.5 ms（大部分时间 `prepare_only` 早返回），
而消息里的 `modelExecutionTime` 是 20 ms——两个数都对，但测的不是同一个进程。

**排查时先确认实例数：**

```bash
ps -eo pid,ppid,args | grep -E "[s]elfdrive\.|[o]penpilot\.|[m]anager\.py|[w]ebcam\."
```

正确的清理 pattern 集合：

```bash
[m]anager\.py   [l]aunch_chffrplus\.sh   [s]elfdrive\.[a-z]   [o]penpilot\.selfdrive\.
[o]penpilot\.system\.   [o]penpilot\.tools\.webcam\.camerad   [c]arrot_web_watchdog
[o]openpilot/selfdrive/carrot/recovery/server\.py
```

顺序有讲究：**先杀 manager**（否则它不停重生子进程），再杀子进程，**循环三轮**。
watchdog 和 recovery server 挂在 systemd 下，不在进程树里，必须单独点名。

`launch_openpilot.sh` 已内置这套清理，启动时会自动执行并打印清理结果。

### 3.2 大模型的 `img` 输入 dtype 因模型而异

读引擎绑定才能确定，别猜：

```python
m = TensorRTModel("<plan>")
print(m.input_dtypes)   # numpy dtype
```

| 大模型 | `img` / `big_img` | 说明 |
|---|---|---|
| BigCombo | **uint8** | warp 输出直接进引擎，无转换 |
| TGC | **float16** | CPU 上多一道 uint8→fp16，且图像带宽翻倍（393 KB → 786 KB ×2） |

TGC 已知代价：**0.79 ms/帧**。要消除需改 ONNX 图（输入层加 Cast）再重编 plan。

### 3.3 只有 ONNX 的目录不算可用的 merged bundle

`bundle_mode()` 判定 merged 需要 **metadata 和 engine 同时存在**：

```python
MERGED_REQUIRED_FILES = ("big_driving_supercombo_metadata.pkl",)
MERGED_ENGINE = "driving_supercombo_fp16.plan"
```

只有 `big_driving_supercombo.onnx` 的目录（如未编译的 CTM_V3）**不可用**，网页不应列出，
`api_select` 应拒绝。缺这一步会重演「modeld 无限崩溃重启」。

### 3.4 `.active_model` 和 `.active_big_model` 是两套东西

| 文件 | 含义 | 谁读 |
|---|---|---|
| `models/.small_order`（及 legacy `.active_model`） | **小模型 / 回退**顺序 | `model_bundle.active_name()` |
| `models/.active_big_model` | 选中的 fused 大模型 | `model_bundle.active_big_name()` |

把大模型名写进小模型列表 → `ModelState` 去找 `driving_vision_metadata.pkl` → `FileNotFoundError`
→ manager 反复重启。**实测踩过 452 次崩溃。**

`write_small_order()` 内部已按 split bundle 过滤，`write_selection()` / `write_big_selection()`
会对非法名字抛 `ValueError`——校验在写入边界，不要在调用方各自重复判断。

### 3.5 大模型加载失败会自动标记并回落

`modeld.py` 的 `_load_usable_model()` 按 `read_small_order()` 顺序试，全失败则记日志后退避重试
（`MODEL_RETRY_INTERVAL`，默认 10 s）而**不 raise**——raise 会让 manager 重启进同一个死循环。

大模型侧对应 `model_bundle.mark_big_failed()`：写入 `.big_model_failed` 后 `active_big_name()`
返回 None，小模型接管，直到用户重新选择大模型才清除标记。

**排查时先看这两个标记文件**，它们记录了失败原因：

```bash
cat openpilot/selfdrive/modeld/models/.big_model_failed
```

### 3.6 eGPU 相关参数的三种语义

`UsbGpuActive` 曾经被误用。它只表示「**大模型跑在 USB eGPU 上**」，本机没有 USB eGPU，
恒为 `False` 是正确的。不要为了让 UI 变绿去改它。

| 参数 | 语义 | 本机值 |
|---|---|---|
| `UsbGpuPresent` | GPU 后端可用 | True |
| `UsbGpuCompiled` | 大模型编译产物存在 | True |
| `UsbGpuActive` | 大模型跑在 **USB eGPU** 上 | False（正确） |
| `BigModelActive` | **大模型正在运行** | True |
| `GpuInferenceActive` | GPU 正在做推理 | True |

HUD 角标的状态优先级：`startup_failed → loading → compile_pending → active → not_compiled → ready`，
绿色（active）由 `usbgpu_active or gpu_inference_active or big_model_active` 任一为真触发。

---

## 四、接新大模型的流程

```
1. 读 metadata → 确认 IO 签名（重点：img 是 uint8 还是 fp16）
2. trtexec 编 plan
3. trtexec 独立测引擎 → 得到这张图的基线 qps（必须停栈）
4. 从 ONNX 图确认时序语义（Concat/Gather 的 axis）
5. 放进 models/<Name>/，确认 bundle_mode 认它（metadata + engine 都要在）
6. 起栈，确认 modeld 实例数为 1，再测端到端
7. 与第 3 步基线比对
```

第 7 步的判断能力：

- 引擎慢 → 模型本身的问题，换更小的模型或优化图
- 引擎快、端到端慢 → **问题在 I/O 管线**（warp / d2h / dtype 转换 / temporal），跟模型无关

### 4.1 时序语义必须从图里确认

`features_buffer` 的形状差异很大：

| 大模型 | `features_buffer` | `desire_pulse` | 输出 |
|---|---|---|---|
| BigCombo | (1, 24, 512) | (1, 25, 8) | (1, 2580) |
| TGC | (1, **32, 32**, 512) | (1, 33, 8) | (1, 18452) |

TGC 的 `(1, 32, 32, 512)` 里，第 1 维是不是时间槽，**不能靠猜**。已从 ONNX 图确认：

```
消费 features_buffer 的唯一节点:  Concat(axis=1)
消费 desire_pulse 的节点:          Gather(axis=1)
```

即 axis 1 是时间轴，`fb_shape[1]` 为槽数。`modeld_bigcombo` 已按 metadata 驱动
（`feature_len = prod(fb_shape[2:])`，`full_history_buffer_len = desire_slots * temporal_skip`），
换新模型时这些会自动适配，但**轴序语义仍需逐图确认**。

---

## 五、可优化的点（尚未实施）

按性价比排序。均**不影响当前 20 Hz 输出**，只在提高 `MODEL_RUN_FREQ` 后才兑现。

| 项 | 预计收益 | 风险 |
|---|---|---|
| `temporal` 改环形缓冲区 | 2.72 ms | 低（纯数组搬运，不碰 GPU） |
| TGC 的 `img` 改 uint8 | 0.79 ms + 图像带宽减半 | 需改 ONNX 图并重编 plan |
| 修零拷贝（跳过 D2H→H2D 往返） | runner 开销的大部分 | 中偏高，要重验零拷贝链 |
| CUDA Graph | 部分 runner 开销 | 中，要重验 context 切换 |

理论下限约 **14 ms / 71 fps**（引擎 11.87 + warp/d2h 1.65 + parse 0.54 + inputs 0.12）。
