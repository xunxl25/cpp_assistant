"""题库管理页面"""
import streamlit as st
import json
from pathlib import Path

st.set_page_config(
    page_title="题库管理 - C++ 做题助手",
    page_icon="📚",
    layout="wide"
)

from app.core.question_loader import load_questions, get_knowledge_point_frequency

# 题库路径
QUESTION_BANK_PATH = "question_bank/gesp4-2606.json"


def main():
    """题库管理页面"""
    st.title("📚 题库管理")

    # 加载题库
    questions = load_questions(QUESTION_BANK_PATH)

    # 题库概览
    st.header("题库概览")
    col1, col2, col3 = st.columns(3)
    col1.metric("总题目数", len(questions))
    col2.metric("知识点数量", len(set(q["knowledge_point"] for q in questions)))
    freq = get_knowledge_point_frequency(questions)
    col3.metric("最多知识点", max(freq.keys(), key=lambda k: freq[k]) if freq else "无")

    # 知识点分布
    st.subheader("知识点分布")
    st.json(freq)

    # 题库表格
    st.header("题目列表")
    df_data = []
    for q in questions:
        df_data.append({
            "ID": q["id"],
            "知识点": q["knowledge_point"],
            "类型": "选择题" if q["type"] == "single_choice" else "判断题",
            "题目": q["question"][:50] + "..."
        })
    st.dataframe(df_data, use_container_width=True)

    # 题库编辑
    st.divider()
    st.header("编辑题库")
    st.warning("⚠️ 请谨慎编辑，JSON 格式必须正确")

    # 显示当前 JSON 内容
    json_content = json.dumps(questions, ensure_ascii=False, indent=2)
    edited_json = st.text_area(
        "JSON 内容",
        json_content,
        height=400,
        help="手动编辑题库 JSON"
    )

    # 保存按钮
    col1, col2 = st.columns(2)
    with col1:
        if st.button("💾 保存更改"):
            try:
                # 验证 JSON 格式
                new_questions = json.loads(edited_json)

                # 验证必需字段
                required_fields = ["id", "knowledge_point", "type", "question", "answer", "explanation"]
                for q in new_questions:
                    for field in required_fields:
                        if field not in q:
                            raise ValueError(f"题目 ID {q.get('id', '未知')} 缺少字段: {field}")
                    if q["type"] == "single_choice" and "options" not in q:
                        raise ValueError(f"题目 ID {q.get('id', '未知')} 是选择题但缺少 options 字段")

                # 保存到文件
                with open(QUESTION_BANK_PATH, "w", encoding="utf-8") as f:
                    json.dump(new_questions, f, ensure_ascii=False, indent=2)

                st.success("✅ 题库保存成功！")

            except json.JSONDecodeError as e:
                st.error(f"❌ JSON 格式错误: {e}")
            except ValueError as e:
                st.error(f"❌ 数据验证错误: {e}")
            except Exception as e:
                st.error(f"❌ 保存失败: {e}")

    with col2:
        if st.button("🔄 重新加载"):
            st.rerun()

    # 添加新题目模板
    st.divider()
    st.header("添加新题目")
    st.write("参考以下模板添加新题目：")

    template = {
        "id": "7",
        "knowledge_point": "知识点名称",
        "type": "single_choice",  # 或 "true_false"
        "question": "题目内容",
        "options": {  # 选择题需要
            "A": "选项 A",
            "B": "选项 B",
            "C": "选项 C",
            "D": "选项 D"
        },
        "answer": "A",  # 选择题填选项字母，判断题填 "true" 或 "false"
        "explanation": "解析内容"
    }

    st.json(template)
    st.info("复制上方模板，编辑后粘贴到上面的 JSON 内容区域即可")


if __name__ == "__main__":
    main()