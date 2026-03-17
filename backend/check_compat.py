"""
本机兼容性检测：Python、CPU、Paddle/PaddleOCR 是否可用。
在 backend 目录下运行: python check_compat.py
"""
import os
import platform
import sys

# 与 main 一致：推理前关闭 oneDNN，避免 ConvertPirAttribute2RuntimeAttribute 等错误
os.environ["PADDLE_PDX_EAGER_INIT"] = os.environ.get("PADDLE_PDX_EAGER_INIT", "0")
os.environ["FLAGS_use_mkldnn"] = os.environ.get("FLAGS_use_mkldnn", "0")

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

    # Paddle
    print("\n[PaddlePaddle]")
    try:
        import paddle
        print(f"  版本: {paddle.__version__}")
        print("  导入: 成功")
    except Exception as e:
        print(f"  导入失败: {e}")
        print("  请安装: pip install paddlepaddle")
        return

    # PaddleOCR
    print("\n[PaddleOCR]")
    try:
        import paddleocr
        v = getattr(paddleocr, "__version__", "未知")
        print(f"  版本: {v}")
        print("  导入: 成功")
    except Exception as e:
        print(f"  导入失败: {e}")
        print("  请安装: pip install paddleocr")
        return

    # 可选：轻量推理测试（不加载 PP-Structure 大模型，仅验证环境）
    print("\n[推理环境]")
    try:
        import paddle
        paddle.utils.run_check()
        print("  run_check(): 通过")
    except Exception as e:
        print(f"  run_check(): {e}")

    print("\n" + "=" * 60)
    print("检测完成。若上述无报错，本机可运行票据识别后端。")
    print("启动方式: 在 backend 目录执行 .\\run.ps1 或 run.bat")
    print("=" * 60)

if __name__ == "__main__":
    main()
