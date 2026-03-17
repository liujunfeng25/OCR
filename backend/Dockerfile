# OCR 后端：FastAPI + 百度/Paddle OCR
FROM python:3.10-slim

WORKDIR /app

# 构建阶段依赖（OpenCV/Paddle 等用）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

ENV PADDLE_PDX_EAGER_INIT=0 \
    FLAGS_use_mkldnn=0 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p data/documents/uploads

EXPOSE 8010

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8010"]
