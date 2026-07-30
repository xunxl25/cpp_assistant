"""错题本页面"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import streamlit as st
import pandas as pd
import random
from app.core.cache import get_all_questions
from app.core.question_loader import get_question_by_id
from app.core.practice_tracker import get_mistake_questions, PracticeTracker
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

# 初始化 session state
if "mistake_questions" not in st.session_state:
    st.session_state.mistake_questions = []
    st.session_state.mistake_current_index = 0
    st.session_state.mistake_started = False


def remove_from_mistake(question_id: str):
    """移出错题本"""
    tracker = PracticeTracker(DB_PATH)
    tracker.mark_mastered(question_id)
    # 从当前错题列表中移除
    st.session_state.mistake_questions = [
        q for q in st.session_state.mistake_questions
        if q["question_id"] != question_id
    ]


def main():
    """错题本页面"""
    st.title("📝 错题本")

    # 加载数据
    questions = get_all_questions(QUESTION_BANK_PATH)
    mistake_logs = get_mistake_questions(DB_PATH)

    if not mistake_logs:
        st.info("🎉 暂无错题！")
        return

    # 获取错题详细信息
    mistakes = []
    for log in mistake_logs:
        question = get_question_by_id(questions, log["question_id"])
        if question:
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

    # 筛选模式
    st.header("筛选模式")
    filter_mode = st.radio(
        "选择筛选模式",
        ["全部错题", "按知识点", "高频错题", "随机练习"]
    )

    # 根据模式排序/过滤
    if filter_mode == "按知识点":
        knowledge_points = sorted(set(m["知识点"] for m in mistakes))
        selected_kp = st.selectbox("选择知识点", knowledge_points)
        mistakes = [m for m in mistakes if m["知识点"] == selected_kp]
    elif filter_mode == "高频错题":
        mistakes = sorted(mistakes, key=lambda x: -x["错误次数"])
    elif filter_mode == "随机练习":
        random.shuffle(mistakes)

    # 显示错题表格
    st.header("错题列表")
    if mistakes:
        df = pd.DataFrame(mistakes)
        st.dataframe(df, width='stretch')

        # 题目复习
        st.divider()
        st.header("题目复习")
        
        # 加载当前筛选条件下的完整题目列表
        questions_to_practice = []
        for m in mistakes:
            q = get_question_by_id(questions, m["题目ID"])
            if q:
                questions_to_practice.append(q)
                
        if not questions_to_practice:
            st.warning("没有符合条件的错题")
        else:
            # 初始化或获取当前复习索引
            if "review_current_index" not in st.session_state:
                st.session_state.review_current_index = 0
                
            # 防止索引越界 (比如移出错题本后列表变短了)
            if st.session_state.review_current_index >= len(questions_to_practice):
                st.session_state.review_current_index = 0

            # 直接使用做题组件渲染整个列表
            result = render_practice_ui(
                questions=questions_to_practice,
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
    else:
        st.warning("没有符合条件的错题")


if __name__ == "__main__":
    main()