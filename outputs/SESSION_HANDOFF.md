# 雀神争霸 AI 教练项目交接说明

更新时间：2026-06-22  
项目目录：`C:\Users\Yunis\Documents\Codex\2026-06-22\ni`

这份文档用于切换新会话后快速继续。新会话优先阅读本文，然后查看 `README.md`、`outputs/IMPLEMENTATION_NOTES.md`、`config/regions_1280x720_v2.json`。

## 目标

为《燕云十六声》里的“雀神争霸”做人机练习 AI 教练。

最终使用方式希望是：

1. 用户本机只运行一个极简截图工具。
2. 截图工具不读取游戏进程、不注入、不自动点击，只截取屏幕固定区域并保存图片。
3. Codex/分析器监控 `watch/inbox`。
4. 有新截图后自动分析，输出建议到 `watch/results`。
5. 建议只用于人机练习教学，不用于真人竞技。

## 安全边界

本项目刻意避免做这些事：

- 不读游戏内存
- 不修改游戏文件
- 不注入 DLL
- 不 hook 游戏进程
- 不拦截网络
- 不自动点击/自动出牌
- 不隐藏进程或绕过反作弊

本地运行的轻量截图器只做屏幕截图保存。  
分析器可在 Codex 沙盒中运行；如果分析器不在用户 Windows 环境中运行，游戏一般检测不到分析器本身。  
但本地截图工具仍然是 Windows 上的第三方进程，合规风险不能保证为 0。

## 已整理的雀神争霸规则

规则来源：用户提供的游戏内规则截图。

核心规则：

- 用牌：`1-9万`、`1-9筒`、`1-9条`，共 108 张。
- 可以碰、杠；不能吃。
- 有定缺：选择一门花色作为缺门，摸到这门花色必须打出，对局中不可更改。
- 胡牌时手牌不能超过 2 门花色。
- 允许一炮多响。
- 玩家胡牌后牌局继续，直到 3 人胡牌或摸完所有牌。
- 摸完牌后，未听牌、花猪玩家有惩罚。

番型规则已保存：

- `outputs/yanyun_queshen_rules.json`
- `outputs/yanyun_queshen_rules.schema.json`

重点番型：

- 平胡 x1
- 自摸、根、断幺九、碰碰胡、海底捞月、抢杠胡、杠上开花 x2
- 金钩钓、七对、清一色、幺九 x4
- 将对、龙七对 x8
- 双龙七对、将七对 x16
- 天胡、地胡、三龙七对 x32
- 将双龙七对、十八罗汉 x64
- 将三龙七对 x128

## 当前架构

### 轻量截图器

文件：

- `tools/quick_capture.py`
- `start_quick_capture.ps1`

功能：

- 小窗口置顶。
- 可手动输入 `x/y/width/height`。
- 已新增“手动选区”按钮：全屏半透明遮罩，拖拽选择区域。
- 点击“一键截图”后保存到 `watch/inbox`。

运行：

```powershell
.\start_quick_capture.ps1
```

### 自动监听分析器

文件：

- `src/queshen_agent/watch_analyzer.py`
- `run_watch_analyzer.py`
- `start_watch_analyzer.ps1`

功能：

- 轮询 `watch/inbox`。
- 发现新图片后调用识别器和策略引擎。
- 输出 JSON 结果到 `watch/results`。

运行：

```powershell
.\start_watch_analyzer.ps1
```

### 完整桌面教练原型

文件：

- `run_queshen_agent.py`
- `start_queshen_agent.ps1`
- `src/queshen_agent/ui.py`

功能：

- 深色悬浮 UI。
- 可校准游戏区域、手牌、待打牌、自己碰杠、倒计时、三家弃牌/碰杠区。
- 可一键截图识别。
- 有手动输入兜底。

需要安装：

```powershell
python -m pip install -r requirements.txt
```

依赖包括：`PySide6`、`opencv-python`、`mss`、`Pillow`、`numpy`。

## 已确认的固定分区 v2

用户确认过两点修正：

1. `L` 区不是牌墙/剩余牌，而是“出牌倒计时/方位提示”。20 秒内没出牌会自动选一张出。
2. `C` 自己碰/杠区需要加长，因为可能有很多碰和杠。

已生成并应用：

- 分区图：`outputs/queshen_region_map_v2.png`
- 默认配置：`config/regions_1280x720_v2.json`
- 当前生效配置：`config/regions.json`

应用默认分区命令：

```powershell
.\apply_1280x720_layout.ps1
```

当前 v2 区域大意：

- `A`：自己手牌区
- `B`：新摸/待打牌
- `C`：自己碰/杠区，加长
- `D`：自己定缺/头像分数
- `E/G/I`：左家、上家、右家弃牌区
- `F/H/J`：左家、上家、右家碰/杠区
- `K`：中部公共弃牌/河牌兜底
- `L`：出牌倒计时/方位提示，不识别成牌墙
- `M/N`：玩家信息/定缺/分数辅助

## 核心源码说明

主要模块：

- `src/queshen_agent/models.py`
  - `Region`
  - `RegionConfig`
  - `GameState`
  - `RecommendationResult`
- `src/queshen_agent/recognition.py`
  - 模板识别框架
  - 识别 `hand`、`drawn_tile`、`self_melds`、对手弃牌、对手碰杠
  - 将绝对屏幕坐标转换为截图相对坐标
- `src/queshen_agent/strategy.py`
  - 出牌策略评分
  - 定缺优先
  - 七对/龙七对/将对/将七对/清一色/碰碰胡路线判断
- `src/queshen_agent/shanten.py`
  - 标准胡、七对向听估算
- `src/queshen_agent/rules.py`
  - 读取规则 JSON
- `src/queshen_agent/layout_profiles.py`
  - 加载 `1280x720_v2` 区域配置
- `tools/quick_capture.py`
  - 本地极简截图工具
- `tools/apply_layout_profile.py`
  - 把 v2 默认区域复制到 `config/regions.json`

## 当前验证状态

已运行并通过：

```powershell
$env:PYTHONPATH='src'
python -m unittest discover -s tests
```

当前测试数量：9 个，全部 OK。

已通过编译检查：

```powershell
python -m compileall src tools tests
```

## 当前限制

自动牌面识别还没有真正可用，原因是还没建立模板库。

需要采集：

```text
samples/templates/
  1m/
  2m/
  ...
  9m/
  1p/
  ...
  9p/
  1s/
  ...
  9s/
```

每种牌建议至少 2-5 张清晰小图。

当前分析器如果没有模板，会生成结果文件，但 `hand` 为空，建议为“没有识别到手牌”。这是预期行为。

## 已发生的实测

用户运行过截图工具。

曾捕获到一张截图：

- `watch/inbox/queshen_20260622_143012_280693.png`

但该截图内容是桌面和截图工具窗口，不是游戏画面，因此分析结果为空。

后续需要用户用“手动选区”框住游戏/牌桌区域，再截一张完整雀神争霸画面。

## 新会话继续步骤

1. 先查看本文：

```text
outputs/SESSION_HANDOFF.md
```

2. 查看当前生效分区：

```text
config/regions.json
```

3. 确认用户截图工具已运行，并检查新截图：

```powershell
Get-ChildItem watch\inbox -File | Sort-Object LastWriteTime -Descending | Select-Object -First 5
```

4. 如果有新图，先人工查看：

```text
watch/inbox/<latest>.png
```

5. 如果模板未建立，先人工读图给出建议，同时开始裁剪模板。

6. 如果用户要求自动分析，运行：

```powershell
.\start_watch_analyzer.ps1
```

或对最新图片单次分析：

```powershell
python -c "from pathlib import Path; import sys; sys.path.insert(0,'src'); from queshen_agent.watch_analyzer import analyze_image; latest=max(Path('watch/inbox').glob('*'), key=lambda p:p.stat().st_mtime); print(analyze_image(latest, Path('watch/results')))"
```

## 下一步建议

最合理的下一步是做“模板采集工具”：

- 输入一张完整牌桌截图。
- 按 `regions_1280x720_v2.json` 自动裁出各区域。
- 提供一个小 UI 或脚本，把单张牌框出来并标注为 `1m/2m/.../9s`。
- 保存到 `samples/templates/<tile>/sample_xxx.png`。

之后再改进 `recognition.py` 的切牌算法，让它适应牌的倾斜、旋转和不同桌布亮度。

## 重要提醒

本项目目标是“教学辅助 + 人机练习”。  
不要加入自动点击、自动出牌、绕过检测、隐藏进程、读内存等功能。
