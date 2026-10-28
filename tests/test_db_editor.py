"""db_editor 模块的测试：差异计算 / 校验 / 备份 / 写回 / 页面渲染"""
import re
import sqlite3
from contextlib import closing
from pathlib import Path

import pandas as pd
import pytest

from app.core.db_editor import (
    EDITABLE_COLS,
    apply_changes,
    backup_db,
    diff_changes,
    list_backups,
    load_table,
    validate_changes,
)

SCHEMA = """
CREATE TABLE practice_log (
    question_id TEXT PRIMARY KEY,
    knowledge_points TEXT NOT NULL,
    first_attempt_time TEXT NOT NULL,
    last_attempt_time TEXT NOT NULL,
    correct_count INTEGER DEFAULT 0,
    wrong_count INTEGER DEFAULT 0,
    mastered INTEGER DEFAULT 0,
    user_answer TEXT,
    correct_answer TEXT,
    hidden INTEGER DEFAULT 0
)
"""


@pytest.fixture
def practice_db(tmp_path):
    """合成一个与真实 schema 一致的 practice_log 数据库"""
    db = tmp_path / "practice_log.db"
    with closing(sqlite3.connect(db)) as conn:
        conn.execute(SCHEMA)
        conn.execute(
            "INSERT INTO practice_log VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("q-1", '["数组"]', "2026-08-01T10:00:00", "2026-08-01T10:00:05",
             2, 1, 0, "A", "B", 0),
        )
        conn.execute(
            "INSERT INTO practice_log VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("q-2", '["循环"]', "2026-08-02T10:00:00", "2026-08-02T10:00:05",
             0, 3, 0, None, None, 0),
        )
        conn.execute(
            "INSERT INTO practice_log VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("q-3", '["函数"]', "2026-08-03T10:00:00", "2026-08-03T10:00:05",
             5, 0, 1, "C", "C", 1),
        )
        conn.commit()
    return str(db)


def _base_df(db_path):
    return load_table(db_path, "practice_log", "question_id")


# ---------- diff_changes ----------

class TestDiffChanges:
    def test_unchanged_yields_empty(self, practice_db):
        base = _base_df(practice_db)
        assert diff_changes(base, base.copy()) == {}

    def test_single_cell_detected(self, practice_db):
        base = _base_df(practice_db)
        edited = base.copy()
        edited.at["q-1", "hidden"] = 1
        assert diff_changes(base, edited) == {"q-1": {"hidden": 1}}

    def test_double_nan_not_changed(self, practice_db):
        """双侧 NULL（NaN）不算修改"""
        base = _base_df(practice_db)
        edited = base.copy()
        edited.at["q-2", "user_answer"] = None
        assert diff_changes(base, edited) == {}

    def test_null_transitions_detected(self, practice_db):
        base = _base_df(practice_db)
        edited = base.copy()
        edited.at["q-2", "user_answer"] = "不会"
        edited.at["q-1", "user_answer"] = None
        changes = diff_changes(base, edited)
        assert changes["q-2"] == {"user_answer": "不会"}
        assert changes["q-1"] == {"user_answer": None}

    def test_int_float_equal_not_changed(self, practice_db):
        """编辑器可能返回 float 型整数（1.0），应视为与 1 相同"""
        base = _base_df(practice_db)
        edited = base.copy()
        edited["correct_count"] = edited["correct_count"].astype(float)
        assert diff_changes(base, edited) == {}


# ---------- validate_changes ----------

class TestValidateChanges:
    def test_valid_changes_pass(self):
        errors, cleaned = validate_changes(
            {"q-1": {"hidden": 1, "correct_count": 3, "user_answer": None}}
        )
        assert errors == []
        assert cleaned == {"q-1": {"hidden": 1, "correct_count": 3, "user_answer": None}}

    def test_string_int_coerced(self):
        errors, cleaned = validate_changes({"q-1": {"mastered": "1"}})
        assert errors == []
        assert cleaned["q-1"]["mastered"] == 1

    def test_bool_out_of_range_rejected(self):
        errors, _ = validate_changes({"q-1": {"mastered": 2}})
        assert any("mastered" in e for e in errors)

    def test_negative_count_rejected(self):
        errors, _ = validate_changes({"q-1": {"wrong_count": -1}})
        assert any("wrong_count" in e for e in errors)

    def test_not_null_empty_rejected(self):
        errors, _ = validate_changes({"q-1": {"knowledge_points": "  "}})
        assert any("knowledge_points" in e for e in errors)

    def test_invalid_json_rejected(self):
        errors, _ = validate_changes({"q-1": {"knowledge_points": "数组"}})
        assert any("JSON" in e for e in errors)

    def test_json_non_array_rejected(self):
        errors, _ = validate_changes({"q-1": {"knowledge_points": '"数组"'}})
        assert any("数组" in e for e in errors)

    def test_bad_timestamp_rejected(self):
        errors, _ = validate_changes({"q-1": {"last_attempt_time": "2026/08/01 10:00"}})
        assert any("ISO" in e for e in errors)

    def test_nullable_text_allows_empty(self):
        errors, cleaned = validate_changes({"q-1": {"user_answer": ""}})
        assert errors == []
        assert cleaned["q-1"]["user_answer"] is None


# ---------- apply_changes ----------

class TestApplyChanges:
    def test_only_changed_cells_updated(self, practice_db):
        """未变化的列保持原值（不被旧快照覆盖）"""
        _, cleaned = validate_changes({"q-1": {"hidden": 1}})
        updated, missing = apply_changes(
            practice_db, "practice_log", "question_id", cleaned
        )
        assert (updated, missing) == (1, [])

        with closing(sqlite3.connect(practice_db)) as conn:
            row = conn.execute(
                "SELECT correct_count, wrong_count, hidden, user_answer "
                "FROM practice_log WHERE question_id = 'q-1'"
            ).fetchone()
        assert row == (2, 1, 1, "A")  # 只有 hidden 变了

    def test_multiple_rows_and_missing_pk(self, practice_db):
        _, cleaned = validate_changes(
            {"q-2": {"mastered": 1}, "q-404": {"hidden": 1}}
        )
        updated, missing = apply_changes(
            practice_db, "practice_log", "question_id", cleaned
        )
        assert updated == 1
        assert missing == ["q-404"]

    def test_column_whitelist_enforced(self, practice_db):
        with pytest.raises(ValueError, match="不允许写回的列"):
            apply_changes(
                practice_db, "practice_log", "question_id",
                {"q-1": {"question_id": "hack"}},
                allowed_cols=EDITABLE_COLS,
            )

    def test_rollback_on_bad_column(self, practice_db):
        """事务性：中途失败则整体回滚"""
        with pytest.raises(Exception):
            apply_changes(
                practice_db, "practice_log", "question_id",
                {"q-1": {"hidden": 1}, "q-2": {"not_a_col": 1}},
            )
        with closing(sqlite3.connect(practice_db)) as conn:
            hidden = conn.execute(
                "SELECT hidden FROM practice_log WHERE question_id = 'q-1'"
            ).fetchone()[0]
        assert hidden == 0  # q-1 的修改也被回滚

    def test_roundtrip_with_diff(self, practice_db):
        """load → 编辑 → diff → validate → apply → 重读验证"""
        base = _base_df(practice_db)
        edited = base.copy()
        edited.at["q-3", "mastered"] = 0
        edited.at["q-3", "hidden"] = 0
        changes = diff_changes(base, edited)
        errors, cleaned = validate_changes(changes)
        assert errors == []
        apply_changes(practice_db, "practice_log", "question_id", cleaned)

        reloaded = _base_df(practice_db)
        assert reloaded.at["q-3", "mastered"] == 0
        assert reloaded.at["q-3", "hidden"] == 0


# ---------- backup ----------

class TestBackup:
    def test_backup_creates_file_and_rotates(self, practice_db, tmp_path):
        bdir = tmp_path / "backups"
        for _ in range(3):
            backup_db(practice_db, str(bdir), keep=2)
        backups = list_backups(str(bdir))
        assert len(backups) == 2  # 轮转保留最近 2 份

        # 备份内容与源一致
        with closing(sqlite3.connect(backups[0])) as conn:
            count = conn.execute("SELECT COUNT(*) FROM practice_log").fetchone()[0]
        assert count == 3

    def test_list_backups_empty_dir(self, tmp_path):
        assert list_backups(str(tmp_path / "nope")) == []


# ---------- 页面渲染（AppTest 无头）----------
# streamlit 1.64 起 from_file 的相对路径按调用者文件所在目录解析，须传绝对路径
PAGE_PATH = Path(__file__).parent.parent / "app" / "pages" / "4_DB_Browser.py"


def _run_page():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(PAGE_PATH), default_timeout=60)
    at.run()
    return at


def _captions(at):
    return " | ".join(c.value for c in at.caption)


class TestPageRender:
    def test_practice_log_view_renders(self):
        at = _run_page()
        assert not at.exception
        assert "数据库浏览" in at.title[0].value

    def test_row_count_caption_shown(self):
        at = _run_page()
        assert re.search(r"显示 \d+ / \d+ 行", _captions(at))

    def test_switch_to_index_shows_readonly_hint(self):
        at = _run_page()
        idx_label = next(v for v in at.radio[0].options if "question_index" in v)
        at.radio[0].set_value(idx_label)
        at.run()
        assert not at.exception
        infos = " ".join(e.value for e in at.info)
        assert "缓存索引" in infos

    def test_search_filters_rows(self):
        at = _run_page()
        m_before = re.search(r"显示 (\d+) / (\d+) 行", _captions(at))
        assert m_before and m_before.group(1) == m_before.group(2)  # 初始无筛选

        at.text_input[0].set_value("不存在的关键字xyz")
        at.run()
        m_after = re.search(r"显示 (\d+) / (\d+) 行", _captions(at))
        assert m_after and m_after.group(1) == "0"
