from http.server import BaseHTTPRequestHandler
import json
import os
import time
import requests
import urllib.parse

# -----------------------------
# 从环境变量获取配置
# -----------------------------
APP_ID = os.getenv("APP_ID", "")
APP_SECRET = os.getenv("APP_SECRET", "")
DEFAULT_FOLDER_TOKEN = os.getenv("DEFAULT_FOLDER_TOKEN", "")
TENANT_DOMAIN = os.getenv("TENANT_DOMAIN", "")

# 根据文档域名自动切换 BaseURL
def pick_base_url(doc_url: str) -> str:
    return "https://open.feishu.cn" if "feishu.cn" in doc_url else "https://open.larksuite.com"

_token_cache = {"value": None, "expire": 0}

# -----------------------------
# 获取访问令牌
# -----------------------------
def get_tenant_access_token(base_url: str) -> str:
    print(f"🔑 开始获取访问令牌...")
    if not APP_ID or not APP_SECRET:
        raise RuntimeError("APP_ID 或 APP_SECRET 未配置")

    now = time.time()
    if _token_cache["value"] and now < _token_cache["expire"] - 60:
        return _token_cache["value"]

    url = f"{base_url}/open-apis/auth/v3/tenant_access_token/internal"
    payload = {"app_id": APP_ID, "app_secret": APP_SECRET}
    r = requests.post(url, json=payload, timeout=10)
    data = r.json()
    if data.get("code") != 0:
        raise RuntimeError(f"获取令牌失败: {data}")

    _token_cache["value"] = data["tenant_access_token"]
    _token_cache["expire"] = now + int(data.get("expire", 7200))
    return _token_cache["value"]

# -----------------------------
# 从 URL 提取 token
# -----------------------------
def extract_token_from_url(url: str) -> str:
    if not url:
        return ""
    try:
        path = url.split("?", 1)[0]
        segs = [s for s in path.split("/") if s]
        return segs[-1] if segs else ""
    except Exception:
        return ""

# -----------------------------
# 复制文件
# -----------------------------
def copy_file(file_token: str, folder_token: str, token: str, base_url: str):
    url = f"{base_url}/open-apis/drive/v1/files/{file_token}/copy"
    payload = {}
    if folder_token:
        payload["dst_folder_token"] = folder_token
    headers = {"Authorization": f"Bearer {token}"}

    r = requests.post(url, headers=headers, json=payload, timeout=20)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text}")
    try:
        return r.json()
    except Exception as e:
        raise RuntimeError(f"响应解析失败: {e}")

# -----------------------------
# HTTP 处理器
# -----------------------------
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_json(200, {
            "status": "✅ 飞书文档分发API运行正常！",
            "message": "使用POST方法发送分发请求",
            "version": "v1.3-fixed",
            "config_status": {
                "APP_ID": "✅" if APP_ID else "❌",
                "APP_SECRET": "✅" if APP_SECRET else "❌",
                "TENANT_DOMAIN": TENANT_DOMAIN or "❌",
                "DEFAULT_FOLDER_TOKEN": "✅" if DEFAULT_FOLDER_TOKEN else "⚠️"
            }
        })

    def do_POST(self):
        try:
            data = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))).decode())
            record_id = data.get("record_id", "")
            template_doc_url = data.get("template_doc_url", "")
            target_folder_url = data.get("target_folder_url", "")

            file_token = extract_token_from_url(template_doc_url)
            folder_token = extract_token_from_url(target_folder_url) or DEFAULT_FOLDER_TOKEN
            if not file_token:
                return self.send_json(400, {"ok": False, "error": "模板文档URL无效", "record_id": record_id})

            base_url = pick_base_url(template_doc_url)
            token = get_tenant_access_token(base_url)
            copy_res = copy_file(file_token, folder_token, token, base_url)

            new_token = copy_res.get("data", {}).get("token") or copy_res.get("token")
            new_url = copy_res.get("data", {}).get("url") or copy_res.get("url")
            if not new_url and new_token and TENANT_DOMAIN:
                new_url = f"https://{TENANT_DOMAIN}/docx/{new_token}"

            self.send_json(200, {
                "ok": True,
                "record_id": record_id,
                "new_doc_token": new_token,
                "new_doc_url": new_url,
                "copy_raw": copy_res,
                "message": "✅ 文档复制成功！"
            })
        except Exception as e:
            self.send_json(500, {"ok": False, "error": str(e), "record_id": record_id})

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    # 工具：统一返回 JSON
    def send_json(self, status, payload):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(payload, ensure_ascii=False, indent=2).encode())

# Vercel 导出
handler = Handler
