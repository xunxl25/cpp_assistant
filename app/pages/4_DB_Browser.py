"""数据库浏览页面：网页版 SQLite 查看器

- practice_log（练习记录）：可搜索、排序、单元格手改，保存前自动备份
- question_index（题库索引）：只读浏览（此表由 JSON 重建，手改会被刷新索引覆盖）
"""
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="数据库浏览 - C++ 做题助手",
    page_icon="🗄️",
    layout="wide"
)

from app.core.db_editor import (
    PRACTICE_LOG_PATH,
    PRACTICE_LOG_TABLE,
    PRACTICE_LOG_PK,
    apply_changes,
    backup_db,
    diff_changes,
    list_backups,
    load_table,
    validate_changes,
)
from app.core.question_loader import QUESTION_BANK_INDEX_PATH

BACKUP_DIR = "data/backups"

DB_PRACTICE = "practice_log（练习记录 · 可编辑）"
DB_INDEX = "question_index（题库索引 · 只读）"


def _open_backup_dir():
    """用系统文件管理器打开备份目录（与"打开原卷"按钮同款逻辑）"""
    p = Path(BACKUP_DIR)
    p.mkdir(parents=True, exist_ok=True)
    try:
        if sys.platform == "win32":
            os.startfile(p)  # noqa: S606（本机工具）
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(p)])
        else:
            subprocess.Popen(["xdg-open", str(p)])
    except Exception as e:
        st.toast(f"打开目录失败：{e}", icon="⚠️")


def _fmt(value) -> str:
    """修改明细里的值显示（NaN 显示为空）"""
    return "" if pd.isna(value) else str(value)


def _search_mask(df: pd.DataFrame, keyword: str) -> pd.Series:
    """全表不区分大小写的子串匹配"""
    return df.apply(
        lambda row: row.astype(str).str.contains(keyword, case=False, na=False).any(),
        axis=1,
    )


def _practice_column_config() -> dict:
    """列配置：编辑控件类型 + 中文语义提示"""
    return {
        "knowledge_points": st.column_config.TextColumn(
            "knowledge_points", help='JSON 数组字符串，如 ["数组", "循环"]'
        ),
        "first_attempt_time": st.column_config.TextColumn(
            "first_attempt_time", help="首次作答时间（ISO 格式，如 2026-08-06T08:07:23）"
        ),
        "last_attempt_time": st.column_config.TextColumn(
            "last_attempt_time", help="最近作答时间（ISO 格式）"
        ),
        "correct_count": st.column_config.NumberColumn(
            "correct_count", min_value=0, step=1, help="答对次数"
        ),
        "wrong_count": st.column_config.NumberColumn(
            "wrong_count", min_value=0, step=1, help="答错次数"
        ),
        "mastered": st.column_config.SelectboxColumn(
            "mastered", options=[0, 1],
            help="0=未掌握 / 1=已掌握（正确率 ≥ 0.75 时答题流程自动置 1）"
        ),
        "hidden": st.column_config.SelectboxColumn(
            "hidden", options=[0, 1],
            help="0=正常 / 1=已从错题本隐藏（再次答错会自动回到 0）"
        ),
        "user_answer": st.column_config.TextColumn(
            "user_answer", help="最近一次作答（A/B/C/D 或 true/false/不会）"
        ),
        "correct_answer": st.column_config.TextColumn(
            "correct_answer", help="最近一次作答时的正确答案"
        ),
    }


def _render_backup_section():
    """备份列表 + 打开备份目录按钮"""
    with st.expander("🗂️ 备份（每次保存前自动复制，保留最近 10 份）"):
        backups = list_backups(BACKUP_DIR)
        if backups:
            rows = [
                {
                    "文件": b.name,
                    "大小 (KB)": b.stat().st_size / 1024,
                    "时间": datetime.fromtimestamp(b.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                }
                for b in backups
            ]
            st.dataframe(rows, width='stretch', hide_index=True)
            if st.button("📂 打开备份目录"):
                _open_backup_dir()
        else:
            st.caption("暂无备份（保存修改时会自动生成）")


def _render_practice_log():
    if not Path(PRACTICE_LOG_PATH).exists():
        st.warning("未找到 data/practice_log.db，答题后会自动创建。")
        return

    # 每次渲染都直读 DB（不走缓存），保证编辑基线最新
    base = load_table(PRACTICE_LOG_PATH, PRACTICE_LOG_TABLE, PRACTICE_LOG_PK)
    total = len(base)

    st.subheader("练习记录（practice_log）")
    st.caption(
        "点击单元格直接修改；点击列标题排序。"
        "⚠️ 修改后请直接点保存，切换搜索/筛选会丢弃未保存的修改。"
    )

    # ---------- 筛选 ----------
    col_search, col_quick = st.columns([3, 2])
    with col_search:
        search = st.text_input("搜索（任意列包含，不区分大小写）", key="db_search").strip()
    with col_quick:
        quick = st.selectbox("快捷筛选", ["全部", "有错题", "未掌握", "已隐藏"], key="db_quick")

    filtered = base
    if search:
        filtered = filtered[_search_mask(filtered, search)]
    if quick == "有错题":
        filtered = filtered[filtered["wrong_count"] > 0]
    elif quick == "未掌握":
        filtered = filtered[filtered["mastered"] == 0]
    elif quick == "已隐藏":
        filtered = filtered[filtered["hidden"] == 1]

    st.caption(f"显示 {len(filtered)} / {total} 行")

    # ---------- 编辑器 ----------
    # key 随 版本/筛选/搜索 变化：切换筛选时编辑器整体重置，
    # 避免 data_editor 按行索引暂存的编辑错位到别的行
    version = st.session_state.get("db_ed_version", 0)
    editor_key = f"db_ed_v{version}_{quick}_{search or 'ALL'}"
    edited = st.data_editor(
        filtered,
        key=editor_key,
        num_rows="fixed",
        width='stretch',
        height=560,
        column_config=_practice_column_config(),
    )

    changes = diff_changes(filtered, edited)

    # ---------- 保存 ----------
    if changes:
        n_cells = sum(len(cols) for cols in changes.values())
        st.caption(f"✏️ 未保存修改：{n_cells} 处（{len(changes)} 行）")
        with st.expander("修改明细"):
            for pk, cols in changes.items():
                for col, new in cols.items():
                    st.write(f"• **{pk}** · {col}：{_fmt(filtered.at[pk, col])} → {_fmt(new)}")

        if st.button(f"💾 保存修改（{n_cells} 处）", type="primary"):
            errors, cleaned = validate_changes(changes)
            if errors:
                st.error("修改未保存：\n- " + "\n- ".join(errors))
            else:
                try:
                    bpath = backup_db(PRACTICE_LOG_PATH, BACKUP_DIR)
                    updated, missing = apply_changes(
                        PRACTICE_LOG_PATH, PRACTICE_LOG_TABLE, PRACTICE_LOG_PK, cleaned
                    )
                    st.cache_data.clear()
                    st.session_state.db_ed_version = version + 1
                    msg = f"✅ 已保存 {updated} 行修改（备份：{bpath}）"
                    if missing:
                        msg += f"；{len(missing)} 行未找到已跳过：{', '.join(missing[:5])}"
                    st.session_state.db_flash = msg
                    st.rerun()
                except Exception as e:
                    st.error(f"保存失败，数据未写入：{e}")

    _render_backup_section()


def _render_question_index():
    if not Path(QUESTION_BANK_INDEX_PATH).exists():
        st.warning("未找到题库索引，请到「题库管理」页点击刷新索引。")
        return

    base = load_table(QUESTION_BANK_INDEX_PATH, "question_index", "question_id")
    total = len(base)

    st.subheader("题库索引（question_index）")
    st.info(
        "此表是从 question_bank/*.json 构建的缓存索引，「刷新题库索引」会整体重建。"
        "如需修改题库元数据（类型/级别/日期等），请编辑 JSON 后刷新，手改此表会被覆盖。"
    )

    col_search, col_type, col_level = st.columns([3, 2, 2])
    with col_search:
        search = st.text_input("搜索（任意列包含，不区分大小写）", key="idx_search").strip()
    with col_type:
        types = ["全部"] + base["exam_type"].unique().tolist()
        exam_type = st.selectbox("考试类型", types, key="idx_type")
    with col_level:
        levels = ["全部"] + base["exam_level"].unique().tolist()
        exam_level = st.selectbox("级别", levels, key="idx_level")

    filtered = base
    if exam_type != "全部":
        filtered = filtered[filtered["exam_type"] == exam_type]
    if exam_level != "全部":
        filtered = filtered[filtered["exam_level"] == exam_level]
    if search:
        filtered = filtered[_search_mask(filtered, search)]

    st.caption(f"显示 {len(filtered)} / {total} 行 · 点击列标题排序")
    st.dataframe(filtered, width='stretch', height=560)


def main():
    st.title("🗄️ 数据库浏览")
    st.caption("网页版 SQLite 查看器：练习记录支持筛选 / 排序 / 手改，题库索引只读。")

    # 保存成功提示（rerun 后展示一次）
    flash = st.session_state.pop("db_flash", None)
    if flash:
        st.success(flash)

    db_choice = st.radio(
        "选择数据库",
        [DB_PRACTICE, DB_INDEX],
        horizontal=True,
        label_visibility="collapsed",
    )

    if db_choice == DB_PRACTICE:
        _render_practice_log()
    else:
        _render_question_index()


if __name__ == "__main__":
    main()
