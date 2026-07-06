"""题目加载模块"""
import json
from typing import List, Dict, Optional


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
    按知识点筛选题目

    Args:
        questions: 题目列表
        knowledge_point: 知识点名称

    Returns:
        匹配的题目列表
    """
    return [q for q in questions if q["knowledge_point"] == knowledge_point]


def get_knowledge_points(questions: List[Dict]) -> List[str]:
    """
    获取所有知识点

    Args:
        questions: 题目列表

    Returns:
        知识点列表（去重）
    """
    points = set(q["knowledge_point"] for q in questions)
    return sorted(list(points))


def get_knowledge_point_frequency(questions: List[Dict]) -> Dict[str, int]:
    """
    统计各知识点的题目数量

    Args:
        questions: 题目列表

    Returns:
        知识点 -> 题目数量的映射
    """
    freq = {}
    for q in questions:
        point = q["knowledge_point"]
        freq[point] = freq.get(point, 0) + 1
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