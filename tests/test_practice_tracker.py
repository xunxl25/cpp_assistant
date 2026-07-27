"""practice_tracker 模块的测试"""
import pytest
import sqlite3
import tempfile
import os
import json
from pathlib import Path
from datetime import datetime
from app.core.practice_tracker import (
    PracticeTracker,
    record_answer,
    get_practice_log,
    get_question_stats,
    get_mistake_stats,
    get_mistake_questions
)


@pytest.fixture
def db_path():
    """创建临时数据库文件"""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    os.unlink(path)


@pytest.fixture
def tracker(db_path):
    """创建 PracticeTracker 实例"""
    return PracticeTracker(db_path)


class TestPracticeTracker:
    """测试 PracticeTracker 类"""

    def test_init_creates_table(self, tracker, db_path):
        """测试初始化时创建表"""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        assert "practice_log" in tables

    def test_add_practice_log(self, tracker):
        """测试添加练习记录"""
        tracker.add_practice_log(
            question_id="1",
            user_answer="A",
            correct_answer="A",
            is_correct=True,
            knowledge_points=json.dumps(["变量与数据类型"], ensure_ascii=False)
        )
        logs = tracker.get_all_logs()
        assert len(logs) == 1
        assert logs[0]["question_id"] == "1"
        assert logs[0]["correct_count"] == 1
        assert logs[0]["wrong_count"] == 0
        assert logs[0]["user_answer"] == "A"
        assert logs[0]["correct_answer"] == "A"

    def test_update_practice_log_existing_question(self, tracker):
        """测试更新已有题目的记录"""
        # 第一次记录（答错）
        tracker.add_practice_log(
            question_id="1",
            user_answer="B",
            correct_answer="A",
            is_correct=False,
            knowledge_points=json.dumps(["变量与数据类型"], ensure_ascii=False)
        )
        # 第二次记录（答对，更新 user_answer/correct_answer）
        tracker.add_practice_log(
            question_id="1",
            user_answer="A",
            correct_answer="A",
            is_correct=True,
            knowledge_points=json.dumps(["变量与数据类型"], ensure_ascii=False)
        )
        logs = tracker.get_all_logs()
        assert len(logs) == 1  # 同一题目只有一条记录
        assert logs[0]["wrong_count"] == 1
        assert logs[0]["correct_count"] == 1
        # user_answer 应为最后一次的值
        assert logs[0]["user_answer"] == "A"
        assert logs[0]["correct_answer"] == "A"

    def test_multi_knowledge_points_stored(self, tracker):
        """测试多知识点题目正确存储"""
        kps = ["二维数组与多维数组", "指针类型的概念及基本应用"]
        tracker.add_practice_log(
            question_id="1",
            user_answer="A",
            correct_answer="A",
            is_correct=True,
            knowledge_points=json.dumps(kps, ensure_ascii=False)
        )
        logs = tracker.get_all_logs()
        stored_kps = json.loads(logs[0]["knowledge_points"])
        assert stored_kps == kps

    def test_mark_mastered(self, tracker):
        """测试标记为已掌握"""
        tracker.add_practice_log(
            question_id="1",
            user_answer="A",
            correct_answer="A",
            is_correct=True,
            knowledge_points=json.dumps(["变量与数据类型"], ensure_ascii=False)
        )
        tracker.mark_mastered("1")
        logs = tracker.get_all_logs()
        assert logs[0]["mastered"] == 1


class TestFunctionalAPI:
    """测试函数式 API"""

    def test_record_answer(self, db_path):
        """测试 record_answer 函数"""
        record_answer(
            db_path,
            question_id="1",
            user_answer="A",
            correct_answer="A",
            is_correct=True,
            knowledge_points=json.dumps(["变量与数据类型"], ensure_ascii=False)
        )
        logs = get_practice_log(db_path)
        assert len(logs) == 1
        assert logs[0]["correct_count"] == 1
        assert logs[0]["wrong_count"] == 0
        assert logs[0]["user_answer"] == "A"
        assert logs[0]["correct_answer"] == "A"

    def test_get_question_stats(self, db_path):
        """测试 get_question_stats 函数"""
        # 记录 3 次练习：2 错 1 对
        record_answer(db_path, "1", "B", "A", False, json.dumps(["变量与数据类型"], ensure_ascii=False))
        record_answer(db_path, "1", "C", "A", False, json.dumps(["变量与数据类型"], ensure_ascii=False))
        record_answer(db_path, "1", "A", "A", True, json.dumps(["变量与数据类型"], ensure_ascii=False))

        stats = get_question_stats(db_path, "1")
        assert stats["wrong_count"] == 2
        assert stats["correct_count"] == 1
        assert stats["total_attempts"] == 3
        assert stats["accuracy"] == pytest.approx(1/3)

    def test_get_mistake_stats(self, db_path):
        """测试 get_mistake_stats 函数"""
        # 记录两道题
        record_answer(db_path, "1", "B", "A", False, json.dumps(["变量与数据类型"], ensure_ascii=False))
        record_answer(db_path, "2", "A", "A", True, json.dumps(["变量与数据类型"], ensure_ascii=False))

        stats = get_mistake_stats(db_path)
        assert stats["total_questions"] == 2
        assert stats["mistake_questions"] == 1

    def test_get_mistake_questions(self, db_path):
        """测试 get_mistake_questions 函数"""
        # 记录两道题，一道有错
        record_answer(db_path, "1", "B", "A", False, json.dumps(["变量与数据类型"], ensure_ascii=False))
        record_answer(db_path, "2", "A", "A", True, json.dumps(["变量与数据类型"], ensure_ascii=False))

        mistakes = get_mistake_questions(db_path)
        assert len(mistakes) == 1
        assert mistakes[0]["question_id"] == "1"
        assert mistakes[0]["user_answer"] == "B"
        assert mistakes[0]["correct_answer"] == "A"