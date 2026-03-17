"""
票据识别模块：上传、OCR/表格识别、结构化输出、双单对比。
"""
import asyncio
import json
import logging
import sys
import uuid
from pathlib import Path
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from starlette.datastructures import FormData
try:
    from starlette.formparsers import MultiPartException
except ImportError:
    MultiPartException = None

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from config import DOCUMENTS_UPLOAD_DIR, DOCUMENTS_OCR_ENGINE

logger = logging.getLogger(__name__)

# 大文件上传：Starlette 默认 max_part_size=1MB，超过会 500，此处放宽到 20MB
RECOGNIZE_MAX_PART_SIZE = 20 * 1024 * 1024


async def get_recognize_form(request: Request) -> FormData:
    """解析 /recognize 的表单，允许单文件最大 20MB。"""
    logger.info("get_recognize_form: parsing form (max_part_size=%s)", RECOGNIZE_MAX_PART_SIZE)
    try:
        form = await request.form(max_part_size=RECOGNIZE_MAX_PART_SIZE)
        keys = list(form.keys()) if form else []
        logger.info("get_recognize_form: done, keys=%s", keys)
        return form
    except TypeError as e:
        logger.warning("get_recognize_form: request.form(max_part_size=...) not supported: %s", e)
        try:
            form = await request.form()
            logger.info("get_recognize_form: fallback form() done, keys=%s", list(form.keys()) if form else [])
            return form
        except Exception as e2:
            logger.exception("get_recognize_form fallback failed: %s", e2)
            raise HTTPException(500, f"解析表单失败: {e2}")
    except Exception as e:
        logger.exception("get_recognize_form failed: %s", e)
        if MultiPartException and isinstance(e, MultiPartException):
            raise HTTPException(413, f"文件过大，请压缩或分张上传: {e}")
        raise HTTPException(500, f"解析上传失败: {type(e).__name__}: {e}")


router = APIRouter()


# ---------- 请求/响应模型 ----------
class CompareRule(BaseModel):
    match_key: str = "name"  # 按哪个字段匹配（如品名/编码）
    compare_fields: List[str] = ["quantity", "amount"]  # 要比对的字段


class CompareRequest(BaseModel):
    doc_a: dict  # 发货单结构化数据
    doc_b: dict  # 收货单结构化数据
    rules: Optional[CompareRule] = None


class CompareItem(BaseModel):
    key: str
    field: str
    value_a: Any
    value_b: Any
    match: bool


class CompareResponse(BaseModel):
    matches: List[dict]
    diffs: List[CompareItem]
    summary: dict


# ---------- 占位 OCR：返回 mock 结构化数据与 HTML ----------
def _mock_ocr(image_path: Path) -> dict:
    """Mock OCR 结果，便于前后端联调。"""
    return {
        "tables": [
            {"headers": ["品名", "规格", "数量", "单位", "备注"], "rows": [
                ["白菜", "箱", "100", "箱", ""],
                ["萝卜", "斤", "50", "斤", ""],
                ["土豆", "袋", "30", "袋", ""],
            ]}
        ],
        "key_values": [
            {"key": "单据类型", "value": "发货单"},
            {"key": "日期", "value": "2025-03-13"},
            {"key": "单号", "value": "FH20250313001"},
        ],
    }


def _structured_to_html(structured: dict) -> str:
    """将结构化数据转为简单 HTML 片段。"""
    html_parts = []
    if structured.get("key_values"):
        html_parts.append("<table border='1' cellpadding='6' style='border-collapse:collapse'><tbody>")
        for kv in structured["key_values"]:
            html_parts.append(f"<tr><td><b>{kv['key']}</b></td><td>{kv['value']}</td></tr>")
        html_parts.append("</tbody></table>")
    if structured.get("tables"):
        for tbl in structured["tables"]:
            headers = tbl.get("headers", [])
            rows = tbl.get("rows", [])
            html_parts.append("<table border='1' cellpadding='6' style='border-collapse:collapse;margin-top:12px'><thead><tr>")
            for h in headers:
                html_parts.append(f"<th>{h}</th>")
            html_parts.append("</tr></thead><tbody>")
            for row in rows:
                html_parts.append("<tr>")
                for cell in row:
                    html_parts.append(f"<td>{cell}</td>")
                html_parts.append("</tr>")
            html_parts.append("</tbody></table>")
    return "\n".join(html_parts) if html_parts else "<p>无识别内容</p>"


def _run_recognize(image_path: Path) -> tuple[dict, str]:
    """执行识别，返回 (structured, html_snippet)。"""
    if DOCUMENTS_OCR_ENGINE == "baidu":
        try:
            from app.services.ocr_baidu import run_baidu_table_ocr
            structured = run_baidu_table_ocr(image_path)
        except Exception as e:
            logger.exception("百度表格识别失败: %s", e)
            raise
    elif DOCUMENTS_OCR_ENGINE == "paddle":
        logger.warning("Paddle 已移除，使用 mock 占位。请设置 DOCUMENTS_OCR_ENGINE=baidu 使用百度识别。")
        structured = _mock_ocr(image_path)
    else:
        structured = _mock_ocr(image_path)
    html_snippet = _structured_to_html(structured)
    return structured, html_snippet


# ---------- 对比逻辑：按 match_key 匹配行，比较 compare_fields ----------
def _compare_docs(doc_a: dict, doc_b: dict, match_key: str, compare_fields: List[str]) -> CompareResponse:
    """按品名（或 match_key）匹配，比较数量等字段。"""
    rows_a = []
    rows_b = []
    if doc_a.get("tables") and doc_a["tables"]:
        headers = doc_a["tables"][0].get("headers", [])
        try:
            name_idx = headers.index(match_key) if match_key in headers else 0
        except ValueError:
            name_idx = 0
        for row in doc_a["tables"][0].get("rows", []):
            key = row[name_idx] if name_idx < len(row) else ""
            rows_a.append({"key": key, "row": row, "headers": headers})
    if doc_b.get("tables") and doc_b["tables"]:
        headers = doc_b["tables"][0].get("headers", [])
        try:
            name_idx = headers.index(match_key) if match_key in headers else 0
        except ValueError:
            name_idx = 0
        for row in doc_b["tables"][0].get("rows", []):
            key = row[name_idx] if name_idx < len(row) else ""
            rows_b.append({"key": key, "row": row, "headers": headers})

    key_to_a = {r["key"]: r for r in rows_a}
    key_to_b = {r["key"]: r for r in rows_b}
    all_keys = sorted(set(key_to_a) | set(key_to_b))
    matches = []
    diffs: List[CompareItem] = []
    # 每条 match 均带 row_* 与 headers_*，供前端「仅 A 有 / 仅 B 有」键值表格展示，勿删。
    for key in all_keys:
        ra = key_to_a.get(key)
        rb = key_to_b.get(key)
        if not ra:
            matches.append({"key": key, "in_a": False, "in_b": True, "row_b": rb["row"] if rb else [], "headers_b": rb["headers"] if rb else []})
            continue
        if not rb:
            matches.append({"key": key, "in_a": True, "in_b": False, "row_a": ra["row"], "headers_a": ra["headers"]})
            continue
        headers = ra["headers"]
        for field in compare_fields:
            if field not in headers:
                continue
            idx = headers.index(field)
            va = ra["row"][idx] if idx < len(ra["row"]) else ""
            vb = rb["row"][idx] if idx < len(rb["row"]) else ""
            if str(va).strip() != str(vb).strip():
                diffs.append(CompareItem(key=key, field=field, value_a=va, value_b=vb, match=False))
        matches.append({"key": key, "in_a": True, "in_b": True, "row_a": ra["row"], "row_b": rb["row"], "headers_a": ra["headers"], "headers_b": rb["headers"]})

    summary = {"total_keys": len(all_keys), "diff_count": len(diffs), "only_in_a": sum(1 for m in matches if m.get("in_a") and not m.get("in_b")), "only_in_b": sum(1 for m in matches if m.get("in_b") and not m.get("in_a"))}
    return CompareResponse(matches=matches, diffs=diffs, summary=summary)


# ---------- 流式进度 SSE 生成器 ----------
async def _recognize_stream_gen(content: bytes, save_path: Path, image_id: str):
    """SSE 流：先发进度，识别过程中定期推送“进行中”避免用户以为卡死，最后发 result。"""
    def sse(event: str, data: Any):
        if isinstance(data, (dict, list)):
            data = json.dumps(data, ensure_ascii=False)
        return f"event: {event}\ndata: {data}\n\n"

    try:
        logger.info("stream_gen: yield progress 1/3")
        yield sse("progress", "1/3 正在接收并保存文件…")
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_bytes(content)
        logger.info("stream_gen: wrote %s bytes", len(content))
        yield sse("progress", "2/3 正在识别票据内容（首次约 1～3 分钟，请勿刷新）…")

        loop = asyncio.get_event_loop()
        done = asyncio.Event()
        result_holder: List[tuple] = []
        exc_holder: List[Exception] = []

        def run_sync():
            try:
                out = _run_recognize(save_path)
                result_holder.append(out)
            except Exception as e:
                exc_holder.append(e)
            finally:
                done.set()

        task = loop.run_in_executor(None, run_sync)
        progress_interval = 15
        elapsed = 0
        while not done.is_set():
            await asyncio.wait(
                [asyncio.create_task(done.wait()), asyncio.create_task(asyncio.sleep(progress_interval))],
                return_when=asyncio.FIRST_COMPLETED,
            )
            if done.is_set():
                break
            elapsed += progress_interval
            yield sse("progress", f"2/3 识别进行中… 已用时 {elapsed} 秒（请勿刷新）")
        await task
        if exc_holder:
            raise exc_holder[0]
        structured, html_snippet = result_holder[0]
        yield sse("progress", "3/3 识别完成")
        yield sse("result", {"structured": structured, "html_snippet": html_snippet, "image_id": image_id})
    except Exception as e:
        logger.exception("recognize stream error")
        yield sse("error", str(e))


# ---------- 路由 ----------
@router.post("/recognize")
async def recognize(
    form_data: FormData = Depends(get_recognize_form),
    stream: bool = Query(False, description="流式返回进度（SSE）"),
):
    """上传票据图片，返回结构化数据与 HTML 片段。支持 stream=1 流式输出进度。单文件最大 20MB。"""
    try:
        return await _do_recognize(form_data, stream)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("recognize unhandled: %s", e)
        raise HTTPException(500, f"识别异常: {type(e).__name__}: {e}")


async def _do_recognize(form_data: FormData, stream: bool):
    """识别逻辑，便于顶层统一捕获异常。"""
    logger.info("recognize: entry, stream=%s", stream)
    file = form_data.get("file")
    if isinstance(file, list):
        file = file[0] if file else None
    logger.info("recognize: file=%s, has_read=%s", getattr(file, "filename", None), bool(file and getattr(file, "read", None)))
    if not file or not getattr(file, "read", None):
        raise HTTPException(400, "请上传图片文件（字段名须为 file）")
    fn = (file.filename or "").lower()
    if file.content_type and not file.content_type.startswith("image/"):
        raise HTTPException(400, "请上传图片文件（如 jpg、png）")
    if not fn or not any(fn.endswith(s) for s in (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp")):
        if file.content_type:
            raise HTTPException(400, "请上传图片文件（如 jpg、png）")
    ext = Path(file.filename or "img").suffix or ".jpg"
    name = f"{uuid.uuid4().hex}{ext}"
    try:
        DOCUMENTS_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        save_path = DOCUMENTS_UPLOAD_DIR / name
        logger.info("recognize: save_path=%s", save_path)
    except Exception as e:
        logger.exception("mkdir upload dir")
        raise HTTPException(500, f"创建上传目录失败: {e}")

    if stream:
        logger.info("recognize: reading file body (stream mode)...")
        try:
            content = await file.read()
            logger.info("recognize: read done, len=%s", len(content))
        except Exception as e:
            logger.exception("read upload file")
            raise HTTPException(500, f"读取上传文件失败: {e}")
        logger.info("recognize: returning StreamingResponse")
        return StreamingResponse(
            _recognize_stream_gen(content, save_path, name),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # 非流式：原逻辑，并捕获所有异常便于排查 500
    try:
        content = await file.read()
        save_path.write_bytes(content)
    except Exception as e:
        logger.exception("save file: %s", e)
        raise HTTPException(500, f"保存文件失败: {e}")
    try:
        structured, html_snippet = _run_recognize(save_path)
        return {"structured": structured, "html_snippet": html_snippet, "image_id": name}
    except Exception as e:
        logger.exception("recognize: %s", e)
        raise HTTPException(500, f"识别失败: {type(e).__name__}: {e}")


@router.post("/compare", response_model=CompareResponse)
async def compare(body: CompareRequest):
    """发货单 vs 收货单对比。"""
    rules = body.rules or CompareRule()
    return _compare_docs(
        body.doc_a,
        body.doc_b,
        match_key=rules.match_key,
        compare_fields=rules.compare_fields,
    )
