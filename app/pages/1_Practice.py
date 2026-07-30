"""按知识点刷题页"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import streamlit as st
from app.core.cache import (
    get_exam_types,
    get_exam_levels,
    get_knowledge_points_with_frequency,
)
from app.core.question_loader import (
    get_questions_by_filter,
    build_question_bank_index
)
from app.core.practice_ui import render_practice_ui

st.set_page_config(
    page_title="按知识点刷题 - C++ 做题助手",
    page_icon="📝",
    layout="wide"
)

# 数据库路径
DB_PATH = "data/practice_log.db"

# 初始化 session state
if "filtered_questions" not in st.session_state:
    st.session_state.filtered_questions = []
    st.session_state.current_index = 0
    st.session_state.started = False


def remove_from_mistake(question_id: str):
    """移出错题本（占位函数，刷题页不需要）"""
    pass


def main():
    """按知识点刷题页面"""
    st.title("📝 按知识点刷题")

    # 侧边栏：筛选条件
    st.sidebar.header("筛选条件")

    # 刷新索引按钮
    if st.sidebar.button("刷新题库索引"):
        with st.sidebar:
            with st.spinner("正在构建索引..."):
                build_question_bank_index()
                st.cache_data.clear()
                st.success("索引已刷新")

    st.sidebar.divider()

    # 1. 考试类型（多选）
    st.sidebar.subheader("1. 考试类型")
    all_exam_types = get_exam_types()
    selected_exam_types = st.sidebar.multiselect(
        "选择考试类型",
        all_exam_types,
        default=all_exam_types
    )

    # 2. 级别（多选）
    st.sidebar.subheader("2. 级别")
    all_exam_levels = get_exam_levels()
    selected_exam_levels = st.sidebar.multiselect(
        "选择级别",
        all_exam_levels,
        default=all_exam_levels
    )

    # 3. 考察频次（单选）
    st.sidebar.subheader("3. 考察频次")
    frequency_options = ["全部", "常考", "其他"]
    selected_frequency = st.sidebar.radio(
        "选择考察频次",
        frequency_options
    )

    # 4. 知识点（多选，根据频次动态加载）
    st.sidebar.subheader("4. 知识点")
    all_kps = get_knowledge_points_with_frequency()

    # 根据选择的频次过滤知识点
    if selected_frequency == "全部":
        available_kps = []
        for kp_list in all_kps.values():
            available_kps.extend(kp_list)
        available_kps = sorted(list(set(available_kps)))
    else:
        available_kps = all_kps.get(selected_frequency, [])

    selected_knowledge_points = st.sidebar.multiselect(
        "选择知识点",
        available_kps,
        default=available_kps
    )

    # 开始按钮
    st.sidebar.divider()
    if st.sidebar.button("开始刷题", type="primary"):
        # 构建筛选条件
        exam_types = selected_exam_types if selected_exam_types else None
        exam_levels = selected_exam_levels if selected_exam_levels else None
        frequency = selected_frequency if selected_frequency != "全部" else None
        knowledge_points = selected_knowledge_points if selected_knowledge_points else None

        # 查询题目
        questions = get_questions_by_filter(
            exam_types=exam_types,
            exam_levels=exam_levels,
            frequency=frequency,
            knowledge_points=knowledge_points
        )

        st.session_state.filtered_questions = questions
        st.session_state.current_index = 0
        st.session_state.started = True

    # 做题界面
    if st.session_state.started:
        if st.session_state.filtered_questions:
            result = render_practice_ui(
                questions=st.session_state.filtered_questions,
                current_index=st.session_state.current_index,
                db_path=DB_PATH,
                is_mistake_mode=False
            )

            # 处理返回的动作
            if result['action'] == 'next':
                st.session_state.current_index = result['next_index']
                st.rerun()
        else:
            st.warning("没有符合条件的题目")
    else:
        st.info('👈 请在侧边栏选择筛选条件，然后点击"开始刷题"')


if __name__ == "__main__":
    main()