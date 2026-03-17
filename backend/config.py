# 票据识别模块配置
import os
from pathlib import Path

# 后端目录（config.py 所在目录的上一级 = backend）
BASE_DIR = Path(__file__).resolve().parent
# 票据上传与结果目录（放在 backend/data 下，避免工作目录影响）
DOCUMENTS_UPLOAD_DIR = BASE_DIR / "data" / "documents" / "uploads"
DOCUMENTS_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# 是否启用图像预处理（去模糊、增强、透视校正）
DOCUMENTS_PREPROCESS_ENABLED = True

# OCR 引擎：baidu（百度表格识别）/ mock。paddle 已移除，若设为 paddle 将回退为 mock。
DOCUMENTS_OCR_ENGINE = os.environ.get("DOCUMENTS_OCR_ENGINE", "baidu")

# 百度表格识别 API Key（Bearer bce-v3/ALTAK-...），仅当 DOCUMENTS_OCR_ENGINE=baidu 时使用。建议用环境变量覆盖。
DOCUMENTS_BAIDU_TABLE_API_KEY = os.environ.get(
    "DOCUMENTS_BAIDU_TABLE_API_KEY",
    "Bearer bce-v3/ALTAK-ue73WKfvh1NL7gAekq6Lb/a5bd23e8ad8f338450de27441059cdc02f625743",
)
