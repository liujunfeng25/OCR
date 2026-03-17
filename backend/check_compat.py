"""
本机兼容性检测：Python、百度 OCR 配置等。
在 backend 目录下运行: python check_compat.py
"""
import os
import platform
import sys

def main():
    print("=" * 60)
    print("票据识别后端 - 本机兼容性检测")
    print("=" * 60)

    # Python
    print(f"\n[Python] {sys.version}")
    print(f"  路径: {sys.executable}")
    if sys.version_info < (3, 8):
        print("  建议: Python 3.8+")
    else:
        print("  版本: 符合要求")

    # 系统与 CPU
    print(f"\n[系统] {platform.system()} {platform.release()}")
    print(f"  架构: {platform.machine()}")
    try:
        import cpuinfo
        info = cpuinfo.get_cpu_info()
        print(f"  CPU: {info.get('brand_raw', 'N/A')}")
    except ImportError:
        print(f"  CPU: {platform.processor() or 'N/A'} (安装 py-cpuinfo 可显示更详细)")

    # OCR 引擎（Paddle 已移除，仅 baidu / mock）
    print("\n[OCR 引擎]")
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        from config import DOCUMENTS_OCR_ENGINE, DOCUMENTS_BAIDU_TABLE_API_KEY
        print(f"  当前: DOCUMENTS_OCR_ENGINE={DOCUMENTS_OCR_ENGINE}")
        if DOCUMENTS_OCR_ENGINE == "baidu":
            key_pre = (DOCUMENTS_BAIDU_TABLE_API_KEY or "").strip()[:20]
            print(f"  百度 API Key: {'已配置' if key_pre else '未配置'} ({key_pre}...)")
        print("  Paddle: 已移除，无需安装")
    except Exception as e:
        print(f"  加载 config: {e}")

    print("\n" + "=" * 60)
    print("检测完成。本机可运行票据识别后端（百度 / mock）。")
    print("启动方式: 在 backend 目录执行 .\\run.ps1 或 run.bat")
    print("=" * 60)

if __name__ == "__main__":
    main()
