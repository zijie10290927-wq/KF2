"""IntentService — 意图识别服务。

双层判断：第一层规则引擎（0ms）→ 第二层 LLM 精细判断 → 置信度策略兜底。
分类标签：product_qa / off_topic / ambiguous。
"""

import json
import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Optional

from app.config.settings import settings

if TYPE_CHECKING:  # pragma: no cover
    from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)

IntentType = Literal["product_qa", "off_topic", "ambiguous"]


@dataclass
class IntentResult:
    """意图识别结果。"""

    intent: IntentType
    confidence: float
    source: str = "rule"  # rule / llm / strategy


# ====================================================================== #
# 第一层：规则引擎正则
# ====================================================================== #
# 无关问题：纯问候、极短无意义、无关关键词
QUICK_OFF_TOPIC_PATTERNS: list[re.Pattern] = [
    re.compile(r"^(你好|您好|hi|hello|hey|哈喽|在吗|在不在|有人吗)\s*[!?。！？]*$", re.IGNORECASE),
    re.compile(r"^(谢谢|感谢|thanks|thx|多谢|辛苦了)\s*[!?。！？]*$", re.IGNORECASE),
    re.compile(r"^(再见|拜拜|bye|88|晚安)\s*[!?。！？]*$", re.IGNORECASE),
    re.compile(r"(天气|股票|彩票|新闻|笑话|脑筋急转弯|算命|星座|运势)"),
    re.compile(r"(今天几号|现在几点|星期几)"),
]

# 产品相关：生成/出图/提示词/报错/付费等
QUICK_PRODUCT_PATTERNS: list[re.Pattern] = [
    re.compile(r"(生成|出图|画图|绘图|做图|AI画|画一张|生成一张|帮我画)", re.IGNORECASE),
    re.compile(r"(提示词|prompt|咒语|描述词|正向提示|反向提示)", re.IGNORECASE),
    re.compile(r"(分辨率|清晰度|尺寸|宽高|像素|比例|aspect)", re.IGNORECASE),
    re.compile(r"(报错|错误|失败|无法|不能|用不了|bug|error|崩溃|卡住)", re.IGNORECASE),
    re.compile(r"(付费|充值|订阅|会员|套餐|价格|多少钱|计费|pricing)", re.IGNORECASE),
    re.compile(r"(风格|水墨|油画|水彩|动漫|写实|赛博朋克|3D|扁平|卡通)", re.IGNORECASE),
    re.compile(r"(模型|大模型|duc|stable.diffusion|sd|midjourney|mj)", re.IGNORECASE),
    re.compile(r"(下载|导出|保存图片|保存到|下载图片)", re.IGNORECASE),
    re.compile(r"(账户|账号|登录|注册|登入|sign.?in|sign.?up|log.?in)", re.IGNORECASE),
    re.compile(r"(删除|修改|编辑|重做|撤销|历史记录|我的作品)", re.IGNORECASE),
]


# ====================================================================== #
# 第二层：LLM Prompt (Few-shot V2)
# ====================================================================== #
INTENT_PROMPT_V2 = """你是一个意图分类器。请判断用户问题是否与「AI出图产品」相关。

分类标签：
- product_qa：与AI出图/绘画/图像生成产品相关的问题（功能使用、提示词、报错、付费、账户、风格、分辨率、模型、下载等）
- off_topic：与AI出图产品完全无关的问题（天气、新闻、闲聊问候、其他行业咨询等）

输出 JSON 格式：
{"intent": "product_qa" | "off_topic", "confidence": 0.0~1.0}

示例：
用户：如何生成一张水墨风格的山水画？
输出：{"intent": "product_qa", "confidence": 0.98}

用户：提示词怎么写效果更好？
输出：{"intent": "product_qa", "confidence": 0.97}

用户：图片分辨率最高支持多少？
输出：{"intent": "product_qa", "confidence": 0.99}

用户：为什么我生成的图这么模糊？
输出：{"intent": "product_qa", "confidence": 0.95}

用户：你们和Midjourney比怎么样？
输出：{"intent": "product_qa", "confidence": 0.92}

用户：你们这破产品太垃圾了
输出：{"intent": "product_qa", "confidence": 0.88}

用户：会员套餐多少钱？
输出：{"intent": "product_qa", "confidence": 0.99}

用户：图片下载下来是PNG还是JPG？
输出：{"intent": "product_qa", "confidence": 0.97}

用户：账号登录不上了
输出：{"intent": "product_qa", "confidence": 0.96}

用户：今天天气怎么样？
输出：{"intent": "off_topic", "confidence": 0.99}

请对以下用户问题进行分类，只输出 JSON，不要任何其他文字：
用户：{message}
输出："""


class IntentService:
    """意图识别服务：规则 + LLM 双层判断。"""

    CONFIDENCE_HIGH: float = settings.INTENT_CONFIDENCE_HIGH  # 0.85
    CONFIDENCE_LOW: float = settings.INTENT_CONFIDENCE_LOW  # 0.60

    def __init__(self, llm_service: "Optional[LLMService]" = None) -> None:
        self.llm_service = llm_service

    async def classify(self, message: str, history: Optional[list[dict]] = None) -> IntentResult:
        """主入口：规则过滤 → LLM 判断 → 置信度策略。"""
        message = (message or "").strip()
        if not message:
            return IntentResult(intent="ambiguous", confidence=0.0, source="rule")

        # 第一层：规则匹配
        rule_result = self._match_rules(message)
        if rule_result is not None:
            return rule_result

        # 第二层：LLM 精细判断
        if self.llm_service is None:
            # 无 LLM 时，保守视为产品问题（宁可多答）
            return IntentResult(intent="product_qa", confidence=0.50, source="fallback")

        try:
            llm_result = await self._call_llm_classify(message, history or [])
        except Exception as e:
            logger.error("LLM classify failed: %s", e)
            return IntentResult(intent="product_qa", confidence=0.50, source="fallback")

        # 置信度策略
        return self._apply_confidence_strategy(llm_result)

    # ------------------------------------------------------------------ #
    # 第一层：规则引擎
    # ------------------------------------------------------------------ #
    def _match_rules(self, message: str) -> Optional[IntentResult]:
        """关键词/正则快速匹配，命中则返回高置信度结果。"""
        # off_topic 优先（防误判）
        for pattern in QUICK_OFF_TOPIC_PATTERNS:
            if pattern.search(message):
                return IntentResult(intent="off_topic", confidence=0.99, source="rule")
        for pattern in QUICK_PRODUCT_PATTERNS:
            if pattern.search(message):
                return IntentResult(intent="product_qa", confidence=0.95, source="rule")
        return None

    # ------------------------------------------------------------------ #
    # 第二层：LLM 判断
    # ------------------------------------------------------------------ #
    async def _call_llm_classify(
        self, message: str, history: list[dict]
    ) -> IntentResult:
        """调用 LLM，temperature=0.05，JSON 模式输出。"""
        prompt = INTENT_PROMPT_V2.format(message=message[:500])

        messages = [
            {"role": "system", "content": "你是严格的意图分类器，只输出JSON。"},
            {"role": "user", "content": prompt},
        ]

        # 注入最近 2 轮上下文（用于多轮短回复判断）
        if history:
            recent = history[-4:]  # 最近 2 轮（user+assistant）
            context_lines = [
                f"{'用户' if m.get('role') == 'user' else '助手'}: {m.get('content', '')[:200]}"
                for m in recent
            ]
            if context_lines:
                messages.insert(
                    1,
                    {
                        "role": "user",
                        "content": f"对话历史参考（注意多轮上下文）：\n" + "\n".join(context_lines),
                    },
                )

        # LLMService.generate 非流式返回 str
        raw = await self.llm_service.generate(
            messages=messages,
            stream=False,
            temperature=0.05,
            max_tokens=80,
        )
        raw = (raw or "").strip()

        data = self._parse_json_safe(raw)
        intent_raw = str(data.get("intent", "")).strip().lower()
        confidence = float(data.get("confidence", 0.0))

        if intent_raw not in ("product_qa", "off_topic"):
            return IntentResult(intent="ambiguous", confidence=confidence, source="llm")

        return IntentResult(intent=intent_raw, confidence=confidence, source="llm")  # type: ignore[arg-type]

    # ------------------------------------------------------------------ #
    # 置信度策略
    # ------------------------------------------------------------------ #
    def _apply_confidence_strategy(self, result: IntentResult) -> IntentResult:
        """置信度兜底：≥0.85 直取；0.60~0.85 间 off_topic 改为 product_qa；<0.60 ambiguous。"""
        conf = result.confidence
        if conf >= self.CONFIDENCE_HIGH:
            return result
        if conf >= self.CONFIDENCE_LOW:
            # 宁可多答不漏答：中间区间的 off_topic 保守改为 product_qa
            if result.intent == "off_topic":
                return IntentResult(
                    intent="product_qa", confidence=conf, source="strategy"
                )
            return result
        # 低置信度
        return IntentResult(intent="ambiguous", confidence=conf, source="strategy")

    # ------------------------------------------------------------------ #
    # JSON 容错解析
    # ------------------------------------------------------------------ #
    @staticmethod
    def _parse_json_safe(text: str) -> dict:
        """从模型输出中容错提取 JSON（支持首尾噪声 + markdown 代码块）。"""
        text = text.strip()
        # 去除 markdown 代码块
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        # 直接尝试
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # 提取第一个 {...}
        match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        return {}
