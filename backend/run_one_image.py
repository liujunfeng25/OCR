"""
命令行单图识别：在 backend 目录执行
  python run_one_image.py <图片路径>
会打印进度（每 15 秒）和最终识别结果，便于本地测试。
"""
import os
import sys
import threading
from pathlib import Path

# 与 main 一致，必须在 import paddle 相关前设置
os.environ["PADDLE_PDX_EAGER_INIT"] = os.environ.get("PADDLE_PDX_EAGER_INIT", "0")
os.environ["FLAGS_use_mkldnn"] = os.environ.get("FLAGS_use_mkldnn", "0")

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

    result_holder = []
    exc_holder = []
    stop_progress = threading.Event()

    def run_ocr():
        try:
            from app.services.ocr_service import run_paddle_ocr
            out = run_paddle_ocr(image_path)
            result_holder.append(out)
        except Exception as e:
            exc_holder.append(e)
        finally:
            stop_progress.set()

    print("正在加载模型并识别（首次约 1～3 分钟）…")
    print("-" * 50)
    th = threading.Thread(target=run_ocr)
    th.start()
    elapsed = 0
    while not stop_progress.wait(timeout=15):
        elapsed += 15
        print(f"  [进度] 识别进行中… 已用时 {elapsed} 秒")
    th.join()
    if exc_holder:
        print("识别失败:", exc_holder[0])
        sys.exit(3)
    data = result_holder[0]
    tables = data.get("tables") or []
    key_vals = data.get("key_values") or []
    print("-" * 50)
    print("识别完成。")
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
