"""工具函数层。"""

from app.utils.crypto import decrypt, decrypt_api_key, encrypt, encrypt_api_key
from app.utils.document_parser import parse_auto, parse_docx, parse_md, parse_pdf, parse_txt
from app.utils.sse import (
    make_answer_event,
    make_done_event,
    make_error_event,
    make_fallback_event,
    make_source_event,
    sse_pack,
    sse_pack_raw,
    sse_stream,
)

__all__ = [
    # crypto
    "encrypt",
    "decrypt",
    "encrypt_api_key",
    "decrypt_api_key",
    # document_parser
    "parse_auto",
    "parse_pdf",
    "parse_docx",
    "parse_txt",
    "parse_md",
    # sse
    "sse_pack",
    "sse_pack_raw",
    "sse_stream",
    "make_answer_event",
    "make_source_event",
    "make_fallback_event",
    "make_done_event",
    "make_error_event",
]
