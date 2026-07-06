"""做题界面组件 - 复用逻辑"""
from typing import List, Dict, Optional, Callable
import streamlit as st
from pathlib import Path
from app.core.practice_tracker import record_answer
from app.core.ai_chat import ask_question


def render_practice_ui(
    questions: List[Dict],
    current_index: int,
    db_path: str,
    is_mistake_mode: bool = False,
    on_remove_from_mistake: Optional[Callable] = None
) -> Dict:
    """
    渲染做题界面

    Args:
        questions: 题目列表
        current_index: 当前题目索引
        db_path: 数据库路径
        is_mistake_mode: 是否为错题模式（会显示"移出错题本"选项）
        on_remove_from_mistake: 移出错题本的回调函数

    Returns:
        {'action': 'next'/'stay'/'remove', 'next_index': int}
    """
    if not questions or current_index >= len(questions):
        return {'action': 'stay', 'next_index': current_index}

    current_question = questions[current_index]

    # 获取知识点（兼容新旧格式）
    kps = current_question.get("knowledge_points", [])
    if not kps:
        kp = current_question.get("knowledge_point", "")
        kps = [kp] if kp else ["未知"]
    knowledge_point = kps[0] if kps else "未知"

    # 显示题目
    st.subheader(f"题目 {current_index + 1} / {len(questions)}")
    st.write(current_question["question"])
    st.caption(f"知识点: {knowledge_point}")

    # 显示选项（选择题）
    if current_question["type"] == "single_choice":
        options = current_question["options"]
        for key, value in options.items():
            st.write(f"**{key}.** {value}")
        user_answer = st.radio("选择答案", list(options.keys()), key=f"answer_{current_question['id']}")

    # 判断题
    elif current_question["type"] == "true_false":
        user_answer = st.radio("选择答案", ["true", "false"],
                               format_func=lambda x: "正确" if x == "true" else "错误",
                               key=f"answer_tf_{current_question['id']}")

    else:
        st.error("未知题目类型")
        return {'action': 'stay', 'next_index': current_index}

    # 提交按钮
    submit_col, next_col = st.columns([1, 1])
    with submit_col:
        if st.button("提交答案", key=f"submit_{current_question['id']}"):
            is_correct = user_answer == current_question["answer"]

            # 记录答案
            record_answer(
                db_path,
                current_question["id"],
                user_answer,
                current_question["answer"],
                is_correct,
                knowledge_point
            )

            # 显示结果
            if is_correct:
                st.success("✅ 回答正确！")

                # 错题模式：答对后显示"移出错题本"/"再练一次"
                if is_mistake_mode and on_remove_from_mistake:
                    remove_col, stay_col = st.columns([1, 1])
                    with remove_col:
                        if st.button("移出错题本", key=f"remove_{current_question['id']}"):
                            on_remove_from_mistake(current_question["id"])
                            return {'action': 'remove', 'next_index': current_index + 1}
                    with stay_col:
                        if st.button("再练一次", key=f"stay_{current_question['id']}"):
                            return {'action': 'stay', 'next_index': current_index}
            else:
                st.error(f"❌ 回答错误！正确答案是: {current_question['answer']}")

            # 显示解析
            st.info(current_question["explanation"])

    # 下一题按钮
    with next_col:
        if st.button("下一题", key=f"next_{current_question['id']}"):
            if current_index + 1 < len(questions):
                return {'action': 'next', 'next_index': current_index + 1}
            else:
                st.success("🎉 已完成所有题目！")

    # AI 问答区域
    st.divider()
    st.header("💬 AI 问答助手")

    # 获取当前题目的上下文
    context = {
        "question": current_question["question"],
        "user_answer": user_answer if 'user_answer' in locals() else "",
        "correct_answer": current_question["answer"]
    }

    # 用户输入
    user_input = st.text_input("向 AI 提问（关于当前题目）", placeholder="例如：为什么我的答案错了？")

    if st.button("发送问题", key=f"ask_{current_question['id']}"):
        if user_input:
            response = ask_question(user_input, context=context)
            st.info(response)
        else:
            st.warning("请输入问题")

    return {'action': 'stay', 'next_index': current_index}