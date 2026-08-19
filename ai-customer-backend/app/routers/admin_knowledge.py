"""知识库管理路由 /admin/knowledge/*（需 admin 角色）。

- POST   /admin/knowledge/upload              上传文档 → 立即返回 doc_id + status=uploading → 后台异步处理
- GET    /admin/knowledge/docs                分页文档列表（status/category/keyword 过滤）
- GET    /admin/knowledge/docs/{doc_id}       单条文档详情
- DELETE /admin/knowledge/docs/{doc_id}       联动清理（MinIO + Milvus + MySQL）
- POST   /admin/knowledge/docs/{doc_id}/reindex  重新向量化索引
"""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db
from app.exceptions import NotFoundError
from app.models import User
from app.schemas.common import ApiResponse
from app.schemas.knowledge import DocListItem, DocUploadResponse
from app.services.deps import get_admin_user, get_knowledge_service
from app.services.knowledge_service import KnowledgeService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/knowledge", tags=["B端-知识库管理"])

# 允许的文件扩展名
_ALLOWED_EXTENSIONS = {"pdf", "docx", "doc", "txt", "md", "markdown"}
# 最大文件大小（50MB）
_MAX_FILE_SIZE = 50 * 1024 * 1024


@router.post("/upload", response_model=ApiResponse, summary="上传知识库文档")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="PDF/Word/TXT/MD 文档"),
    category: str = Form(default="", description="知识分类标签"),
    chunk_size: int = Form(default=0, description="分块大小，0 表示用系统默认"),
    overlap: int = Form(default=0, description="分块重叠，0 表示用系统默认"),
    knowledge_service: KnowledgeService = Depends(get_knowledge_service),
    user: User = Depends(get_admin_user),
) -> ApiResponse:
    """multipart/form-data 上传文档。

    立即返回 doc_id + status=uploading，文件落 MinIO 后由 BackgroundTasks 异步执行
    解析 → 分块 → 向量化 → Milvus 入库流水线。
    """
    # 1. 校验扩展名
    filename = file.filename or "unknown.txt"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in _ALLOWED_EXTENSIONS:
        return ApiResponse.error(
            message=f"不支持的文件类型: {ext}，仅支持 {_ALLOWED_EXTENSIONS}"
        )

    # 2. 读取文件内容并校验大小
    file_bytes = await file.read()
    if not file_bytes:
        return ApiResponse.error(message="文件内容为空")
    if len(file_bytes) > _MAX_FILE_SIZE:
        return ApiResponse.error(message=f"文件超过 {_MAX_FILE_SIZE // 1024 // 1024}MB 限制")

    # 3. 落 MinIO + 创建 doc 记录（status=uploading）
    try:
        doc = await knowledge_service.upload_document(
            file_bytes=file_bytes,
            filename=filename,
            file_size=len(file_bytes),
            category=category or None,
            chunk_size=chunk_size or None,
            overlap=overlap or None,
        )
    except Exception as e:
        logger.error("Upload document failed: %s", e)
        return ApiResponse.error(message=f"上传失败: {e}")

    # 4. 后台触发处理流水线（从 MinIO 拉文件，避免 UploadFile 已关闭）
    background_tasks.add_task(
        knowledge_service.process_document_from_minio, doc.doc_id
    )

    return ApiResponse.success(
        data=DocUploadResponse(
            doc_id=doc.doc_id,
            filename=doc.filename,
            chunk_count=doc.chunk_count,
            status=doc.status,
        ).model_dump(mode="json"),
        message="上传成功，正在后台处理",
    )


@router.get("/docs", response_model=ApiResponse, summary="分页文档列表")
async def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    status: str = Query("", description="状态过滤：uploading/processing/indexed/failed"),
    category: str = Query("", description="分类过滤"),
    keyword: str = Query("", description="文件名关键词"),
    knowledge_service: KnowledgeService = Depends(get_knowledge_service),
    user: User = Depends(get_admin_user),
) -> ApiResponse:
    """分页获取文档列表（支持状态/分类/关键词过滤）。"""
    result = await knowledge_service.list_documents(
        page=page,
        page_size=page_size,
        status_filter=status or None,
        category=category or None,
        keyword=keyword or None,
    )
    data = [
        DocListItem(
            doc_id=d.doc_id,
            filename=d.filename,
            file_type=d.file_type,
            file_size=d.file_size,
            category=d.category,
            chunk_count=d.chunk_count,
            status=d.status,
            error_msg=d.error_msg,
            created_at=d.created_at,
        ).model_dump(mode="json")
        for d in result["list"]
    ]
    return ApiResponse.success(
        data={
            "list": data,
            "total": result["total"],
            "page": result["page"],
            "page_size": result["page_size"],
        }
    )


@router.get("/docs/{doc_id}", response_model=ApiResponse, summary="文档详情")
async def get_document(
    doc_id: str,
    knowledge_service: KnowledgeService = Depends(get_knowledge_service),
    user: User = Depends(get_admin_user),
) -> ApiResponse:
    """获取单条文档详情。"""
    doc = await knowledge_service.get_document(doc_id)
    if doc is None:
        raise NotFoundError("文档不存在")
    return ApiResponse.success(
        data=DocListItem(
            doc_id=doc.doc_id,
            filename=doc.filename,
            file_type=doc.file_type,
            file_size=doc.file_size,
            category=doc.category,
            chunk_count=doc.chunk_count,
            status=doc.status,
            error_msg=doc.error_msg,
            created_at=doc.created_at,
        ).model_dump(mode="json")
    )


@router.delete("/docs/{doc_id}", response_model=ApiResponse, summary="删除文档")
async def delete_document(
    doc_id: str,
    knowledge_service: KnowledgeService = Depends(get_knowledge_service),
    user: User = Depends(get_admin_user),
) -> ApiResponse:
    """删除文档（联动清理 MinIO + Milvus + MySQL chunks + MySQL doc）。"""
    deleted = await knowledge_service.delete_document(doc_id)
    if not deleted:
        raise NotFoundError("文档不存在")
    return ApiResponse.success(message="文档已删除")


@router.post("/docs/{doc_id}/reindex", response_model=ApiResponse, summary="重建索引")
async def reindex_document(
    doc_id: str,
    background_tasks: BackgroundTasks,
    knowledge_service: KnowledgeService = Depends(get_knowledge_service),
    user: User = Depends(get_admin_user),
) -> ApiResponse:
    """重新解析与向量化文档（后台异步执行）。"""
    doc = await knowledge_service.get_document(doc_id)
    if doc is None:
        raise NotFoundError("文档不存在")

    # 后台触发重建（先清旧 chunks 与 Milvus 记录，再走流水线）
    background_tasks.add_task(
        knowledge_service.reindex_from_minio, doc.doc_id
    )
    return ApiResponse.success(message="已触发重建索引，请稍后查看状态")
