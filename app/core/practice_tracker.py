"""练习记录跟踪模块"""
import sqlite3
from typing import List, Dict, Optional
from datetime import datetime


class PracticeTracker:
    """练习记录跟踪器"""

    def __init__(self, db_path: str):
        """
        初始化练习记录跟踪器

        Args:
            db_path: SQLite 数据库文件路径
        """
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """初始化数据库表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS practice_log (
                question_id TEXT PRIMARY KEY,
                knowledge_point TEXT NOT NULL,
                first_attempt_time TEXT NOT NULL,
                last_attempt_time TEXT NOT NULL,
                correct_count INTEGER DEFAULT 0,
                wrong_count INTEGER DEFAULT 0,
                mastered INTEGER DEFAULT 0
            )
        """)
        conn.commit()
        conn.close()

    def add_practice_log(
        self,
        question_id: str,
        user_answer: str,
        correct_answer: str,
        is_correct: bool,
        knowledge_point: str
    ):
        """
        添加或更新练习记录

        Args:
            question_id: 题目 ID
            user_answer: 用户答案
            correct_answer: 正确答案
            is_correct: 是否正确
            knowledge_point: 知识点
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        now = datetime.now().isoformat()

        cursor.execute(
            "SELECT question_id FROM practice_log WHERE question_id = ?",
            (question_id,)
        )
        exists = cursor.fetchone()

        if exists:
            # 更新已有记录
            if is_correct:
                cursor.execute("""
                    UPDATE practice_log
                    SET correct_count = correct_count + 1,
                        last_attempt_time = ?
                    WHERE question_id = ?
                """, (now, question_id))
            else:
                cursor.execute("""
                    UPDATE practice_log
                    SET wrong_count = wrong_count + 1,
                        last_attempt_time = ?
                    WHERE question_id = ?
                """, (now, question_id))
        else:
            # 插入新记录
            correct_count = 1 if is_correct else 0
            wrong_count = 0 if is_correct else 1
            cursor.execute("""
                INSERT INTO practice_log (
                    question_id, knowledge_point, first_attempt_time,
                    last_attempt_time, correct_count, wrong_count
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (question_id, knowledge_point, now, now, correct_count, wrong_count))

        conn.commit()
        conn.close()

    def mark_mastered(self, question_id: str):
        """
        标记题目为已掌握

        Args:
            question_id: 题目 ID
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE practice_log
            SET mastered = 1
            WHERE question_id = ?
        """, (question_id,))
        conn.commit()
        conn.close()

    def get_all_logs(self) -> List[Dict]:
        """
        获取所有练习记录

        Returns:
            练习记录列表
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT question_id, knowledge_point, first_attempt_time,
                   last_attempt_time, correct_count, wrong_count, mastered
            FROM practice_log
        """)
        rows = cursor.fetchall()
        conn.close()

        return [
            {
                "question_id": row[0],
                "knowledge_point": row[1],
                "first_attempt_time": row[2],
                "last_attempt_time": row[3],
                "correct_count": row[4],
                "wrong_count": row[5],
                "mastered": row[6]
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
    knowledge_point: str
):
    """
    记录答题结果（函数式 API）

    Args:
        db_path: 数据库路径
        question_id: 题目 ID
        user_answer: 用户答案
        correct_answer: 正确答案
        is_correct: 是否正确
        knowledge_point: 知识点
    """
    tracker = PracticeTracker(db_path)
    tracker.add_practice_log(
        question_id, user_answer, correct_answer, is_correct, knowledge_point
    )


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
    tracker = PracticeTracker(db_path)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT correct_count, wrong_count FROM practice_log WHERE question_id = ?
    """, (question_id,))
    row = cursor.fetchone()
    conn.close()

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
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM practice_log")
    total_questions = cursor.fetchone()[0]
    cursor.execute("""
        SELECT COUNT(*) FROM practice_log
        WHERE wrong_count > 0 AND mastered = 0
    """)
    mistake_questions = cursor.fetchone()[0]
    conn.close()

    return {
        "total_questions": total_questions,
        "mistake_questions": mistake_questions
    }


def get_mistake_questions(db_path: str) -> List[Dict]:
    """
    获取错题列表（未掌握且有过错误）

    Args:
        db_path: 数据库路径

    Returns:
        错题列表
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT question_id, knowledge_point, correct_count, wrong_count
        FROM practice_log
        WHERE wrong_count > 0 AND mastered = 0
    """)
    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "question_id": row[0],
            "knowledge_point": row[1],
            "correct_count": row[2],
            "wrong_count": row[3]
        }
        for row in rows
    ]