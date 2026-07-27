"""总览页 - 只显示知识点统计"""
import sys
import os
import json
from pathlib import Path

# ========== 先添加项目根目录到 Python 路径 ==========
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
# ========== 然后再导入 app 模块 ==========

import importlib
import app.core.question_loader
importlib.reload(app.core.question_loader)

import streamlit as st
import pandas as pd
import plotly.express as px
from app.core.question_loader import (
    load_questions,
    load_questions_from_folder,
    get_knowledge_points,
    get_knowledge_point_frequency
)
from app.core.practice_tracker import get_practice_log


st.set_page_config(
    page_title="总览 - C++ 做题助手",
    page_icon="📊",
    layout="wide"
)

# 数据库路径
DB_PATH = Path("data/practice_log.db")

# 题库路径
# QUESTION_BANK_PATH = "question_bank/gesp4-2606.json"
QUESTION_BANK_PATH = "question_bank"


def main():
    """总览页面"""
    st.title("📊 学习总览")

    # 加载数据
    # questions = load_questions(QUESTION_BANK_PATH)
    questions = load_questions_from_folder(QUESTION_BANK_PATH)
    practice_logs = get_practice_log(str(DB_PATH))

    if not questions:
        st.warning("没有题目数据")
        return

    # 知识点概览
    st.header("知识点概览")
    freq = get_knowledge_point_frequency(questions)
    knowledge_points = get_knowledge_points(questions)

    # 计算每个知识点的完成度
    completion = {}
    for kp in knowledge_points:
        # 从 practice_log 中匹配包含该知识点的记录
        kp_logs = []
        for log in practice_logs:
            try:
                log_kps = json.loads(log.get("knowledge_points", "[]"))
            except (json.JSONDecodeError, TypeError):
                log_kps = []
            if kp in log_kps:
                kp_logs.append(log)
        practiced_count = len(kp_logs)

        if len(kp_logs) > 0:
            correct_attempts = sum(log["correct_count"] for log in kp_logs)
            total_attempts = sum(log["correct_count"] + log["wrong_count"] for log in kp_logs)
            accuracy = correct_attempts / total_attempts if total_attempts > 0 else 0
        else:
            accuracy = 0

        completion[kp] = {
            "total": freq[kp],
            "practiced": practiced_count,
            "accuracy": accuracy
        }

    # 创建柱状图
    chart_data = pd.DataFrame([
        {
            "知识点": kp,
            "题目数量": completion[kp]["total"],
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
    st.plotly_chart(fig, width='stretch')

    # 显示正确率
    st.write("### 知识点正确率")
    accuracy_chart = px.bar(
        chart_data,
        x="知识点",
        y="正确率",
        title="各知识点正确率",
        range_y=[0, 1]
    )
    st.plotly_chart(accuracy_chart, width='stretch')

    # 统计卡片
    st.divider()
    col1, col2, col3, col4 = st.columns(4)

    total_practiced = sum(c["practiced"] for c in completion.values())
    total_correct = sum(
        log["correct_count"] for log in practice_logs
    )
    total_attempts = sum(
        log["correct_count"] + log["wrong_count"] for log in practice_logs
    )
    overall_accuracy = total_correct / total_attempts if total_attempts > 0 else 0

    col1.metric("总题目数", len(questions))
    col2.metric("已练习题目", total_practiced)
    col3.metric("总作答次数", total_attempts)
    col4.metric("总体正确率", f"{overall_accuracy:.1%}")


if __name__ == "__main__":
    main()