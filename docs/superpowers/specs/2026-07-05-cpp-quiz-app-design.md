# C++ 复习做题应用 — 设计文档

- **日期**：2026-07-05
- **状态**：已确认，待实现
- **作者**：用户 + ZCode 协作

## 一、项目目标

开发一个本地运行的做题小应用，用于复习 C++ 考试（GESP / CSP 等）的概念题（选择、判断）。

**核心功能**：

1. 从完整题库按知识点刷题
2. 从错题库做题（按知识点 / 高频错题 / 随机），错题本范围 = 准确率 < 75% 的题
3. 自动记录错题，跟踪作答次数、准确率
4. 答题界面内嵌 AI 问答，自动关联当前题目讨论知识点
5. 题库可随时间更新（手动添加 PDF → 程序解析生成 JSON → 可手改校对）

**非目标（YAGNI）**：

- ❌ 账户登录系统（个人单机使用）
- ❌ 云部署 / 公网访问
- ❌ 多用户数据隔离
- ❌ 题目协作编辑（直接改 JSON 文件即可）
- ❌ 打包成 .exe（`start.bat` 已足够简单）

## 二、使用场景与约束

- **使用者**：仅本人，单机使用
- **启动方式**：双击 `start.bat` → 自动启动本地服务并打开浏览器
- **数据偏好**：错题数据必须是"看得见、摸得着"的文件，能用 GUI 工具打开查看，不接受浏览器黑盒存储
- **开发者背景**：前后端浅了解，写过 R Shiny
- **优先级**：快速搭建 > UI 精美 > 技术先进性

## 三、技术栈

| 层 | 选型 | 理由 |
|---|---|---|
| 应用框架 | Python + Streamlit | 等价于 Python 版 R Shiny，学习成本最低；一个 `.py` 文件即完整应用 |
| 题库存储 | JSON 文件 | 结构化、可手改、git 友好；含代码块的题干不受多行限制 |
| 错题存储 | SQLite（单文件 `.db`） | 真实文件可用 DB Browser GUI 查看；支持按知识点/错频/准确率查询排序 |
| PDF 解析 | markitdown + 大模型 | markitdown 提取题干原文，大模型生成知识点标签和解析 |
| AI 问答 | Streamlit 内调大模型 API | key 存 `.env` 不暴露 |
| UI 风格 | Streamlit 原生组件 + `config.toml` 主题 | 无需额外 UI 库，原生即现代风格 |
| 启动 | `start.bat` 双击 | 内含 `streamlit run app/app.py`，自动开浏览器 |

**为何不选其它方案**：

- **React/Vue 前端**：UI 更精美但需学 npm/构建工具链，与"快速搭建"冲突；且纯前端错题只能 localStorage（黑盒存储，不满足"看得见的表"诉求）
- **Flask + 原生前端**：前后端分离增加复杂度，对浅背景用户负担重
- **打包 .exe**：题库更新后需重新打包，性价比低

## 四、目录结构

```
cpp_assistant/
├── past_exam/              # PDF 原始题源（保持不动）
│   ├── gesp4/2606.pdf
│   ├── gesp4 - 2503.pdf
│   └── ...
├── question_bank/          # 结构化题库（程序生成 + 可手改）
│   ├── gesp4-2606.json
│   ├── gesp4-2503.json
│   └── ...
├── builder/                # 题库构建器（一次性/偶发脚本）
│   ├── pdf_to_questions.py # PDF → markitdown → 大模型 → JSON
│   ├── prompt_templates.py # 知识点/解析生成的提示词
│   └── (读取根目录 .env)
├── app/
│   ├── app.py              # Streamlit 主入口（重定向到做题页）
│   ├── pages/
│   │   ├── 1_做题.py       # 含 AI 问答（自动关联当前题）
│   │   ├── 2_错题本.py     # accuracy < 75% 的题
│   │   └── 3_题库管理.py   # 表格查看 + 文本编辑 JSON
│   └── core/
│       ├── question_loader.py  # 读 JSON 题库
│       ├── practice_tracker.py # SQLite 练习记录读写
│       └── ai_chat.py          # 大模型调用
├── data/
│   └── practice_log.db     # SQLite 练习跟踪库（自动生成）
├── .env                    # 大模型 API key（根目录）
├── .streamlit/
│   └── config.toml         # 主题配置
├── start.bat               # 双击启动
└── requirements.txt
```

## 五、数据模型

### 5.1 题目 JSON 结构

文件命名：`question_bank/<exam_type>-<level>-<date>.json`，如 `gesp4-2606.json`。

每个文件是一个数组，元素为一道题：

**选择题**：
```json
{
  "id": "gesp4-2606-001",
  "exam": {"type": "GESP", "level": 4, "date": "2026-06"},
  "type": "single_choice",
  "knowledge_points": ["循环", "for"],
  "stem": "以下代码输出什么？\n```cpp\nfor(int i=0;i<3;i++)cout<<i;\n```",
  "options": {"A": "012", "B": "123", "C": "0 1 2", "D": "1 2 3"},
  "answer": "A",
  "explanation": "for 循环从 i=0 执行到 i<3，每次输出 i 不换行，结果为 012"
}
```

**判断题**（保留选项，固定为正确/错误，user 勾选）：
```json
{
  "id": "gesp4-2606-010",
  "exam": {"type": "GESP", "level": 4, "date": "2026-06"},
  "type": "true_false",
  "knowledge_points": ["变量作用域"],
  "stem": "在 for 循环内定义的变量，可以在循环外继续使用。",
  "options": {"正确": "正确", "错误": "错误"},
  "answer": "错误",
  "explanation": "for 循环内定义的变量作用域限于循环体内，循环外不可访问"
}
```

**字段约束**：

- `id`：全局唯一，格式 `<exam_type><level>-<date>-<seq>`，如 `gesp4-2606-001`
- `exam.type`：`GESP` / `CSP` 等
- `exam.level`：GESP 为 1-8，CSP 为 `J` / `S`
- `exam.date`：`YYYY-MM` 格式
- `type`：`single_choice` | `true_false`
- `knowledge_points`：知识点标签数组，用于按知识点刷题
- `stem`：题干，可含 Markdown 代码块（```cpp）
- `options`：选择题为 `{A,B,C,D}`；判断题固定为 `{"正确","错误"}`
- `answer`：选择题为选项 key（`A`/`B`/...），判断题为 `正确`/`错误`
- `explanation`：纯文本解析（一句话讲清原理）

### 5.2 SQLite 练习跟踪表

文件：`data/practice_log.db`，可用 [DB Browser for SQLite](https://sqlitebrowser.org/) GUI 查看。

表名 `practice_log`：记录所有练过的题（含首次答对）。错题本是它的查询子集视图，不单列成表。

```sql
CREATE TABLE IF NOT EXISTS practice_log (
  question_id       TEXT PRIMARY KEY,        -- 关联题目 JSON 的 id
  exam_type         TEXT,                    -- GESP / CSP（冗余存便于查询）
  exam_level        TEXT,                    -- 1-8 / J / S
  attempt_count     INTEGER DEFAULT 0,       -- 作答次数（含答对答错）
  wrong_count       INTEGER DEFAULT 0,       -- 答错次数
  last_wrong_answer TEXT,                    -- 只保留最近一次错误的答案
  first_wrong_at    TEXT,                    -- 首次作答时间（ISO 8601）
  last_wrong_at     TEXT,                    -- 最近答错时间（无答错则为 NULL）
  last_attempt_at   TEXT,                    -- 最近作答时间
  accuracy          REAL DEFAULT 0.0,        -- 准确率 = (attempt-wrong)/attempt
  mastered          INTEGER DEFAULT 0        -- 0/1：accuracy >= 0.75 时为 1
);
```

**设计说明**：

- **知识点不存表**：题目 JSON 是唯一真相。展示/筛选用 `question_id` 从内存题库（`@st.cache_data` 字典）查找，O(1)，无 LIKE 误匹配，题库改了分类自动同步。
- `accuracy`：应用层计算，每次作答后更新 `= (attempt_count - wrong_count) / attempt_count`
- `mastered`：应用层计算，`accuracy >= 0.75` 时置 1，否则置 0
- `last_wrong_answer`：每次答错覆盖写入，只留最近一次
- `exam_type` / `exam_level`：从题目 JSON 冗余存入，便于不 join 题库直接按考试筛选
- **mastered 重置规则**：`mastered=1` 的题若再次答错，`wrong_count++` 后重算 accuracy，若 `< 0.75` 则 `mastered` 重置为 0，重新进入错题本出题范围

**写入语义**：

- 首次作答（无论对错）→ INSERT 一行，`attempt_count=1`，答错则 `wrong_count=1` + 记 `last_wrong_answer` + `last_wrong_at`
- 再次作答 → UPDATE，`attempt_count++`，答错则 `wrong_count++` + 覆盖 `last_wrong_answer` + 更新 `last_wrong_at`
- 每次作答后重算 `accuracy` 和 `mastered`

**错题本视图**（查询，非物理表）：
```sql
SELECT * FROM practice_log WHERE wrong_count > 0 AND mastered = 0;
```
即"答错过且当前准确率未达 75%"的题。首次答对的题（`wrong_count=0`）留在表中用于完成度统计，但不进错题本。

## 六、功能流程

### 6.1 做题（`1_做题.py`）

**入口**：侧边栏配置出题范围

- 选考试类型/级别（多选）
- 选知识点（多选，可"全部"）
- 选出题模式：顺序 / 随机
- 点"开始"

**知识点概览面板**（出题前展示）：

- 柱状图：x 轴 = 知识点，y 轴 = 题目数
- 每根柱子分两段：**已练习（深色）/ 未练习（浅色）** → 直观看出完成度
- 柱顶标注该知识点准确率（有作答记录时）
- 用 `st.bar_chart` 或 plotly 实现
- 数据来源：题库（总数）+ `practice_log` 表（已练习数、准确率）

**答题界面**（每次一题）：

1. 渲染题干（`st.markdown` 支持代码块高亮）
2. 渲染选项：
   - 选择题：radio 单选
   - 判断题：radio 单选（正确/错误）
3. 提交按钮 → 判对错
4. 答错 → 自动写入/更新 `practice_log.db`（`wrong_count++`，`last_wrong_answer` 覆盖，`attempt_count++`）
5. 答对 → 若该题在表中，`attempt_count++` 并重算 `accuracy`/`mastered`；若不在表中，INSERT（`wrong_count=0`）
6. 显示答案 + 静态解析
7. 下方"讨论此题"输入框 → AI 问答（见 6.4）
8. "下一题"按钮

### 6.2 错题本（`2_错题本.py`）

**出题范围**：`SELECT * FROM practice_log WHERE wrong_count > 0 AND mastered = 0`（即答错过且当前准确率 < 75%）

**三种出题模式**：

- **按知识点**：取出题范围 question_id → 用 question_id 从内存题库查知识点 → 在应用层过滤（无 LIKE）
- **高频错题**：`ORDER BY wrong_count DESC`
- **随机**：`ORDER BY RANDOM()`

**答题流程**：同 6.1，但额外：

- 答对后显示选项："移出错题本" / "再练一次"
- "移出错题本" = 强制 `mastered = 1`（即使 accuracy 未到 75%）
- 表格视图：`st.dataframe` 展示所有错题，知识点列从题库查得。列：question_id、exam、知识点、attempt_count、wrong_count、accuracy、mastered、最近答错时间。可排序可筛选

### 6.3 题库管理（`3_题库管理.py`）

**两个功能**：

1. **表格查看**：`st.dataframe` 展示所有题目（id、exam、type、知识点、题干预览、答案），支持按知识点/考试筛选、排序、搜索
2. **文本编辑 JSON**：
   - 选择某个题库文件（如 `gesp4-2606.json`）
   - 显示其 JSON 原文于 `st.text_area`
   - 改完点"保存"→ 校验 JSON 合法性 → 覆盖原文件
   - 保存后点"重新加载题库"按钮（`st.cache_data.clear()`）让应用读到最新

**打开方式**：提供"打开题库文件夹"按钮（调用系统文件管理器），方便外部编辑器修改。

### 6.4 AI 问答（嵌在答题界面）

- 位置：每道题答题区下方
- 自动上下文：当前题的题干 + 选项 + 你的答案 + 正确答案，作为系统提示发给大模型
- 用户在输入框提问（如"为什么选 A？for 循环的执行顺序是怎样的？"）
- 调用大模型 API，流式输出回答（`st.write_stream`）
- key 从根目录 `.env` 读取

### 6.5 题库构建器（`builder/`，独立子系统）

**用途**：把新 PDF 转成结构化 JSON 题库。一次性/偶发运行，不是日常使用流程。

**命令**：
```
python builder/pdf_to_questions.py past_exam/gesp4/2606.pdf
```

**流程**：

1. 用 markitdown 把 PDF 转成 Markdown 文本
2. 调大模型，按 `prompt_templates.py` 中的提示词结构化：
   - 识别每道题（题干、选项、答案）
   - 生成知识点标签
   - 生成纯文本解析
3. 输出 `question_bank/gesp4-2606.json`
4. 容忍小错误率，生成后可手改 JSON 修复

**题库更新机制**：

1. 把新 PDF 放进 `past_exam/<exam_type><level>/<date>.pdf`
2. 跑一次 `python builder/pdf_to_questions.py <pdf路径>`
3. 生成 JSON，手改校对
4. 应用启动时自动扫描 `question_bank/*.json` 加载

## 七、缓存与刷新策略

- **题库加载**：`@st.cache_data` 缓存，避免每次交互重读 JSON
- **JSON 改动后**：题库管理页点"重新加载题库"按钮 → `st.cache_data.clear()` → 下次读取拿最新
- **错题库**：每次作答直接写 SQLite，无缓存层，实时一致
- **大模型 key**：`@st.cache_resource` 加载一次

## 八、配置文件

### 8.1 `.env`（根目录）

```
LLM_API_KEY=sk-xxxxxxxx
LLM_BASE_URL=https://api.deepseek.com    # 或其他兼容 OpenAI 协议的服务
LLM_MODEL=deepseek-chat
```

### 8.2 `.streamlit/config.toml`

```toml
[theme]
primaryColor = "#2563eb"      # 主色（蓝）
backgroundColor = "#ffffff"
secondaryBackgroundColor = "#f8fafc"
textColor = "#1e293b"
font = "sans serif"

[server]
port = 8501
headless = true
openBrowserOnLaunch = true
```

### 8.3 `start.bat`

```bat
@echo off
cd /d %~dp0
streamlit run app/app.py
```

### 8.4 `requirements.txt`

```
streamlit>=1.38
python-dotenv
openai               # 兼容 DeepSeek/智谱等 OpenAI 协议
markitdown           # PDF 解析
```

## 九、错误处理

- **JSON 解析失败**（手改出错）：题库管理页保存时校验，失败提示行号不覆盖原文件
- **题库为空**：做题页提示"请先用 builder 生成题库或检查 question_bank 目录"
- **大模型 API 失败**：AI 问答区显示错误信息，不影响做题
- **SQLite 文件锁**：单机使用不会冲突，无需处理

## 十、测试策略

- `question_loader.py`：单元测试 JSON 加载、字段校验、知识点筛选
- `practice_tracker.py`：单元测试作答记录、准确率计算、mastered 判定与重置、错题本视图查询、知识点应用层 join
- `ai_chat.py`：mock 大模型响应测试上下文拼装
- 集成测试：跑通"做题→答错→入练习库→错题本复习→答对→mastered→再次答错→mastered 重置"完整流程
- 题库构建器：用一个 PDF 跑通端到端，人工校对输出

## 十一、未来可扩展（当前不做）

- 题目支持多选/填空
- 错题本导出 PDF/打印
- 做题统计仪表盘（按知识点准确率图表）
- 题库版本管理（git tag 标记题库快照）
