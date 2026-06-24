# 雀神争霸 AI 教练 — 代码审查与交接文档

> 单文件交接。新对话只需先读本文件即可获得全部上下文：项目背景、规则要点、代码地图、
> 审查发现（含优先级）、待办与开放问题。生成于 2026-06-24，基于 Opus 4.8 的一次完整代码审查。

---

## 0. 一句话现状

代码整体质量良好（31 个测试全过、向听算法对拍零误差），但存在一个**阻碍实战可用的核心缺陷**：
**玩家碰/杠（副露）之后，策略完全不再给出出牌建议**。这是本次审查最该优先修复的问题（P1）。

> **更新（2026-06-24）：P1–P7 全部处理完毕。** 全量测试 43 例通过（新增 `tests/test_furo.py`、
> `tests/test_vision_format.py` 及 strategy 的 P3 用例）。逐项结果见下方各条 ✅ 标注。
> P1 详细设计见 `docs/superpowers/specs/2026-06-24-furo-discard-recovery-design.md`。

---

## 1. 项目背景

- **是什么**：Windows 桌面 AI 教练原型，面向《燕云十六声》"雀神争霸"人机练习模式。
- **硬边界（必须保持）**：只从屏幕像素读图给**教学建议**；不读游戏内存、不改游戏、不自动点击。
- **语言约定**：UI 文案 / 推荐理由 / 多数 config key 为中文；代码标识符为英文。
- **两种运行模式**（都只给建议）：
  1. 完整桌面叠加层：`python -m queshen_agent.app` → `ui.py`（PySide6），用于标定区域 + 一次性截图→建议。
  2. 轻量截图+分析：`tools/quick_capture.py`（tkinter）抓屏到 `watch/`，`watch_analyzer.py` 轮询分析。
     适合"手机投屏到 PC"。`quick_capture` 故意复用 `watch_analyzer` 的私有函数，后者是事实上的共享分析库。
- **导入根是 `src`**：`PYTHONPATH=src`，或用 `run_*.py` / `.ps1` 启动器。
- 无构建步骤、无 linter。

### 运行与测试
```bash
python -m pip install -r requirements.txt          # PySide6, opencv-python, mss, Pillow, numpy

# 测试
PYTHONPATH=src python -m unittest discover -s tests
PYTHONPATH=src python -m unittest tests.test_strategy

# 不依赖截图的最快反馈：直接喂手牌给策略引擎
PYTHONPATH=src python -m queshen_agent.cli --missing-suit p --hand 1m 2m 3m 5m 5m 8m 8m 2s 3s 4s 9p
```
> 注意：本机 `git` 当前报 `not a git repository`（尽管 `.git/` 存在），提交前需排查仓库 ownership/损坏（见 P7）。

---

## 2. 规则要点（已据 `outputs/yanyun_queshen_rules.json` 核对）

**这是游戏内自定义规则，不是四川麻将。** 复核代码时务必以此为准：

- 牌山：108 张 = 万(m)/筒(p)/条(s) × 1-9 × 4 张；**无字牌/风牌/三元牌**。
- 副露：**不能吃（can_chi=false）；可碰（peng）、可杠（gang）**。
- 定缺（dingque）：选 1 门为缺；**摸到缺门必打**；对局中不可改；胡牌时手牌**≤ 2 门花色**。
- 「将」在本规则 = 序数 **2、5、8**。
- 罚则：未听牌罚、花猪罚（仍持缺门牌）。
- 番型（倍率，乘法叠加，`excludes` 互斥）：
  - 七对系（**均要求门清 `concealed_only`，不能碰杠**）：七对 ×4、龙七对 ×8、双龙七对 ×16、
    三龙七对 ×32、将七对 ×16、将双龙七对 ×64、将三龙七对 ×128。
    **龙七对：1 组杠（4 张）按"两对"计入七对结构**——这是 `seven_pairs_shanten` 把 `count//2`
    当对子数的规则依据，**不是 bug**。
  - 标准型：平胡 ×1、碰碰胡 ×2、将对 ×8（全 2/5/8 的碰碰胡，**注明可碰杠**）、幺九 ×4
    （每个面子含 1 或 9）、断幺九 ×2（无 1/9）。
  - 依赖副露的牌型：金钩钓 ×4（其他牌全碰杠、手里仅 1 张单钓）、十八罗汉 ×64（金钩钓 + 4 杠）。
  - 一色：清一色 ×4。
  - 时机番：自摸 ×2、天胡 ×32、地胡 ×32、海底捞月 ×2、抢杠胡 ×2、杠上开花 ×2。
  - 根 ×2：手牌 4 张一样为一根；高阶七对番型已 `excludes: gen` 时不重复计。
- Agent 决策优先级（规则文件 `agent_guidance`）：先打缺门 → 判断更接近哪种胡型 →
  2/5/8 与对子多则评将对/将七对 → 对子多且无碰杠则评七对/龙七对 → 单花色占优则评清一色。

---

## 3. 代码地图（`src/queshen_agent/`，约 2700 行）

`screenshot → recognition → GameState → strategy → RecommendationResult`

| 模块 | 职责 | 关键点 |
|---|---|---|
| `tile.py` | 词汇层：27 牌、花色/牌别名归一化、`counts_to_27` | 下游全部依赖其归一化，改动需谨慎 |
| `models.py` | 数据契约 dataclass（`slots=True`）+ `from_dict`/`to_dict` | `GameState.all_hand_tiles()` 只含暗手+摸牌，**不含 self_melds**（P1 根因之一） |
| `recognition.py` | OpenCV 模板匹配（`TM_CCOEFF_NORMED`） | 裁剪→Otsu 分割→匹配；低于 threshold(0.78) 的牌记为 `X` 并进 `uncertain_tiles` |
| `shanten.py` | 标准向听（记忆化递归）+ 七对变体；`best_shanten`=两者 min | 仅 27 牌空间、无字牌；**不处理已成型副露** |
| `strategy.py` | 纯函数、无 I/O。`recommend_discard` / `analyze_routes` / `recommend_missing_suit` | 最重测试模块；保持确定性、无副作用 |
| `rules.py` | 加载 `outputs/yanyun_queshen_rules.json` → `RuleSet` | |
| `paths.py` | 所有文件路径的单一真源（`PROJECT_ROOT = parents[2]`） | 新路径加这里，别硬编码 |
| `config.py` | 读写 `config/regions.json` | |
| `watch_analyzer.py` | 两个监视循环 + 结果落盘（local/vision 双路） | `watch()`（目录收件箱）/ `watch_latest_frame()`（连续抓帧） |
| `vision_analyzer.py` | 可选 OpenAI 视觉回退（`/v1/responses`，JSON schema） | 默认关闭；需 `config/vision_analyzer.json` `enabled:true` + 环境变量 API key |
| `ui.py` / `app.py` | PySide6 叠加层 | |
| `screenshot.py` | mss 抓屏 + Pillow 裁剪 | |
| `template_collection.py` + `tools/*` | 模板采集/标注工作流 | 若 `samples/templates` 为空，识别置信度=0、策略拒答（预期行为，非 bug） |

**坐标约定（易错）**：`RegionConfig` 所有区域存**绝对**屏幕坐标；`recognition.py` 用
`_relative_region` 相对 `game_area` rebase 后再裁剪。新增区域存绝对坐标、让识别层去 rebase，别预先相减。

---

## 4. 审查发现（按优先级）

### 🔴 P1 — 副露（碰/杠）后策略完全失效【核心缺陷，优先修】
- **现象**：碰/杠后 `recommend_discard` 以 `hand_count_unstable` 拒绝建议。**已实测确认**
  （碰一组、暗手 11 张 → `recommended_discard=None`）。
- **根因**：
  - `strategy.py:42` 要求 `len(tiles) in (13,14)`。
  - `models.py:190` `all_hand_tiles()` 只算暗手+摸牌，碰后剩 10/11 张 → 永远落入"非完整 13/14"分支。
  - `shanten.py` 与 `_score_discard` 未把副露当作完成面子计入向听。
- **为何严重**：本规则可碰可杠，且金钩钓/十八罗汉/将对/碰碰胡等番型**必须依赖副露**。
  恰在最需建议的碰杠流局面下教练失声。
- **修复方向**：
  1. 期望暗手张数改为随副露数浮动（碰每组 -3；杠的张数/补张需另外确认，见下方开放问题）。
  2. 向听计算把 `self_melds` 折算为已完成面子，按 `4 - len(self_melds)` 调整面子预算。
  3. 七对系要求门清——有副露时七对路线应排除（现有 `not self_melds` 守卫方向正确，保留）。

### 🟡 P2 — `recognition_confidence` 可能虚高
- `recognition.py:97-100`：`min` 只取**已过滤为 ≥threshold** 的牌，低置信度牌已被剔成 `X`，
  不参与计算。半数手牌为 `X` 时上报置信度仍可能 0.95。
- 危害有限（见到 `X` 会拒答兜底），但展示给用户的"识别置信度"有误导性。
- 修复：低置信牌按原始置信度纳入 min，或文本并列显示"X 牌数"。

### 🟡 P3 — `winning_hand_max_suit_count: 2` 未主动引导
- 策略只有"清一色"占优加成，对"持 3 门花色"无收敛倾向。多数情况被定缺机制自然覆盖
  （摸缺门必打→压到 2 门）；仅在**未定缺**且三门均布的早期略缺主动减门倾向。优先级低。

### 🟢 P4 — 视觉输出与本地输出牌面表示不一致
- `vision_analyzer.py:217` 用原始牌码（`7m`），本地路径用 `tile_label`（`七万`）。
  同一 `latest_result.txt` 来源不同写法不同。修复：视觉路径也走 `tile_label` 归一化。

### 🟢 P5 — 补注释：七对把"杠"算两对是规则本意
- `shanten.py:8-13` `seven_pairs_shanten` 用 `count//2`，`4+4+4+2` 判为七对和了（`-1`）。
  **正确且符合龙七对规则**（`quad_group_count`）。仅建议补一行注释，避免后人误"修坏"。

### 🟢 P6 — 13 张手牌也会算"弃一张后向听"
- `_score_discard` 对 13 张（无摸牌）算 `best_shanten(remaining)`（12 张），语义略异常。
  作为"保留价值"启发式可用；严格说 13 张应只分析不催打。优先级低。

### ⚙️ P7 — `git` 仓库不可用
- `git status` 报 `not a git repository`。提交前排查 ownership/损坏。

---

## 5. 已验证为「正确 / 非问题」的点（避免新对话重复怀疑）

- ✅ `standard_shanten`：2 万组随机 13/14 张牌面与暴力参考实现**零误差**。
- ✅ 七对 `count//2` 计对子数：符合龙七对规则（见 P5），勿改。
- ✅ 七对/将七对等路线的 `not game_state.self_melds` 守卫：符合"门清"要求。
- ✅ 「将」用 (2,5,8)：与规则一致。
- ✅ 缺门 `+10000` 强制弃牌：对应花猪罚机制，正确。
- ✅ `samples/templates` 为空→置信度 0、策略拒答：预期行为，非 bug。
- ✅ 31 个单元测试全部通过。

---

## 6. 开放问题（修 P1 前需先定，规则文件未写明）

1. **明杠 vs 暗杠 vs 补杠** 对暗手张数与"何时该提示打牌"的影响？杠后会补摸一张，
   补张帧如何对应到截图时机？
2. 识别区 `self_melds` 里**一组杠显示 4 张还是 3 张**？（决定张数校验与向听折算的写法）
3. P1 修复后，希望对**有副露的局面**给到何种程度的建议——仅"打哪张"，还是也提示
   金钩钓/碰碰胡/将对等路线判断？

> 建议：新对话先回答上述 3 点，再动手改 `models.all_hand_tiles`/`strategy.recommend_discard`
> 的张数校验与 `shanten` 的面子预算。改完务必跑 `PYTHONPATH=src python -m unittest discover -s tests`
> 并补针对副露场景的新测试。

---

## 7. 建议处理顺序

1. **P1**（副露）——唯一阻碍实战可用，先答开放问题再动手。
2. P2 / P4 ——信息展示准确性，成本低，顺手修。
3. P5 ——补注释，几分钟。
4. P3 / P6 ——体验打磨，可延后。
5. P7 ——提交前处理。

---

## 8. 处理结果一览（2026-06-24 收尾）

| 项 | 结果 | 改动落点 |
|---|---|---|
| P1 副露后失声 | ✅ 已修复 | `models.expected_hand_counts`/`meld_count`、`shanten.melds_done`、`strategy` 张数校验+折算、`recognition` 张数校验 |
| P2 置信度虚高 | ✅ 已修复 | `recognition.py`：min 纳入低置信(原始)牌 |
| P3 ≤2 门收敛 | ✅ 已修复 | `strategy._score_discard`：未定缺且三门均布时弱门 +10 |
| P4 视觉牌面不一致 | ✅ 已修复 | `vision_analyzer._format_human_text`：走 `tile_label`/`suit_label`，非法牌码回退 |
| P5 七对杠算两对 | ✅ 已补注释 | `shanten.seven_pairs_shanten` |
| P6 13 张算弃后向听 | ✅ 已补注释 | `strategy._score_discard`：保留价值启发式、有意为之（测试锁定） |
| P7 git 不可用 | ✅ 已确认可用 | 本会话 `rev-parse/status/log/diff` 均正常，不再复现 |

测试：全量 `PYTHONPATH=src python -m unittest discover -s tests` → 43 例通过。
新增 `tests/test_furo.py`（副露场景 9 例）、`tests/test_vision_format.py`（P4 2 例）、`test_strategy` P3 1 例。
