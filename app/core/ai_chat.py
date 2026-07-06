"""AI 问答模块"""
import os
from typing import Optional, Dict
from openai import OpenAI


def ask_question(question: str, context: Optional[Dict] = None) -> str:
    """
    向 AI 提问

    Args:
        question: 用户问题
        context: 上下文信息（题目详情）

    Returns:
        AI 回答
    """
    if not question or question.strip() == "":
        return "请输入有效的问题"

    # 从环境变量读取配置
    api_key = os.getenv("LLM_API_KEY", "")
    base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    model = os.getenv("LLM_MODEL", "gpt-3.5-turbo")

    if not api_key:
        return "未配置 LLM_API_KEY，请在 .env 文件中设置"

    client = OpenAI(api_key=api_key, base_url=base_url)

    # 构建消息
    messages = []

    # 如果有上下文，添加系统消息
    if context:
        system_prompt = f"""你是一个 C++ 学习助手，正在帮助学生解答关于以下题目的问题：

题目：{context.get('question', '未知')}
用户答案：{context.get('user_answer', '未知')}
正确答案：{context.get('correct_answer', '未知')}

请根据以上上下文，用简洁明了的语言回答学生的问题。"""
        messages.append({"role": "system", "content": system_prompt})
    else:
        messages.append({
            "role": "system",
            "content": "你是一个 C++ 学习助手，请用简洁明了的语言回答学生的问题。"
        })

    # 添加用户问题
    messages.append({"role": "user", "content": question})

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.7,
            max_tokens=500
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"AI 回答出错：{str(e)}"