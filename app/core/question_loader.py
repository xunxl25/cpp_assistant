"""题目加载模块"""
import os
import json
import sqlite3
import glob
from collections import defaultdict
from typing import List, Dict, Optional, Set, Tuple
from pathlib import Path


def load_questions(file_path: str) -> List[Dict]:
    """
    从 JSON 文件加载题目

    Args:
        file_path: JSON 文件路径

    Returns:
        题目列表

    Raises:
        FileNotFoundError: 文件不存在时抛出
        json.JSONDecodeError: JSON 格式错误时抛出
    """
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_questions_from_folder(folder_path: str) -> List[Dict]:
    """
    从文件夹加载所有 JSON 文件中的题目
    
    Args:
        folder_path: 文件夹路径
    
    Returns:
        合并后的题目列表（平铺，不嵌套）
    """
    all_questions = []
    
    # 获取文件夹中所有 .json 文件
    json_pattern = os.path.join(folder_path, "*.json")
    json_files = glob.glob(json_pattern)
    
    # 遍历每个文件，加载并合并
    for file_path in json_files:
        questions = load_questions(file_path)
        all_questions.extend(questions)  # 平铺合并，不是 append
    
    return all_questions


def get_questions_by_knowledge_point(questions: List[Dict], knowledge_point: str) -> List[Dict]:
    """
    按知识点筛选题目（兼容新旧格式）

    Args:
        questions: 题目列表
        knowledge_point: 知识点名称

    Returns:
        匹配的题目列表
    """
    result = []
    for q in questions:
        # 新格式：knowledge_points 数组
        kps = q.get("knowledge_points", [])
        if kps:
            if knowledge_point in kps:
                result.append(q)
        # 旧格式：knowledge_point 字符串
        elif q.get("knowledge_point") == knowledge_point:
            result.append(q)
    return result


def get_knowledge_points(questions: List[Dict]) -> List[str]:
    """
    获取所有知识点（兼容新旧格式）

    Args:
        questions: 题目列表

    Returns:
        知识点列表（去重）
    """
    points = set()
    for q in questions:
        # 新格式：knowledge_points 数组
        kps = q.get("knowledge_points", [])
        if kps:
            points.update(kps)
        # 旧格式：knowledge_point 字符串
        else:
            kp = q.get("knowledge_point")
            if kp:
                points.add(kp)
    return sorted(list(points))


def get_knowledge_point_frequency(questions: List[Dict]) -> Dict[str, int]:
    """
    统计各知识点的题目数量（兼容新旧格式）

    Args:
        questions: 题目列表

    Returns:
        知识点 -> 题目数量的映射
    """
    freq = {}
    for q in questions:
        # 新格式：knowledge_points 数组
        kps = q.get("knowledge_points", [])
        if kps:
            for kp in kps:
                freq[kp] = freq.get(kp, 0) + 1
        # 旧格式：knowledge_point 字符串
        else:
            kp = q.get("knowledge_point")
            if kp:
                freq[kp] = freq.get(kp, 0) + 1
    return freq


def get_question_by_id(questions: List[Dict], question_id: str) -> Optional[Dict]:
    """
    根据 ID 获取题目

    Args:
        questions: 题目列表
        question_id: 题目 ID

    Returns:
        题目字典，未找到时返回 None
    """
    for q in questions:
        if q["id"] == question_id:
            return q
    return None


# 题库索引相关功能
QUESTION_BANK_INDEX_PATH = "data/question_bank_index.db"


def build_question_bank_index(question_bank_dir: str = "question_bank") -> None:
    """
    构建题库索引

    Args:
        question_bank_dir: 题库目录路径
    """
    # 确保 data 目录存在
    Path("data").mkdir(exist_ok=True)

    # 统计知识点频次
    knowledge_point_counts = {}

    # 扫描所有 JSON 文件
    json_files = glob.glob(str(Path(question_bank_dir) / "*.json"))

    for json_file in json_files:
        try:
            questions = load_questions(json_file)

            for question in questions:
                # 统计知识点频次
                kps = question.get("knowledge_points", [])
                if not kps:
                    # 兼容旧格式 knowledge_point
                    kp = question.get("knowledge_point", "")
                    if kp:
                        kps = [kp]

                for kp in kps:
                    knowledge_point_counts[kp] = knowledge_point_counts.get(kp, 0) + 1
        except Exception as e:
            print(f"警告: 无法读取 {json_file}: {e}")

    # 计算考察频次
    total_questions = sum(knowledge_point_counts.values())

    def get_frequency(ratio: float) -> str:
        if ratio > 0.05:
            return "常考"
        else:
            return "其他"

    knowledge_point_frequency = {
        kp: get_frequency(count / total_questions)
        for kp, count in knowledge_point_counts.items()
    }

    # 创建索引表
    conn = sqlite3.connect(QUESTION_BANK_INDEX_PATH)
    cursor = conn.cursor()

    # 删除旧表
    cursor.execute("DROP TABLE IF EXISTS question_index")

    # 创建新表
    cursor.execute("""
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
    """)

    # 插入索引数据
    for json_file in json_files:
        try:
            questions = load_questions(json_file)

            for idx, question in enumerate(questions):
                exam = question.get("exam", {"type": "GESP", "level": 1, "date": "2026-06"})

                # 获取知识点
                kps = question.get("knowledge_points", [])
                if not kps:
                    kp = question.get("knowledge_point", "")
                    kps = [kp] if kp else ["其他"]

                # 获取考察频次（取主知识点的频次）
                main_kp = kps[0] if kps else "其他"
                frequency = question.get("frequency", knowledge_point_frequency.get(main_kp, "其他"))

                cursor.execute("""
                    INSERT INTO question_index VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    question["id"],
                    exam.get("type", "GESP"),
                    str(exam.get("level", 1)),
                    exam.get("date", "2026-06"),
                    json.dumps(kps, ensure_ascii=False),
                    frequency,
                    json_file,
                    idx
                ))
        except Exception as e:
            print(f"警告: 无法索引 {json_file}: {e}")

    # 创建索引
    cursor.execute("CREATE INDEX idx_exam_type ON question_index(exam_type)")
    cursor.execute("CREATE INDEX idx_exam_level ON question_index(exam_level)")
    cursor.execute("CREATE INDEX idx_frequency ON question_index(frequency)")

    conn.commit()
    conn.close()

    print(f"题库索引已构建，共 {len(json_files)} 个文件")


def ensure_index_exists(question_bank_dir: str = "question_bank") -> None:
    """
    确保题库索引存在，不存在则自动构建

    Args:
        question_bank_dir: 题库目录路径
    """
    index_path = Path(QUESTION_BANK_INDEX_PATH)
    if not index_path.exists():
        build_question_bank_index(question_bank_dir)


def get_questions_by_filter(
    exam_types: List[str] = None,
    exam_levels: List[str] = None,
    frequency: Optional[str] = None,
    knowledge_points: List[str] = None,
    question_bank_dir: str = "question_bank"
) -> List[Dict]:
    """根据筛选条件获取题目"""
    import logging
    import traceback
    import os
    
    # 确保日志目录存在
    log_dir = os.path.dirname(os.path.abspath(__file__))
    log_file = os.path.join(log_dir, 'question_loader_errors.log')
    
    logging.basicConfig(
        filename=log_file,
        level=logging.ERROR,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    try:
        ensure_index_exists(question_bank_dir)
        conn = sqlite3.connect(QUESTION_BANK_INDEX_PATH)
        cursor = conn.cursor()
        
        # 构建 SQL 查询
        conditions = []
        params = []
        
        if exam_types:
            placeholders = ",".join(["?"] * len(exam_types))
            conditions.append(f"exam_type IN ({placeholders})")
            params.extend(exam_types)
        
        if exam_levels:
            placeholders = ",".join(["?"] * len(exam_levels))
            conditions.append(f"exam_level IN ({placeholders})")
            params.extend(exam_levels)
        
        if frequency:
            conditions.append("frequency = ?")
            params.append(frequency)
        
        if knowledge_points:
            # 使用正确的变量名 current_kp（不是 kp）
            kp_conditions = []
            for current_kp in knowledge_points:  # ← 使用 current_kp 而不是 kp
                kp_conditions.append("knowledge_points LIKE ?")
                params.append(f'%"{current_kp}"%')
            conditions.append(f"({' OR '.join(kp_conditions)})")
        
        query = "SELECT source_file, question_index FROM question_index"
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()
        
        # 按 source_file 分组，每个文件只加载一次
        file_to_indices = defaultdict(list)
        for source_file, question_index in results:
            file_to_indices[source_file].append(question_index)

        questions = []
        for source_file, indices in file_to_indices.items():
            try:
                file_questions = load_questions(source_file)
                for qi in indices:
                    if qi < len(file_questions):
                        questions.append(file_questions[qi])
            except Exception as e:
                error_msg = f"无法加载题目 {source_file}: {e}"
                logging.error(error_msg)
                logging.error(traceback.format_exc())
                print(error_msg)

        return questions
        
    except Exception as e:
        error_msg = f"get_questions_by_filter 发生错误: {e}"
        logging.error(error_msg)
        logging.error(traceback.format_exc())
        print(error_msg)
        raise


def get_all_exam_types(question_bank_dir: str = "question_bank") -> List[str]:
    """
    获取所有考试类型

    Args:
        question_bank_dir: 题库目录路径

    Returns:
        考试类型列表（如 ["GESP", "CSP"]）
    """
    ensure_index_exists(question_bank_dir)

    conn = sqlite3.connect(QUESTION_BANK_INDEX_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT exam_type FROM question_index ORDER BY exam_type")
    results = cursor.fetchall()
    conn.close()

    return [row[0] for row in results]


def get_all_exam_levels(question_bank_dir: str = "question_bank") -> List[str]:
    """
    获取所有级别

    Args:
        question_bank_dir: 题库目录路径

    Returns:
        级别列表（如 ["1", "2", ..., "8"]）
    """
    ensure_index_exists(question_bank_dir)

    conn = sqlite3.connect(QUESTION_BANK_INDEX_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT exam_level FROM question_index ORDER BY exam_level")
    results = cursor.fetchall()
    conn.close()

    return [row[0] for row in results]


def get_all_knowledge_points_with_frequency(question_bank_dir: str = "question_bank") -> Dict[str, List[str]]:
    """
    获取所有知识点，按考察频次分组

    Args:
        question_bank_dir: 题库目录路径

    Returns:
        字典：{"常考": [...], "其他": [...]}
    """
    ensure_index_exists(question_bank_dir)

    conn = sqlite3.connect(QUESTION_BANK_INDEX_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT knowledge_points, frequency FROM question_index")
    results = cursor.fetchall()
    conn.close()

    # 按频次分组
    frequency_groups = {"常考": set(), "其他": set()}

    for kp_json, freq in results:
        try:
            kps = json.loads(kp_json)
            for kp in kps:
                if freq in frequency_groups:
                    frequency_groups[freq].add(kp)
        except:
            pass

    # 转换为排序列表
    return {
        freq: sorted(list(kps))
        for freq, kps in frequency_groups.items()
    }


def get_exam_dates(
    exam_types: List[str] = None,
    exam_levels: List[str] = None,
    question_bank_dir: str = "question_bank"
) -> List[str]:
    """
    获取符合条件的所有考试日期（去重、降序）

    Args:
        exam_types: 考试类型筛选（None 表示不限）
        exam_levels: 级别筛选（None 表示不限）
        question_bank_dir: 题库目录路径

    Returns:
        日期列表（降序，如 ["2026-06", "2025-12", ...]）
    """
    ensure_index_exists(question_bank_dir)

    conn = sqlite3.connect(QUESTION_BANK_INDEX_PATH)
    cursor = conn.cursor()

    conditions = []
    params = []
    if exam_types:
        placeholders = ",".join(["?"] * len(exam_types))
        conditions.append(f"exam_type IN ({placeholders})")
        params.extend(exam_types)
    if exam_levels:
        placeholders = ",".join(["?"] * len(exam_levels))
        conditions.append(f"exam_level IN ({placeholders})")
        params.extend(exam_levels)

    query = "SELECT DISTINCT exam_date FROM question_index"
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY exam_date DESC"

    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()

    return [row[0] for row in results]


def get_questions_by_exam_date(
    exam_date: str,
    exam_types: List[str] = None,
    exam_levels: List[str] = None,
    question_bank_dir: str = "question_bank"
) -> List[Dict]:
    """
    按考试日期获取题目（可同时按考试类型/级别过滤）

    Args:
        exam_date: 考试日期（如 "2026-06"）
        exam_types: 考试类型筛选（None 表示不限）
        exam_levels: 级别筛选（None 表示不限）
        question_bank_dir: 题库目录路径

    Returns:
        题目列表
    """
    ensure_index_exists(question_bank_dir)

    conn = sqlite3.connect(QUESTION_BANK_INDEX_PATH)
    cursor = conn.cursor()

    conditions = ["exam_date = ?"]
    params = [exam_date]
    if exam_types:
        placeholders = ",".join(["?"] * len(exam_types))
        conditions.append(f"exam_type IN ({placeholders})")
        params.extend(exam_types)
    if exam_levels:
        placeholders = ",".join(["?"] * len(exam_levels))
        conditions.append(f"exam_level IN ({placeholders})")
        params.extend(exam_levels)

    query = "SELECT source_file, question_index FROM question_index"
    query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY source_file, question_index"

    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()

    # 按 source_file 分组，每个文件只加载一次
    file_to_indices = defaultdict(list)
    for source_file, question_index in results:
        file_to_indices[source_file].append(question_index)

    questions = []
    for source_file, indices in file_to_indices.items():
        try:
            file_questions = load_questions(source_file)
            for qi in indices:
                if qi < len(file_questions):
                    questions.append(file_questions[qi])
        except Exception as e:
            print(f"警告: 无法加载题目 {source_file}: {e}")

    return questions


# 单题搜索 / 更新（题库管理单题编辑用）

REQUIRED_FIELDS = ["id", "knowledge_points", "type", "question", "answer", "explanation"]
VALID_TYPES = {"single_choice", "true_false"}


def search_questions(questions: List[Dict], keyword: str) -> List[Dict]:
    """
    根据 ID 或题目内容搜索题目（兼容新旧知识点格式）

    Args:
        questions: 题目列表
        keyword: 搜索关键字（ID 或题目内容）

    Returns:
        匹配的题目列表
    """
    if not keyword:
        return []
    results = []
    keyword_lower = keyword.lower()

    for q in questions:
        # 精确匹配 ID
        if q.get("id", "").lower() == keyword_lower:
            results.append(q)
            continue

        # 模糊匹配题目内容
        question_text = q.get("question", "")
        if keyword_lower in question_text.lower():
            results.append(q)
            continue

        # 匹配知识点（新旧格式）
        kps = q.get("knowledge_points", [])
        if not kps:
            kp = q.get("knowledge_point", "")
            kps = [kp] if kp else []
        for kp in kps:
            if keyword_lower in str(kp).lower():
                results.append(q)
                break

    return results


def validate_question(q: Dict) -> Tuple[bool, str]:
    """
    校验单道题目格式

    Returns:
        (是否有效, 错误信息)
    """
    for field in REQUIRED_FIELDS:
        if field not in q:
            return False, f"缺少字段: {field}"

    if not isinstance(q.get("knowledge_points"), list):
        return False, "knowledge_points 必须是列表格式"

    if q["type"] not in VALID_TYPES:
        return False, f'type 必须是 {VALID_TYPES} 之一'

    if q["type"] == "single_choice" and "options" not in q:
        return False, "选择题缺少 options 字段"

    if q["type"] == "true_false" and q["answer"] not in ("true", "false", "T", "F"):
        return False, '判断题 answer 必须为 "true"/"false" 或 "T"/"F"'

    return True, ""


def update_question_in_file(file_path: str, updated_question: Dict) -> Tuple[bool, str]:
    """
    更新单个题目到 JSON 文件中（保持文件内题目顺序）

    Args:
        file_path: JSON 文件路径
        updated_question: 更新后的题目（必须包含 id 字段）

    Returns:
        (成功/失败, 错误信息)；成功时索引已自动刷新
    """
    try:
        questions = load_questions(file_path)

        ok, err = validate_question(updated_question)
        if not ok:
            return False, err

        question_id = updated_question["id"]
        found = False
        for idx, q in enumerate(questions):
            if q["id"] == question_id:
                questions[idx] = updated_question
                found = True
                break

        if not found:
            return False, f"未找到 ID 为 {question_id} 的题目"

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(questions, f, ensure_ascii=False, indent=2)

        # 刷新索引
        build_question_bank_index()

        return True, ""

    except json.JSONDecodeError as e:
        return False, f"JSON 格式错误: {e}"
    except FileNotFoundError:
        return False, f"文件不存在: {file_path}"
    except Exception as e:
        return False, f"保存失败: {e}"


def get_question_by_id_from_all(
    question_id: str, question_bank_dir: str = "question_bank"
) -> Tuple[Optional[Dict], Optional[str]]:
    """
    在所有题库文件中查找指定 ID 的题目（走索引，O(1) 定位）

    Args:
        question_id: 题目 ID
        question_bank_dir: 题库目录

    Returns:
        (题目字典, 文件路径) 或 (None, None)
    """
    ensure_index_exists(question_bank_dir)

    conn = sqlite3.connect(QUESTION_BANK_INDEX_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT source_file, question_index FROM question_index WHERE question_id = ?",
        (question_id,)
    )
    row = cursor.fetchone()
    conn.close()

    if row is None:
        return None, None

    source_file, qi = row
    try:
        file_questions = load_questions(source_file)
        if qi < len(file_questions):
            return file_questions[qi], source_file
    except Exception:
        pass

    return None, None