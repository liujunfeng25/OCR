"""
命令行单图识别：在 backend 目录执行
  python run_one_image.py <图片路径>
使用 config.DOCUMENTS_OCR_ENGINE（默认 baidu），打印识别结果，便于本地测试。
"""
import sys
from pathlib import Path

_backend_dir = Path(__file__).resolve().parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))


def main():
    if len(sys.argv) < 2:
        print("用法: python run_one_image.py <图片路径>")
        print("示例: python run_one_image.py data/documents/uploads/xxx.jpg")
        sys.exit(1)
    image_path = Path(sys.argv[1])
    if not image_path.is_file():
        print(f"错误: 文件不存在: {image_path}")
        sys.exit(2)

    from config import DOCUMENTS_OCR_ENGINE

    if DOCUMENTS_OCR_ENGINE == "baidu":
        try:
            from app.services.ocr_baidu import run_baidu_table_ocr
            data = run_baidu_table_ocr(image_path)
        except Exception as e:
            print("百度识别失败:", e)
            sys.exit(3)
    else:
        from app.routers.documents import _mock_ocr
        data = _mock_ocr(image_path)

    tables = data.get("tables") or []
    key_vals = data.get("key_values") or []
    print("-" * 50)
    print("识别完成。")
    print(f"  引擎: {DOCUMENTS_OCR_ENGINE}")
    print(f"  表格数: {len(tables)}")
    print(f"  键值对数: {len(key_vals)}")
    if key_vals:
        print("  键值对示例:")
        for kv in key_vals[:10]:
            print(f"    {kv.get('key')}: {kv.get('value')}")
    if tables:
        print("  第一个表表头:", tables[0].get("headers", []))
        rows = tables[0].get("rows", [])
        print(f"  行数: {len(rows)}")
        if rows:
            print("  首行:", rows[0])
    print("-" * 50)


if __name__ == "__main__":
    main()
