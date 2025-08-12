from http.server import BaseHTTPRequestHandler
import json
import os
import time
import requests

# -----------------------------
# 环境变量
# -----------------------------
APP_ID = os.getenv("APP_ID", "")
APP_SECRET = os.getenv("APP_SECRET", "")
DEFAULT_FOLDER_TOKEN = os.getenv("DEFAULT_FOLDER_TOKEN", "")
TENANT_DOMAIN = os.getenv("TENANT_DOMAIN", "")

_token_cache = {"value": None, "expire": 0}

# -----------------------------
# 根据域名选 base_url
# -----------------------------
def pick_base_url(doc_url: str) -> str:
    return "https://open.feishu.cn" if "feishu.cn" in doc_url else "https://open.larksuite.com"

# -----------------------------
# 获取 tenant_access_token
# -----------------------------
def get_tenant_access_token(base_url: str) -> str:
    if not APP_ID or not APP_SECRET:
        raise RuntimeError("APP_ID / APP_SECRET 未配置")

    now = time.time()
    if _token_cache["value"] and now < _token_cache["expire"] - 60:
        return _token_cache["value"]

    url = f"{base_url}/open-apis/auth/v3/tenant_access_token/internal"
    res = requests.post(url, json={"app_id": APP_ID, "app_secret": APP_SECRET}, timeout=10)
    data = res.json()
    if data.get("code") != 0:
        raise RuntimeError(f"token error: {data}")

    _token_cache["value"] = data["tenant_access_token"]
    _token_cache["expire"] = now + int(data.get("expire", 7200))
    return _token_cache["value"]

# -----------------------------
# 提取 token
# -----------------------------
def extract_token_from_url(url: str) -> str:
    if not url:
        return ""
    try:
        return url.split("?", 1)[0].rstrip("/").split("/")[-1]
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

    res = requests.post(url, headers=headers, json=payload, timeout=20)
    if res.status_code != 200:
        raise RuntimeError(f"HTTP {res.status_code}: {res.text}")
    return res.json()

# -----------------------------
# HTTP 处理器
# -----------------------------
class Handler(BaseHTTPRequestHandler):
    def send_json(self, status, payload):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(payload, ensure_ascii=False, indent=2).encode())

    def do_GET(self):
        self.send_json(200, {
            "status": "✅ OK",
            "version": "v1.4-final-fix",
            "config": {
                "APP_ID": bool(APP_ID),
                "APP_SECRET": bool(APP_SECRET),
                "TENANT_DOMAIN": TENANT_DOMAIN,
                "DEFAULT_FOLDER_TOKEN": bool(DEFAULT_FOLDER_TOKEN)
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
                return self.send_json(400, {"ok": False, "error": "模板文档URL无效"})

            base_url = pick_base_url(template_doc_url)
            token = get_tenant_access_token(base_url)
            result = copy_file(file_token, folder_token, token, base_url)

            new_token = result.get("data", {}).get("token") or result.get("token")
            new_url = result.get("data", {}).get("url") or result.get("url")
            if not new_url and new_token and TENANT_DOMAIN:
                new_url = f"https://{TENANT_DOMAIN}/docx/{new_token}"

            self.send_json(200, {
                "ok": True,
                "record_id": record_id,
                "new_doc_token": new_token,
                "new_doc_url": new_url
            })
        except Exception as e:
            self.send_json(500, {"ok": False, "error": str(e)})

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

# Vercel 导出
handler = Handler
