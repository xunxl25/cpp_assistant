"""pdf_parser 模块的测试

mock markitdown 与 call_llm，不进行真实 PDF 解析或 LLM 调用。
"""
import json
import pytest
from unittest.mock import patch, MagicMock
from app.core import pdf_parser
from app.core.pdf_parser import (
    generate_filename,
    validate_metadata,
    check_duplicate,
    parse_pdf_metadata,
    parse_metadata_from_filename,
    normalize_metadata,
    extract_metadata,
    parse_pdf_questions,
    validate_question,
    _extract_json,
)


class TestGenerateFilename:
    def test_normal(self):
        assert generate_filename("gesp", "4", "2606") == "gesp-4-2606"

    def test_sample(self):
        assert generate_filename("csp", "A", "sample") == "csp-A-sample"


class TestValidateMetadata:
    def test_valid(self):
        ok, err = validate_metadata("gesp", "4", "202606")
        assert ok and err == ""

    def test_valid_sample(self):
        ok, _ = validate_metadata("csp", "A", "sample")
        assert ok

    def test_type_too_short(self):
        ok, err = validate_metadata("g", "4", "202606")
        assert not ok
        assert "考试类型" in err

    def test_empty_level(self):
        ok, err = validate_metadata("gesp", "", "202606")
        assert not ok

    def test_bad_date(self):
        # 4 位 yymm 已非标准（统一 6 位 yyyymm），应报错提示
        ok, err = validate_metadata("gesp", "4", "2606")
        assert not ok
        assert "日期" in err


class TestCheckDuplicate:
    def test_no_duplicate(self, tmp_path, monkeypatch):
        monkeypatch.setattr(pdf_parser, "PAST_EXAM_DIR", str(tmp_path / "pdf"))
        monkeypatch.setattr(pdf_parser, "QUESTION_BANK_DIR", str(tmp_path / "bank"))
        (tmp_path / "pdf").mkdir()
        (tmp_path / "bank").mkdir()
        assert check_duplicate("gesp", "4", "2606") is False

    def test_pdf_duplicate(self, tmp_path, monkeypatch):
        pdf_dir = tmp_path / "pdf"
        pdf_dir.mkdir()
        (pdf_dir / "gesp-4-2606.pdf").write_bytes(b"%PDF")
        monkeypatch.setattr(pdf_parser, "PAST_EXAM_DIR", str(pdf_dir))
        monkeypatch.setattr(pdf_parser, "QUESTION_BANK_DIR", str(tmp_path / "bank"))
        assert check_duplicate("gesp", "4", "2606") is True

    def test_json_duplicate(self, tmp_path, monkeypatch):
        bank_dir = tmp_path / "bank"
        bank_dir.mkdir()
        (bank_dir / "gesp-4-2606.json").write_text("[]", encoding="utf-8")
        monkeypatch.setattr(pdf_parser, "PAST_EXAM_DIR", str(tmp_path / "pdf"))
        monkeypatch.setattr(pdf_parser, "QUESTION_BANK_DIR", str(bank_dir))
        assert check_duplicate("gesp", "4", "2606") is True


class TestExtractJson:
    def test_plain_json(self):
        assert _extract_json('{"a":1}') == {"a": 1}

    def test_fenced_json(self):
        assert _extract_json('```json\n{"a":1}\n```') == {"a": 1}

    def test_json_with_surrounding_text(self):
        assert _extract_json('结果如下: {"a":1} 完成') == {"a": 1}

    def test_array(self):
        assert _extract_json('[1,2,3]') == [1, 2, 3]

    def test_invalid(self):
        assert _extract_json("not json at all") is None
        assert _extract_json("") is None


class TestParsePdfMetadata:
    @patch("app.core.pdf_parser.call_llm")
    def test_extracts_metadata(self, mock_call):
        mock_call.return_value = '{"type": "gesp", "level": "4", "date": "2606"}'
        md = "# GESP 四级 2026年6月\n题目..."
        meta = parse_pdf_metadata(md)
        # 4 位日期自动归一化为 6 位
        assert meta == {"type": "gesp", "level": "4", "date": "202606"}

    @patch("app.core.pdf_parser.call_llm")
    def test_normalizes_variants(self, mock_call):
        mock_call.return_value = '{"type": "GESP", "level": "五级", "date": "2024年6月"}'
        meta = parse_pdf_metadata("xxx")
        assert meta == {"type": "gesp", "level": "5", "date": "202406"}

    @patch("app.core.pdf_parser.call_llm")
    def test_failure_returns_empty(self, mock_call):
        mock_call.return_value = "无法解析"
        assert parse_pdf_metadata("xxx") == {}

    @patch("app.core.pdf_parser.call_llm")
    def test_llm_error_returns_empty(self, mock_call):
        mock_call.side_effect = RuntimeError("no key")
        assert parse_pdf_metadata("xxx") == {}

    @patch("app.core.pdf_parser.call_llm")
    def test_empty_response_returns_empty(self, mock_call):
        mock_call.return_value = ""
        assert parse_pdf_metadata("xxx") == {}


class TestNormalizeMetadata:
    def test_type_case(self):
        assert normalize_metadata("GESP", "4", "202406")["type"] == "gesp"

    def test_chinese_level(self):
        assert normalize_metadata("gesp", "五级", "202406")["level"] == "5"
        assert normalize_metadata("gesp", "第4级", "202406")["level"] == "4"

    def test_date_variants(self):
        cases = [
            ("202406", "202406"),
            ("2406", "202406"),
            ("2024年6月", "202406"),
            ("2024-06", "202406"),
            ("2024.6", "202406"),
            ("sample", "sample"),
            ("样题", "sample"),
        ]
        for raw, expect in cases:
            assert normalize_metadata("gesp", "4", raw)["date"] == expect, raw

    def test_unrecognized_date_kept(self):
        # 无法识别的日期原样返回，交给 validate_metadata 报错
        assert normalize_metadata("gesp", "4", "abcd")["date"] == "abcd"


class TestParseMetadataFromFilename:
    def test_standard_six_digit(self):
        assert parse_metadata_from_filename("gesp-5-202406.pdf") == {
            "type": "gesp", "level": "5", "date": "202406"
        }

    def test_case_insensitive(self):
        assert parse_metadata_from_filename("GESP-4-sample.pdf") == {
            "type": "gesp", "level": "4", "date": "sample"
        }

    def test_loose_spacing_four_digit(self):
        assert parse_metadata_from_filename("gesp5 - 2509.pdf") == {
            "type": "gesp", "level": "5", "date": "202509"
        }

    def test_four_digit_suffix(self):
        assert parse_metadata_from_filename("gesp-5-2509.pdf")["date"] == "202509"

    def test_unparseable(self):
        assert parse_metadata_from_filename("试卷 final.pdf") == {}
        assert parse_metadata_from_filename("gesp.pdf") == {}
        assert parse_metadata_from_filename("scan_001.pdf") == {}


class TestExtractMetadata:
    @patch("app.core.pdf_parser.call_llm")
    def test_llm_success(self, mock_call):
        mock_call.return_value = '{"type": "gesp", "level": "5", "date": "202406"}'
        meta, source, error = extract_metadata("md", "whatever.pdf")
        assert meta == {"type": "gesp", "level": "5", "date": "202406"}
        assert source == "llm"
        assert error == ""

    @patch("app.core.pdf_parser.call_llm")
    def test_llm_fail_filename_fallback(self, mock_call):
        mock_call.side_effect = RuntimeError("no key")
        meta, source, error = extract_metadata("md", "gesp-5-202406.pdf")
        assert meta == {"type": "gesp", "level": "5", "date": "202406"}
        assert source == "filename"
        assert "no key" in error

    @patch("app.core.pdf_parser.call_llm")
    def test_both_fail(self, mock_call):
        mock_call.return_value = ""
        meta, source, error = extract_metadata("md", "试卷 final.pdf")
        assert meta == {"type": "", "level": "", "date": ""}
        assert source == ""
        assert "手动填写" in error

    @patch("app.core.pdf_parser.call_llm")
    def test_llm_empty_response_fallback(self, mock_call):
        mock_call.return_value = ""
        meta, source, error = extract_metadata("md", "gesp-5-2406.pdf")
        assert meta == {"type": "gesp", "level": "5", "date": "202406"}
        assert source == "filename"


class TestParsePdfQuestions:
    @patch("app.core.pdf_parser.call_llm")
    def test_parses_and_validates(self, mock_call):
        questions = [
            {
                "id": "gesp-4-2606-1",
                "exam": {"type": "GESP", "level": 4, "date": "2606"},
                "knowledge_points": ["数组"],
                "type": "single_choice",
                "question": "题",
                "options": {"A": "a", "B": "b", "C": "c", "D": "d"},
                "answer": "A",
                "explanation": "解析"
            },
            {
                "id": "gesp-4-2606-2",
                "exam": {"type": "GESP", "level": 4, "date": "2606"},
                "knowledge_points": ["循环"],
                "type": "true_false",
                "question": "对吗",
                "answer": "true",
                "explanation": "解析"
            }
        ]
        mock_call.return_value = json.dumps(questions, ensure_ascii=False)
        result = parse_pdf_questions("md text", {"type": "gesp", "level": "4", "date": "2606"})
        assert len(result) == 2
        assert result[0]["type"] == "single_choice"
        assert result[1]["type"] == "true_false"

    @patch("app.core.pdf_parser.call_llm")
    def test_filters_invalid(self, mock_call):
        questions = [
            {"id": "x-1", "type": "single_choice", "question": "?"},  # 缺字段
            {"id": "x-2", "knowledge_points": ["a"], "type": "judgment",  # 非法 type
             "question": "?", "answer": "正确", "explanation": ""},
        ]
        mock_call.return_value = json.dumps(questions, ensure_ascii=False)
        result = parse_pdf_questions("md", {"type": "gesp", "level": "4", "date": "2606"})
        assert result == []

    @patch("app.core.pdf_parser.call_llm")
    def test_llm_failure_returns_empty(self, mock_call):
        mock_call.side_effect = RuntimeError("no key")
        assert parse_pdf_questions("md", {"type": "gesp", "level": "4", "date": "2606"}) == []


class TestValidateQuestion:
    def test_valid_single_choice(self):
        q = {"id": "1", "knowledge_points": ["a"], "type": "single_choice",
             "question": "?", "options": {"A": "a"}, "answer": "A", "explanation": ""}
        ok, _ = validate_question(q)
        assert ok

    def test_valid_true_false(self):
        q = {"id": "1", "knowledge_points": ["a"], "type": "true_false",
             "question": "?", "answer": "true", "explanation": ""}
        ok, _ = validate_question(q)
        assert ok

    def test_true_false_wrong_answer(self):
        q = {"id": "1", "knowledge_points": ["a"], "type": "true_false",
             "question": "?", "answer": "正确", "explanation": ""}
        ok, err = validate_question(q)
        assert not ok
        assert "true" in err

    def test_missing_options(self):
        q = {"id": "1", "knowledge_points": ["a"], "type": "single_choice",
             "question": "?", "answer": "A", "explanation": ""}
        ok, err = validate_question(q)
        assert not ok


class TestPdfToMarkdown:
    def test_calls_markitdown(self, tmp_path):
        """markitdown 未安装时通过 sys.modules 注入 mock"""
        import sys
        fake_result = MagicMock()
        fake_result.text_content = "# markdown"
        fake_module = MagicMock()
        fake_module.MarkItDown.return_value.convert.return_value = fake_result
        with patch.dict(sys.modules, {"markitdown": fake_module}):
            from app.core.pdf_parser import pdf_to_markdown
            out = pdf_to_markdown(tmp_path / "x.pdf")
            assert out == "# markdown"
            fake_module.MarkItDown.return_value.convert.assert_called_once()
