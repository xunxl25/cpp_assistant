# C++ 做题助手

一个本地运行的 C++ 做题学习应用，支持题目练习、错题复习和 AI 答疑。

## 功能特性

- ✅ **做题练习** - 支持选择题和判断题，实时反馈
- ✅ **知识点分析** - 柱状图展示题目分布和完成度
- ✅ **错题本** - 按知识点/高频错题/随机模式复习
- ✅ **题库管理** - 表格查看、JSON 编辑、实时重载
- ✅ **AI 答疑** - 智能助手解释题目和知识点

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

如不配置，AI 功能将不可用，但其他功能正常。

### 启动应用

**Windows（推荐）：**
```cmd
start.bat
```

**Windows PowerShell：**
```powershell
.\start.ps1
```

**手动启动：**
```bash
cd D:\Projects\cpp_assistant
set PYTHONPATH=D:\Projects\cpp_assistant
streamlit run app/app.py
```

### 访问应用

- 主页（做题）: http://localhost:8501
- 错题本: http://localhost:8501/错题本
- 题库管理: http://localhost:8501/题库管理

## 项目结构

```
cpp_assistant/
├── app/
│   ├── app.py              # 主应用（做题页）
│   ├── pages/
│   │   ├── 错题本.py        # 错题本页
│   │   └── 题库管理.py      # 题库管理页
│   └── core/
│       ├── question_loader.py   # 题库加载模块
│       ├── practice_tracker.py  # 练习记录模块
│       └── ai_chat.py           # AI 问答模块
├── question_bank/
│   └── gesp4-2606.json     # 示例题库
├── tests/
│   ├── test_question_loader.py
│   ├── test_practice_tracker.py
│   └── test_ai_chat.py
├── data/
│   └── practice_log.db     # 练习记录数据库（自动生成）
├── .env                    # AI 配置（需自行填写）
├── start.bat              # Windows 启动脚本
├── start.ps1              # PowerShell 启动脚本
└── test_app.py            # 应用自检脚本
```

## 添加题目

在题库管理页面，复制以下模板并编辑：

```json
{
  "id": "7",
  "knowledge_point": "知识点名称",
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

或使用判断题模板：

```json
{
  "id": "8",
  "knowledge_point": "知识点名称",
  "type": "true_false",
  "question": "题目内容",
  "answer": "true",
  "explanation": "解析内容"
}
```

## 测试

运行所有单元测试：

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
set PYTHONPATH=D:\Projects\cpp_assistant
streamlit run app/app.py
```

### AI 功能不可用

检查 `.env` 文件是否配置了正确的 API Key。

### 练习记录丢失

练习记录保存在 `data/practice_log.db`，确保该文件没有被删除。

## 技术栈

- **前端**: Streamlit
- **后端**: Python
- **数据库**: SQLite
- **AI**: OpenAI API
- **测试**: pytest

## License

MIT License