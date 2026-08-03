"""做题界面组件 - 复用逻辑"""
import json
from typing import List, Dict, Optional, Callable
import streamlit as st
from pathlib import Path
from app.core.practice_tracker import record_answer
from app.core.ai_chat import ask_question


@st.dialog("🎉 做题完成")
def _show_completion_dialog(total: int, correct: int, skipped: int):
    """完成所有题目后弹出统计"""
    answered = total - skipped
    accuracy = correct / answered if answered > 0 else 0
    st.markdown(f"""
    **本次做题统计**

    | 项目 | 数量 |
    |------|------|
    | 总题目数 | {total} |
    | 实际作答 | {answered} |
    | 跳过未答 | {skipped} |
    | 答对 | {correct} |
    | 答错 | {answered - correct} |

    ### 正确率：{accuracy:.1%}
    """)
    if st.button("好的", type="primary"):
        st.rerun()


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

    # 初始化答案变量（防御性：避免 if/elif 分支未命中时 NameError）
    user_answer = None
    correct_answer = None

    # 获取知识点（兼容新旧格式），转为 JSON 数组字符串存入 DB
    kps = current_question.get("knowledge_points", [])
    if not kps:
        kp = current_question.get("knowledge_point", "")
        kps = [kp] if kp else ["未知"]
    knowledge_points_json = json.dumps(kps, ensure_ascii=False)

    # 显示题目
    st.subheader(f"题目 {current_index + 1} / {len(questions)}")
    # 将字符串中的 \n 替换为 HTML 的 <br> 标签
    # st.write(current_question["question"].replace("\n", "<br>"))
    st.markdown(current_question["question"].replace("\n", "<br>"), unsafe_allow_html=True)

    # 显示选项（选择题）
    if current_question["type"] == "single_choice":
        options = current_question["options"]
        correct_answer = current_question["answer"]
        # 固定在最后追加"不会"选项
        choice_keys = list(options.keys()) + ["__unknown__"]
        user_answer = st.radio(
            "选择你的答案",
            choice_keys,
            index=None,
            format_func=lambda x: "不会" if x == "__unknown__" else f"**{x}.** {options[x]}",
            key=f"answer_{current_question['id']}",
            label_visibility="collapsed"  # 隐藏标签
        )

    # 判断题
    elif current_question["type"] == "true_false":
        correct_answer = current_question.get("answer", "")
        # load_questions 已在加载时归一化 T/F → true/false，
        # 这里仅做防御性校验
        if correct_answer not in ("true", "false"):
            st.warning(
                f"⚠️ 题目数据异常：判断题答案应为 true/false，"
                f"实际为「{correct_answer}」。"
                f"请检查题库 JSON 文件中此题（ID: {current_question['id']}）的 answer 字段。"
            )
        # 固定在最后追加"不会"选项
        user_answer = st.radio(
            "选择你的答案",
            ["true", "false", "__unknown__"],
            index=None,
            format_func=lambda x: "不会" if x == "__unknown__" else ("正确" if x == "true" else "错误"),
            key=f"answer_tf_{current_question['id']}",
            label_visibility="collapsed"  # 隐藏标签
        )

    else:
        st.error("未知题目类型")
        return {'action': 'stay', 'next_index': current_index}

    # 提交状态跟踪（防止重复提交：同一道题提交一次后按钮消失，结果持久展示）
    submit_key = f"submitted_{current_question['id']}"
    already_submitted = st.session_state.get(submit_key, False)

    # session 级答题统计（key 按题目列表 ID 隔离，避免不同批次混计）
    session_key = f"session_stats_{id(questions)}"
    if session_key not in st.session_state:
        st.session_state[session_key] = {"total": len(questions), "answered": 0, "correct": 0}

    # 提交按钮 + 下一题按钮
    submit_col, next_col = st.columns([1, 1])
    with submit_col:
        if not already_submitted:
            # 未提交：显示提交按钮
            if st.button("提交答案", key=f"submit_{current_question['id']}"):
                if user_answer is None:
                    st.warning("请先选择一个选项")
                else:
                    if user_answer == "__unknown__":
                        is_correct = False
                        recorded_answer = "不会"
                    else:
                        is_correct = user_answer == correct_answer
                        recorded_answer = user_answer

                    # 记录答案
                    record_answer(
                        db_path,
                        current_question["id"],
                        recorded_answer,
                        correct_answer,
                        is_correct,
                        knowledge_points_json
                    )
                    # 清除练习记录缓存（practice_log 变更后需刷新）
                    st.cache_data.clear()

                    # 累计 session 统计
                    st.session_state[session_key]["answered"] += 1
                    if is_correct:
                        st.session_state[session_key]["correct"] += 1

                    # 标记已提交，存储结果，rerun 后走 else 分支持久展示
                    st.session_state[submit_key] = True
                    st.session_state[f"result_{current_question['id']}"] = is_correct
                    st.rerun()
        else:
            # 已提交：持久展示结果（不受 rerun 影响）
            is_correct = st.session_state.get(f"result_{current_question['id']}", False)

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
                            # 重置提交状态，允许重新作答
                            if submit_key in st.session_state:
                                del st.session_state[submit_key]
                            return {'action': 'stay', 'next_index': current_index}
            else:
                # 判断题显示中文，选择题显示字母
                if current_question["type"] == "true_false":
                    display = "正确" if correct_answer == "true" else "错误"
                else:
                    display = correct_answer
                st.error(f"❌ 回答错误！正确答案是: {display}")

            # 显示解析
            st.info(current_question["explanation"])

    # 下一题按钮
    with next_col:
        if st.button("下一题", key=f"next_{current_question['id']}"):
            if current_index + 1 < len(questions):
                return {'action': 'next', 'next_index': current_index + 1}
            else:
                # 最后一题：弹出统计
                stats = st.session_state.get(session_key, {"total": len(questions), "answered": 0, "correct": 0})
                skipped = stats["total"] - stats["answered"]
                _show_completion_dialog(
                    total=stats["total"],
                    correct=stats["correct"],
                    skipped=skipped
                )

    # AI 问答区域
    st.divider()
    st.header("💬 AI 问答助手")

    # 用户输入
    user_input = st.text_input("向 AI 提问（关于当前题目）", placeholder="例如：为什么我的答案错了？")

    if st.button("发送问题", key=f"ask_{current_question['id']}"):
        if user_input:
            # 只在点击发送时构建 context，避免每次渲染都创建
            context = {
                "question": current_question["question"],
                "user_answer": user_answer,
                "correct_answer": correct_answer
            }
            response = ask_question(user_input, context=context)
            st.info(response)
        else:
            st.warning("请输入问题")

    return {'action': 'stay', 'next_index': current_index}