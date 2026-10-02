"""PDF 解析模块

将考试 PDF 转为 Markdown（基于 markitdown），再用 LLM 提取元数据与题目。
LLM 调用复用 app.core.ai_chat.call_llm（同样的 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL）。

题目格式遵循本仓库既有 schema（见 question_bank/*.json 与 practice_ui.py）：
- type: "single_choice" 或 "true_false"
- 判断题 answer 为 "true" / "false"
- 判断题不需要 options 字段
- id 格式: {type}-{level}-{date}-sc-{n} 或 {type}-{level}-{date}-tf-{n}
"""

import json
import logging
import re
from typing import Dict, List, Tuple
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.core.ai_chat import call_llm

logger = logging.getLogger(__name__)

# 目录常量（与 question_loader.py 保持一致的相对路径风格）
PAST_EXAM_DIR = "past_exam"
QUESTION_BANK_DIR = "question_bank"

# 题目必填字段（不含 id 和 exam，这两个由后处理生成）
REQUIRED_FIELDS = ["type", "knowledge_points", "question", "answer", "explanation"]
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
    从 LLM 输出中提取 JSON（容忍json 代码块、前后说明文字）
    Returns: 解析后的对象（dict/list）或 None
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

    # 回退：截取第一个 [ ... ] 或 { ... }
    for pattern in [r"\[.*\]", r"\{.*\}"]:
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
    Args: markdown_text, PDF 转换后的 Markdown
    Returns: {"type": "gesp", "level": "4", "date": "202606"}; 解析失败时返回空
    """

    header = "\n".join(markdown_text.split("\n")[:20])

    prompt = f"""从这份考试文档中提取以下信息：
    1. 考试类型（GESP/CSP/CCF等，返回小写，如 gesp）
    2. 考试级别（数字1-8或字母A/B/C，保持原格式，如 4）
    3. 考试日期（格式：yyyymm，如 202606；若是样题则填 "sample"）

    文档标题区域：
    {header}

    只返回 JSON，不要额外说明: {{"type": "gesp", "level": "4", "date": "202606"}}
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
    Returns: (是否有效, 错误信息)
    """
    if not type or len(type) < 2:
        return False, "考试类型无效"
    if not level:
        return False, "级别不能为空"
    if date != "sample" and not (len(date) == 6 and date.isdigit()):
        return False, "日期格式错误，应为 yyyymm 格式（如 202606）或 sample"
    return True, ""


def check_duplicate(type: str, level: str, date: str) -> bool:
    """检查 past_exam/ 和 question_bank/ 是否已存在同名文件"""
    stem = generate_filename(type, level, date)
    pdf_exists = Path(f"{PAST_EXAM_DIR}/{stem}.pdf").exists()
    json_exists = Path(f"{QUESTION_BANK_DIR}/{stem}.json").exists()
    return pdf_exists or json_exists


def split_by_questions(lines: List[str], max_chars: int = 4000) -> List[str]:
    """按题号边界切分文本，确保不会在题目中间断开"""
    segments = []
    current = []
    current_len = 0
    # 匹配题号行，如 "第1题", "第 1 题", "1. ", "## 第1题" 等
    question_pattern = re.compile(r'^#*\s*第\s*\d+\s*题|^#*\s*\d+.\s')

    for line in lines:
        # 如果当前段已超长且遇到新题号，则切分
        if current_len > max_chars and question_pattern.match(line.strip()):
            segments.append("\n".join(current))
            current = []
            current_len = 0
        current.append(line)
        current_len += len(line)

    if current:
        segments.append("\n".join(current))

    return segments


def _process_segment(segment: str, seg_idx: int, total_segs: int) -> List[Dict]:
    """处理单个文本段，调用 LLM 提取题目"""

    logger.debug("[Segment %d] 输入文本长度: %d", seg_idx + 1, len(segment))

    # 2. 构造严格的 Prompt
    json_example = """
[
  {
    "type": "single_choice",
    "question": "题目内容",
    "options": {"A": "选项A", "B": "选项B", "C": "选项C", "D": "选项D"},
    "answer": "A",
    "knowledge_points": ["考点1"],
    "explanation": "解析"
  }
]
"""

    # 关键修改：强调 "直接输出 JSON"，"不要解释"，"不要代码块"
    # 答案与代码规则移植自人工解析 prompt（LLM 自答 + 代码缺失标记）
    prompt = (
        f"提取文档片段中的题目，转为 JSON 数组，并解答每道题。\n"
        f"文档内容：\n{segment}\n\n"
        f"格式要求：\n"
        f"1. 必须输出 JSON 数组，如：{json_example}\n"
        f"2. type 为 single_choice 或 true_false\n"
        f"3. 判断题 answer 为 true/false\n"
        f"4. 答案规则（重要）：PDF 转换可能丢失或错乱答案标记（√、×、A/B/C/D），"
        f"不要照抄原文标记；必须根据题干和代码逻辑自行推理作答：\n"
        f"   - 选择题：分析各选项后输出 A/B/C/D；\n"
        f"   - 判断题：分析题干正确性后输出 true/false；\n"
        f"   - explanation 中给出完整的解题依据。\n"
        f"5. 代码处理（重要）：\n"
        f"   - 题干中的 C++ 代码需恢复标准格式（换行、缩进、结构完整可编译，如 int main() {{ ... }}）；\n"
        f"   - 若代码为图片形式无法提取、内容乱码或明显残缺，则在题干末尾追加\"（参照原PDF代码）\"，"
        f"并根据题干描述、选项和上下文推断作答，同时在 explanation 中注明\"代码内容缺失，答案基于题干描述推断\"。\n"
        f"6. 直接输出 JSON 字符串，禁止输出 Markdown 标题、禁止解释、禁止思考过程。\n"
        f"直接输出 JSON："
    )

    # 3. 调用 LLM
    logger.debug("[Segment %d] 开始调用 LLM...", seg_idx + 1)
    try:
        raw = call_llm(
            prompt,
            system="You are a JSON API. You only output valid JSON arrays. No other text.",
            max_tokens=4000,
        )
        logger.debug("[Segment %d] LLM 返回长度: %d, 开头: %s, 结尾: ...%s",
                     seg_idx + 1, len(raw), raw[:100], raw[-300:])
    except Exception as e:
        logger.warning("[Segment %d] LLM 调用异常: %s", seg_idx + 1, e)
        return []

    # 5. 解析 JSON
    questions = _extract_json(raw)
    if questions is None:
        logger.warning("[Segment %d] JSON 解析失败", seg_idx + 1)
    else:
        logger.debug("[Segment %d] 成功解析题目数: %d", seg_idx + 1, len(questions))

    return questions if isinstance(questions, list) else []


def parse_pdf_questions(markdown_text: str, metadata: Dict[str, str]) -> List[Dict]:
    """
    调用 LLM 完整解析 PDF 中的题目（支持分段并发提取）
    Returns: 校验通过的题目列表；解析失败返回空列表
    """

    type_lower = metadata.get("type", "")
    level = metadata.get("level", "")
    date = metadata.get("date", "")
    id_prefix = generate_filename(type_lower, level, date)
    exam_type_upper = type_lower.upper() if type_lower else ""

    try:
        exam_level = int(level)
    except (ValueError, TypeError):
        exam_level = level

    # 1. 截断编程题部分，减少 token 消耗和干扰
    cut_markers = ["## 3编程题", "## 3.1编程题", "## 3 编程题", "## 编程题"]
    cut_pos = len(markdown_text)
    for marker in cut_markers:
        pos = markdown_text.find(marker)
        if pos != -1 and pos < cut_pos:
            cut_pos = pos
    clean_markdown = markdown_text[:cut_pos]

    # 2. 按题号边界切分文本
    lines = clean_markdown.split("\n")
    segments = split_by_questions(lines, max_chars=4000)
    total_segs = len(segments)

    # 3. 并发调用 LLM 处理各段
    all_questions = []
    with ThreadPoolExecutor(max_workers=min(5, total_segs)) as executor:
        futures = {
            executor.submit(_process_segment, seg, idx, total_segs): idx
            for idx, seg in enumerate(segments)
        }
        for future in as_completed(futures):
            try:
                seg_questions = future.result()
                all_questions.extend(seg_questions)
            except Exception:
                continue

    # 4. 去重（分段边界可能导致同一题被提取两次）
    seen = set()
    unique_questions = []
    for q in all_questions:
        if not isinstance(q, dict):
            continue
        # 用题目前50字符做去重键
        key = str(q.get("question", ""))[:50]
        if key and key not in seen:
            seen.add(key)
            unique_questions.append(q)

    # 5. 生成 ID 并补充 exam 字段
    sc_count = 0
    tf_count = 0
    valid = []

    for q in unique_questions:
        ok, _ = validate_question(q)
        if not ok:
            continue

        # 根据 type 生成对应的 ID
        if q["type"] == "single_choice":
            sc_count += 1
            q["id"] = f"{id_prefix}-sc-{sc_count}"
        else:
            tf_count += 1
            q["id"] = f"{id_prefix}-tf-{tf_count}"

        # 补充 exam 字段
        q["exam"] = {
            "type": exam_type_upper,
            "level": exam_level,
            "date": date,
        }
        valid.append(q)

    return valid


def validate_question(q: Dict) -> Tuple[bool, str]:
    """
    校验单道题目格式（不校验 id 和 exam，因为由后处理生成）
    Returns: (是否有效, 错误信息)
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

    if q["type"] == "true_false" and q["answer"] not in ("true", "false", "T", "F"):
        return False, '判断题 answer 必须为 "true"/"false" 或 "T"/"F"'

    return True, ""
