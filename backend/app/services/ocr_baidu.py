"""
百度表格文字识别 API：https://ai.baidu.com/ai-doc/OCR/Al1zvpylt
将图片 POST 到百度 rest/2.0/ocr/v1/table，解析为与现有前端一致的 structured 结构。
只调表格识别一个接口；备注列标红由前端根据「备注列有内容」判断，无需手写接口。
"""
import base64
import logging
from pathlib import Path
from typing import Dict, List

import requests

from config import DOCUMENTS_BAIDU_TABLE_API_KEY

logger = logging.getLogger(__name__)

TABLE_API_URL = "https://aip.baidubce.com/rest/2.0/ocr/v1/table"
TIMEOUT = 60


def _build_grid_from_body(body: List[dict]) -> List[List[str]]:
    """根据 body 单元格的 row_start/row_end/col_start/col_end 构建二维表格。"""
    if not body:
        return []
    max_r = max(c.get("row_end", 0) for c in body)
    max_c = max(c.get("col_end", 0) for c in body)
    if max_r <= 0 or max_c <= 0:
        return []
    grid = [["" for _ in range(max_c)] for _ in range(max_r)]
    for c in body:
        words = (c.get("words") or "").strip()
        rs, re = c.get("row_start", 0), c.get("row_end", 0)
        cs, ce = c.get("col_start", 0), c.get("col_end", 0)
        for r in range(rs, min(re, max_r)):
            for col in range(cs, min(ce, max_c)):
                grid[r][col] = words
    return grid


def _table_result_to_structured(table: dict) -> dict:
    """单张表 tables_result 项 -> { headers, rows }。"""
    header_list = table.get("header") or []
    headers = [str(h.get("words") or "").strip() for h in header_list]
    body = table.get("body") or []
    grid = _build_grid_from_body(body)
    if not headers and grid:
        headers = [str(i) for i in range(len(grid[0]))]
    if headers and grid and len(grid[0]) != len(headers):
        nc = max(len(headers), len(grid[0]) if grid else 0)
        headers = (headers + [""] * nc)[:nc]
        grid = [list(row) + [""] * (nc - len(row)) for row in grid]
    return {"headers": headers, "rows": grid}


def run_baidu_table_ocr(image_path: Path) -> dict:
    """
    调用百度表格识别 API（仅此一个接口），返回与 run_paddle_ocr 一致的结构：
    { "tables": [ { "headers": [...], "rows": [[...], ...] } ], "key_values": [] }
    """
    if not DOCUMENTS_BAIDU_TABLE_API_KEY or not DOCUMENTS_BAIDU_TABLE_API_KEY.strip():
        raise ValueError("未配置 DOCUMENTS_BAIDU_TABLE_API_KEY，请在 config 或环境变量中设置百度 API Key")

    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode("utf-8")
    body = {"image": img_b64}
    headers_req: Dict[str, str] = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": DOCUMENTS_BAIDU_TABLE_API_KEY.strip()
        if DOCUMENTS_BAIDU_TABLE_API_KEY.strip().lower().startswith("bearer ")
        else f"Bearer {DOCUMENTS_BAIDU_TABLE_API_KEY.strip()}",
    }

    resp = requests.post(TABLE_API_URL, data=body, headers=headers_req, timeout=TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    if "error_code" in data and data.get("error_code"):
        raise RuntimeError(data.get("error_msg", "百度表格识别接口返回错误"))

    tables_result = data.get("tables_result") or []
    tables = []
    for t in tables_result:
        st = _table_result_to_structured(t)
        if st["headers"] or st["rows"]:
            tables.append(st)
    return {"tables": tables, "key_values": []}
