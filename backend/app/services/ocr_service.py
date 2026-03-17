"""
票据 OCR 服务：使用 PaddleOCR PP-StructureV3 管道做表格+文字识别。
适用于中文三联单、送货单等（文档类票据）。
"""
# 必须在 import paddleocr/paddlex 之前设置，否则 PDX 会在 import 时 initialize 一次，
# 后续 PPStructureV3 内部再 initialize 即报 "PDX has already been initialized"
import os
os.environ["PADDLE_PDX_EAGER_INIT"] = os.environ.get("PADDLE_PDX_EAGER_INIT", "0")
os.environ["FLAGS_use_mkldnn"] = os.environ.get("FLAGS_use_mkldnn", "0")

import logging
import threading
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, List

from config import DOCUMENTS_PREPROCESS_ENABLED

logger = logging.getLogger(__name__)

# 延迟初始化 PP-StructureV3 管道（避免多次重复加载模型）
# 加锁防止并发请求时重复初始化，触发 PDX "already initialized" 报错
_table_pipeline = None
_pipeline_lock = threading.Lock()


def _get_table_pipeline():
    global _table_pipeline
    if _table_pipeline is not None:
        return _table_pipeline
    with _pipeline_lock:
        if _table_pipeline is not None:
            return _table_pipeline
        try:
            from paddleocr import PPStructureV3

            # 关闭 MKLDNN，避免 Paddle 3.3 oneDNN PIR 转换 NotImplementedError
            _table_pipeline = PPStructureV3(enable_mkldnn=False)
            logger.info("PaddleOCR PPStructureV3 管道初始化完成")
        except RuntimeError as e:
            if "PDX has already been initialized" in str(e) or "Reinitialization is not supported" in str(e):
                logger.error(
                    "PDX 重复初始化。请用 backend/run.ps1 启动后端，或先设置环境变量: $env:PADDLE_PDX_EAGER_INIT='0' 再启动。错误: %s",
                    e,
                )
            raise
        except Exception as e:
            logger.exception("PaddleOCR PPStructureV3 初始化失败: %s", e)
            raise
    return _table_pipeline


class _TableHTMLParser(HTMLParser):
    """从 PP-Structure 返回的 HTML 表格中解析出单元格文本。"""
    def __init__(self):
        super().__init__()
        self.rows = []
        self.current_row = []
        self.current_cell = []
        self.in_td = False
        self.in_th = False

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.current_row = []
        elif tag in ("td", "th"):
            self.in_td = tag == "td"
            self.in_th = tag == "th"
            self.current_cell = []

    def handle_endtag(self, tag):
        if tag == "tr":
            if self.current_row:
                self.rows.append(self.current_row)
        elif tag in ("td", "th"):
            cell_text = "".join(self.current_cell).strip()
            self.current_row.append(cell_text)
            self.in_td = self.in_th = False

    def handle_data(self, data):
        if self.in_td or self.in_th:
            self.current_cell.append(data)


def _parse_table_html(html: str) -> List[List[str]]:
    """将 PP-Structure 的 table HTML 转为二维列表 [行][列]。"""
    parser = _TableHTMLParser()
    try:
        parser.feed(html)
        return parser.rows
    except Exception as e:
        logger.warning("解析表格 HTML 失败: %s", e)
        return []


# 票据表格常见列顺序（左→右），用于纠正 PP-Structure 可能返回的错序（如 RTL）
_CANONICAL_HEADER_ORDER = [
    "序号", "品名", "规格", "单位", "数量", "基准价", "上浮率",
    "创价网", "京东", "85%", "90%", "80%",  # 创价网85%/90% 京东自营80% 相关列
    "结算金额", "备注",
]


def _header_sort_key(h: str) -> tuple:
    """给表头一个排序键：优先按 _CANONICAL_HEADER_ORDER 出现顺序，否则放最后。"""
    h_lower = (h or "").strip()
    for i, kw in enumerate(_CANONICAL_HEADER_ORDER):
        if kw in h_lower:
            return (0, i, h_lower)
    return (1, 0, h_lower)


def _reorder_table_columns(headers: List[str], rows: List[List[str]]) -> tuple:
    """按票据常见列顺序重排表头与数据列，避免识别结果列错位。"""
    if not headers or not rows:
        return headers, rows
    n = len(headers)
    indices = list(range(n))
    indices.sort(key=lambda j: _header_sort_key(headers[j]))
    new_headers = [headers[j] for j in indices]
    new_rows = []
    for row in rows:
        if len(row) >= n:
            new_rows.append([row[j] for j in indices])
        else:
            new_rows.append(row)
    return new_headers, new_rows


def _html_table_to_structured(html: str) -> dict:
    """单张表 HTML -> { headers, rows }。首行作表头，并按票据列顺序重排。"""
    rows = _parse_table_html(html)
    if not rows:
        return {"headers": [], "rows": []}
    headers = rows[0]
    data_rows = rows[1:] if len(rows) > 1 else []
    headers, data_rows = _reorder_table_columns(headers, data_rows)
    return {"headers": headers, "rows": data_rows}


def _extract_key_values_from_text(regions: List[dict]) -> List[dict]:
    """从 type=text 区域提取键值对（如收货单位、日期），用于 key_values。"""
    key_values = []
    key_patterns = [
        "收货单位", "司机", "下单日期", "送货日期", "送达时间",
        "单据类型", "日期", "单号", "联系电话", "地址", "司机电话",
    ]
    for r in regions:
        if r.get("type") != "text":
            continue
        res = r.get("res")
        if res is None:
            continue
        lines = res if isinstance(res, list) else [res]
        for line in lines:
            if isinstance(line, dict):
                text = (line.get("text") or "").strip()
            elif isinstance(line, (list, tuple)) and len(line) >= 1:
                text = str(line[0]).strip()
            else:
                text = str(line).strip()
            if not text:
                continue
            for k in key_patterns:
                if k not in text:
                    continue
                for sep in ("：", ":"):
                    if sep in text:
                        parts = text.split(sep, 1)
                        if len(parts) == 2 and parts[0].strip() == k:
                            key_values.append({"key": k, "value": parts[1].strip()})
                            break
    return key_values


def _extract_key_values_from_rec_texts(rec_texts: List[str]) -> List[dict]:
    """从 table_recognition 的 rec_texts 列表中匹配键值对（如 收货单位：xxx）。"""
    key_values = []
    key_patterns = [
        "收货单位", "司机", "下单日期", "送货日期", "送达时间",
        "单据类型", "日期", "单号", "联系电话", "地址", "司机电话",
    ]
    for text in (rec_texts or []):
        if not isinstance(text, str) or not text.strip():
            continue
        text = text.strip()
        for k in key_patterns:
            if k not in text:
                continue
            for sep in ("：", ":"):
                if sep in text:
                    parts = text.split(sep, 1)
                    if len(parts) == 2 and parts[0].strip() == k:
                        key_values.append({"key": k, "value": parts[1].strip()})
                        break
    return key_values


def _preprocess_for_ocr(img):
    """
    面向普通用户的固定预处理流水线：
    - 灰度化 + 对比度增强
    - 轻度去噪
    - 轻微纠偏（如有明显歪斜）

    保持「傻瓜式」：无参数可调，只根据总开关 DOCUMENTS_PREPROCESS_ENABLED 启用或关闭。
    """
    import cv2
    import numpy as np

    if img is None:
        return img

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 对比度增强（在票据这种背景较单一的场景里通常安全）
    try:
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)
    except Exception:
        # 某些极端环境下 CLAHE 可能不可用，失败则直接用原灰度
        pass

    # 轻度去噪，避免过度模糊细字
    denoised = cv2.GaussianBlur(gray, (3, 3), 0)

    # 粗略纠偏：只在存在明显整体文本区域时尝试
    try:
        _, thresh = cv2.threshold(
            denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )
        # 文本通常接近黑色，这里反色便于找轮廓
        binary = 255 - thresh
        coords = cv2.findNonZero(binary)
        if coords is not None:
            rect = cv2.minAreaRect(coords)
            angle = rect[-1]
            # OpenCV 返回的角度定义比较反直觉，这里做一次归一化
            if angle < -45:
                angle = -(90 + angle)
            else:
                angle = -angle
            if abs(angle) > 1.0 and abs(angle) < 20.0:
                h, w = denoised.shape[:2]
                m = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), angle, 1.0)
                denoised = cv2.warpAffine(
                    denoised,
                    m,
                    (w, h),
                    flags=cv2.INTER_LINEAR,
                    borderMode=cv2.BORDER_REPLICATE,
                )
    except Exception:
        # 纠偏失败不影响主流程，继续用去噪后的灰度图
        pass

    return cv2.cvtColor(denoised, cv2.COLOR_GRAY2BGR)


def run_paddle_ocr(image_path: Path) -> dict:
    """
    对票据图片做表格识别（PaddleX table_recognition），返回与现有前端一致的 structured 结构：
    { "tables": [ { "headers": [...], "rows": [[...], ...] } ], "key_values": [ {"key","value"} ] }
    """
    import cv2

    img = cv2.imread(str(image_path))
    if img is None:
        raise FileNotFoundError(f"无法读取图片: {image_path}")

    if DOCUMENTS_PREPROCESS_ENABLED:
        try:
            img = _preprocess_for_ocr(img)
        except Exception as e:
            logger.warning("图像预处理失败，使用原图继续: %s", e)

    pipeline = _get_table_pipeline()
    # predict 支持 numpy 数组或文件路径；传数组便于使用预处理后的图
    output = pipeline.predict(
        input=img,
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
    )
    tables = []
    key_values = []
    try:
        for res in output:
            j = getattr(res, "json", None) or (res if isinstance(res, dict) else {})
            if not isinstance(j, dict):
                continue
            # 兼容不同层级：有的在 res 下
            res_body = j.get("res", j)
            table_res_list = res_body.get("table_res_list") or j.get("table_res_list") or []
            for item in table_res_list:
                if not isinstance(item, dict):
                    continue
                html = item.get("pred_html") or item.get("html") or ""
                if html:
                    tbl = _html_table_to_structured(html)
                    if tbl["headers"] or tbl["rows"]:
                        tables.append(tbl)
            overall = res_body.get("overall_ocr_res") or j.get("overall_ocr_res") or {}
            rec_texts = overall.get("rec_texts") or []
            if isinstance(rec_texts, list):
                key_values = _extract_key_values_from_rec_texts(rec_texts)
            break
    except Exception as e:
        logger.exception("解析 table_recognition 结果失败: %s", e)

    return {"tables": tables, "key_values": key_values}
