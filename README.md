# 票据识别（puaojuchuli）

票据/收货单识别与发货单 vs 收货单对比模块，前后端分离实现。

## 技术栈

- **后端**：FastAPI，路由 `/api/documents`（识别、对比）
- **前端**：Vue3 + Element Plus + Vite，单页「票据识别」+ 内 Tab（识别 / 对比）

## 目录结构

```
puaojuchuli/
├── backend/
│   ├── main.py              # FastAPI 入口
│   ├── config.py            # 上传目录、OCR 引擎等配置
│   ├── requirements.txt
│   └── app/
│       └── routers/
│           └── documents.py # 票据识别与对比接口
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── main.js
│       ├── App.vue
│       ├── router/index.js
│       ├── api/request.js、api/documents.js
│       └── views/Documents.vue
├── data/documents/uploads/  # 上传图片存储（自动创建）
├── docker-compose.yml      # Docker 一键运行（项目名 OCR）
└── README.md
```

## Docker 一键运行（推荐）

项目已配置 Docker Compose，项目名为 **OCR**。在仓库根目录执行：

```bash
docker compose up -d --build
```

- **前端**：浏览器访问 http://localhost:8081（端口以 docker-compose.yml 为准）
- **后端**：经前端 nginx 代理到后端，接口文档见前端同端口 `/docs` 或直连 backend:8010
- 默认使用 **百度表格识别**（`DOCUMENTS_OCR_ENGINE=baidu`），需在 `docker-compose.yml` 或环境中配置 `DOCUMENTS_BAIDU_TABLE_API_KEY`
- 上传文件持久化在 volume `backend_uploads`
- 使用百度 OCR 时，可在 `docker-compose.yml` 的 `backend` 下增加环境变量 `DOCUMENTS_BAIDU_TABLE_API_KEY`（或使用 `.env` 文件）

停止：`docker compose down`

## 运行方式

### 1. 后端

**推荐（Windows）**：用脚本启动：

```powershell
cd backend
pip install -r requirements.txt
.\run.ps1
```

或 CMD：`run.bat`

**或手动**：

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8010
```

- **OCR**：默认使用 **百度表格识别**（`DOCUMENTS_OCR_ENGINE=baidu`），需配置 `DOCUMENTS_BAIDU_TABLE_API_KEY`。联调时可设为 `mock` 使用占位数据。
- 本机兼容性检测：`python check_compat.py`
- 接口文档：http://127.0.0.1:8010/docs

### 2. 前端

```bash
cd frontend
npm install
npm run dev
```

浏览器访问：http://localhost:5173 ，默认进入「票据识别」页。

### 3. 使用说明

- **识别**：上传票据图片，点击「开始识别」。默认使用 **PaddleOCR** 真实识别（表格+版面），适合中文三联单/送货单。
- **对比**：在「对比」Tab 中分别为单据 A、B 上传图片并识别，再点击「执行对比」。按「品名」匹配，比较「数量」「单位」等字段，结果中展示差异明细。

## 配置（backend/config.py）

- `DOCUMENTS_UPLOAD_DIR`：上传文件保存目录
- `DOCUMENTS_PREPROCESS_ENABLED`：是否启用图像预处理（预留）
- `DOCUMENTS_OCR_ENGINE`：`baidu` 百度表格识别（默认）/ `mock` 占位联调

## 后续扩展

- 图像预处理（去模糊、透视校正）
- 异步任务与轮询（长耗时识别）
- 接入 ai-agent 时，将此前端与后端模块按原方案挂到 ai-agent 路由与菜单即可
