---
AIGC:
    Label: "1"
    ContentProducer: 001191110102MACQD9K64018705
    ProduceID: 7628402559795020083-data_volume/files/所有对话/主对话/README.md
    ReservedCode1: ""
    ContentPropagator: 001191110102MACQD9K64028705
    PropagateID: 1065898525067047#1785655279335
    ReservedCode2: ""
---
# C++ 做题助手

一个本地运行的 GESP C++ 做题学习应用，支持 PDF 导入题目、按知识点练习、错题复习、题库管理和 AI 答疑。

## 功能特性

- 📄 **PDF 导入** — 上传 GESP 历年真题 PDF，自动解析并导入题库
- ✅ **做题练习** — 按考试类型、级别、知识点筛选，支持选择题和判断题，实时反馈
- 📊 **知识点分析** — Plotly 柱状图展示题目分布、完成度与知识点频次（必考/常考/轮考）
- 🔄 **错题复习** — 按知识点/高频错题/随机模式复习，支持掌握标记
- 📝 **题库管理** — 表格查看、单题编辑、JSON 批量导入、实时重载
- 🔍 **题目搜索** — 按关键字搜索题目，支持按知识点/考试类型/难度筛选
- 🤖 **AI 答疑** — 智能助手解释题目和知识点（需配置 API Key）
- ⚡ **缓存加速** — 题目索引、考试日期等数据缓存，提升页面响应速度

## 快速开始

### 前置要求

- Python 3.8+
- pip

### 安装依赖

```bash
pip install -r requirements.txt
```

### 配置 AI（可选）

编辑 `.env` 文件，填写你的 DeepSeek API Key：

```env
LLM_API_KEY=your_deepseek_api_key
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
```

如不配置，AI 功能将不可用，但其他功能正常运行。

### 启动应用

**Windows（推荐）：**

双击 `run.bat`，自动完成：清理缓存 → 激活虚拟环境 → 安装依赖 → 启动应用。

**手动启动：**

```bash
# Windows CMD
set PYTHONPATH=%cd%
streamlit run app/0_Overview.py

# macOS / Linux
PYTHONPATH=$(pwd) streamlit run app/0_Overview.py
```

### 访问应用

启动后默认地址：http://localhost:8501

| 页面 | 路径 | 功能 |
|------|------|------|
| 概览 | `/` | 项目介绍与使用说明 |
| 做题练习 | `/做题练习` | 按知识点筛选做题，实时反馈 |
| 错题复习 | `/错题复习` | 错题本复习，支持多种模式 |
| 题库管理 | `/题库管理` | 查看、编辑、导入题目 |

## 项目结构

```
cpp_assistant/
├── app/
│   ├── 0_Overview.py                  # 首页（概览）
│   ├── pages/
│   │   ├── 1_Practice.py              # 做题练习页
│   │   ├── 2_Review.py                # 错题复习页
│   │   └── 3_Question_bank_manage.py  # 题库管理页（含单题编辑、PDF导入）
│   └── core/
│       ├── question_loader.py         # 题库加载 + SQLite 索引 + 搜索
│       ├── practice_tracker.py        # 练习记录与统计
│       ├── practice_ui.py             # 练习页面逻辑（抽离自 Practice 页）
│       ├── ai_chat.py                 # AI 问答模块
│       ├── cache.py                   # 缓存层（考试日期、题目统计等）
│       ├── pdf_parser.py              # PDF 解析模块（markitdown + PyMuPDF）
│       └── pdf_parser_old.py          # PDF 解析旧版（备用）
├── data/
│   └── practice_log.db                # 练习记录数据库（自动生成）
├── past_exam/                         # 历年试卷 PDF（不入库）
├── tests/
│   └── test_practice_tracker.py       # 练习记录模块测试
├── .env                               # AI 配置（需自行填写，不入库）
├── run.bat                            # Windows 一键启动脚本
├── test_app.py                        # 应用自检脚本
├── requirements.txt                   # Python 依赖
├── pytest.ini                         # 测试配置
└── CLAUDE.md                          # Claude Code 开发指南
```

## 添加题目

### 方式一：PDF 导入（推荐）

在题库管理页面上传 GESP 历年真题 PDF，系统自动解析题目并导入到 `question_bank/` 目录下的 JSON 文件。

### 方式二：手动编辑 JSON

在题库管理页面点击"添加题目"，编辑以下模板：

**选择题：**

```json
{
  "id": "7",
  "knowledge_points": ["变量与数据类型"],
  "type": "single_choice",
  "question": "题目内容",
  "options": {
    "A": "选项 A",
    "B": "选项 B",
    "C": "选项 C",
    "D": "选项 D"
  },
  "answer": "A",
  "explanation": "解析内容"
}
```

**判断题：**

```json
{
  "id": "8",
  "knowledge_points": ["变量与数据类型"],
  "type": "true_false",
  "question": "题目内容",
  "answer": "true",
  "explanation": "解析内容"
}
```

> **注意：** `knowledge_points` 为 JSON 数组格式（如 `["变量与数据类型"]`），不是裸字符串。

## 测试

运行单元测试：

```bash
python -m pytest tests/ -v
```

运行应用自检：

```bash
python test_app.py
```

## 常见问题

### 启动时出现 ModuleNotFoundError

确保设置了 PYTHONPATH：

```cmd
set PYTHONPATH=%cd%
streamlit run app/0_Overview.py
```

### AI 功能不可用

检查 `.env` 文件是否配置了正确的 API Key。未配置时其他功能不受影响。

### 练习记录丢失

练习记录保存在 `data/practice_log.db`，确保该文件没有被删除。

### 题库索引异常

题库索引存储在 `data/question_bank_index.db`。如果题目数据异常，可以删除该文件，系统会在下次启动时自动重建索引。

## 技术栈

- **前端**: Streamlit + Plotly + streamlit-aggrid
- **后端**: Python 3.8+
- **数据库**: SQLite（练习记录 + 题目索引）
- **PDF 解析**: markitdown + PyMuPDF
- **AI**: OpenAI 兼容 API（默认 DeepSeek）
- **测试**: pytest

## License

MIT License

---

> 本内容由 Coze AI 生成，请遵循相关法律法规及《人工智能生成合成内容标识办法》使用与传播。
