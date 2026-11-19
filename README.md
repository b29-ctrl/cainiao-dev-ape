# 菜鸟开发猿 (Cainiao Dev Ape)

[![Version](https://img.shields.io/badge/version-4.64.0-blue.svg)](https://github.com/b29-ctrl/cainiao-dev-ape/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**菜鸟开发猿**（原名 `dev-workflow-1n1n`）是一套 **「1 主理人 + N 小组队长 + N AI」** 的通用软件开发流程与工具集。它专为单人开发者或小团队设计，帮助你规范从需求立项、方案评审、代码构建到独立验收的全过程，避免 AI 协作过程中的混乱与返工。

> **决策头永远 1 个，执行可以无限加，人多不会打架。**

## ✨ 核心特性

- **全流程覆盖**：从 S-1 环境初始化、S0 需求问卷、S1 产品功能说明书、S2 效果图、S3 批注，到 S4 风格冻结、S5 方案评审、S6 实施与验收。
- **五道门禁**：方案审、代码审、构建自检、独立验收、终验发版，确保质量。
- **6 个零依赖工具**：基于 Python/HTML，无需安装任何第三方库，开箱即用。
  - `S-1_环境初始化.html`：四问勾选器，自动生成环境档案
  - `02_工具/UI调试台.py`：左预览右源码，双击改代码，带虚线网格与量尺
  - `02_工具/启动项目.py`：先弹风格选型再起调试台
  - `02_工具/S4_冻结.py`：锁风格 + 打 tag + 出冻结记录
  - `02_工具/门禁矩阵.py`：从说明书抽验收项 + 查漏交付
  - `02_工具/任务书生成.py`：依赖图 + 里程碑 + 并行度计算
- **UI 交付六铁律**：针对 AI 生成 UI 的专项验收规范，避免"AI 味"与交互缺陷。
- **方案图证据链**：确保方案图每条连线都有代码/文档出处，防止"配置≠运行"。

## 🚀 快速开始

### 1. 作为 DSH (DeepSeek Harness) 技能使用
如果你正在使用 DeepSeek Harness：
1. 将本仓库内容放入 `~/.dsh/skills/cainiao-dev-ape/` 目录下。
2. 在对话中说：**「立项 / 开工 / 走开发流程」** 即可激活。

### 2. 作为通用 AI 提示词使用
1. 打开 `SKILL.md`，复制全部内容。
2. 将其作为 System Prompt 或上下文提供给你的 AI 助手（Claude、GPT-4、DeepSeek 等）。
3. AI 会严格遵循流程，要求你提供需求、并分步执行。

### 3. 运行本地工具
所有工具均为零依赖，仅需 Python 3.9+：
```bash
# Windows
python 02_工具\启动项目.py --dir "你的项目目录" --port 8792

# macOS / Linux
python3 02_工具/启动项目.py --dir ~/你的项目目录 --port 8792
```

## 📂 目录结构

```
cainiao-dev-ape/
├── SKILL.md                    # 技能入口与完整流程定义
├── 01_流程/                    # 通用开发流程本体 (v4.45)
├── 02_工具/                    # 6 个零依赖 Python/HTML 工具
├── 03_模板/                    # 各阶段模板 (环境初始化、说明书、任务书、UI交付等)
├── 04_示例/                    # 示例数据与效果图
├── 05_方案图与一页讲清.md      # 方案图证据链规范
├── 06_UI交付与验收.md          # UI 交付六铁律与验收三查
├── config.json                 # 流程配置与阶段定义
├── 交付须知.md                 # 授权、商用、改动回传说明
└── 先读我.txt                  # 人类与 AI 的快速导航
```

## 📝 版本历史

- **v4.64.0** (2026-11-16): 并入 UI 交付与验收规范 (六铁律+五步+三查+十坑)。
- **v4.63.0**: 蒸馏 TRAE ui-delivery-kit，强化 UI 交付。
- **v4.62.0**: 蒸馏 Archify，强化方案图证据纪律。
- **v4.45.0**: 流程本体 finalized。

## 🤝 贡献与反馈

如果你在使用过程中有任何建议、发现了 Bug，或者想要贡献新的工具/模板，欢迎提交 Issue 或 Pull Request。

## 📜 许可证

本项目采用 [MIT License](LICENSE) 开源。

---
*Designed for humans and AI agents working together.*
