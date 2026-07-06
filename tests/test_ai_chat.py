"""ai_chat 模块的测试"""
import pytest
from unittest.mock import Mock, patch
from app.core.ai_chat import ask_question


class TestAskQuestion:
    """测试 ask_question 函数"""

    @patch("app.core.ai_chat.OpenAI")
    def test_basic_question(self, mock_openai):
        """测试基本问答"""
        import os
        os.environ["LLM_API_KEY"] = "test_key"
        os.environ["LLM_BASE_URL"] = "http://test.com"
        os.environ["LLM_MODEL"] = "test_model"

        # 模拟 OpenAI 响应
        mock_client = Mock()
        mock_openai.return_value = mock_client
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="这是测试回答"))]
        mock_client.chat.completions.create.return_value = mock_response

        result = ask_question("什么是变量？")

        assert result == "这是测试回答"
        mock_client.chat.completions.create.assert_called_once()

    @patch("app.core.ai_chat.OpenAI")
    def test_question_with_context(self, mock_openai):
        """测试带上下文的问答"""
        import os
        os.environ["LLM_API_KEY"] = "test_key"
        os.environ["LLM_BASE_URL"] = "http://test.com"
        os.environ["LLM_MODEL"] = "test_model"

        mock_client = Mock()
        mock_openai.return_value = mock_client
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="带上下文的回答"))]
        mock_client.chat.completions.create.return_value = mock_response

        context = {
            "question": "C++ 中 int 的大小是？",
            "user_answer": "2 字节",
            "correct_answer": "4 字节"
        }

        result = ask_question("为什么我的答案错了？", context=context)

        assert result == "带上下文的回答"
        # 验证上下文被传递到系统消息中
        call_args = mock_client.chat.completions.create.call_args
        messages = call_args.kwargs["messages"]
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert "上下文" in messages[0]["content"]

    @patch("app.core.ai_chat.OpenAI")
    def test_api_key_from_env(self, mock_openai):
        """测试从环境变量读取 API Key"""
        import os
        os.environ["LLM_API_KEY"] = "test_key"
        os.environ["LLM_BASE_URL"] = "http://test.com"
        os.environ["LLM_MODEL"] = "test_model"

        mock_client = Mock()
        mock_openai.return_value = mock_client
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="回答"))]
        mock_client.chat.completions.create.return_value = mock_response

        result = ask_question("测试")

        mock_openai.assert_called_with(
            api_key="test_key",
            base_url="http://test.com"
        )
        call_args = mock_client.chat.completions.create.call_args
        assert call_args.kwargs["model"] == "test_model"

    @patch("app.core.ai_chat.OpenAI")
    def test_empty_question(self, mock_openai):
        """测试空问题"""
        mock_client = Mock()
        mock_openai.return_value = mock_client

        result = ask_question("")

        assert result == "请输入有效的问题"
        mock_client.chat.completions.create.assert_not_called()