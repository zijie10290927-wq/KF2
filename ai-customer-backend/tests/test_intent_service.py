"""意图识别测试：规则引擎第一层（无 LLM 依赖）。"""

from app.services.intent_service import IntentService, IntentResult


def make_service() -> IntentService:
    """llm_service=None：规则命中直接返回，未命中走保守 fallback。"""
    return IntentService(llm_service=None)


class TestRuleLayer:
    async def test_greeting_is_off_topic(self):
        result = await make_service().classify("你好")
        assert result.intent == "off_topic"
        assert result.confidence == 0.99
        assert result.source == "rule"

    async def test_thanks_is_off_topic(self):
        result = await make_service().classify("谢谢！")
        assert result.intent == "off_topic"

    async def test_weather_is_off_topic(self):
        result = await make_service().classify("今天天气怎么样")
        assert result.intent == "off_topic"

    async def test_image_generation_is_product_qa(self):
        result = await make_service().classify("帮我画一张水墨山水画")
        assert result.intent == "product_qa"
        assert result.confidence == 0.95

    async def test_pricing_is_product_qa(self):
        result = await make_service().classify("会员套餐多少钱")
        assert result.intent == "product_qa"

    async def test_error_is_product_qa(self):
        result = await make_service().classify("生成图片报错了")
        assert result.intent == "product_qa"

    async def test_empty_message_is_ambiguous(self):
        result = await make_service().classify("")
        assert result.intent == "ambiguous"
        assert result.confidence == 0.0

    async def test_unmatched_falls_back_to_product_qa(self):
        """无 LLM 时未命中规则 → 保守视为产品问题（宁可多答）。"""
        result = await make_service().classify("某一个完全不匹配规则的问题语句")
        assert result.intent == "product_qa"
        assert result.source == "fallback"


class TestIntentResult:
    def test_defaults(self):
        r = IntentResult(intent="product_qa", confidence=0.9)
        assert r.source == "rule"
