"""question_loader 模块的测试"""
import pytest
import json
from app.core.question_loader import (
    load_questions,
    get_questions_by_knowledge_point,
    get_knowledge_points,
    get_knowledge_point_frequency,
    get_question_by_id,
    search_questions,
    update_question_in_file,
    get_question_by_id_from_all,
)
from pathlib import Path


class TestLoadQuestions:
    """测试 load_questions 函数"""

    def test_load_valid_json(self):
        """测试加载有效的 JSON 文件"""
        file_path = "question_bank/gesp-4-202606.json"
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
        questions = load_questions("question_bank/gesp-4-202606.json")
        filtered = get_questions_by_knowledge_point(questions, "变量与数据类型")
        assert len(filtered) == 3
        # 兼容新旧格式
        for q in filtered:
            kps = q.get("knowledge_points", [])
            kp = q.get("knowledge_point")
            if kps:
                assert "变量与数据类型" in kps
            else:
                assert kp == "变量与数据类型"

    def test_filter_by_nonexistent_knowledge_point(self):
        """测试筛选不存在的知识点"""
        questions = load_questions("question_bank/gesp-4-202606.json")
        filtered = get_questions_by_knowledge_point(questions, "不存在")
        assert len(filtered) == 0


class TestGetKnowledgePoints:
    """测试 get_knowledge_points 函数"""

    def test_get_all_knowledge_points(self):
        """测试获取所有知识点"""
        questions = load_questions("question_bank/gesp-4-202606.json")
        points = get_knowledge_points(questions)
        assert set(points) == {"变量与数据类型", "控制流"}
        assert len(points) == 2


class TestGetKnowledgePointFrequency:
    """测试 get_knowledge_point_frequency 函数"""

    def test_frequency_count(self):
        """测试知识点频率统计"""
        questions = load_questions("question_bank/gesp-4-202606.json")
        freq = get_knowledge_point_frequency(questions)
        assert freq == {"变量与数据类型": 3, "控制流": 3}


class TestGetQuestionById:
    """测试 get_question_by_id 函数"""

    def test_get_existing_question(self):
        """测试获取存在的题目"""
        questions = load_questions("question_bank/gesp-4-202606.json")
        question = get_question_by_id(questions, "1")
        assert question is not None
        assert question["id"] == "1"
        # 兼容新旧格式
        kps = question.get("knowledge_points", [])
        kp = question.get("knowledge_point")
        if kps:
            assert "变量与数据类型" in kps
        else:
            assert kp == "变量与数据类型"

    def test_get_nonexistent_question(self):
        """测试获取不存在的题目"""
        questions = load_questions("question_bank/gesp-4-202606.json")
        question = get_question_by_id(questions, "999")
        assert question is None


class TestSearchQuestions:
    """测试 search_questions 函数"""

    @pytest.fixture
    def questions(self):
        return load_questions("question_bank/gesp-4-202606.json")

    def test_search_by_id(self, questions):
        results = search_questions(questions, "1")
        assert len(results) == 1
        assert results[0]["id"] == "1"

    def test_search_by_content(self, questions):
        results = search_questions(questions, "数据类型")
        assert len(results) > 0
        # 命中可来自题目内容或知识点，只要非空即可
        for q in results:
            assert q.get("id")

    def test_search_no_match(self, questions):
        results = search_questions(questions, "完全不存在的关键字xyz")
        assert results == []

    def test_search_empty_keyword(self, questions):
        results = search_questions(questions, "")
        assert results == []


class TestUpdateQuestionInFile:
    """测试 update_question_in_file 函数"""

    @pytest.fixture
    def bank_file(self, tmp_path):
        """复制真实题库到临时目录，避免修改原文件"""
        src = Path("question_bank/gesp-4-202606.json")
        dst = tmp_path / "gesp-4-202606.json"
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        return str(dst)

    def test_update_success(self, bank_file, monkeypatch):
        # 屏蔽索引重建（避免依赖 data/ 目录与真实 question_bank）
        monkeypatch.setattr(
            "app.core.question_loader.build_question_bank_index", lambda *a, **k: None
        )
        questions = load_questions(bank_file)
        q = questions[0]
        q["explanation"] = "更新后的解析"
        ok, err = update_question_in_file(bank_file, q)
        assert ok, err
        reloaded = load_questions(bank_file)
        assert reloaded[0]["explanation"] == "更新后的解析"

    def test_update_missing_id(self, bank_file, monkeypatch):
        monkeypatch.setattr(
            "app.core.question_loader.build_question_bank_index", lambda *a, **k: None
        )
        q = {"id": "999", "knowledge_points": ["x"], "type": "single_choice",
             "question": "?", "options": {"A": "a"}, "answer": "A", "explanation": ""}
        ok, err = update_question_in_file(bank_file, q)
        assert not ok
        assert "未找到" in err

    def test_update_missing_field(self, bank_file, monkeypatch):
        monkeypatch.setattr(
            "app.core.question_loader.build_question_bank_index", lambda *a, **k: None
        )
        q = {"id": "1", "type": "single_choice"}  # 缺 knowledge_points 等
        ok, err = update_question_in_file(bank_file, q)
        assert not ok

    def test_update_bad_kp_type(self, bank_file, monkeypatch):
        monkeypatch.setattr(
            "app.core.question_loader.build_question_bank_index", lambda *a, **k: None
        )
        q = {"id": "1", "knowledge_points": "变量", "type": "single_choice",
             "question": "?", "options": {"A": "a"}, "answer": "A", "explanation": ""}
        ok, err = update_question_in_file(bank_file, q)
        assert not ok
        assert "列表" in err


class TestGetQuestionByIdFromAll:
    """测试 get_question_by_id_from_all 函数"""

    def test_found_in_bank(self):
        q, path = get_question_by_id_from_all("1", "question_bank")
        assert q is not None
        assert q["id"] == "1"
        assert path is not None

    def test_not_found(self):
        q, path = get_question_by_id_from_all("nonexistent-id-999")
        assert q is None
        assert path is None