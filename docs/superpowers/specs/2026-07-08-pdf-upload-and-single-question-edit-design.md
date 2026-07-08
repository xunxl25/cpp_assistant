# PDF批量上传和单题编辑功能设计文档

**日期**: 2026-07-08
**状态**: 设计阶段
**作者**: ZCode AI Assistant

---

## 1. 概述

### 1.1 目标
为 C++ 做题助手题库管理系统添加两个核心功能：
1. **批量PDF上传**：支持批量上传考试PDF，自动解析元数据、查重、LLM解析题目、生成JSON文件
2. **单题编辑**：支持搜索、选择和编辑单个题目，替代原有全量JSON编辑方式

### 1.2 背景
- 当前系统：题库以JSON格式存储在 `question_bank/` 目录，PDF存储在 `past_exam/` 子目录中
- 现有问题：
  - 添加新题目需要手动编辑JSON，效率低
  - PDF文件组织混乱（子目录结构不一致）
  - 无法快速编辑单个题目，必须处理整个JSON文件
- 用户需求：批量上传PDF并自动解析，快速定位并编辑单个题目

---

## 2. 总体架构

### 2.1 系统架构

```
题库管理页面 (app/pages/3_Question_bank_manage.py)
├── 现有功能
│   ├── 题库概览（统计、索引管理）
│   └── 题库浏览（表格展示）
├── 改进功能
│   └── 单题编辑（替代原有全量JSON编辑）
│       ├── 搜索/筛选题目（支持ID或关键字）
│       ├── 选择题目（下拉选择或表格点击）
│       ├── 编辑单题JSON
│       └── 保存更新（替换原JSON中的对应题目）
└── 新增功能
    └── 批量PDF上传
        ├── 文件上传区（支持多文件选择）
        ├── 元数据解析与编辑（基于markitdown）
        ├── 查重验证
        ├── LLM内容解析
        └── 批量保存与索引刷新
```

### 2.2 核心组件

| 组件 | 路径 | 职责 |
|------|------|------|
| PDF解析模块 | `app/core/pdf_parser.py` | PDF转Markdown、元数据提取、查重、题目解析 |
| 题目加载器（扩展） | `app/core/question_loader.py` | 单题更新、题目搜索 |
| 题库管理页面（重构） | `app/pages/3_Question_bank_manage.py` | UI交互、流程编排 |
| PDF存储 | `past_exam/` | 扁平化存储重命名后的PDF |
| JSON存储 | `question_bank/` | 存储解析后的题目JSON |
| 索引存储 | `data/question_bank_index.db` | SQLite索引 |

---

## 3. 详细设计

### 3.1 批量PDF上传功能

#### 3.1.1 文件组织方案

**目录结构（扁平化）：**
```
cpp_assistant/
├── past_exam/                    # PDF存储目录（扁平化）
│   ├── gesp-4-2606.pdf
│   ├── csp-A-sample.pdf
│   └── ...
└── question_bank/                # JSON存储目录
    ├── gesp-4-2606.json
    ├── csp-A-sample.json
    └── ...
```

**文件命名规范：**
- **格式**：`{type}-{level}-{date}.{ext}`
- **type**: 考试类型（gesp, csp, ccf等，小写）
- **level**: 级别（数字1-8或字母A/B/C）
- **date**: 日期（yymm格式如2606）或特殊标识（sample）

**示例：**
- PDF: `gesp-4-2606.pdf`
- JSON: `gesp-4-2606.json`
- 样题: `gesp-1-sample.pdf`

#### 3.1.2 数据流程

```
1. 用户选择多个PDF文件
   ↓
2. 点击"解析元数据"按钮
   ├─ PDF → markitdown → Markdown
   ├─ LLM解析Markdown提取 type/level/date
   ├─ 生成标准文件名：{type}-{level}-{date}
   └─ 检查 past_exam/ 和 question_bank/ 是否存在同名文件
   ↓
3. 展示表格（可编辑）
   | 原文件名 | Type | Level | Date | 状态 | 操作 |
   | exam.pdf | GESP | 4 | 2606 | ⚠️ 已存在 | 跳过 |
   | test.pdf | CSP  | A | sample| ✅ 新题 | 编辑 |
   ↓
4. 用户编辑表格中的解析结果（可选）
   ↓
5. 点击"确认无误，开始解析题目"
   ├─ 对"✅ 新题"的文件调用LLM完整解析
   └─ 展示生成的JSON预览
   ↓
6. 用户检查JSON预览，点击"保存所有新题"
   ├─ 重命名PDF文件，保存到 past_exam/
   ├─ 保存JSON文件到 question_bank/
   └─ 刷新题库索引（调用 build_question_bank_index()）
```

#### 3.1.3 UI布局

```
┌─────────────────────────────────────────────────────────────┐
│ 📤 批量PDF上传                                              │
├─────────────────────────────────────────────────────────────┤
│ 选择PDF文件：                                                │
│ [拖拽或点击选择多个PDF]                                     │
│ [支持 .pdf 格式，最多同时上传 20 个文件]                    │
├─────────────────────────────────────────────────────────────┤
│ [🔍 解析元数据]  [📋 批量粘贴文件名列表]                    │
├─────────────────────────────────────────────────────────────┤
│ 元数据解析结果（可编辑表格）                                 │
│ | 原文件名 | Type | Level | Date | 状态 | 解析进度 |       │
│ | exam.pdf  | GESP | 4     | 2606  | ⚠️ 已存在 | -      |       │
│ | test.pdf  | CSP  | A     | sample| ✅ 新题   | -      |       │
│ [表格支持直接编辑，状态列只读]                              │
├─────────────────────────────────────────────────────────────┤
│ [✅ 确认无误，开始解析题目]                                 │
│ [进度条: ████████░░ 80% - 正在解析第 8/10 题]              │
├─────────────────────────────────────────────────────────────┤
│ JSON 预览（仅显示新题）                                      │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ [                                                        │ │
│ │   {                                                      │ │
│ │     "id": "gesp-4-2606-1",                              │ │
│ │     "exam": {...},                                      │ │
│ │     "knowledge_points": ["数组", "循环"],               │ │
│ │     ...                                                  │ │
│ │   },                                                     │ │
│ │   ...                                                    │ │
│ │ ]                                                        │ │
│ └─────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│ [💾 保存所有新题]  [🔄 重新解析]  [🗑️ 清空]               │
│ [处理报告：成功 8 个，跳过 2 个，失败 0 个]                 │
└─────────────────────────────────────────────────────────────┘
```

#### 3.1.4 核心模块设计：`app/core/pdf_parser.py`

```python
"""PDF解析模块"""
from markitdown import MarkItDown
from typing import Dict, List, Optional
from pathlib import Path

def pdf_to_markdown(pdf_file) -> str:
    """
    将PDF转换为Markdown格式

    Args:
        pdf_file: 文件路径或bytes

    Returns:
        Markdown文本
    """
    md_converter = MarkItDown()
    result = md_converter.convert(pdf_file)
    return result.text_content

def parse_pdf_metadata(pdf_file) -> Dict[str, str]:
    """
    解析PDF的基本元数据

    Args:
        pdf_file: 文件路径或bytes

    Returns:
        {"type": "GESP", "level": "4", "date": "2606", "confidence": 0.9}
    """
    markdown_text = pdf_to_markdown(pdf_file)
    # 取前几行（标题区域）
    header = "\n".join(markdown_text.split("\n")[:20])

    # 调用LLM解析
    prompt = f"""
从这份考试文档中提取以下信息：
1. 考试类型（GESP/CSP/CCF等，返回小写）
2. 考试级别（数字1-8或字母A/B/C，保持原格式）
3. 考试日期（格式：yymm，如2506；若是样题则填"sample"）

文档标题：
{header}

返回JSON格式：{{"type": "gesp", "level": "4", "date": "2606"}}
"""
    # LLM调用逻辑...
    return metadata

def check_duplicate(type: str, level: str, date: str) -> bool:
    """
    检查 past_exam/ 和 question_bank/ 是否存在同名文件

    Args:
        type: 考试类型
        level: 级别
        date: 日期

    Returns:
        True if duplicate exists
    """
    filename = f"{type}-{level}-{date}"
    pdf_exists = Path(f"past_exam/{filename}.pdf").exists()
    json_exists = Path(f"question_bank/{filename}.json").exists()
    return pdf_exists or json_exists

def parse_pdf_questions(pdf_file, metadata: Dict[str, str]) -> List[Dict]:
    """
    调用LLM完整解析PDF中的题目

    Args:
        pdf_file: 文件路径或bytes
        metadata: 元数据 {"type": "gesp", "level": "4", "date": "2606"}

    Returns:
        题目列表
    """
    markdown_text = pdf_to_markdown(pdf_file)

    # 构建ID前缀
    id_prefix = f"{metadata['type']}-{metadata['level']}-{metadata['date']}"

    prompt = f"""
解析这份考试文档中的所有题目，返回JSON数组格式。

文档内容：
{markdown_text}

返回格式示例：
[
  {{
    "id": "{id_prefix}-1",
    "exam": {{
      "type": "{metadata['type'].upper()}",
      "level": {metadata['level']},
      "date": "{metadata['date']}"
    }},
    "knowledge_points": ["数组", "循环"],
    "type": "single_choice",
    "question": "题目内容",
    "options": {{"A": "选项A", "B": "选项B", "C": "选项C", "D": "选项D"}},
    "answer": "A",
    "explanation": "解析内容"
  }}
]

注意：
- ID格式必须为 {id_prefix}-序号
- type字段：single_choice（选择题）或 judgment（判断题）
- 判断题不需要options字段，answer为"正确"或"错误"
"""
    # LLM调用逻辑...
    return questions

def generate_filename(type: str, level: str, date: str) -> str:
    """
    生成标准文件名

    Args:
        type: 考试类型
        level: 级别
        date: 日期

    Returns:
        {type}-{level}-{date}
    """
    return f"{type}-{level}-{date}"

def validate_metadata(type: str, level: str, date: str) -> tuple[bool, str]:
    """
    验证元数据格式

    Args:
        type: 考试类型
        level: 级别
        date: 日期

    Returns:
        (是否有效, 错误信息)
    """
    if not type or len(type) < 2:
        return False, "考试类型无效"

    # 级别可以是数字或字母
    if not level:
        return False, "级别不能为空"

    # 日期检查：yymm格式或"sample"
    if date != "sample" and not (len(date) == 4 and date.isdigit()):
        return False, "日期格式错误，应为yymm格式（如2606）或sample"

    return True, ""
```

#### 3.1.5 错误处理

| 错误类型 | 触发条件 | 处理方式 | 用户提示 |
|---------|---------|---------|---------|
| PDF解析失败 | markitdown转换失败 | 标记"❌ 解析失败"，跳过 | "无法解析文件内容，可能格式损坏" |
| 元数据提取失败 | LLM无法提取或置信度低 | 使用默认值，允许手动修正 | 表格中显示红色警告 |
| 元数据格式无效 | 类型/级别/日期不符合规范 | 阻止继续，要求修正 | "元数据格式错误：具体原因" |
| 查重发现重复 | 同名文件已存在 | 标记"⚠️ 已存在"，跳过 | "文件已存在，已自动跳过" |
| LLM解析失败 | API错误或超时 | 标记"❌ 解析失败"，跳过 | "题目解析失败，请稍后重试" |
| JSON格式错误 | LLM返回格式不正确 | 标记"❌ 格式错误" | "生成的JSON格式不正确" |
| 保存失败 | 文件权限或磁盘空间 | 标记"❌ 保存失败" | "保存时出错：具体错误信息" |
| 索引刷新失败 | 索引数据库错误 | 警告提示，建议手动刷新 | "索引刷新失败，请手动点击刷新按钮" |

### 3.2 单题编辑功能

#### 3.2.1 功能概述

**替换原有**：全量JSON编辑（`st.text_area` 显示所有题目）

**改进为**：
- 搜索题目（支持ID或关键字）
- 选择题目（下拉或点击）
- 只显示选中题目的JSON
- 保存时只更新该题目

#### 3.2.2 UI布局

```
┌─────────────────────────────────────────────────────────────┐
│ 🔍 单题编辑                                                 │
├─────────────────────────────────────────────────────────────┤
│ 方式1：搜索题目                                              │
│ 搜索框：[ID或题目内容关键字]              [🔍 搜索]      │
│ 方式2：直接输入ID                                            │
│ 题目ID：[gesp-4-2606-1]                 [📂 加载]        │
├─────────────────────────────────────────────────────────────┤
│ 当前选中：gesp-4-2606-1（第 3/45 题）                        │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ {                                                        │ │
│ │   "id": "gesp-4-2606-1",                                │ │
│ │   "exam": {                                              │ │
│ │     "type": "GESP",                                      │ │
│ │     "level": 4,                                          │ │
│ │     "date": "2606"                                       │ │
│ │   },                                                     │ │
│ │   "knowledge_points": ["数组", "循环"],                 │ │
│ │   "type": "single_choice",                              │ │
│ │   "question": "以下哪种数据结构支持随机访问？",          │ │
│ │   "options": {                                           │ │
│ │     "A": "链表",                                         │ │
│ │     "B": "栈",                                           │ │
│ │     "C": "数组",                                         │ │
│ │     "D": "队列"                                          │ │
│ │   },                                                     │ │
│ │   "answer": "C",                                         │ │
│ │   "explanation": "数组支持通过下标随机访问，时间复杂度O(1)" │ │
│ │ }                                                        │ │
│ └─────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│ [💾 保存修改]  [🔄 重新加载]  [◀ 上一题]  [下一题 ▶]      │
│ [保存到：question_bank/gesp-4-2606.json]                   │
└─────────────────────────────────────────────────────────────┘
```

#### 3.2.3 核心模块扩展：`app/core/question_loader.py`

**新增函数：**

```python
def search_questions(questions: List[Dict], keyword: str) -> List[Dict]:
    """
    根据ID或题目内容搜索题目

    Args:
        questions: 题目列表
        keyword: 搜索关键字（ID或题目内容）

    Returns:
        匹配的题目列表
    """
    results = []
    keyword_lower = keyword.lower()

    for q in questions:
        # 精确匹配ID
        if q.get("id", "").lower() == keyword_lower:
            results.append(q)
            continue

        # 模糊匹配题目内容
        question_text = q.get("question", "")
        if keyword_lower in question_text.lower():
            results.append(q)
            continue

        # 匹配知识点
        kps = q.get("knowledge_points", [])
        for kp in kps:
            if keyword_lower in kp.lower():
                results.append(q)
                break

    return results

def update_question_in_file(file_path: str, updated_question: Dict) -> tuple[bool, str]:
    """
    更新单个题目到JSON文件中

    Args:
        file_path: JSON文件路径
        updated_question: 更新后的题目（必须包含id字段）

    Returns:
        (成功/失败, 错误信息)
    """
    try:
        # 加载原文件
        questions = load_questions(file_path)

        # 验证必填字段
        required_fields = ["id", "knowledge_points", "type", "question", "answer", "explanation"]
        for field in required_fields:
            if field not in updated_question:
                return False, f"缺少字段: {field}"

        if not isinstance(updated_question.get("knowledge_points"), list):
            return False, "knowledge_points 必须是列表格式"

        if updated_question["type"] == "single_choice" and "options" not in updated_question:
            return False, "选择题缺少 options 字段"

        # 查找并替换题目
        question_id = updated_question["id"]
        found = False

        for idx, q in enumerate(questions):
            if q["id"] == question_id:
                questions[idx] = updated_question
                found = True
                break

        if not found:
            return False, f"未找到ID为 {question_id} 的题目"

        # 保存文件
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(questions, f, ensure_ascii=False, indent=2)

        # 刷新索引
        build_question_bank_index()

        return True, ""

    except json.JSONDecodeError as e:
        return False, f"JSON格式错误: {e}"
    except Exception as e:
        return False, f"保存失败: {e}"

def get_question_by_id_from_all(question_id: str, question_bank_dir: str = "question_bank") -> tuple[Optional[Dict], Optional[str]]:
    """
    在所有题库文件中查找指定ID的题目

    Args:
        question_id: 题目ID
        question_bank_dir: 题库目录

    Returns:
        (题目字典, 文件路径) 或 (None, None)
    """
    json_files = glob.glob(str(Path(question_bank_dir) / "*.json"))

    for json_file in json_files:
        try:
            questions = load_questions(json_file)
            for q in questions:
                if q["id"] == question_id:
                    return q, json_file
        except Exception:
            continue

    return None, None
```

#### 3.2.4 错误处理

| 错误类型 | 触发条件 | 处理方式 | 用户提示 |
|---------|---------|---------|---------|
| ID不存在 | 搜索无结果 | 提示重新输入或搜索 | "未找到指定ID的题目，请检查ID或使用关键字搜索" |
| 搜索无结果 | 关键字不匹配 | 显示"无结果"提示 | "未找到匹配的题目，请尝试其他关键字" |
| JSON格式错误 | 编辑内容格式不正确 | 显示具体错误位置和行号 | "JSON格式错误：第X行，具体原因" |
| 缺少必填字段 | 用户删除了必要字段 | 列出缺失字段 | "缺少必填字段：knowledge_points" |
| 数据类型错误 | knowledge_points不是列表 | 验证失败 | "knowledge_points 必须是数组格式，例如：[\"数组\", \"循环\"]" |
| 保存失败 | 文件权限或磁盘空间 | 回滚编辑，保留原内容 | "保存失败，请重试。错误信息：具体错误" |

---

## 4. 依赖和技术栈

### 4.1 新增依赖

| 包名 | 版本 | 用途 |
|------|------|------|
| markitdown | >=0.0.1 | PDF转Markdown |
| pymupdf | 最新 | markitdown的PDF处理依赖 |

### 4.2 更新 `requirements.txt`

```
streamlit>=1.28.0
openai  # LLM API
markitdown>=0.0.1  # 新增
pymupdf  # 新增，PDF处理
```

### 4.3 环境变量配置

```bash
# .env 文件
OPENAI_API_KEY=your_api_key_here
LLM_MODEL=gpt-4o  # 或其他模型
MAX_PDF_SIZE_MB=10  # 最大PDF文件大小限制
```

---

## 5. 测试计划

### 5.1 单元测试

**`test_pdf_parser.py`:**
- 测试 `pdf_to_markdown()` - 各种PDF格式转换
- 测试 `parse_pdf_metadata()` - 不同考试类型、级别格式
- 测试 `check_duplicate()` - 重复/不重复场景
- 测试 `generate_filename()` - 边界情况（特殊字符、空值）
- 测试 `validate_metadata()` - 各种无效输入

**`test_question_loader.py`:**
- 测试 `search_questions()` - ID匹配、内容匹配、无匹配
- 测试 `update_question_in_file()` - 替换成功/失败场景
- 测试 `get_question_by_id_from_all()` - 跨文件查找

### 5.2 集成测试

**批量上传流程测试：**
1. 上传单个新PDF → 验证保存成功 → 验证索引更新
2. 上传多个PDF（包含重复）→ 验证跳过逻辑 → 验证报告正确
3. 上传格式错误的PDF → 验证错误处理 → 验证不影响其他文件
4. 上传后手动修改元数据 → 验证最终文件名正确
5. 上传大文件（>50页）→ 验证解析性能

**单题编辑测试：**
1. 搜索题目 → 选择题目 → 编辑JSON → 保存 → 验证原文件更新
2. 搜索不存在ID → 验证错误提示
3. 编辑JSON格式错误 → 验证保存失败提示
4. 使用"上一题/下一题"导航 → 验证跳转正确
5. 修改知识点 → 验证索引刷新后筛选正确

### 5.3 端到端测试

**完整工作流：**
1. 上传多个PDF
2. 解析元数据并查重
3. 编辑解析结果
4. LLM完整解析
5. 预览JSON
6. 保存并刷新索引
7. 在单题编辑中修改某道题
8. 验证题库浏览页面显示正确

### 5.4 性能测试

- **并发上传测试**：同时上传10+ PDF文件
- **大文件测试**：上传超过50页的考试PDF
- **索引刷新性能**：题库包含100+ 题目时刷新速度
- **LLM调用性能**：解析10题的平均时间和成本

---

## 6. 部署考虑

### 6.1 目录初始化

**启动脚本中添加目录检查：**
```python
# 确保必要的目录存在
for dir_name in ["past_exam", "question_bank", "data", "temp"]:
    Path(dir_name).mkdir(exist_ok=True)
```

### 6.2 配置管理

**新增配置项（`config.py`）：**
```python
import os

# LLM配置
LLM_API_KEY = os.getenv("OPENAI_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o")

# 文件处理配置
MAX_PDF_SIZE_MB = 10
TEMP_DIR = "temp"
QUESTION_BANK_DIR = "question_bank"
PAST_EXAM_DIR = "past_exam"

# 索引配置
INDEX_DB_PATH = "data/question_bank_index.db"
```

### 6.3 错误日志

**扩展日志系统：**
```python
import logging

logging.basicConfig(
    filename='logs/question_bank.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def log_upload(file_name: str, status: str, error: str = None):
    """记录上传日志"""
    logging.info(f"Upload: {file_name}, Status: {status}, Error: {error}")

def log_llm_call(tokens_used: int, cost: float):
    """记录LLM调用成本"""
    logging.info(f"LLM: Tokens={tokens_used}, Cost=${cost:.4f}")
```

### 6.4 数据迁移

**现有数据迁移脚本：**
```python
# scripts/migrate_pdfs.py
"""
将 past_exam/ 下的子目录结构迁移到扁平化结构
例如：past_exam/gesp4/2606.pdf → past_exam/gesp-4-2606.pdf
"""
from pathlib import Path
import shutil

def migrate_pdf_structure():
    old_dir = Path("past_exam - 副本")  # 备份目录
    new_dir = Path("past_exam")

    for subfolder in old_dir.iterdir():
        if subfolder.is_dir():
            # 解析目录名获取type和level
            # 例如：gesp4 → type="gesp", level="4"
            folder_name = subfolder.name

            if folder_name.startswith("gesp"):
                level = folder_name[4:]  # 提取数字
                type_part = "gesp"
            else:
                continue  # 跳过无法解析的目录

            for pdf_file in subfolder.glob("*.pdf"):
                # 从文件名提取date
                date = pdf_file.stem  # 例如：2606

                # 生成新文件名
                new_filename = f"{type_part}-{level}-{date}.pdf"
                new_path = new_dir / new_filename

                # 复制文件
                shutil.copy2(pdf_file, new_path)
                print(f"Migrated: {pdf_file} → {new_path}")

if __name__ == "__main__":
    migrate_pdf_structure()
```

---

## 7. 后续扩展

### 7.1 短期扩展（本版本后续）

1. **进度可视化**：LLM解析时显示更详细的进度（"正在解析第3/10题"）
2. **解析历史**：记录已解析的PDF，避免重复解析
3. **批量删除**：在题库管理中支持批量删除题目
4. **模板编辑**：为不同考试类型提供不同的JSON模板

### 7.2 中期扩展

1. **题目去重**：不仅查重文件名，还检查题目内容是否重复（基于题目文本相似度）
2. **知识点自动标注**：LLM自动为新题目推荐知识点，用户确认
3. **批量导出**：支持导出选中题目为PDF或Word格式
4. **OCR支持**：支持扫描版PDF的OCR识别和解析

### 7.3 长期扩展

1. **AI批改**：用户提交答案后，AI自动批改并给出反馈
2. **错题分析**：基于用户答题历史，AI分析薄弱知识点并推荐练习
3. **智能推荐**：根据用户水平和薄弱环节，智能推荐练习题目
4. **多语言支持**：支持中文、英文等多种语言的题目解析

---

## 8. 风险和挑战

### 8.1 技术风险

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| LLM解析不准确 | 生成错误的JSON | 增加用户确认步骤，提供编辑功能 |
| markitdown转换失败 | 无法处理某些PDF格式 | 提供错误提示，建议用户手动转换 |
| 文件名冲突 | 重复题目覆盖 | 严格查重，跳过已存在文件 |
| 索引刷新慢 | 大量题目时性能下降 | 增量更新索引，而非全量重建 |

### 8.2 用户体验风险

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| LLM调用慢 | 用户等待时间长 | 显示进度条，提供预估时间 |
| 解析结果错误 | 用户需要手动修正 | 提供可编辑表格，降低门槛 |
| 批量操作失败率高 | 影响整体效率 | 增加详细错误报告，支持部分重试 |

### 8.3 数据安全风险

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| PDF包含敏感信息 | 隐私泄露 | 提醒用户不要上传敏感文件 |
| JSON格式错误 | 程序崩溃 | 严格的格式验证和错误处理 |
| 数据丢失 | 保存失败 | 自动备份原始文件 |

---

## 9. 成功指标

### 9.1 功能指标

- [ ] 支持批量上传PDF（最多20个文件）
- [ ] 自动解析元数据准确率 >90%
- [ ] 查重准确率 100%
- [ ] LLM题目解析成功率 >85%
- [ ] 单题编辑响应时间 <1秒

### 9.2 性能指标

- [ ] 单个PDF解析时间 <30秒（元数据提取）
- [ ] 完整题目解析平均时间 <2分钟（10题）
- [ ] 索引刷新时间 <5秒（100题）
- [ ] 搜索响应时间 <500ms

### 9.3 用户体验指标

- [ ] 首次使用无需文档即可完成上传
- [ ] 错误提示清晰易懂
- [ ] 批量操作提供详细进度反馈
- [ ] 支持部分失败时的重试机制

---

## 10. 实施计划

### 10.1 开发阶段

**阶段1：基础功能开发（1-2天）**
- [ ] 创建 `app/core/pdf_parser.py` 模块
- [ ] 实现 markitdown 集成和元数据提取
- [ ] 实现查重和文件名生成逻辑
- [ ] 编写单元测试

**阶段2：UI开发（1-2天）**
- [ ] 重构 `app/pages/3_Question_bank_manage.py`
- [ ] 实现批量上传UI（文件选择、元数据编辑表格）
- [ ] 实现单题编辑UI（搜索、选择、编辑）
- [ ] 实现进度条和状态展示

**阶段3：LLM集成和完整流程（1-2天）**
- [ ] 实现LLM元数据解析
- [ ] 实现LLM题目解析
- [ ] 实现JSON预览和保存逻辑
- [ ] 实现索引自动刷新

**阶段4：测试和优化（1天）**
- [ ] 单元测试和集成测试
- [ ] 端到端测试
- [ ] 性能优化
- [ ] 错误处理完善

### 10.2 部署阶段

**阶段5：文档和部署（0.5天）**
- [ ] 更新用户文档
- [ ] 数据迁移脚本
- [ ] 部署到生产环境
- [ ] 监控和日志配置

---

## 11. 附录

### 11.1 LLM Prompt模板

**元数据提取Prompt：**
```python
METADATA_PROMPT = """
从这份考试文档中提取以下信息：
1. 考试类型（GESP/CSP/CCF等，返回小写）
2. 考试级别（数字1-8或字母A/B/C，保持原格式）
3. 考试日期（格式：yymm，如2506；若是样题则填"sample"）

文档标题：
{header}

返回JSON格式：{{"type": "gesp", "level": "4", "date": "2606"}}
"""
```

**题目解析Prompt：**
```python
QUESTIONS_PROMPT = """
解析这份考试文档中的所有题目，返回JSON数组格式。

文档内容：
{markdown_text}

返回格式示例：
[
  {{
    "id": "{id_prefix}-1",
    "exam": {{
      "type": "{exam_type}",
      "level": {exam_level},
      "date": "{exam_date}"
    }},
    "knowledge_points": ["数组", "循环"],
    "type": "single_choice",
    "question": "题目内容",
    "options": {{"A": "选项A", "B": "选项B", "C": "选项C", "D": "选项D"}},
    "answer": "A",
    "explanation": "解析内容"
  }}
]

注意：
- ID格式必须为 {id_prefix}-序号
- type字段：single_choice（选择题）或 judgment（判断题）
- 判断题不需要options字段，answer为"正确"或"错误"
- knowledge_points必须是数组格式
"""
```

### 11.2 数据结构示例

**题目JSON结构：**
```json
{
  "id": "gesp-4-2606-1",
  "exam": {
    "type": "GESP",
    "level": 4,
    "date": "2606"
  },
  "knowledge_points": ["数组", "循环"],
  "type": "single_choice",
  "question": "以下哪种数据结构支持随机访问？",
  "options": {
    "A": "链表",
    "B": "栈",
    "C": "数组",
    "D": "队列"
  },
  "answer": "C",
  "explanation": "数组支持通过下标随机访问，时间复杂度O(1)"
}
```

**索引表结构（SQLite）：**
```sql
CREATE TABLE question_index (
    question_id TEXT PRIMARY KEY,
    exam_type TEXT NOT NULL,
    exam_level TEXT NOT NULL,
    exam_date TEXT NOT NULL,
    knowledge_points TEXT NOT NULL,
    frequency TEXT NOT NULL,
    source_file TEXT NOT NULL,
    question_index INTEGER NOT NULL
)
```

### 11.3 参考资源

- [markitdown文档](https://github.com/microsoft/markitdown)
- [Streamlit文档](https://docs.streamlit.io/)
- [OpenAI API文档](https://platform.openai.com/docs)
- [现有代码库](../)

---

**文档版本**: 1.0
**最后更新**: 2026-07-08
**状态**: 待用户审核