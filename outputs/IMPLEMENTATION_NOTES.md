# 雀神争霸 AI 教练实现说明

## 已实现

- Python 包结构：`src/queshen_agent`
- 桌面 UI 入口：`run_queshen_agent.py`
- PowerShell 启动脚本：`start_queshen_agent.ps1`
- 配置示例：`config/regions.example.json`
- 规则读取：`outputs/yanyun_queshen_rules.json`
- 核心策略引擎：
  - 定缺优先
  - 七对/龙七对/将对/将七对/清一色/碰碰胡路线识别
  - 标准胡和七对向听估算
  - 每张可打牌评分
- 截图模块：
  - 按选定游戏区域截图
  - 保存截图样本
- 桌面 UI：
  - 深色 Fluent 风格
  - 选择游戏区域
  - 校准手牌、碰杠、弃牌、定缺区域
  - 一键截图识别
  - 手动输入兜底分析
  - 保存样本和运行记录
- 模板识别框架：
  - `samples/templates/1m` 到 `9s` 模板目录
  - 区域切牌、模板匹配、置信度输出
  - 绝对屏幕坐标到截图相对坐标转换
- 测试：
  - 8 个核心单元测试已通过

## 需要安装依赖

```powershell
python -m pip install -r requirements.txt
```

当前环境缺少：

- PySide6
- OpenCV
- mss
- Pillow
- numpy

Codex 自带 Python 已有 Pillow/numpy，但没有 PySide6/OpenCV/mss。

## 首次实战前需要做

1. 运行 `.\start_queshen_agent.ps1`。
2. 点击 `初始化模板目录`。
3. 从游戏截图裁剪每种牌的小图，放进：

```text
samples/templates/1m
samples/templates/2m
...
samples/templates/9s
```

4. 重新启动应用，让模板加载。
5. 框选游戏区域和各牌区。
6. 点击 `一键截图识别`。

## 当前限制

- 定缺区已可校准，但图标自动识别还未单独训练模板；第一版建议用手动输入或后续补定缺识别模板。
- 模板识别的准确率依赖样本质量，需要用实际游戏截图校准。
- GUI 和截图功能需要安装依赖后才能运行。
