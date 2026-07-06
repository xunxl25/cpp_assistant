"""错题本页面"""
import streamlit as st
import pandas as pd
from pathlib import Path

st.set_page_config(
    page_title="错题本 - C++ 做题助手",
    page_icon="📝",
    layout="wide"
)

from app.core.question_loader import load_questions, get_question_by_id
from app.core.practice_tracker import get_mistake_questions, get_practice_log

# 数据库路径
DB_PATH = Path("data/practice_log.db")

# 题库路径
QUESTION_BANK_PATH = "question_bank/gesp4-2606.json"


def main():
    """错题本页面"""
    st.title("📝 错题本")

    # 加载数据
    questions = load_questions(QUESTION_BANK_PATH)
    mistake_logs = get_mistake_questions(str(DB_PATH))

    if not mistake_logs:
        st.info("🎉 暂无错题！")
        return

    # 获取错题详细信息
    mistakes = []
    for log in mistake_logs:
        question = get_question_by_id(questions, log["question_id"])
        if question:
            mistakes.append({
                "题目ID": log["question_id"],
                "知识点": log["knowledge_point"],
                "题目内容": question["question"][:50] + "...",
                "错误次数": log["wrong_count"],
                "正确次数": log["correct_count"],
                "正确率": round(log["correct_count"] / (log["correct_count"] + log["wrong_count"]), 2) if (log["correct_count"] + log["wrong_count"]) > 0 else 0
            })

    # 筛选模式
    st.header("筛选模式")
    filter_mode = st.radio(
        "选择筛选模式",
        ["按知识点", "高频错题", "随机练习"]
    )

    # 按知识点筛选
    if filter_mode == "按知识点":
        knowledge_points = sorted(set(m["知识点"] for m in mistakes))
        selected_kp = st.selectbox("选择知识点", knowledge_points)
        filtered_mistakes = [m for m in mistakes if m["知识点"] == selected_kp]

    # 高频错题（按错误次数排序）
    elif filter_mode == "高频错题":
        filtered_mistakes = sorted(mistakes, key=lambda x: -x["错误次数"])

    # 随机练习
    else:
        import random
        filtered_mistakes = mistakes.copy()
        random.shuffle(filtered_mistakes)

    # 显示错题表格
    st.header("错题列表")
    if filtered_mistakes:
        df = pd.DataFrame(filtered_mistakes)
        st.dataframe(df, use_container_width=True)

        # 选择题目进行复习
        st.divider()
        st.header("题目复习")

        selected_idx = st.selectbox(
            "选择要复习的题目",
            range(len(filtered_mistakes)),
            format_func=lambda i: f"{filtered_mistakes[i]['题目ID']}: {filtered_mistakes[i]['题目内容']}"
        )

        current_mistake = filtered_mistakes[selected_idx]
        current_question = get_question_by_id(questions, current_mistake["题目ID"])

        # 显示题目详情
        st.subheader(f"题目 {selected_mistake['题目ID']}")
        st.write(current_question["question"])
        st.caption(f"知识点: {current_question['knowledge_point']}")

        # 显示选项（选择题）
        if current_question["type"] == "single_choice":
            options = current_question["options"]
            for key, value in options.items():
                st.write(f"{key}. {value}")

        # 判断题
        elif current_question["type"] == "true_false":
            st.write("正确 / 错误")

        # 显示统计
        st.warning(f"错误次数: {current_mistake['错误次数']}, 正确次数: {current_mistake['正确次数']}")

        # 显示正确答案和解析
        st.divider()
        st.write(f"正确答案: {current_question['answer']}")
        st.info(current_question["explanation"])

    else:
        st.warning("没有符合条件的错题")


if __name__ == "__main__":
    main()