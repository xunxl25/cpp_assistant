"""错题本页面"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import streamlit as st
import pandas as pd
import random
from app.core.question_loader import load_questions, get_question_by_id
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
QUESTION_BANK_PATH = "question_bank/gesp4-2606.json"

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
    questions = load_questions(QUESTION_BANK_PATH)
    mistake_logs = get_mistake_questions(DB_PATH)

    if not mistake_logs:
        st.info("🎉 暂无错题！")
        return

    # 获取错题详细信息
    mistakes = []
    for log in mistake_logs:
        question = get_question_by_id(questions, log["question_id"])
        if question:
            # 获取知识点（兼容新旧格式）
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
                "正确率": round(log["correct_count"] / (log["correct_count"] + log["wrong_count"]), 2) if (log["correct_count"] + log["wrong_count"]) > 0 else 0
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
        st.dataframe(df, use_container_width=True)

        # 选择题目进行复习
        st.divider()
        st.header("题目复习")

        selected_idx = st.selectbox(
            "选择要复习的题目",
            range(len(mistakes)),
            format_func=lambda i: f"{mistakes[i]['题目ID']}: {mistakes[i]['题目内容']}"
        )

        # 加载完整题目
        current_mistake = mistakes[selected_idx]
        current_question = get_question_by_id(questions, current_mistake["题目ID"])

        # 使用做题组件
        result = render_practice_ui(
            questions=[current_question],
            current_index=0,
            db_path=DB_PATH,
            is_mistake_mode=True,
            on_remove_from_mistake=remove_from_mistake
        )

        # 处理移出错题本后的重新加载
        if result['action'] == 'remove':
            st.success("已移出错题本")
            st.rerun()

    else:
        st.warning("没有符合条件的错题")


if __name__ == "__main__":
    main()