"""题目加载模块"""
import json
import sqlite3
import glob
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
        if ratio > 0.8:
            return "必考"
        elif 0.4 <= ratio <= 0.8:
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
    """
    根据筛选条件获取题目

    Args:
        exam_types: 考试类型列表（如 ["GESP", "CSP"]）
        exam_levels: 级别列表（如 ["4", "5"]）
        frequency: 考察频次（"必考"/"常考"/"其他"）
        knowledge_points: 知识点列表
        question_bank_dir: 题库目录路径

    Returns:
        符合条件的题目列表
    """
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
        # 用 OR 条件匹配知识点（任一知识点匹配即可）
        kp_conditions = []
        for _ in knowledge_points:
            kp_conditions.append("knowledge_points LIKE ?")
            params.append(f'%"{kp}"%')
        conditions.append(f"({' OR '.join(kp_conditions)})")

    query = "SELECT source_file, question_index FROM question_index"
    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()

    # 根据 source_file 和 question_index 加载题目
    questions = []
    for source_file, question_index in results:
        try:
            file_questions = load_questions(source_file)
            if question_index < len(file_questions):
                questions.append(file_questions[question_index])
        except Exception as e:
            print(f"警告: 无法加载题目 {source_file}:{question_index}: {e}")

    return questions


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
        字典：{"必考": [...], "常考": [...], "其他": [...]}
    """
    ensure_index_exists(question_bank_dir)

    conn = sqlite3.connect(QUESTION_BANK_INDEX_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT knowledge_points, frequency FROM question_index")
    results = cursor.fetchall()
    conn.close()

    # 按频次分组
    frequency_groups = {"必考": set(), "常考": set(), "其他": set()}

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