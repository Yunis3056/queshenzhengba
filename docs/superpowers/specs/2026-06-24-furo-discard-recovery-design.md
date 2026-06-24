# P1 修复设计 — 副露（碰/杠）后恢复出牌建议

> 设计文档。生成于 2026-06-24，对应 `docs/code-review-2026-06-24.md` 的 P1。
> 范围：**最小修复** —— 只恢复副露后的出牌建议，不新增副露专属番型路线。
>
> **状态：已实现并验证（2026-06-24）。** 五处根因全部修复；新增 `tests/test_furo.py`（9 例），
> 全量 `unittest discover` 40 例通过、零回归。改动文件：`models.py` / `shanten.py` /
> `strategy.py` / `recognition.py`。

---

## 1. 背景与目标

**现状缺陷（P1）**：玩家碰/杠（副露）之后，`recommend_discard` 以 `hand_count_unstable` 拒绝建议。
恰在最需建议的碰杠流局面下教练失声，而本规则可碰可杠、金钩钓/十八罗汉/将对/碰碰胡等番型必须依赖副露。

**目标**：副露之后，策略能像无副露时一样给出「打哪张」的出牌建议，向听与评分把已锁定的副露面子正确计入。

**范围决策（已与用户确认）**：**最小修复**。
- 只恢复「打哪张」的出牌建议；路线标签复用现有 `analyze_routes`。
- **不**新增金钩钓 / 十八罗汉 / 碰碰胡 / 将对等副露专属番型路线判断（YAGNI，留待后续）。
- **不**做听牌提示与番数估算。

---

## 2. 根因链（已定位，共 5 处）

| 位置 | 问题 |
|---|---|
| `models.py:190` `all_hand_tiles()` | 只含 `hand + drawn_tile`，不含 `self_melds` |
| `strategy.py:42`、`strategy.py:110` | 硬校验 `len(tiles) in (13,14)`，副露后暗手只剩 10/11 张 → 拒答 |
| `shanten.py`（`standard_shanten` 等） | 面子预算写死 4（`8 - 2*melds`、`min(taatsu, 4-melds)`），不知道副露已锁定的面子 |
| `strategy.py:193` `_score_discard` | 用 `best_shanten`（含七对），副露局面应排除七对 |
| `recognition.py:106` | **审查文档未提**：`expected_hand_counts=(13,14)` 会把副露帧的识别置信度直接压成 0 → 即使改了 strategy，端到端仍拒答 |

---

## 3. 核心方案

### 3.1 让 shanten 感知副露：显式折算，而非塞牌

直觉上「把副露牌塞进 `all_hand_tiles()` 让算法自动识别面子」**不可行**：

- shanten 的递归搜索会把已锁定的碰/杠**拆开重组**（例如把碰的 ⟨5m 5m 5m⟩ 拆进顺子），得出与实际不符的向听。
- 杠是 4 张同牌，会破坏 27 牌空间「每种牌 ≤ 4」之外的结构假设，污染搜索。

**采用方案**：给 `standard_shanten` / `best_shanten` 增加 `melds_done` 参数（默认 0），把副露**组数**作为「已锁定面子数」显式折算。`all_hand_tiles()` 语义保持不变（仍只含暗手+摸牌）。

### 3.2 向听数学

设 `f = melds_done`（副露组数）：

```
meld_budget = 4 - f                      # 手牌内还需凑的面子数
(melds, taatsu) = _best_meld_taatsu(...) # 手牌内最优分解，不受 f 影响
melds  = min(melds, meld_budget)         # 防御性 clamp（张数约束下通常已满足）
taatsu = min(taatsu, meld_budget - melds)
shanten = 2 * meld_budget - 2 * melds - taatsu - has_pair
```

`f = 0` 时退化为原式 `8 - 2*melds - taatsu - has_pair`，向后兼容。

**验证**：
- 金钩钓 `f=4` → `meld_budget=0`，暗手单钓 ⟨5m⟩ → `shanten=0`（听牌）✓；摸到对 ⟨5m 5m⟩ → `has_pair=1` → `shanten=-1`（和牌）✓。
- 碰一组 `f=1` → `meld_budget=3`，暗手 3 面子+对 → `shanten=-1`（和牌）✓；2 面子+1 对+1 搭+单 → `shanten=0`（听牌）✓。

### 3.3 暗手张数模型

每组副露（碰/明杠/暗杠/补杠）在和牌结构里都锁定**一个面子**，故期望暗手张数随组数浮动：

```
expected_hand_counts(f) = (13 - 3*f, 14 - 3*f)   # (等待态, 待打态)
```

杠多出的第 4 张是补摸的额外牌，显示在副露区、不进暗手，因此对暗手张数的影响与碰一致（每组 -3）。补摸动画的中间态张数对不上时，沿用现有「等下一帧」容错（仍返回 `hand_count_unstable`）。

---

## 4. 分模块改动

### ① `models.py` — 数据契约
- 不改 `all_hand_tiles()`（保持只含暗手+摸牌）。
- 新增 `GameState.meld_count`（property 或方法）= `len(self_melds)`。
- 新增模块级函数 `expected_hand_counts(meld_count: int) -> tuple[int, ...]` 返回 `(13-3f, 14-3f)`，供 strategy 与 recognition 共用，避免张数逻辑在两处漂移。

### ② `shanten.py` — 向听
- `standard_shanten(tiles, melds_done=0)`：按 §3.2 调整面子预算、taatsu 截断、向听公式，并 clamp `melds`。
- `best_shanten(tiles, melds_done=0)`：`melds_done>0` 时只返回 `standard_shanten(tiles, melds_done)`（七对要门清，副露不适用）；`=0` 时维持 `min(standard, seven_pairs)`。
- `_best_meld_taatsu` 与其 `lru_cache` **不动**（返回手牌内最优分解，与预算无关）。
- `seven_pairs_shanten` **不动**。

### ③ `strategy.py` — 策略
- `recommend_discard`、`recommend_missing_suit` 的张数校验：`(13,14)` → `expected_hand_counts(game_state.meld_count)`。
- `_score_discard`、`analyze_routes` 内所有 `best_shanten / standard_shanten` 调用传入 `melds_done = game_state.meld_count`。
- 现有 `if not game_state.self_melds` 的七对/将七对/龙七对守卫 **保留**（方向正确）。

### ④ `recognition.py` — 识别
- `recognize_game_state` 中 `line 106` 的 `expected_hand_counts=(13,14)` 校验，改为先按 `self_meld_obs` 分组算组数，再用 §① 同一个 `expected_hand_counts(f)` 校验暗手张数。
- 折算只看**组数**，对每组 3 张（碰）/ 4 张（杠）都鲁棒。
- **标注**：杠在实际游戏识别区是否铺开 4 张，需用真实截图验证；逻辑不依赖该值，仅 sanity check 使用。

### ⑤ 测试 `tests/`
新增副露场景单测（`test_strategy.py` 或新建 `test_shanten_melds.py`）：
- 碰一组（暗手 10/11 张）→ 能给出 `recommended_discard`，不再 `hand_count_unstable`。
- 向听折算正确：构造已和牌/听牌的副露手牌，断言 `best_shanten(..., melds_done=f)` 为 -1 / 0。
- 金钩钓（f=4 单钓）→ 听牌识别正确。
- 有副露时七对路线被 `analyze_routes` 排除。
- 补摸动画态（暗手张数与 `expected_hand_counts(f)` 不符）→ 仍安全返回 `hand_count_unstable`。

### ⑥ 明确不动（防误改）
`all_hand_tiles()` 语义、七对 `count//2`、(2,5,8) 将牌判定、缺门 `+10000` 强制弃牌。

---

## 5. 开放问题处理（对应审查文档第 6 节）

1. **明杠/暗杠/补杠 + 补摸时机** → 已推导：四者对暗手张数影响一致（每组 -3）；补摸中间态用现有容错跳过。
2. **杠在识别区显示几张** → 折算只用组数，不依赖每组张数；设计为兼容 3/4 张，真实值留待截图验证。
3. **建议深度** → 已确认：最小修复，仅「打哪张」。

---

## 6. 风险与验证

- **风险**：`standard_shanten` 公式改动影响无副露（f=0）路径。**缓解**：f=0 退化为原式；运行全部现有 31 个测试 + 已有向听对拍确认零回归。
- **风险**：`melds > meld_budget` 导致 shanten 异常负值。**缓解**：clamp `melds = min(melds, meld_budget)`；张数约束下实际不会触发。
- **验证命令**：
  ```bash
  PYTHONPATH=src python -m unittest discover -s tests
  PYTHONPATH=src python -m pytest tests/test_strategy.py
  ```
- **P7（git）**：提交前确认仓库可用；本机曾报 `not a git repository`，若复现需先排查 ownership/损坏。
