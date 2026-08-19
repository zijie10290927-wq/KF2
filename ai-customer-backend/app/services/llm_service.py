"""LLMService — 大模型调用服务。

多模型统一调用封装，支持流式/非流式、动态模型切换、API Key 解密。
"""

import asyncio
import logging
import re
from typing import TYPE_CHECKING, Any, AsyncGenerator, Optional

from openai import AsyncOpenAI

from app.config.settings import settings
from app.models import ModelConfig

if TYPE_CHECKING:  # pragma: no cover
    from app.services.config_service import ConfigService

logger = logging.getLogger(__name__)

# 占位符 API Key 检测：这些值都视为"未配置"，触发 mock 模式
_PLACEHOLDER_PATTERNS = (
    "sk-your-",
    "your-api-key",
    "please-change",
    "sk-xxxxxxxx",
    "sk-test",
)


def _is_mock_key(key: Optional[str]) -> bool:
    """判断是否是占位符/无效 Key，决定是否走 mock 降级。"""
    if not key:
        return True
    k = key.strip().lower()
    return any(p in k for p in _PLACEHOLDER_PATTERNS) or len(k) < 10


# -------- Mock 模式响应逻辑 --------
_MOCK_INTENT_MAP = {
    "价格": "询问产品定价",
    "费用": "询问产品定价",
    "多少钱": "询问产品定价",
    "购买": "购买/下单流程咨询",
    "下单": "购买/下单流程咨询",
    "发货": "物流与发货时间",
    "快递": "物流与发货时间",
    "物流": "物流与发货时间",
    "退款": "售后与退款政策",
    "退货": "售后与退款政策",
    "售后": "售后与退款政策",
    "使用": "产品使用说明",
    "教程": "产品使用说明",
    "怎么用": "产品使用说明",
    "出图": "AI 出图功能咨询",
    "生成": "AI 出图功能咨询",
    "图片": "AI 出图功能咨询",
    "账号": "账号与安全",
    "登录": "账号与安全",
    "密码": "账号与安全",
    "联系": "联系人工客服",
    "人工": "联系人工客服",
    "客服": "联系人工客服",
}


def _mock_classify_intent(message: str) -> tuple[str, float]:
    """mock 意图识别：关键词匹配 → (intent, confidence)。"""
    msg = message
    for kw, intent in _MOCK_INTENT_MAP.items():
        if kw in msg:
            return intent, 0.92
    return "general_qa", 0.55


_MOCK_FALLBACK_TEMPLATE = (
    "您好！感谢您的咨询。我是 AI 智能客服助手，为您提供以下帮助：\n\n"
    "📦 **常见问题快速导航**\n"
    "• 💰 价格与套餐：基础版 99 元/月，专业版 299 元/月，企业版定制\n"
    "• 🚚 发货物流：下单后 24 小时内处理，默认顺丰快递\n"
    "• 🔧 使用教程：登录后进入「帮助中心」查看视频教程\n"
    "• 🎨 AI 出图：支持文字转图片、批量生成、风格迁移等 12 种功能\n"
    "• 🧾 售后退款：7 天无理由退款，15 天质量问题退换\n\n"
    "如需人工服务，请点击右上角「转人工」按钮，或拨打客服热线 400-888-8888。"
)


def _build_mock_reply(message: str, sources: Optional[list] = None) -> str:
    """基于简单关键词规则构建 mock 回复文本。"""
    msg = message.strip()
    intent, _ = _mock_classify_intent(msg)

    if intent == "询问产品定价":
        return (
            f"关于您询问的「{msg}」价格，目前我们提供三种套餐方案：\n\n"
            "1️⃣ **基础版** ¥99/月 — 适合个人用户，含 1000 次 AI 出图、2GB 云存储\n"
            "2️⃣ **专业版** ¥299/月 — 适合中小团队，含 5000 次 AI 出图、20GB 存储、API 调用\n"
            "3️⃣ **企业版** 定制报价 — 适合企业客户，私有化部署、专属客户成功经理\n\n"
            "现在年付享 8 折优惠！如需开通请联系销售 010-12345678。"
        )
    if intent == "购买/下单流程咨询":
        return (
            "购买流程非常简单：\n\n"
            "1. 登录账号后进入「产品中心」选择您需要的套餐\n"
            "2. 点击「立即购买」，确认订单信息\n"
            "3. 选择支付方式（支持微信/支付宝/对公转账）\n"
            "4. 支付成功后服务自动开通，可在「我的订单」查看进度\n\n"
            "如有优惠券可在结算时抵扣。需要人工协助？请拨打 400-888-8888。"
        )
    if intent == "物流与发货时间":
        return (
            "关于物流与发货：\n\n"
            "• 发货时效：工作日 16:00 前付款的订单当天发货，之后顺延至下一个工作日\n"
            "• 快递选择：默认顺丰速运（包邮），偏远地区 EMS\n"
            "• 送达时间：一线城市 1-2 天，二三线 2-3 天，偏远地区 3-5 天\n"
            "• 物流跟踪：发货后可在「我的订单-物流详情」实时查看\n\n"
            "如需指定其他快递，请下单时备注或联系客服。"
        )
    if intent == "售后与退款政策":
        return (
            "售后保障政策如下：\n\n"
            "✅ **7 天无理由退款**：开通后 7 天内未使用核心功能可全额退款\n"
            "✅ **15 天质量保障**：15 天内如遇系统稳定性问题可申请退款或延期\n"
            "✅ **技术支持**：订阅期间享受免费技术支持与版本升级\n"
            "✅ **发票开具**：支持增值税普通/专用发票，在订单详情中申请\n\n"
            "退款申请路径：个人中心 → 订单记录 → 申请退款，一般 1-3 个工作日到账。"
        )
    if intent == "产品使用说明":
        return (
            f"关于「{msg}」的使用方法：\n\n"
            "1. 登录系统后进入工作台\n"
            "2. 左侧菜单选择对应的功能模块（如「AI 出图」「素材管理」等）\n"
            "3. 按照页面引导上传素材/输入提示词\n"
            "4. 点击「生成」按钮，等待几秒即可查看结果\n"
            "5. 结果可编辑、下载或分享\n\n"
            "详细图文教程和视频演示请访问「帮助中心」或点击首页「新手引导」。"
        )
    if intent == "AI 出图功能咨询":
        return (
            "AI 出图功能介绍：\n\n"
            "🎯 **核心能力**\n"
            "• 文字转图片：用自然语言描述即可生成高质量图片\n"
            "• 风格迁移：一键转换为动漫、油画、水彩、赛博朋克等 20+ 风格\n"
            "• 批量生成：一次最多生成 9 张不同变体供选择\n"
            "• 高清放大：2K/4K 高清放大，细节增强\n"
            "• 局部编辑：支持橡皮擦与重绘区域控制\n\n"
            "🚀 **操作步骤**：输入描述 → 选择风格与比例 → 点击生成，约 10-30 秒出图。\n\n"
            f"从您的提问「{msg}」来看，建议先从文字转图功能开始体验！"
        )
    if intent == "账号与安全":
        return (
            "账号与安全相关说明：\n\n"
            "🔐 **密码管理**：个人中心 → 账号安全可修改密码，建议字母+数字+符号组合\n"
            "📱 **绑定手机**：首次登录请绑定手机号用于找回密码与接收通知\n"
            "🛡️ **登录保护**：异地登录需短信验证，您可在安全中心开启二次验证\n"
            "⚠️ **账号异常**：如发现非本人登录记录，请立即修改密码并联系客服\n\n"
            "忘记密码可通过登录页「忘记密码」链接，用绑定手机号接收验证码重置。"
        )
    if intent == "联系人工客服":
        return (
            "已为您转接人工客服通道，请稍候 🔄\n\n"
            "您也可以直接通过以下方式联系我们：\n"
            "📞 客服热线：400-888-8888（工作日 9:00-21:00，周末 10:00-18:00）\n"
            "📧 邮件支持：support@example.com\n"
            "💬 在线客服：点击右下角「在线客服」按钮\n"
            "📋 工单系统：提交工单后 2 小时内必有响应\n\n"
            "请问还有什么可以帮您的吗？"
        )

    # 默认 general_qa 兜底回复
    if sources:
        src_names = "、".join(
            [s.get("filename") or s.get("source") or f"文档{i+1}" for i, s in enumerate(sources[:3])]
        )
        return (
            f"关于您的问题「{msg}」，我为您检索了知识库中的相关文档：{src_names}。\n\n"
            "基于这些资料，总结如下：\n"
            "• 本系统采用 FastAPI + Vue3 全栈架构，支持 RAG 检索增强生成\n"
            "• 通过知识库模块可上传 PDF/Word/TXT/Markdown 文档进行智能问答\n"
            "• 对话结果会自动记录，管理员可在后台查看与导出\n"
            "• 支持转人工客服、多轮对话记忆、用户画像分析\n\n"
            "如需更详细的说明，请告诉我您具体想了解哪个方面，或拨打 400-888-8888 联系人工。"
        )
    return _MOCK_FALLBACK_TEMPLATE


async def _mock_stream_tokens(text: str) -> AsyncGenerator[str, None]:
    """按 ~6 字 chunk 模拟流式输出（不阻塞事件循环）。"""
    chunk_size = 6
    for i in range(0, len(text), chunk_size):
        await asyncio.sleep(0.02)  # 控制节奏
        yield text[i : i + chunk_size]


class LLMService:
    """大模型调用服务（OpenAI 兼容协议）。

    降级策略：
    - 当 API Key 为占位符（sk-your-xxx 等）或真实调用失败时，
      自动切换到本地 mock 模式，保证系统在无外部依赖时也能演示。
    """

    def __init__(self, config_service: "Optional[ConfigService]" = None) -> None:
        self.config_service = config_service
        self._client_cache: dict[str, AsyncOpenAI] = {}
        self._force_mock: bool = False

    # ------------------------------------------------------------------ #
    # 客户端构建
    # ------------------------------------------------------------------ #
    async def get_client(self, model_name: Optional[str] = None) -> tuple[Optional[AsyncOpenAI], dict, bool]:
        """构建 AsyncOpenAI 客户端，并返回是否应走 mock。

        Returns:
            (client, model_config_dict, use_mock)
            - client: 当 use_mock=True 时为 None
        """
        model_config: Optional[ModelConfig] = None
        if self.config_service is not None:
            if model_name:
                model_config = await self.config_service.get_model_by_name(model_name)
            else:
                model_config = await self.config_service.get_default_or_env_model()

        if model_config is not None:
            api_key = await self.config_service.get_decrypted_api_key(model_config)  # type: ignore[union-attr]
            use_mock = _is_mock_key(api_key)
            cfg = {
                "model_name": model_config.model_name,
                "api_base": model_config.api_base,
                "temperature": float(model_config.temperature),
                "max_tokens": model_config.max_tokens,
            }
            if use_mock:
                return None, cfg, True
            cache_key = f"{model_config.model_name}:{model_config.api_base}"
            if cache_key not in self._client_cache:
                self._client_cache[cache_key] = AsyncOpenAI(
                    api_key=api_key or "empty",
                    base_url=model_config.api_base,
                )
            return self._client_cache[cache_key], cfg, False

        # 兜底：使用环境变量默认配置
        env_key = settings.LLM_API_KEY
        use_mock = _is_mock_key(env_key)
        cfg = {
            "model_name": settings.LLM_MODEL_NAME,
            "api_base": settings.LLM_API_BASE,
            "temperature": 0.7,
            "max_tokens": 2048,
        }
        if use_mock:
            return None, cfg, True
        cache_key = f"env:{settings.LLM_MODEL_NAME}:{settings.LLM_API_BASE}"
        if cache_key not in self._client_cache:
            self._client_cache[cache_key] = AsyncOpenAI(
                api_key=env_key or "empty",
                base_url=settings.LLM_API_BASE,
            )
        return self._client_cache[cache_key], cfg, False

    # ------------------------------------------------------------------ #
    # 通用生成接口
    # ------------------------------------------------------------------ #
    async def generate(
        self,
        messages: list[dict],
        system_prompt: Optional[str] = None,
        stream: bool = False,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Any:
        """通用生成接口。

        - 非流式：返回 str
        - 流式：返回 AsyncGenerator[str, None]（调用方需 ``async for token in ...``）
        """
        client, cfg, use_mock = await self.get_client(model_name)

        full_messages: list[dict] = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        # 提取最后一条用户消息给 mock 逻辑使用
        last_user_msg = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                last_user_msg = m.get("content", "")
                break

        temp = temperature if temperature is not None else cfg["temperature"]
        max_tok = max_tokens if max_tokens is not None else cfg["max_tokens"]

        if use_mock or self._force_mock:
            if not use_mock:
                logger.info("LLM force mock mode due to prior failures")
            reply = _build_mock_reply(last_user_msg or last_user_msg)
            if stream:
                return _mock_stream_tokens(reply)
            return reply

        if stream:
            return self._stream_generate(client, cfg["model_name"], full_messages, temp, max_tok, last_user_msg)

        try:
            resp = await client.chat.completions.create(
                model=cfg["model_name"],
                messages=full_messages,
                temperature=temp,
                max_tokens=max_tok,
                stream=False,
            )
            return resp.choices[0].message.content or ""
        except Exception as e:
            logger.error("LLM generate (non-stream) failed: %s — fallback to mock", e)
            self._force_mock = True
            return _build_mock_reply(last_user_msg)

    async def _stream_generate(
        self,
        client: AsyncOpenAI,
        model_name: str,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
        last_user_msg: str = "",
    ) -> AsyncGenerator[str, None]:
        """流式生成器：真实 API 失败时自动切 mock 续流。"""
        try:
            stream = await client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )
            any_yield = False
            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if delta is None:
                    continue
                content = getattr(delta, "content", None)
                if content:
                    any_yield = True
                    yield content
            if any_yield:
                return
            # 空回复降级
            logger.warning("LLM stream returned empty content — fallback to mock")
            self._force_mock = True
            reply = _build_mock_reply(last_user_msg)
            async for tok in _mock_stream_tokens(reply):
                yield tok
        except Exception as e:
            logger.error("LLM stream generate failed: %s — fallback to mock", e)
            self._force_mock = True
            reply = _build_mock_reply(last_user_msg)
            async for tok in _mock_stream_tokens(reply):
                yield tok

    # ------------------------------------------------------------------ #
    # 辅助
    # ------------------------------------------------------------------ #
    @staticmethod
    async def count_tokens(text: str) -> int:
        """粗略估算 token 数（4 字符 ≈ 1 token）。"""
        return max(1, len(text) // 4)

    async def list_enabled_models(self) -> list[dict]:
        """从 DB 读所有启用模型（带缓存）。"""
        if self.config_service is None:
            return []
        models = await self.config_service.list_models(enabled_only=True)
        return [
            {
                "id": m.id,
                "model_name": m.model_name,
                "api_base": m.api_base,
                "temperature": float(m.temperature),
                "max_tokens": m.max_tokens,
                "is_default": m.is_default,
            }
            for m in models
        ]

    async def close(self) -> None:
        """关闭所有缓存的客户端。"""
        for client in self._client_cache.values():
            try:
                await client.close()
            except Exception:  # pragma: no cover
                pass
        self._client_cache.clear()
