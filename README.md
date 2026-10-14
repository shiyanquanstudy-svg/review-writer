# 自动化综述撰写平台

> 从一句自然语言指令，到一份带引用、可追溯、通过质量核查的学术综述。

## 简介

这是一个多智能体 + 检索增强生成（Agentic RAG）架构的学术综述自动撰写平台。

输入一句自然语言指令（如帮我撰写一个综述，阿尔茨海默病 tau 蛋白 PET 显像剂近十年的发展），平台自动完成：

1. 解析指令为结构化综述规格（章节、核心实体、证据类型）
2. 规划双源检索策略（PubMed + ClinicalTrials.gov）
3. 检索并落盘真实文献
4. 提取每条文献的结构化信息并归类到章节
5. 生成大纲并逐节写作，每句事实陈述绑定引用
6. 逐句核查引用支持率，标记幻觉与张冠李戴
7. 组装为完整 Markdown 综述（摘要 + 正文 + 参考文献）

核心理念：LLM 只负责理解和表达，事实性内容必须来自真实检索的文献。宁可诚实标注证据缺口，也不编造。

## 核心特性

- 真实检索：PubMed E-utilities + ClinicalTrials.gov API
- 引用可追溯：每句事实性陈述带 [source_id] 标记
- 三层幻觉防护：检索隔离 / Prompt 硬约束 / 逐句引用核查
- 通用化设计：无硬编码，可处理多类综述
- 浏览器界面：Streamlit 7 步流程
- 本地优先：SQLite 持久化

## 快速开始

环境要求：Python 3.11+，DeepSeek API Key，可选 NCBI API Key。

    git clone https://github.com/shiyanquanstudy-svg/review-writer.git
    cd review-writer
    python -m venv .venv
    .venv\Scripts\activate
    pip install -r requirements.txt

配置 .env：

    DEEPSEEK_API_KEY=sk-your-key-here
    DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
    DEEPSEEK_MODEL=deepseek-chat
    NCBI_API_KEY=your-ncbi-key
    NCBI_EMAIL=your-email@example.com

启动：

    streamlit run app.py

浏览器打开 http://localhost:8501。

## 七步流程

| 步骤 | 名称 | 输出 |
|---|---|---|
| 1 | 指令解析 | ReviewSpec |
| 2 | 双源检索 | PubMed + ClinicalTrials |
| 3 | 信息提取 | 结构化字段 |
| 4 | 大纲生成 | 每节要点 |
| 5 | 分节写作 | A/B 类证据约束 |
| 6 | 引用核查 | 逐句 verdict |
| 7 | 组装输出 | Markdown 综述 |

## 技术栈

- LLM：DeepSeek V3
- 前端：Streamlit
- 数据源：PubMed E-utilities、ClinicalTrials.gov API v2
- 持久化：SQLite
- 数据模型：Pydantic

## 验证案例

案例 1：临床三期抗抑郁药 JS1-1-01 片的发展史
- 118 条源，14072 字符，25 条参考文献
- 引用支持率：76.9% / 92.3% / 75.0% / 92.9%
- 审计：正文引用与参考文献零孤立零缺失

案例 2：阿尔茨海默病 tau 蛋白 PET 显像剂近十年的发展
- 130 条源，27507 字符，19 条参考文献
- 引用支持率：100% / 87.5% / 100% / 94.1%
- 亮点：准确引用 PI-2620 结合位点、MK-6240 的 2.31 Å cryo-EM 结构

## 已知限制

1. 不支持图表生成，输出纯文本
2. 仅输出 Markdown，不含 PDF
3. 临床前研究覆盖取决于文献是否公开发表
4. 云端部署需改造 SQLite 持久化
5. 目前针对中文写作优化

## License

MIT License. 仅供学术研究参考，不得用于提交到期刊或会议。
