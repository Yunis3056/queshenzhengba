# 雀神争霸 AI 教练 Agent

这是一个 Windows 桌面悬浮 AI 教练原型，用于《燕云十六声》雀神争霸人机练习。

它只给教学建议，不会自动点击游戏。

## 功能

- 桌面框选游戏区域
- 一键截图
- 校准手牌、弃牌、碰杠、定缺区域
- 本地模板识别 `1m-9m`、`1p-9p`、`1s-9s`
- 基于雀神争霸规则推荐出牌
- 保存截图、识别结果和建议，方便复盘
- 手动输入兜底，可在没有模板时测试策略引擎

## 安装

```powershell
python -m pip install -r requirements.txt
```

## 启动桌面版

推荐：

```powershell
.\start_queshen_agent.ps1
```

或直接：

```powershell
python -m src.queshen_agent.app
```

如果你习惯设置 `PYTHONPATH`：

```powershell
$env:PYTHONPATH="src"
python -m queshen_agent.app
```

## 命令行测试

```powershell
$env:PYTHONPATH="src"
python -m queshen_agent.cli --missing-suit p --hand 1m 2m 3m 5m 5m 8m 8m 2s 3s 4s 9p
```

## 轻量截图器 + 自动监听分析

如果你不想在游戏旁边运行完整悬浮教练，可以只在本机运行一个轻量截图器：

```powershell
.\start_quick_capture.ps1
```

截图会保存到：

```text
watch/inbox
```

另开一个终端运行监听分析器：

```powershell
.\start_watch_analyzer.ps1
```

监听器发现 `watch/inbox` 有新截图后，会自动分析并把结果保存到：

```text
watch/results
```

这个模式下，本机截图器只做屏幕截图，不读取游戏进程、不修改游戏、不自动点击。

现在也可以只运行截图器一个窗口：它会在窗口下方显示 `实时建议`，不需要另开分析器终端。这个模式适合手机投屏到电脑后框选投屏区域。

### 连续截帧模式

截图器也支持连续截帧。默认每 1 秒截取一次当前固定区域，覆盖保存到：

```text
watch/frames/latest.png
```

启动截图器后，先框选区域，再点 `开始连续截帧`。窗口下方会直接显示最新分析结果。

如需不打开截图器、只运行独立分析器，可以另开一个终端运行：

```powershell
.\start_frame_analyzer.ps1
```

分析器会监听 `watch/frames/latest.png`，只分析最新画面；如果分析速度赶不上截帧速度，会跳过旧帧，避免越积越慢。最新结果会额外覆盖写入：

```text
watch/results/latest_result.json
watch/results/latest_result.txt
```

实时模式默认不保存每一帧的历史结果，只覆盖这两个最新结果文件。需要保留历史时，把 `config/frame_analyzer.json` 里的 `keep_result_history` 改成 `true`。

连续截帧默认配置在 `config/quick_capture.json`：

```json
{
  "frame_dir": "watch/frames",
  "frame_interval_seconds": 1.0,
  "latest_frame_name": "latest.png",
  "keep_frame_history": false,
  "history_dir": "watch/frames/history"
}
```

分析器默认配置在 `config/frame_analyzer.json`，可调整轮询间隔、结果目录和 latest result 路径。

## 模板采集

先用截图器保存一张完整牌桌截图，然后启动模板采集工具：

```powershell
.\start_template_collector.ps1
```

在窗口里拖拽框住单张牌，选择牌名后保存，工具会写入：

```text
samples/templates/<牌名>/
```

也可以先按当前 `config/regions.json` 批量导出候选小图和区域预览：

```powershell
.\start_template_collector.ps1 --export-candidates
```

候选图会保存到 `samples/template_candidates`，确认牌名后再放入对应模板目录。

## 第一次使用流程

1. 启动桌面版。
2. 点击 `选择游戏区域`，框选整个游戏窗口或雀神争霸画面。
3. 分别点击校准按钮，框选：
   - 自己手牌区
   - 自己碰杠区
   - 左/上/右三家弃牌区
   - 左/上/右三家碰杠区
   - 定缺提示区
4. 采集模板：运行 `.\start_template_collector.ps1` 裁剪单张牌，或在 `samples/templates` 下建立 `1m` 到 `9s` 子目录，每个目录放对应牌的 PNG 小图。
5. 点击 `一键截图识别`。

## 模板目录结构

```text
samples/templates/
  1m/
    sample_001.png
  2m/
  ...
  9s/
```

牌码说明：

- `m` = 万
- `p` = 筒
- `s` = 条

## 当前限制

- 模板识别需要先采集牌面样本。
- 若游戏 UI 缩放、分辨率或窗口大小变化，需要重新校准区域。
- 定缺图标识别暂留为校准区数据入口，第一版建议手动确认定缺或后续补模板。
- 低置信度时应先人工修正，不建议直接采纳。

## 固定分区参考

- 1280x720 分区图 v2：[outputs/queshen_region_map_v2.png](outputs/queshen_region_map_v2.png)
- 1280x720 默认区域配置 v2：[config/regions_1280x720_v2.json](config/regions_1280x720_v2.json)

注意：`turn_timer` 是出牌倒计时，不是牌墙；`self_melds` 已加长，用来覆盖多组碰/杠。

应用这套默认分区：

```powershell
.\apply_1280x720_layout.ps1
```

应用后会写入 `config/regions.json`，监听分析器会按这套区域裁剪。

## 验证

```powershell
$env:PYTHONPATH="src"
python -m unittest discover -s tests
```
