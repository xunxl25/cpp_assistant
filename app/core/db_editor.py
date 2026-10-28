"""数据库浏览/编辑核心逻辑

供 4_DB_Browser 页面调用：读取 practice_log 表、计算编辑差异、
校验、备份、按差异写回。不依赖 streamlit，可直接单测。

设计约束：
- question_id 是主键锚点，页面侧锁定为索引列不可编辑
- 写回时只 UPDATE 有变化的单元格，避免整行覆盖
  吞掉渲染期间其他流程（如答题）产生的更新
"""
import json
import shutil
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd

PRACTICE_LOG_PATH = "data/practice_log.db"
PRACTICE_LOG_TABLE = "practice_log"
PRACTICE_LOG_PK = "question_id"

# 允许写回的列（主键除外）
EDITABLE_COLS = (
    "knowledge_points",
    "first_attempt_time",
    "last_attempt_time",
    "correct_count",
    "wrong_count",
    "mastered",
    "user_answer",
    "correct_answer",
    "hidden",
)

# ---- 校验规则（与建表 schema 对应）----
NOT_NULL_COLS = ("knowledge_points", "first_attempt_time", "last_attempt_time")
BOOL_COLS = ("mastered", "hidden")          # 只能 0/1
COUNT_COLS = ("correct_count", "wrong_count")  # 非负整数
JSON_ARRAY_COLS = ("knowledge_points",)    # 必须是 JSON 数组字符串
ISO_TIME_COLS = ("first_attempt_time", "last_attempt_time")


def load_table(db_path: str, table: str, pk_col: str) -> pd.DataFrame:
    """读取整表并按主键列设为索引（索引列在 data_editor 中不可编辑）"""
    with closing(sqlite3.connect(db_path)) as conn:
        df = pd.read_sql(f"SELECT * FROM {table}", conn)
    return df.set_index(pk_col)


def _cell_changed(old: Any, new: Any) -> bool:
    """单元格级比较：双侧 NaN 视为未变化"""
    old_na, new_na = pd.isna(old), pd.isna(new)
    if old_na and new_na:
        return False
    if old_na or new_na:
        return True
    return old != new


def diff_changes(base: pd.DataFrame, edited: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    """
    比较编辑前后的表，返回变化单元格

    Returns:
        {question_id: {列名: 新值, ...}, ...}
    """
    changes: Dict[str, Dict[str, Any]] = {}
    for pk in base.index:
        if pk not in edited.index:
            continue
        row_changes = {}
        for col in base.columns:
            if _cell_changed(base.at[pk, col], edited.at[pk, col]):
                row_changes[col] = edited.at[pk, col]
        if row_changes:
            changes[str(pk)] = row_changes
    return changes


def _is_empty(value: Any) -> bool:
    return pd.isna(value) or (isinstance(value, str) and not value.strip())


def validate_changes(changes: Dict[str, Dict[str, Any]]) -> Tuple[List[str], Dict[str, Dict[str, Any]]]:
    """
    校验修改值并做类型清洗（如 "1" -> 1）

    Returns:
        (错误信息列表, 清洗后的 changes)
        有错误时调用方应中止保存（cleaned 仅包含通过校验的项，仅供参考）
    """
    errors: List[str] = []
    cleaned: Dict[str, Dict[str, Any]] = {}

    for pk, cols in changes.items():
        for col, val in cols.items():
            label = f"{pk} · {col}"

            if _is_empty(val):
                if col in NOT_NULL_COLS:
                    errors.append(f"{label}：该列不允许为空")
                else:
                    cleaned.setdefault(pk, {})[col] = None
                continue

            if col in BOOL_COLS:
                try:
                    iv = int(val)
                except (TypeError, ValueError):
                    errors.append(f"{label}：必须为 0 或 1")
                    continue
                if iv not in (0, 1):
                    errors.append(f"{label}：必须为 0 或 1")
                    continue
                cleaned.setdefault(pk, {})[col] = iv

            elif col in COUNT_COLS:
                try:
                    iv = int(val)
                except (TypeError, ValueError):
                    errors.append(f"{label}：必须为非负整数")
                    continue
                if iv < 0:
                    errors.append(f"{label}：必须为非负整数")
                    continue
                cleaned.setdefault(pk, {})[col] = iv

            elif col in JSON_ARRAY_COLS:
                try:
                    parsed = json.loads(val)
                except (TypeError, ValueError):
                    errors.append(f'{label}：不是合法 JSON（应为数组，如 ["数组", "循环"]）')
                    continue
                if not isinstance(parsed, list):
                    errors.append(f'{label}：必须是 JSON 数组，如 ["数组", "循环"]')
                    continue
                cleaned.setdefault(pk, {})[col] = val

            elif col in ISO_TIME_COLS:
                try:
                    datetime.fromisoformat(str(val))
                except ValueError:
                    errors.append(f"{label}：时间应为 ISO 格式（如 2026-08-06T08:07:23）")
                    continue
                cleaned.setdefault(pk, {})[col] = str(val)

            else:
                # user_answer / correct_answer：可空文本，无特殊校验
                cleaned.setdefault(pk, {})[col] = val

    return errors, cleaned


def backup_db(db_path: str, backup_dir: str = "data/backups", keep: int = 10) -> Path:
    """
    保存前备份 DB 文件，并轮转只保留最近 keep 份

    Returns:
        备份文件路径
    """
    src = Path(db_path)
    if not src.exists():
        raise FileNotFoundError(f"待备份的数据库不存在: {db_path}")

    bdir = Path(backup_dir)
    bdir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = bdir / f"{src.stem}_{ts}{src.suffix}"
    # 同一秒内多次备份时追加序号，避免互相覆盖
    n = 1
    while dst.exists():
        dst = bdir / f"{src.stem}_{ts}_{n}{src.suffix}"
        n += 1
    shutil.copy2(src, dst)

    # 轮转：同名前缀的备份按时间倒序，超出 keep 的删除
    backups = sorted(bdir.glob(f"{src.stem}_*{src.suffix}"), reverse=True)
    for old in backups[keep:]:
        old.unlink()

    return dst


def list_backups(backup_dir: str = "data/backups", db_stem: str = "practice_log") -> List[Path]:
    """列出某数据库的备份文件（新→旧）"""
    bdir = Path(backup_dir)
    if not bdir.exists():
        return []
    return sorted(bdir.glob(f"{db_stem}_*.db"), reverse=True)


def apply_changes(
    db_path: str,
    table: str,
    pk_col: str,
    changes: Dict[str, Dict[str, Any]],
    allowed_cols: Tuple[str, ...] = EDITABLE_COLS,
) -> Tuple[int, List[str]]:
    """
    将修改按单元格写回（单事务：任一 SQL 失败则全部回滚）

    Args:
        changes: {主键值: {列名: 新值}}（应先经 validate_changes 清洗）
        allowed_cols: 允许写回的列白名单

    Returns:
        (更新行数, 未找到的主键列表)
    """
    updated = 0
    missing: List[str] = []

    with closing(sqlite3.connect(db_path)) as conn:
        cursor = conn.cursor()
        try:
            for pk, cols in changes.items():
                if not cols:
                    continue
                bad = set(cols) - set(allowed_cols)
                if bad:
                    raise ValueError(f"不允许写回的列: {bad}")

                assignments = ", ".join(f"{c} = ?" for c in cols)
                cursor.execute(
                    f"UPDATE {table} SET {assignments} WHERE {pk_col} = ?",
                    [*cols.values(), pk],
                )
                if cursor.rowcount:
                    updated += 1
                else:
                    missing.append(pk)
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    return updated, missing
