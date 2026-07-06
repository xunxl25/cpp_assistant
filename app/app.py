"""C++ 做题应用 - 主应用"""
import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 导入核心模块
from app.core.question_loader import (
    load_questions,
    get_questions_by_knowledge_point,
    get_knowledge_points,
    get_knowledge_point_frequency,
    get_question_by_id
)
from app.core.practice_tracker import (
    record_answer,
    get_practice_log
)
from app.core.ai_chat import ask_question

# 页面配置
st.set_page_config(
    page_title="C++ 做题助手",
    page_icon="💻",
    layout="wide"
)

# 数据库路径
DB_PATH = Path("data/practice_log.db")
DB_PATH.parent.mkdir(exist_ok=True)

# 题库路径
QUESTION_BANK_PATH = "question_bank/gesp4-2606.json"


def load_data():
    """加载题库和练习记录"""
    questions = load_questions(QUESTION_BANK_PATH)
    practice_logs = get_practice_log(str(DB_PATH))
    return questions, practice_logs


def main():
    """主页面"""
    st.title("💻 C++ 做题助手")

    # 加载数据
    questions, practice_logs = load_data()

    # 侧边栏：知识点筛选
    st.sidebar.header("知识点筛选")
    knowledge_points = get_knowledge_points(questions)
    selected_kp = st.sidebar.selectbox("选择知识点", ["全部"] + knowledge_points)

    # 筛选题目
    if selected_kp == "全部":
        filtered_questions = questions
    else:
        filtered_questions = get_questions_by_knowledge_point(questions, selected_kp)

    # 知识点概览（柱状图）
    st.header("知识点概览")
    freq = get_knowledge_point_frequency(questions)

    # 计算每个知识点的完成度
    completion = {}
    for kp in knowledge_points:
        kp_questions = get_questions_by_knowledge_point(questions, kp)
        kp_log_ids = [q["id"] for q in kp_questions]
        practiced = [log for log in practice_logs if log["question_id"] in kp_log_ids]

        if len(kp_questions) > 0:
            correct_attempts = sum(log["correct_count"] for log in practiced)
            total_attempts = sum(log["correct_count"] + log["wrong_count"] for log in practiced)
            accuracy = correct_attempts / total_attempts if total_attempts > 0 else 0
            completion[kp] = {
                "total": len(kp_questions),
                "practiced": len(practiced),
                "accuracy": accuracy
            }

    # 创建柱状图
    chart_data = pd.DataFrame([
        {
            "知识点": kp,
            "题目数量": freq[kp],
            "已完成": completion[kp]["practiced"],
            "正确率": completion[kp]["accuracy"]
        }
        for kp in knowledge_points
    ])

    # 显示柱状图
    fig = px.bar(
        chart_data,
        x="知识点",
        y=["题目数量", "已完成"],
        barmode="group",
        title="知识点题目数量与完成情况"
    )
    st.plotly_chart(fig, use_container_width=True)

    # 显示正确率
    st.write("### 知识点正确率")
    accuracy_chart = px.bar(
        chart_data,
        x="知识点",
        y="正确率",
        title="各知识点正确率"
    )
    st.plotly_chart(accuracy_chart, use_container_width=True)

    # 做题界面
    st.header("做题练习")
    st.divider()

    # 题目选择
    if filtered_questions:
        selected_idx = st.selectbox(
            "选择题目",
            range(len(filtered_questions)),
            format_func=lambda i: f"题目 {i+1}: {filtered_questions[i]['question'][:30]}..."
        )
        current_question = filtered_questions[selected_idx]

        # 显示题目
        st.subheader(f"题目 {selected_idx + 1}")
        st.write(current_question["question"])
        st.caption(f"知识点: {current_question['knowledge_point']}")

        # 显示选项（选择题）
        if current_question["type"] == "single_choice":
            options = current_question["options"]
            user_answer = st.radio("选择答案", list(options.keys()))

            # 提交按钮
            if st.button("提交答案"):
                is_correct = user_answer == current_question["answer"]

                # 记录答案
                record_answer(
                    str(DB_PATH),
                    current_question["id"],
                    user_answer,
                    current_question["answer"],
                    is_correct,
                    current_question["knowledge_point"]
                )

                # 显示结果
                if is_correct:
                    st.success("✅ 回答正确！")
                else:
                    st.error(f"❌ 回答错误！正确答案是: {current_question['answer']}")

                # 显示解析
                st.info(current_question["explanation"])

        # 判断题
        elif current_question["type"] == "true_false":
            user_answer = st.radio("选择答案", ["true", "false"], format_func=lambda x: "正确" if x == "true" else "错误")

            if st.button("提交答案"):
                is_correct = user_answer == current_question["answer"]

                record_answer(
                    str(DB_PATH),
                    current_question["id"],
                    user_answer,
                    current_question["answer"],
                    is_correct,
                    current_question["knowledge_point"]
                )

                if is_correct:
                    st.success("✅ 回答正确！")
                else:
                    st.error(f"❌ 回答错误！正确答案是: {'正确' if current_question['answer'] == 'true' else '错误'}")

                st.info(current_question["explanation"])

    else:
        st.warning("没有题目")

    # AI 问答区域
    st.divider()
    st.header("💬 AI 问答助手")

    # 获取当前题目的上下文
    context = None
    if filtered_questions:
        context = {
            "question": current_question["question"],
            "user_answer": st.session_state.get("user_answer", ""),
            "correct_answer": current_question["answer"]
        }

    # 用户输入
    user_input = st.text_input("向 AI 提问（关于当前题目）", placeholder="例如：为什么我的答案错了？")

    if st.button("发送问题"):
        if user_input:
            response = ask_question(user_input, context=context)
            st.info(response)
        else:
            st.warning("请输入问题")

    # 聊天历史
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # 显示聊天记录
    if st.session_state.chat_history:
        st.write("### 对话历史")
        for msg in st.session_state.chat_history:
            if msg["role"] == "user":
                st.write(f"👤 {msg['content']}")
            else:
                st.write(f"🤖 {msg['content']}")


if __name__ == "__main__":
    main()