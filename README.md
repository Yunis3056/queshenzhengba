# 🀄 雀神争霸 AI 教练

专为《燕云十六声》"雀神争霸"（四川麻将）设计的桌面 AI 辅助工具。

[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)](https://github.com/Yunis3056/queshenzhengba/releases/tag/v1.0.0)
[![Python](https://img.shields.io/badge/python-3.8+-green.svg)](https://www.python.org/)

**这是一个教学辅助工具，仅提供出牌建议，不会自动操作游戏。**

---

## ✨ 核心功能

- 🎯 **实时出牌建议** - 0.8 秒响应，推荐牌 + 2 个备选方案
- 🧠 **向听数引擎** - 标准型 + 七对子双路线优化
- 🎨 **中国风 UI** - 麻将毡台深绿配色，金色描边按钮
- 🔍 **智能识别** - OpenCV 模板匹配，62+ 牌型模板
- 📊 **可解释性** - 每个建议都有清晰的中文原因说明
- 🀄 **番型识别** - 七对、龙七对、将对、清一色、碰碰胡

---

## 📊 性能指标

| 指标 | 数值 |
|------|------|
| 响应延迟 | 0.4-1.1 秒（典型 0.8 秒）|
| 内存占用 | 40-60 MB |
| CPU 占用 | 平均 15% |
| 实时性 | 满足回合制游戏需求 |

详见：[PERFORMANCE_ANALYSIS.md](PERFORMANCE_ANALYSIS.md)

---

## 🚀 快速开始

### 安装依赖

```powershell
python -m pip install -r requirements.txt
```

**依赖项**：`opencv-python`, `mss`, `Pillow`, `numpy`

### 启动程序

**推荐方式**（Windows）：
```powershell
.\start_quick_capture.ps1
```

或直接运行：
```powershell
python tools\quick_capture.py
```

### 使用步骤

1. **设置截图区域** - 输入游戏窗口坐标，或点击"手动选区"拖选
2. **开始截帧** - 点击"▶ 开始连续截帧"（默认 2 秒间隔）
3. **查看建议** - 实时显示推荐打牌、置信度、路线、原因

---

## 🎯 策略算法

**核心思路**：向听数 + 启发式评分

### 向听数优先
- 优先打不影响向听数的牌
- 标准型（4 面子 + 1 雀头）和七对子双路线
- 使用 `lru_cache` 缓存计算结果

### 评分维度（9 项）
1. **向听数变化**（-120 分/向听）- 最高权重
2. **孤张加分**（+18~36 分）- 孤立边张优先打
3. **对子/刻子惩罚**（-25~-42 分）- 保留价值高
4. **幺九牌加分**（+8~16 分）- 边张进张面窄
5. **七对/将对路线调整**
6. **清一色路线调整**
7. **可见牌数量**（+6~12 分）
8. **等待牌死张检测**（+4~10 分）
9. **定缺强制打**（+10000 分）- 四川麻将规则

详见：[STRATEGY_EXPLAINED.md](STRATEGY_EXPLAINED.md)

---

## 📖 完整文档

- **[CLAUDE.md](CLAUDE.md)** - 项目结构和开发指南
- **[PERFORMANCE_ANALYSIS.md](PERFORMANCE_ANALYSIS.md)** - 性能分析和执行流程
- **[STRATEGY_EXPLAINED.md](STRATEGY_EXPLAINED.md)** - 策略算法详解
- **[RELEASE_v1.0.0.md](RELEASE_v1.0.0.md)** - 完整的发布说明

---

## ⚠️ 局限性

V1.0 专注于**进攻策略**，以下功能暂不支持：

- ❌ 防守策略（危险牌判断）
- ❌ 对手建模（读牌能力）
- ❌ 胡牌价值评估
- ❌ 概率计算（进张枚数）

这些将在 **V2.0（深度强化学习版本）** 中实现。

---

## 🛣️ 路线图

### ✅ V1.0（当前）- 启发式 AI
- 向听数计算
- 基础出牌建议
- 番型识别（七对、将对、清一色等）
- 图像识别（OpenCV 模板匹配）
- 中国风 UI

### 🚀 V2.0（计划中）- 深度强化学习
- PPO + Transformer
- 防守系统（危险牌预测）
- 对手建模（读牌引擎）
- MCTS 搜索
- 百万局牌谱训练
- **目标：天凤七段+ 水平**

---

## 🔧 高级功能

### 模板采集

如果识别率低，可以重新采集模板：

```powershell
.\start_template_collector.ps1
```

拖拽框选单张牌，选择牌名后保存到 `samples/templates/<牌名>/`

### 命令行测试

无需 UI，直接测试策略引擎：

```powershell
$env:PYTHONPATH="src"
python -m queshen_agent.cli --missing-suit p --hand 1m 2m 3m 5m 5m 8m 8m 2s 3s 4s 9p
```

### 配置文件

- `config/quick_capture.json` - 截图区域和间隔
- `config/regions.json` - 游戏区域坐标
- `config/frame_analyzer.json` - 分析器配置

预设配置：
```powershell
.\apply_1280x720_layout.ps1  # 应用 1280x720 默认布局
```

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

### 开发环境

```powershell
# 运行测试
$env:PYTHONPATH="src"
python -m pytest tests/

# 单元测试
python -m unittest discover -s tests
```

---

## 📄 许可证

本项目仅供学习和个人使用。

---

## 🙏 致谢

- OpenCV 社区
- 麻将 AI 研究社区
- 《燕云十六声》游戏

---

**祝你打牌顺利，早日成为雀神！** 🀄✨
