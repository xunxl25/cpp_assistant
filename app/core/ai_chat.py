"""AI 问答模块"""
import os
from typing import Optional, Dict, List
from dotenv import load_dotenv
from openai import OpenAI

# 加载项目根目录 .env（Streamlit 不会自动加载）
load_dotenv()


def _get_client():
    """构造 OpenAI 客户端（兼容 DeepSeek / GLM / OpenAI 等）"""
    api_key = os.getenv("LLM_API_KEY", "")
    base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    if not api_key:
        return None, None
    return OpenAI(api_key=api_key, base_url=base_url), os.getenv("LLM_MODEL", "gpt-3.5-turbo")


def _chat_create(client, model: str, messages: List[Dict], temperature: float, max_tokens: int):
    """
    发起对话请求。

    对 GLM-4.5 等思考模型，默认传 enable_thinking=False 让答案落在 content
    （否则落 reasoning_content，content 为空）。若服务商不支持该参数报错，
    则回退到普通请求。若 content 仍空但 reasoning_content 有值，取后者。
    GLM-4.5-Air 偶发返回空 content（思考未结束/被截断），此时用更大
    max_tokens 重试一次。
    """
    def _once(mt):
        try:
            return client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=mt,
                extra_body={"enable_thinking": False},
            )
        except Exception:
            return client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=mt,
            )

    response = _once(max_tokens)
    msg = response.choices[0].message
    content = msg.content
    if not content and getattr(msg, "reasoning_content", None):
        content = msg.reasoning_content

    # 偶发空响应：放大 max_tokens 重试一次
    if not content:
        response = _once(max(max_tokens * 4, 4000))
        msg = response.choices[0].message
        content = msg.content
        if not content and getattr(msg, "reasoning_content", None):
            content = msg.reasoning_content

    return content or ""


def call_llm(prompt: str, system: Optional[str] = None, max_tokens: int = 2000) -> str:
    """
    原始 LLM 补全接口（PDF 解析等场景使用）

    复用与 ask_question 相同的 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL 环境变量。
    与 ask_question 的区别：不预设 C++ 学习助手系统提示，调用方完全控制 prompt。

    Args:
        prompt: 用户提示（完整内容）
        system: 可选系统提示
        max_tokens: 最大输出 token 数

    Returns:
        LLM 返回文本

    Raises:
        RuntimeError: 未配置 LLM_API_KEY 时抛出，调用方可据此标记失败
    """
    client, model = _get_client()
    if not client:
        raise RuntimeError("未配置 LLM_API_KEY，请在 .env 文件中设置")

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    return _chat_create(client, model, messages, temperature=0.2, max_tokens=max_tokens)


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

    client, model = _get_client()
    if not client:
        return "未配置 LLM_API_KEY，请在 .env 文件中设置"

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
        return _chat_create(client, model, messages, temperature=0.4, max_tokens=500)
    except Exception as e:
        return f"AI 回答出错：{str(e)}"
