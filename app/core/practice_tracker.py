"""练习记录跟踪模块"""
import json
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
        """初始化数据库表（含旧表迁移）"""
        conn = sqlite3.connect(self.db_path)
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
        conn.close()

    def add_practice_log(
        self,
        question_id: str,
        user_answer: str,
        correct_answer: str,
        is_correct: bool,
        knowledge_points: str
    ):
        """
        添加或更新练习记录

        Args:
            question_id: 题目 ID
            user_answer: 用户答案（覆盖为最后一次的值）
            correct_answer: 正确答案（覆盖为最后一次的值）
            is_correct: 是否正确
            knowledge_points: 知识点 JSON 数组字符串，如 '["数组", "循环"]'
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
            # 更新已有记录：累加计数，覆盖最后一次的答案
            if is_correct:
                cursor.execute("""
                    UPDATE practice_log
                    SET correct_count = correct_count + 1,
                        last_attempt_time = ?,
                        user_answer = ?,
                        correct_answer = ?
                    WHERE question_id = ?
                """, (now, user_answer, correct_answer, question_id))
            else:
                cursor.execute("""
                    UPDATE practice_log
                    SET wrong_count = wrong_count + 1,
                        last_attempt_time = ?,
                        user_answer = ?,
                        correct_answer = ?
                    WHERE question_id = ?
                """, (now, user_answer, correct_answer, question_id))
        else:
            # 插入新记录
            correct_count = 1 if is_correct else 0
            wrong_count = 0 if is_correct else 1
            cursor.execute("""
                INSERT INTO practice_log (
                    question_id, knowledge_points, first_attempt_time,
                    last_attempt_time, correct_count, wrong_count,
                    user_answer, correct_answer
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (question_id, knowledge_points, now, now,
                  correct_count, wrong_count, user_answer, correct_answer))

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
            SELECT question_id, knowledge_points, first_attempt_time,
                   last_attempt_time, correct_count, wrong_count, mastered,
                   user_answer, correct_answer
            FROM practice_log
        """)
        rows = cursor.fetchall()
        conn.close()

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
        SELECT question_id, knowledge_points, correct_count, wrong_count,
               user_answer, correct_answer
        FROM practice_log
        WHERE wrong_count > 0 AND mastered = 0
    """)
    rows = cursor.fetchall()
    conn.close()

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