"""SSE 工具测试：事件帧格式与构造器。"""

import json

from app.utils.sse import (
    make_answer_event,
    make_done_event,
    make_error_event,
    make_fallback_event,
    make_source_event,
    sse_pack,
)


class TestSsePack:
    def test_frame_format(self):
        """帧格式必须为 event: X\\ndata: {...}\\n\\n（前端按 \\n\\n 分割）。"""
        frame = sse_pack(make_answer_event("你好"))
        text = frame.decode("utf-8")
        assert text.startswith("event: answer\n")
        assert text.endswith("\n\n")

    def test_frame_json_payload(self):
        """data 行必须是合法 JSON 且含 type 字段。"""
        frame = sse_pack(make_answer_event("hello"))
        data_line = frame.decode("utf-8").split("\n")[1]
        assert data_line.startswith("data: ")
        payload = json.loads(data_line[6:])
        assert payload["type"] == "answer"
        assert payload["content"] == "hello"

    def test_chinese_content_not_escaped(self):
        """中文应以 UTF-8 原文输出（ensure_ascii=False）。"""
        frame = sse_pack(make_answer_event("你好世界"))
        assert "你好世界".encode("utf-8") in frame


class TestEventBuilders:
    def test_error_event_no_exception_detail(self):
        """回归测试：error 事件消息应为通用文案，不含异常堆栈细节。"""
        evt = make_error_event("处理失败，请稍后重试")
        assert "Traceback" not in evt.message
        assert evt.type == "error"

    def test_done_event_with_message_id(self):
        evt = make_done_event("msg-123")
        assert evt.type == "done"
        assert evt.data == {"message_id": "msg-123"}

    def test_done_event_without_message_id(self):
        evt = make_done_event()
        assert evt.data is None

    def test_source_event(self):
        evt = make_source_event([{"title": "t", "score": 0.9, "snippet": "s"}])
        assert evt.type == "source"
        assert evt.sources[0].title == "t"  # list[dict] 会被包装为 SourceItem

    def test_fallback_event(self):
        evt = make_fallback_event({"show_transfer": True})
        assert evt.type == "fallback"
        assert evt.data["show_transfer"] is True
