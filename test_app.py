"""测试应用能否完整运行"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("正在测试模块导入...")

try:
    from app.core.question_loader import load_questions, get_knowledge_point_frequency
    print("✅ question_loader 导入成功")
except Exception as e:
    print(f"❌ question_loader 导入失败: {e}")
    sys.exit(1)

try:
    from app.core.practice_tracker import PracticeTracker, record_answer, get_practice_log
    print("✅ practice_tracker 导入成功")
except Exception as e:
    print(f"❌ practice_tracker 导入失败: {e}")
    sys.exit(1)

try:
    from app.core.ai_chat import ask_question
    print("✅ ai_chat 导入成功")
except Exception as e:
    print(f"❌ ai_chat 导入失败: {e}")
    sys.exit(1)

print("\n正在测试核心功能...")

# 测试题库加载
try:
    questions = load_questions("question_bank/gesp4-2606.json")
    assert len(questions) == 6
    print(f"✅ 题库加载成功，共 {len(questions)} 道题")
except Exception as e:
    print(f"❌ 题库加载失败: {e}")
    sys.exit(1)

# 测试知识点统计
try:
    freq = get_knowledge_point_frequency(questions)
    assert freq == {"变量与数据类型": 3, "控制流": 3}
    print(f"✅ 知识点统计成功: {freq}")
except Exception as e:
    print(f"❌ 知识点统计失败: {e}")
    sys.exit(1)

# 测试练习记录
import tempfile
with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
    temp_db = f.name

try:
    tracker = PracticeTracker(temp_db)
    tracker.add_practice_log(
        question_id="1",
        user_answer="A",
        correct_answer="A",
        is_correct=True,
        knowledge_points='["变量与数据类型"]'
    )
    logs = tracker.get_all_logs()
    assert len(logs) == 1
    print(f"✅ 练习记录测试成功")
except Exception as e:
    print(f"❌ 练习记录测试失败: {e}")
    sys.exit(1)
finally:
    os.unlink(temp_db)

print("\n正在测试 Streamlit 导入...")

try:
    import streamlit as st
    import pandas as pd
    import plotly.express as px
    print("✅ Streamlit 相关库导入成功")
except Exception as e:
    print(f"❌ Streamlit 相关库导入失败: {e}")
    sys.exit(1)

print("\n" + "="*50)
print("✅ 所有测试通过！应用可以正常运行。")
print("="*50)
print("\n启动命令：")
print("  streamlit run app/app.py")
print("\n访问地址：")
print("  http://localhost:8501")