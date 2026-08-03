"""练习记录跟踪模块"""
import json
import sqlite3
from contextlib import closing
from typing import List, Dict, Optional
from datetime import datetime


class PracticeTracker:
    """练习记录跟踪器"""

    _initialized_dbs: set = set()

    def __init__(self, db_path: str):
        """
        初始化练习记录跟踪器

        Args:
            db_path: SQLite 数据库文件路径
        """
        self.db_path = db_path
        # 只在首次访问该 DB 时跑初始化+迁移，后续直接跳过
        if db_path not in PracticeTracker._initialized_dbs:
            self._init_db()
            PracticeTracker._initialized_dbs.add(db_path)

    def _init_db(self):
        """初始化数据库表（含旧表迁移）"""
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()

            # 新建表（若不存在）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS practice_log (
                    question_id TEXT PRIMARY KEY,
                    knowledge_points TEXT NOT NULL,
                    first_attempt_time TEXT NOT NULL,
                    last_attempt_time TEXT NOT NULL,
                    correct_count INTEGER DEFAULT 0,
                    wrong_count INTEGER DEFAULT 0,
                    mastered INTEGER DEFAULT 0,
                    user_answer TEXT,
                    correct_answer TEXT
                )
            """)

            # 迁移：检查旧表结构，按需升级
            cursor.execute("PRAGMA table_info(practice_log)")
            columns = {row[1] for row in cursor.fetchall()}

            # 旧列 knowledge_point → knowledge_points
            if "knowledge_point" in columns and "knowledge_points" not in columns:
                cursor.execute(
                    "ALTER TABLE practice_log RENAME COLUMN knowledge_point TO knowledge_points"
                )
                # 将旧的单值字符串转为 JSON 数组格式
                cursor.execute(
                    "SELECT question_id, knowledge_points FROM practice_log "
                    "WHERE knowledge_points NOT LIKE '[%'"
                )
                for qid, kp_val in cursor.fetchall():
                    json_val = json.dumps([kp_val], ensure_ascii=False)
                    cursor.execute(
                        "UPDATE practice_log SET knowledge_points = ? WHERE question_id = ?",
                        (json_val, qid),
                    )

            # 新增 user_answer / correct_answer 列
            if "user_answer" not in columns:
                cursor.execute("ALTER TABLE practice_log ADD COLUMN user_answer TEXT")
            if "correct_answer" not in columns:
                cursor.execute("ALTER TABLE practice_log ADD COLUMN correct_answer TEXT")

            conn.commit()

    def add_practice_log(
        self,
        question_id: str,
        user_answer: str,
        correct_answer: str,
        is_correct: bool,
        knowledge_points: str
    ):
        """
        添加或更新练习记录（UPSERT：单条 SQL 完成）

        Args:
            question_id: 题目 ID
            user_answer: 用户答案（覆盖为最后一次的值）
            correct_answer: 正确答案（覆盖为最后一次的值）
            is_correct: 是否正确
            knowledge_points: 知识点 JSON 数组字符串，如 '["数组", "循环"]'
        """
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()

            correct_count = 1 if is_correct else 0
            wrong_count = 0 if is_correct else 1

            # UPSERT：新记录直接插入，已有记录累加计数并覆盖答案
            cursor.execute("""
                INSERT INTO practice_log (
                    question_id, knowledge_points, first_attempt_time,
                    last_attempt_time, correct_count, wrong_count,
                    user_answer, correct_answer
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(question_id) DO UPDATE SET
                    last_attempt_time = excluded.last_attempt_time,
                    correct_count = practice_log.correct_count + excluded.correct_count,
                    wrong_count = practice_log.wrong_count + excluded.wrong_count,
                    user_answer = excluded.user_answer,
                    correct_answer = excluded.correct_answer
            """, (question_id, knowledge_points, now, now,
                  correct_count, wrong_count, user_answer, correct_answer))

            conn.commit()

    def mark_mastered(self, question_id: str):
        """
        标记题目为已掌握

        Args:
            question_id: 题目 ID
        """
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE practice_log
                SET mastered = 1
                WHERE question_id = ?
            """, (question_id,))
            conn.commit()

    def get_all_logs(self) -> List[Dict]:
        """
        获取所有练习记录

        Returns:
            练习记录列表
        """
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT question_id, knowledge_points, first_attempt_time,
                       last_attempt_time, correct_count, wrong_count, mastered,
                       user_answer, correct_answer
                FROM practice_log
            """)
            rows = cursor.fetchall()

        return [
            {
                "question_id": row[0],
                "knowledge_points": row[1],
                "first_attempt_time": row[2],
                "last_attempt_time": row[3],
                "correct_count": row[4],
                "wrong_count": row[5],
                "mastered": row[6],
                "user_answer": row[7],
                "correct_answer": row[8]
            }
            for row in rows
        ]


# 函数式 API
def record_answer(
    db_path: str,
    question_id: str,
    user_answer: str,
    correct_answer: str,
    is_correct: bool,
    knowledge_points: str
):
    """
    记录答题结果（函数式 API）

    Args:
        db_path: 数据库路径
        question_id: 题目 ID
        user_answer: 用户答案（覆盖为最后一次的值）
        correct_answer: 正确答案（覆盖为最后一次的值）
        is_correct: 是否正确
        knowledge_points: 知识点 JSON 数组字符串，如 '["数组", "循环"]'
    """
    tracker = PracticeTracker(db_path)
    tracker.add_practice_log(
        question_id, user_answer, correct_answer, is_correct, knowledge_points
    )


def get_answered_question_ids(db_path: str) -> set:
    """
    返回已答过的 question_id 集合

    Args:
        db_path: 数据库路径

    Returns:
        已答题 ID 集合（空集表示无记录）
    """
    tracker = PracticeTracker(db_path)  # 确保表存在
    with closing(sqlite3.connect(db_path)) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT question_id FROM practice_log")
        return {row[0] for row in cursor.fetchall()}


def get_practice_log(db_path: str) -> List[Dict]:
    """
    获取练习记录（函数式 API）

    Args:
        db_path: 数据库路径

    Returns:
        练习记录列表
    """
    tracker = PracticeTracker(db_path)
    return tracker.get_all_logs()


def get_question_stats(db_path: str, question_id: str) -> Optional[Dict]:
    """
    获取题目统计信息

    Args:
        db_path: 数据库路径
        question_id: 题目 ID

    Returns:
        统计信息字典，未找到时返回 None
    """
    with closing(sqlite3.connect(db_path)) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT correct_count, wrong_count FROM practice_log WHERE question_id = ?
        """, (question_id,))
        row = cursor.fetchone()

    if row is None:
        return None

    correct_count, wrong_count = row
    total_attempts = correct_count + wrong_count
    accuracy = correct_count / total_attempts if total_attempts > 0 else 0.0

    return {
        "question_id": question_id,
        "correct_count": correct_count,
        "wrong_count": wrong_count,
        "total_attempts": total_attempts,
        "accuracy": accuracy
    }


def get_mistake_stats(db_path: str) -> Dict:
    """
    获取错题统计

    Args:
        db_path: 数据库路径

    Returns:
        错题统计信息
    """
    with closing(sqlite3.connect(db_path)) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                COUNT(*),
                SUM(CASE WHEN wrong_count > 0 AND mastered = 0 THEN 1 ELSE 0 END)
            FROM practice_log
        """)
        row = cursor.fetchone()

    return {
        "total_questions": row[0],
        "mistake_questions": row[1] or 0
    }


def get_mistake_questions(db_path: str) -> List[Dict]:
    """
    获取错题列表（未掌握且有过错误）

    Args:
        db_path: 数据库路径

    Returns:
        错题列表
    """
    with closing(sqlite3.connect(db_path)) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT question_id, knowledge_points, correct_count, wrong_count,
                   user_answer, correct_answer
            FROM practice_log
            WHERE wrong_count > 0 AND mastered = 0
        """)
        rows = cursor.fetchall()

    return [
        {
            "question_id": row[0],
            "knowledge_points": row[1],
            "correct_count": row[2],
            "wrong_count": row[3],
            "user_answer": row[4],
            "correct_answer": row[5]
        }
        for row in rows
    ]