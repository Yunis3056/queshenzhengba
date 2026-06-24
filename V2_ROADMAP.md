# 🚀 雀神争霸 V2.0 - 竞技级 AI 技术路线

## 核心目标
达到**天凤七段+**水平，具备防守、读牌、番种优化能力。

---

## 一、技术架构选择

### 1.1 核心算法：深度强化学习（DRL）

**推荐方案：PPO (Proximal Policy Optimization) + Transformer**

```
为什么不用现有的向听数+启发式？
- 天花板太低，无法学习复杂策略
- 无法处理对手建模、危险牌判断
- 固定权重无法适应不同局面

为什么选 PPO？
- 微软 Suphx 和 Meta 的麻将 AI 都用这个
- 训练稳定，不像 DQN 那么脆弱
- 支持连续动作空间（出牌+副露）
```

**网络架构**：
```python
# Transformer Encoder + Value/Policy Head
class MahjongNet(nn.Module):
    def __init__(self):
        self.tile_embedding = nn.Embedding(27+1, 128)  # 27种牌+空位
        self.transformer = nn.TransformerEncoder(
            nn.TransformerEncoderLayer(d_model=128, nhead=8),
            num_layers=6
        )
        self.policy_head = nn.Linear(128, 27)  # 出牌概率
        self.value_head = nn.Linear(128, 1)    # 局面评估
        
    def forward(self, state):
        # state: [手牌, 弃牌河, 对手副露, 剩余牌, 定缺...]
        x = self.tile_embedding(state)
        x = self.transformer(x)
        policy = self.policy_head(x.mean(dim=1))
        value = self.value_head(x.mean(dim=1))
        return policy, value
```

---

### 1.2 训练数据：百万级真人牌谱

**数据源推荐**：
1. **天凤牌谱** - 爬取 tenhou.net 的公开牌谱（有现成爬虫）
2. **雀魂牌谱** - 雀魂有 API 可以获取
3. **自对弈数据** - 训练到一定程度后自己生成

**数据量需求**：
- 初期：10万局牌谱（约 200GB）
- 中期：50万局（1TB）
- 高级：100万+局（2TB+）

**关键**：筛选高段位玩家的牌谱（天凤七段+），质量比数量重要。

---

### 1.3 状态表示（State Encoding）

当前你的 `GameState` 太简单了，需要扩展：

```python
@dataclass
class MahjongState:
    # 基础信息（已有）
    hand: list[str]              # 手牌 13/14张
    drawn_tile: str | None       # 摸牌
    self_melds: list[list[str]]  # 自家副露
    missing_suit: str            # 定缺
    
    # ============ 新增：对手信息 ============
    opponent_discards: dict[str, list[tuple[str, bool]]]  # (牌, 是否危险)
    opponent_melds: dict[str, list[list[str]]]
    opponent_riichi: dict[str, bool]  # 对手是否立直（听牌）
    
    # ============ 新增：牌山信息 ============
    remaining_tiles: dict[str, int]  # 每种牌剩余张数（根据可见牌推算）
    dora_indicators: list[str]       # 宝牌指示牌
    
    # ============ 新增：局面信息 ============
    round_wind: str           # 场风（东/南/西/北）
    seat_wind: str            # 自风
    current_turn: int         # 当前巡目（第几轮）
    dealer: int               # 庄家位置
    honba: int                # 本场数
    riichi_sticks: int        # 立直棒数
    
    # ============ 新增：时序信息 ============
    action_history: list[tuple[str, str, str]]  # (玩家, 动作, 牌)
    
    # ============ 新增：分数信息 ============
    scores: dict[str, int]    # 各家分数
    placement: int            # 当前排名
```

这些信息对应 Transformer 的输入 token：
```
[手牌14个token] + [弃牌河60个token] + [副露token] + [剩余牌27个token] + [局面meta token]
总计约 200-300 个 token
```

---

## 二、四大核心模块

### 2.1 模块一：防守系统（最重要！）

**功能**：判断哪些牌是"危险牌"（对手可能听的牌）

**算法**：
```python
class DefenseModule:
    def __init__(self, model):
        self.danger_predictor = model  # 小型 CNN，输入弃牌河，输出27种牌的危险度
    
    def predict_danger(self, opponent_discards, opponent_melds):
        """
        返回：{牌: 危险度 0-1}
        
        启发式规则（快速版本）：
        - 对手连续打同花色 → 可能清一色 → 其他花色危险
        - 对手打过边张1、9 → 中张安全
        - 对手立直后 → 使用深度学习预测
        """
        if use_heuristic:
            return self._筋牌理论()  # 日本麻将经典防守理论
        else:
            return self.danger_predictor(opponent_discards)
```

**训练方式**：
- 标签：牌谱中标记每张牌是否被下家和了（0/1）
- 损失函数：Binary Cross Entropy
- 这个模块可以**单独训练**，不依赖 PPO

---

### 2.2 模块二：番种优化器

**功能**：不只是"快速听牌"，还要"听大牌"

**算法**：
```python
class YakuOptimizer:
    """
    评估函数：V(s) = α×听牌速度 + β×番数期望 + γ×点数期望
    
    例如：
    - 普通平和：1倍，基础分
    - 清一色：4倍
    
    在2向听时，如果清一色路线期望分更高，就往清一色走
    """
    def calculate_expected_value(self, state):
        speed_to_tenpai = best_shanten(state.hand)
        yaku_potential = self._analyze_yaku_routes(state)
        expected_multiplier = sum(p * mult for yaku, (p, mult) in yaku_potential.items())
        
        return -speed_to_tenpai * 1000 + expected_multiplier * 100
```

**关键番型**（雀神争霸）：
- 天胡/地胡（32倍）
- 将三龙七对（128倍）
- 十八罗汉（64倍）
- 双龙七对/将七对（16倍）
- 龙七对/将对（8倍）
- 清一色/七对/金钩钧/幺九（4倍）
- 断幺九/碰碰胡/海底捞月/抢杠胡/杠上开花/自摸/根（2倍）
- 平胡（1倍）

---

### 2.3 模块三：读牌引擎（对手建模）

**功能**：根据对手打牌推测他的手牌

**算法**：贝叶斯推断 + 神经网络

```python
class OpponentModel:
    def __init__(self):
        self.hand_distribution = np.ones(27) / 27  # 初始均匀分布
    
    def update(self, opponent_action):
        """
        观察：对手打出 5m
        推断：
        - 手里 5m 数量减少（显然）
        - 4m、6m 可能也少（否则不会打5m）
        - 如果早巡打5m → 可能清一色其他花色
        """
        if action.type == "discard":
            tile = action.tile
            self.hand_distribution[tile] *= 0.1  # 打出的牌手里少
            neighbors = [tile-1, tile+1]
            for n in neighbors:
                self.hand_distribution[n] *= 0.7  # 邻牌也可能少
        
        # 用神经网络微调
        self.hand_distribution = self.nn_refine(opponent_history)
```

**应用**：
- 防守时：推测对手听牌范围
- 进攻时：判断对手是否追清一色（要不要跟）

---

### 2.4 模块四：蒙特卡洛树搜索（MCTS）

**功能**：在关键局面（听牌、立直选择）时，模拟未来走势

```python
class MCTS:
    def search(self, state, iterations=1000):
        for _ in range(iterations):
            # 1. 选择：UCB1 算法选择最有潜力的分支
            node = self.select(root)
            
            # 2. 扩展：生成可能的动作
            children = self.expand(node)
            
            # 3. 模拟：快速 rollout 到游戏结束
            reward = self.simulate(children[0])
            
            # 4. 回传：更新路径上所有节点的价值
            self.backpropagate(node, reward)
        
        return self.best_action(root)
```

**使用场景**：
- 是否立直？（立直后不能换牌，需要权衡）
- 是否和牌？（小牌快速和 vs 继续追大牌）
- 危险局面：是否弃和保平（不追求和牌，只求不放炮）

---

## 三、实现路线图

### Phase 1: 基础设施（2-3周）

```
✅ 任务 1.1: 数据管道
   - 爬取天凤牌谱（Python + requests）
   - 解析 mjlog 格式 → 转换成你的 GameState
   - 存储：HDF5 或 Parquet（比 JSON 快 10 倍）

✅ 任务 1.2: 扩展 GameState
   - 添加上面提到的所有新字段
   - 实现 state_to_tensor() 函数（Transformer 输入）

✅ 任务 1.3: 模拟器
   - 实现一个快速的麻将模拟器（用于自对弈）
   - 支持：摸牌、打牌、碰、杠、和牌判断
   - 性能目标：单核 10000 局/秒
```

**推荐库**：
```python
# 已有的开源麻将库
import mahjong  # Python Mahjong Library (Riichi)
# 或自己实现（更快，可以 Cython 加速）
```

---

### Phase 2: 模仿学习（2-3周）

```
✅ 任务 2.1: 监督学习
   目标：让 AI 学会"打得像高手"
   
   损失函数：
   L = CrossEntropy(模型输出, 牌谱中的实际打牌)
   
   数据增强：
   - 旋转座位（自家/下家/对家/上家 四种视角）
   - 镜像翻转（万/筒/条 互换）
   
   训练：
   - Batch size: 256
   - Epochs: 10-20
   - 优化器：AdamW
   - 学习率：1e-4
   
   验证指标：
   - Top-1 准确率：模型预测 == 高手实际打牌（目标 >40%）
   - Top-3 准确率：高手的选择在模型的前3候选内（目标 >70%）

✅ 任务 2.2: 防守模块训练
   单独训练危险牌预测器
   标签：牌谱中标记危险牌（被和了的牌 = 1）
   Top-1 准确率目标：>60%
```

---

### Phase 3: 强化学习（4-6周）

```
✅ 任务 3.1: 自对弈框架
   - 4 个 AI 互相打（每局记录轨迹）
   - 奖励函数设计（见下方）
   - 分布式训练：8-16 个 worker 并行采样

✅ 任务 3.2: PPO 训练
   超参数：
   - Clip epsilon: 0.2
   - GAE lambda: 0.95
   - Value loss coef: 0.5
   - Entropy coef: 0.01
   
   训练时长：
   - 100万局自对弈（约 1 周，8卡 GPU）
   - 每 10 万局保存 checkpoint
   - 每 50 万局对战测试（vs 监督学习版本）

✅ 任务 3.3: 对战评估
   - 实现 Elo 评分系统
   - 定期与基准 AI 对战（10000局）
   - 目标：Elo >2000（天凤七段水平）
```

**奖励函数设计**（关键！）：
```python
def reward_function(game_result):
    """
    不能简单用 胜=1, 负=-1
    要考虑：排名、点数、立直成功率、放炮惩罚
    """
    r = 0
    
    # 1. 排名奖励（主要）
    rank_rewards = {1: 50, 2: 10, 3: -10, 4: -30}
    r += rank_rewards[game_result.placement]
    
    # 2. 点数奖励（次要）
    r += (game_result.final_score - 25000) / 1000  # 归一化
    
    # 3. 和牌奖励
    if game_result.won:
        r += game_result.multiplier * 5  # 倍数越多奖励越高
    
    # 4. 放炮惩罚
    if game_result.dealt_in:
        r -= 20
    
    # 5. 立直成功率（鼓励正确的立直时机）
    if game_result.riichi and game_result.won:
        r += 10
    elif game_result.riichi and not game_result.won:
        r -= 5
    
    # 6. 中间步奖励（稀疏奖励问题）
    r += -best_shanten(state.hand) * 0.1  # 鼓励快速减少向听数
    
    return r
```

---

### Phase 4: 高级功能（2-3周）

```
✅ 任务 4.1: 添加 MCTS
   - 集成到决策流程
   - 只在关键时刻用（听牌、立直选择）
   - 时间预算：200ms

✅ 任务 4.2: 集成到 quick_capture
   - 替换现有的 strategy.py
   - 加载训练好的模型（.pth 文件）
   - 推理优化：TorchScript / ONNX（提速 3-5 倍）

✅ 任务 4.3: 可解释性
   - 注意力可视化（Transformer 的 attention weights）
   - 显示"AI 认为对手听什么牌"
   - 保留原因生成（用 LLM 根据模型输出生成中文解释）
```

---

## 四、硬件需求

### 最低配置（训练）
- **GPU**: RTX 3090 (24GB) × 1
- **CPU**: 16核
- **内存**: 64GB
- **存储**: 2TB SSD
- **训练时间**: 4-6 周

### 推荐配置（快速迭代）
- **GPU**: A100 (40GB) × 4 或 H100 × 2
- **CPU**: 32核+
- **内存**: 128GB
- **存储**: 4TB NVMe
- **训练时间**: 1-2 周

### 云端方案
- **AWS**: p4d.24xlarge（8×A100）- $32/小时
- **阿里云**: ecs.gn7i-c16g1.16xlarge（4×A100）- ¥160/小时
- **预算**: 训练一版约 $5000-10000

---

## 五、开源资源（直接用）

### 5.1 现成的麻将 AI 框架

```bash
# 1. Mortal (Rust + PyTorch) - 天凤高段位水平
git clone https://github.com/Equim-chan/Mortal
# 架构：Transformer + PPO
# 可以直接改 reward function 适配雀神争霸

# 2. akochan (C++) - 经典，但较老
git clone https://github.com/critter-mj/akochan
# 基于概率计算，不是深度学习

# 3. MahjongAI (Python) - 教学用
git clone https://github.com/TakuKitamura/MahjongAI
```

**建议**：Fork **Mortal**，改规则和奖励函数。它的架构已经很成熟了。

---

### 5.2 牌谱爬虫

```python
# 天凤牌谱下载器（现成的）
# https://github.com/shinkuan/TenhouPaifu

import requests

def download_tenhou_log(log_id):
    url = f"https://tenhou.net/0/log/?{log_id}"
    response = requests.get(url)
    return response.content  # mjlog XML 格式

# 雀魂牌谱（需要抓包获取 API）
# https://github.com/Avenshy/majsoul-api
```

---

### 5.3 现成的模拟器

```python
# Python Mahjong Library
pip install mahjong

from mahjong.shanten import Shanten
from mahjong.hand_calculating.hand import HandCalculator

# 或者用 Rust 写的（超快）
# https://github.com/Equim-chan/mjai-reviewer
```

---

## 六、关键优化技巧

### 6.1 训练加速

```python
# 1. 混合精度训练（AMP）
from torch.cuda.amp import autocast, GradScaler

scaler = GradScaler()
with autocast():
    loss = model(state)
scaler.scale(loss).backward()
scaler.step(optimizer)

# 2. 分布式数据并行（DDP）
import torch.distributed as dist
model = nn.parallel.DistributedDataParallel(model)

# 3. 编译优化（PyTorch 2.0）
model = torch.compile(model, mode="max-autotune")
```

---

### 6.2 推理加速（部署）

```python
# 1. TorchScript（静态图优化）
scripted_model = torch.jit.script(model)
scripted_model.save("model.pt")

# 2. ONNX Runtime（跨平台）
torch.onnx.export(model, dummy_input, "model.onnx")

# 3. TensorRT（NVIDIA GPU 专用，提速 5-10 倍）
import torch_tensorrt
trt_model = torch_tensorrt.compile(model, inputs=[...])

# 推理延迟目标：<50ms（从 state 到推荐牌）
```

---

## 七、开发时间表

| 阶段 | 时间 | 关键里程碑 |
|------|------|-----------|
| **Phase 1** | 2-3周 | 数据管道 + 模拟器完成 |
| **Phase 2** | 2-3周 | 监督学习达到 40% Top-1 准确率 |
| **Phase 3** | 4-6周 | PPO 训练，Elo >2000 |
| **Phase 4** | 2-3周 | 集成到 quick_capture，可部署 |
| **总计** | **10-15周**（2.5-4个月） | V2.0 上线 |

---

## 八、成本估算

| 项目 | 费用 | 备注 |
|------|------|------|
| **GPU 训练** | $5000-10000 | 云端 A100 × 4，2-4周 |
| **牌谱爬取** | $0 | 天凤公开数据 |
| **开发工时** | - | 1 人全职 3-4 个月 |
| **部署（推理）** | $0 | 本地 GPU（RTX 3060 够用）|
| **总计** | **$5000-10000** | 主要是 GPU 训练费用 |

如果用本地 RTX 3090，可以省下 GPU 费用，但训练时间延长到 6-8 周。

---

## 九、风险与应对

| 风险 | 概率 | 应对 |
|------|------|------|
| **训练不收敛** | 中 | 先用监督学习打好基础（Warm-start） |
| **过拟合牌谱** | 高 | 数据增强 + 正则化 + 自对弈 |
| **推理太慢** | 中 | TorchScript + 量化（INT8） |
| **模型太大** | 低 | 知识蒸馏（Distillation） |
| **对雀神争霸适配差** | 中 | 自己打10000局标注数据 |

---

## 十、最终对比

| 指标 | V1.0（当前）| V2.0（目标）|
|------|------------|------------|
| **水平** | 初中级 | 天凤七段+ |
| **向听数计算** | ✅ | ✅ |
| **防守能力** | ❌ | ✅ 危险牌预测 |
| **读牌能力** | ❌ | ✅ 对手建模 |
| **番种优化** | ⚠️ 简单 | ✅ 期望分最大化 |
| **推理延迟** | 0.8秒 | <0.1秒（优化后）|
| **可解释性** | ✅ 强 | ⚠️ 中（需要额外工作）|
| **训练成本** | $0 | $5000-10000 |

---

## 总结：立即开始的 3 步

### 第 1 步（本周）：搭建基础设施
```bash
# 1. Fork Mortal 项目
git clone https://github.com/Equim-chan/Mortal
cd Mortal

# 2. 下载 1 万局天凤牌谱（测试用）
python scripts/download_tenhou.py --count 10000

# 3. 运行一次训练流程（验证环境）
python train.py --config configs/test.yaml
```

### 第 2 步（下周）：改造为雀神争霸规则
```python
# 修改规则文件
# mortal/rules.py

class QueshenMahjongRules:
    def __init__(self):
        self.allow_chi = False  # 不能吃
        self.dingque = True     # 定缺
        self.yaku_list = [      # 番种
            "tianhu", "dihu", "longqidui", "jiangqidui",
            "qingyise", "qidui", "pengpenghu", "duanyaojiu"
        ]
```

### 第 3 步（第 3-4 周）：监督学习
```bash
# 训练第一版模型
python train_supervised.py \
    --data data/tenhou_10k.hdf5 \
    --model transformer \
    --epochs 20 \
    --batch_size 256 \
    --gpu 0

# 评估
python evaluate.py --checkpoint checkpoints/best.pth
```

如果 Top-1 准确率达到 **35-40%**，说明基础打好了，可以进入强化学习阶段。

---

**直接开干，不要犹豫。Mortal 的代码质量很高，照着改就行。3 个月后你就有一个天凤七段水平的 AI 了。**
