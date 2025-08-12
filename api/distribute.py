import os, time
import requests
from flask import Flask, request, jsonify

APP_ID = os.getenv("APP_ID", "")
APP_SECRET = os.getenv("APP_SECRET", "")
DEFAULT_FOLDER_TOKEN = os.getenv("DEFAULT_FOLDER_TOKEN", "")  # 可选
TENANT_DOMAIN = os.getenv("TENANT_DOMAIN", "")
LARK_BASE = "https://open.larksuite.com"  # 海外版 Lark API

app = Flask(__name__)
_token_cache = {"value": None, "expire": 0}

def get_tenant_access_token():
    now = time.time()
    if _token_cache["value"] and now < _token_cache["expire"] - 60:
        return _token_cache["value"]
    url = f"{LARK_BASE}/open-apis/auth/v3/tenant_access_token/internal"
    r = requests.post(url, json={"app_id": APP_ID, "app_secret": APP_SECRET}, timeout=10)
    data = r.json()
    if data.get("code") != 0:
        raise RuntimeError(f"get token failed: {data}")
    _token_cache["value"] = data["tenant_access_token"]
    _token_cache["expire"] = now + int(data.get("expire", 7200))
    return _token_cache["value"]

def extract_token_from_url(url: str) -> str:
    if not url:
        return ""
    path = url.split("?", 1)[0]
    segs = [s for s in path.split("/") if s]
    return segs[-1] if segs else ""

def lark_api(path: str, method="GET", token=None, json=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    url = f"{LARK_BASE}{path}"
    r = requests.request(method, url, headers=headers, json=json, timeout=20)
    return r.json()

def copy_file(file_token: str, folder_token: str, token: str):
    payload = {"file_token": file_token}
    if folder_token:
        payload["folder_token"] = folder_token
    return lark_api("/open-apis/drive/v1/files/copy", method="POST", token=token, json=payload)

@app.post("/api/distribute")
def distribute():
    try:
        data = request.get_json(force=True) or {}
    except Exception:
        return jsonify({"ok": False, "error": "invalid json"}), 400

    record_id = data.get("record_id", "")
    template_doc_url = data.get("template_doc_url", "")
    target_folder_url = data.get("target_folder_url", "")

    file_token = extract_token_from_url(template_doc_url)
    folder_token = extract_token_from_url(target_folder_url) or DEFAULT_FOLDER_TOKEN
    if not file_token:
        return jsonify({"ok": False, "error": "missing file_token"}), 400

    token = get_tenant_access_token()
    copy_res = copy_file(file_token, folder_token, token)

    new_token = (
        copy_res.get("data", {}).get("token")
        or copy_res.get("data", {}).get("file", {}).get("token")
        or copy_res.get("token")
    )
    new_url = (
        copy_res.get("data", {}).get("url")
        or copy_res.get("data", {}).get("file", {}).get("url")
        or copy_res.get("url")
    )

    if not new_url and new_token and TENANT_DOMAIN:
        new_url = f"https://{TENANT_DOMAIN}/docx/{new_token}"

    return jsonify({
        "ok": True,
        "record_id": record_id,
        "new_doc_token": new_token,
        "new_doc_url": new_url,
        "copy_raw": copy_res
    })
