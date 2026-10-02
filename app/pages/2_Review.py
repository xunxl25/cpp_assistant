"""错题本页面"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import streamlit as st
import pandas as pd
import random
from app.core.cache import (
    get_mistake_questions_cached,
    get_questions_by_ids_cached,
    get_exam_types,
    get_exam_levels,
    get_default_exam_selection_cached,
)
from app.core.practice_tracker import PracticeTracker
from app.core.practice_ui import render_practice_ui

st.set_page_config(
    page_title="错题本 - C++ 做题助手",
    page_icon="📝",
    layout="wide"
)

# 数据库路径
DB_PATH = "data/practice_log.db"

# 题库路径
# QUESTION_BANK_PATH = "question_bank/gesp4-2606.json"
QUESTION_BANK_PATH = "question_bank"

# 初始化 session state（复习快照 + 进度）
if "review_questions" not in st.session_state:
    st.session_state.review_questions = []
    st.session_state.review_rows = []
    st.session_state.review_started = False
    st.session_state.review_current_index = 0


def remove_from_mistake(question_id: str):
    """移出错题本（隐藏，不影响 mastered；再次答错会自动回来）"""
    tracker = PracticeTracker(DB_PATH)
    tracker.mark_hidden(question_id)
    # 清除练习记录缓存（practice_log 变更后需刷新）
    st.cache_data.clear()
    # 从当前复习快照中移除（表格与答题区同步）
    st.session_state.review_questions = [
        q for q in st.session_state.review_questions
        if q["id"] != question_id
    ]
    st.session_state.review_rows = [
        m for m in st.session_state.review_rows
        if m["题目ID"] != question_id
    ]


def _q_exam_matches(question, selected_exam_types, selected_exam_levels) -> bool:
    """判断题目是否落在所选考试类型/级别内（内存过滤）"""
    exam = question.get("exam", {}) or {}
    q_type = str(exam.get("type", ""))
    q_level = str(exam.get("level", ""))
    if selected_exam_types and q_type not in selected_exam_types:
        return False
    if selected_exam_levels and q_level not in selected_exam_levels:
        return False
    return True


def main():
    """错题本页面"""
    st.title("📝 错题本")

    # 加载数据（只加载错题对应的题目，不加载全量题库）
    mistake_logs = get_mistake_questions_cached(DB_PATH)

    if not mistake_logs:
        st.info("🎉 暂无错题！")
        return

    # 按错题 ID 批量加载题目（走索引，只读命中的文件）
    mistake_ids = tuple(log["question_id"] for log in mistake_logs)
    questions = get_questions_by_ids_cached(mistake_ids)

    # 构建 {id: question} 查找表
    question_map = {q["id"]: q for q in questions}

    # ===== 侧边栏：筛选条件（布局同刷题页） =====
    st.sidebar.header("筛选条件")

    # 1. 考试类型（多选）
    all_exam_types = get_exam_types()

    # 默认值：总览页选中值 -> 未选则 GESP + 题库最高级别
    default_type, default_level = get_default_exam_selection_cached(
        st.session_state.get("overview_exam_type", "全部"),
        st.session_state.get("overview_exam_level", "全部"),
    )
    default_types = [default_type] if default_type in all_exam_types else all_exam_types
    selected_exam_types = st.sidebar.multiselect(
        "考试类型",
        all_exam_types,
        default=default_types
    )

    # 2. 级别（多选）
    all_exam_levels = get_exam_levels()
    default_levels = [default_level] if default_level in all_exam_levels else all_exam_levels
    selected_exam_levels = st.sidebar.multiselect(
        "级别",
        all_exam_levels,
        default=default_levels
    )

    # 按考试类型/级别过滤错题（题目自带 exam 字段，内存过滤）
    filtered_logs = []
    for log in mistake_logs:
        question = question_map.get(log["question_id"])
        if question and _q_exam_matches(question, selected_exam_types, selected_exam_levels):
            filtered_logs.append(log)

    # 获取错题详细信息
    mistakes = []
    for log in filtered_logs:
        question = question_map[log["question_id"]]
        # 获取知识点（兼容新旧格式），取第一个用于表格展示
        kps = question.get("knowledge_points", [])
        if not kps:
            kp = question.get("knowledge_point", "")
            kps = [kp] if kp else ["未知"]
        knowledge_point = kps[0] if kps else "未知"
        mistakes.append({
            "题目ID": log["question_id"],
            "知识点": knowledge_point,
            "题目内容": question["question"][:50] + "...",
            "错误次数": log["wrong_count"],
            "正确次数": log["correct_count"],
            "正确率": round(log["correct_count"] / (log["correct_count"] + log["wrong_count"]), 2) if (log["correct_count"] + log["wrong_count"]) > 0 else 0,
            "最后答案": log.get("user_answer", ""),
            "正确答案": log.get("correct_answer", "")
        })

    # 3. 筛选模式（单选）
    filter_mode = st.sidebar.radio(
        "筛选模式",
        ["全部错题", "按知识点", "高频错题", "随机练习"]
    )

    # 根据模式排序/过滤
    if filter_mode == "按知识点":
        knowledge_points = sorted(set(m["知识点"] for m in mistakes))
        if knowledge_points:
            selected_kp = st.sidebar.selectbox("选择知识点", knowledge_points)
            mode_mistakes = [m for m in mistakes if m["知识点"] == selected_kp]
        else:
            mode_mistakes = []
    elif filter_mode == "高频错题":
        mode_mistakes = sorted(mistakes, key=lambda x: -x["错误次数"])
    elif filter_mode == "随机练习":
        # 点击"开始复习"时才洗牌（快照），避免每次 rerun 顺序变化
        mode_mistakes = list(mistakes)
        random.shuffle(mode_mistakes)
    else:
        mode_mistakes = mistakes

    st.sidebar.caption(f"当前筛选：{len(mode_mistakes)} 道错题")

    # 4. 确认：点击后以快照形式显示表格和答题区
    start_review = st.sidebar.button("开始复习", type="primary", use_container_width=True)

    if start_review:
        questions_to_practice = []
        rows = []
        for m in mode_mistakes:
            q = question_map.get(m["题目ID"])
            if q:
                questions_to_practice.append(q)
                rows.append(m)

        if not questions_to_practice:
            st.sidebar.warning("当前筛选条件下没有错题")
        else:
            st.session_state.review_questions = questions_to_practice
            st.session_state.review_rows = rows
            st.session_state.review_started = True
            st.session_state.review_current_index = 0

    # ===== 主区域：确认后才显示表格和答题区 =====
    if not st.session_state.review_started:
        st.info('👈 请在侧边栏选择筛选条件，然后点击"开始复习"')
        return

    if not st.session_state.review_questions:
        st.warning("没有符合条件的错题")
        return

    # 显示错题表格（来自快照）
    st.header("错题列表")
    df = pd.DataFrame(st.session_state.review_rows)
    st.dataframe(df, width='stretch')

    # 题目复习
    st.divider()
    st.header("题目复习")

    # 防止索引越界 (比如移出错题本后列表变短了)
    if st.session_state.review_current_index >= len(st.session_state.review_questions):
        st.session_state.review_current_index = 0

    # 直接使用做题组件渲染整个列表
    result = render_practice_ui(
        questions=st.session_state.review_questions,
        current_index=st.session_state.review_current_index,
        db_path=DB_PATH,
        is_mistake_mode=True,
        on_remove_from_mistake=remove_from_mistake
    )

    # 处理组件返回的动作 (支持下一题和移出错题本)
    if result['action'] == 'next':
        st.session_state.review_current_index = result['next_index']
        st.rerun()
    elif result['action'] == 'remove':
        st.success("已移出错题本")
        st.rerun()


if __name__ == "__main__":
    main()
