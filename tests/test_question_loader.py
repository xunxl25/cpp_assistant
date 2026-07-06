"""question_loader 模块的测试"""
import pytest
from app.core.question_loader import load_questions, get_questions_by_knowledge_point, get_knowledge_points, get_knowledge_point_frequency, get_question_by_id
from pathlib import Path


class TestLoadQuestions:
    """测试 load_questions 函数"""

    def test_load_valid_json(self):
        """测试加载有效的 JSON 文件"""
        file_path = "question_bank/gesp4-2606.json"
        questions = load_questions(file_path)
        assert isinstance(questions, list)
        assert len(questions) == 6
        assert all(isinstance(q, dict) for q in questions)

    def test_load_nonexistent_file(self):
        """测试加载不存在的文件"""
        with pytest.raises(FileNotFoundError):
            load_questions("question_bank/nonexistent.json")


class TestGetQuestionsByKnowledgePoint:
    """测试 get_questions_by_knowledge_point 函数"""

    def test_filter_by_knowledge_point(self):
        """测试按知识点筛选题目"""
        questions = load_questions("question_bank/gesp4-2606.json")
        filtered = get_questions_by_knowledge_point(questions, "变量与数据类型")
        assert len(filtered) == 3
        assert all(q["knowledge_point"] == "变量与数据类型" for q in filtered)

    def test_filter_by_nonexistent_knowledge_point(self):
        """测试筛选不存在的知识点"""
        questions = load_questions("question_bank/gesp4-2606.json")
        filtered = get_questions_by_knowledge_point(questions, "不存在")
        assert len(filtered) == 0


class TestGetKnowledgePoints:
    """测试 get_knowledge_points 函数"""

    def test_get_all_knowledge_points(self):
        """测试获取所有知识点"""
        questions = load_questions("question_bank/gesp4-2606.json")
        points = get_knowledge_points(questions)
        assert set(points) == {"变量与数据类型", "控制流"}
        assert len(points) == 2


class TestGetKnowledgePointFrequency:
    """测试 get_knowledge_point_frequency 函数"""

    def test_frequency_count(self):
        """测试知识点频率统计"""
        questions = load_questions("question_bank/gesp4-2606.json")
        freq = get_knowledge_point_frequency(questions)
        assert freq == {"变量与数据类型": 3, "控制流": 3}


class TestGetQuestionById:
    """测试 get_question_by_id 函数"""

    def test_get_existing_question(self):
        """测试获取存在的题目"""
        questions = load_questions("question_bank/gesp4-2606.json")
        question = get_question_by_id(questions, "1")
        assert question is not None
        assert question["id"] == "1"
        assert question["knowledge_point"] == "变量与数据类型"

    def test_get_nonexistent_question(self):
        """测试获取不存在的题目"""
        questions = load_questions("question_bank/gesp4-2606.json")
        question = get_question_by_id(questions, "999")
        assert question is None