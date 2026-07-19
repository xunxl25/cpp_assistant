"""PDF 解析模块

将考试 PDF 转为 Markdown（基于 markitdown），再用 LLM 提取元数据与题目。
LLM 调用复用 app.core.ai_chat.call_llm（同样的 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL）。

题目格式遵循本仓库既有 schema（见 question_bank/*.json 与 practice_ui.py）：
- type: "single_choice" 或 "true_false"（注意：不是 spec 文档里写的 "judgment"）
- 判断题 answer 为 "true" / "false"（不是 "正确"/"错误"）
- 判断题不需要 options 字段
"""
import json
import re
from typing import Dict, List, Tuple
from pathlib import Path

from app.core.ai_chat import call_llm

# 目录常量（与 question_loader.py 保持一致的相对路径风格）
PAST_EXAM_DIR = "past_exam"
QUESTION_BANK_DIR = "question_bank"

# 题目必填字段
REQUIRED_FIELDS = ["id", "knowledge_points", "type", "question", "answer", "explanation"]
VALID_TYPES = {"single_choice", "true_false"}


def pdf_to_markdown(pdf_path) -> str:
    """
    将 PDF 转换为 Markdown 文本

    Args:
        pdf_path: 文件路径（str 或 Path）

    Returns:
        Markdown 文本

    Raises:
        Exception: markitdown 转换失败时抛出，由调用方捕获标记失败
    """
    from markitdown import MarkItDown

    md_converter = MarkItDown()
    result = md_converter.convert(str(pdf_path))
    return result.text_content


def _extract_json(text: str):
    """
    从 LLM 输出中提取 JSON（容忍 ```json 代码块、前后说明文字）

    Returns:
        解析后的对象（dict/list）或 None
    """
    if not text:
        return None

    # 去除 ```json ... ``` 代码块
    fence = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    candidate = fence.group(1) if fence else text

    # 直接尝试
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass

    # 回退：截取第一个 { ... } 或 [ ... ]
    for pattern, opener, closer in [
        (r"\[.*\]", "[", "]"),
        (r"\{.*\}", "{", "}"),
    ]:
        match = re.search(pattern, candidate, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                continue

    return None


def parse_pdf_metadata(markdown_text: str) -> Dict[str, str]:
    """
    解析 PDF 的基本元数据（基于 Markdown 文本）

    Args:
        markdown_text: PDF 转换后的 Markdown

    Returns:
        {"type": "gesp", "level": "4", "date": "2606"}；解析失败时返回空 dict
    """
    header = "\n".join(markdown_text.split("\n")[:20])

    prompt = f"""从这份考试文档中提取以下信息：
1. 考试类型（GESP/CSP/CCF等，返回小写，如 gesp）
2. 考试级别（数字1-8或字母A/B/C，保持原格式，如 4）
3. 考试日期（格式：yyyymm，如 202606；若是样题则填 "sample"）

文档标题区域：
{header}

只返回 JSON，不要额外说明：{{"type": "gesp", "level": "4", "date": "2606"}}
"""
    try:
        raw = call_llm(prompt, system="你是一个元数据提取助手，只输出 JSON。", max_tokens=800)
    except Exception:
        return {}

    data = _extract_json(raw)
    if not isinstance(data, dict):
        return {}

    return {
        "type": str(data.get("type", "")).lower().strip(),
        "level": str(data.get("level", "")).strip(),
        "date": str(data.get("date", "")).strip(),
    }


def generate_filename(type: str, level: str, date: str) -> str:
    """生成标准文件名（不含扩展名）：{type}-{level}-{date}"""
    return f"{type}-{level}-{date}"


def validate_metadata(type: str, level: str, date: str) -> Tuple[bool, str]:
    """
    验证元数据格式

    Returns:
        (是否有效, 错误信息)
    """
    if not type or len(type) < 2:
        return False, "考试类型无效"

    if not level:
        return False, "级别不能为空"

    if date != "sample" and not (len(date) == 6 and date.isdigit()):
        return False, "日期格式错误，应为 yyyymm 格式（如 202606）或 sample"

    return True, ""


def check_duplicate(type: str, level: str, date: str) -> bool:
    """
    检查 past_exam/ 和 question_bank/ 是否已存在同名文件

    Returns:
        True 若存在重复
    """
    stem = generate_filename(type, level, date)
    pdf_exists = Path(f"{PAST_EXAM_DIR}/{stem}.pdf").exists()
    json_exists = Path(f"{QUESTION_BANK_DIR}/{stem}.json").exists()
    return pdf_exists or json_exists


def parse_pdf_questions(markdown_text: str, metadata: Dict[str, str]) -> List[Dict]:
    """
    调用 LLM 完整解析 PDF 中的题目

    Args:
        markdown_text: PDF 转换后的 Markdown
        metadata: {"type": "gesp", "level": "4", "date": "2606"}

    Returns:
        校验通过的题目列表；解析失败返回空列表
    """
    type_lower = metadata.get("type", "")
    level = metadata.get("level", "")
    date = metadata.get("date", "")
    id_prefix = generate_filename(type_lower, level, date)
    exam_type_upper = type_lower.upper() if type_lower else ""

    # level 尽量转 int，保持原格式失败则用字符串
    try:
        exam_level = int(level)
    except (ValueError, TypeError):
        exam_level = level

    prompt = f"""解析这份考试文档中的所有选择题和判断题，返回 JSON 数组格式。

文档内容：
{markdown_text}

返回格式（严格遵守）：
[
  {{
    "id": "{id_prefix}-1",
    "exam": {{"type": "{exam_type_upper}", "level": {exam_level}, "date": "{date}"}},
    "knowledge_points": ["数组", "循环"],
    "type": "single_choice",
    "question": "题目内容",
    "options": {{"A": "选项A", "B": "选项B", "C": "选项C", "D": "选项D"}},
    "answer": "A",
    "explanation": "解析内容"
  }}
]

注意：
- id 格式必须为 {id_prefix}-序号（序号从 1 开始）
- type 字段只能取 "single_choice"（选择题）或 "true_false"（判断题）
- 判断题（true_false）不要 options 字段，answer 为 "true" 或 "false"
- knowledge_points 必须是数组
- 只返回 JSON 数组，不要额外说明
"""
    try:
        raw = call_llm(prompt, system="你是一个题目解析助手，只输出 JSON 数组。", max_tokens=4000)
    except Exception:
        return []

    questions = _extract_json(raw)
    if not isinstance(questions, list):
        return []

    # 校验每道题
    valid = []
    for q in questions:
        if not isinstance(q, dict):
            continue
        ok, _ = validate_question(q)
        if ok:
            valid.append(q)

    return valid


def validate_question(q: Dict) -> Tuple[bool, str]:
    """
    校验单道题目格式（与 question_loader.update_question_in_file 一致）

    Returns:
        (是否有效, 错误信息)
    """
    for field in REQUIRED_FIELDS:
        if field not in q:
            return False, f"缺少字段: {field}"

    if not isinstance(q.get("knowledge_points"), list):
        return False, "knowledge_points 必须是列表格式"

    if q["type"] not in VALID_TYPES:
        return False, f"type 必须是 {VALID_TYPES} 之一"

    if q["type"] == "single_choice" and "options" not in q:
        return False, "选择题缺少 options 字段"

    if q["type"] == "true_false" and q["answer"] not in ("true", "false"):
        return False, '判断题 answer 必须为 "true" 或 "false"'

    return True, ""
