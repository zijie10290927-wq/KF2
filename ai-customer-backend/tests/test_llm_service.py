"""LLM 服务测试：mock 降级逻辑（不产生真实 API 调用）。"""

from app.services.llm_service import LLMService, _build_mock_reply, _is_mock_key


class TestMockKeyDetection:
    def test_empty_key_is_mock(self):
        assert _is_mock_key("") is True
        assert _is_mock_key(None) is True

    def test_placeholder_keys_are_mock(self):
        """占位符 Key 应被识别为 mock 模式。"""
        for key in ["sk-your-api-key", "your-api-key-here", "sk-test", "sk-xxxxxxxx"]:
            assert _is_mock_key(key) is True

    def test_short_key_is_mock(self):
        """过短 Key（<10 字符）视为无效。"""
        assert _is_mock_key("sk-abc") is True

    def test_real_key_is_not_mock(self):
        """真实形态的 Key 不应触发 mock。"""
        assert _is_mock_key("sk-prod-abcdef1234567890abcdef") is False


class TestMockReply:
    def test_price_intent(self):
        reply = _build_mock_reply("这个多少钱")
        assert "套餐" in reply or "价格" in reply

    def test_refund_intent(self):
        reply = _build_mock_reply("怎么退款")
        assert "退款" in reply

    def test_off_topic_greeting_falls_to_default(self):
        reply = _build_mock_reply("今天天气不错")
        assert len(reply) > 0  # 默认兜底模板

    def test_reply_with_sources(self):
        reply = _build_mock_reply(
            "系统功能", sources=[{"filename": "产品手册.pdf"}]
        )
        assert "产品手册" in reply


class TestCountTokens:
    async def test_count_tokens_async(self):
        """粗略 token 估算（4 字符 ≈ 1 token）。"""
        assert await LLMService.count_tokens("abcd") == 1
        assert await LLMService.count_tokens("") == 1  # max(1, 0)
        assert await LLMService.count_tokens("abcdefgh") == 2
