"""总览页 - 只显示知识点统计"""
import sys
import os
import json
from pathlib import Path

# ========== 先添加项目根目录到 Python 路径 ==========
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
# ========== 然后再导入 app 模块 ==========

# import importlib
# import app.core.question_loader
# importlib.reload(app.core.question_loader)

import streamlit as st
import pandas as pd
import plotly.express as px
from app.core.cache import (
    get_practice_log_cached,
    get_kp_frequency_cached,
    get_total_question_count_cached,
    get_exam_types,
    get_exam_levels,
    get_exam_info_by_ids_cached,
)


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


def _log_matches_exam_filter(
    log: dict,
    exam_info: dict,
    exam_types,
    exam_levels,
) -> bool:
    """判断一条练习日志对应的题目是否落在所选考试类型/级别内"""
    info = exam_info.get(log.get("question_id"))
    if info is None:
        # 题目不在索引里（可能已被删除），有筛选时保守地排除
        return False
    q_type, q_level = info
    if exam_types and q_type not in exam_types:
        return False
    if exam_levels and q_level not in exam_levels:
        return False
    return True


def main():
    """总览页面"""
    st.title("📊 学习总览")

    # ===== 顶端：考试类型/级别选择（可选，影响下方所有统计） =====
    all_types = get_exam_types()
    all_levels = get_exam_levels()

    col1, col2 = st.columns(2)
    with col1:
        st.selectbox("考试类型", ["全部"] + all_types, key="overview_exam_type")
    with col2:
        st.selectbox("级别", ["全部"] + all_levels, key="overview_exam_level")

    sel_type = st.session_state.get("overview_exam_type", "全部")
    sel_level = st.session_state.get("overview_exam_level", "全部")
    exam_types = None if sel_type == "全部" else [sel_type]
    exam_levels = None if sel_level == "全部" else [sel_level]
    types_param = tuple(exam_types) if exam_types else None
    levels_param = tuple(exam_levels) if exam_levels else None

    # 加载数据（全部从索引 DB 查，不加载 JSON 文件）
    total_questions = get_total_question_count_cached(
        QUESTION_BANK_PATH, types_param, levels_param
    )
    freq = get_kp_frequency_cached(
        QUESTION_BANK_PATH, types_param, levels_param
    )
    practice_logs = get_practice_log_cached(str(DB_PATH))

    # 练习日志按考试类型/级别过滤（日志本身不带 exam 字段，经索引查询题目归属）
    if exam_types or exam_levels:
        practiced_ids = list({log["question_id"] for log in practice_logs})
        exam_info = get_exam_info_by_ids_cached(
            tuple(practiced_ids), QUESTION_BANK_PATH
        )
        practice_logs = [
            log for log in practice_logs
            if _log_matches_exam_filter(log, exam_info, exam_types, exam_levels)
        ]

    if total_questions == 0:
        st.warning("没有题目数据")
        return

    # 知识点概览
    st.header("知识点概览")
    knowledge_points = sorted(freq.keys())

    # 预处理：解析每条日志的知识点，按知识点分组（O(L) 一次扫完）
    kp_logs_map = {}  # {kp: [log, ...]}
    for log in practice_logs:
        try:
            log_kps = json.loads(log.get("knowledge_points", "[]"))
        except (json.JSONDecodeError, TypeError):
            log_kps = []
        for kp in log_kps:
            kp_logs_map.setdefault(kp, []).append(log)

    # 计算每个知识点的完成度
    completion = {}
    for kp in knowledge_points:
        kp_logs = kp_logs_map.get(kp, [])
        practiced_count = len(kp_logs)

        if kp_logs:
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

    col1.metric("总题目数", total_questions)
    col2.metric("已练习题目", total_practiced)
    col3.metric("总作答次数", total_attempts)
    col4.metric("总体正确率", f"{overall_accuracy:.1%}")


if __name__ == "__main__":
    main()