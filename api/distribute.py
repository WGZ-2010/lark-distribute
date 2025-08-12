import os, time
import requests
from http.server import BaseHTTPRequestHandler
import json
import urllib.parse

# 从环境变量获取配置
APP_ID = os.getenv("APP_ID", "")
APP_SECRET = os.getenv("APP_SECRET", "")
DEFAULT_FOLDER_TOKEN = os.getenv("DEFAULT_FOLDER_TOKEN", "")
TENANT_DOMAIN = os.getenv("TENANT_DOMAIN", "")
LARK_BASE = "https://open.larksuite.com"

_token_cache = {"value": None, "expire": 0}

# 获取飞书访问令牌
def get_tenant_access_token():
    print(f"🔑 开始获取访问令牌...")
    
    if not APP_ID or not APP_SECRET:
        error_msg = "APP_ID 或 APP_SECRET 未配置"
        print(f"❌ 错误：{error_msg}")
        raise RuntimeError(error_msg)
    
    now = time.time()
    if _token_cache["value"] and now < _token_cache["expire"] - 60:
        print("✅ 使用缓存的令牌")
        return _token_cache["value"]
    
    url = f"{LARK_BASE}/open-apis/auth/v3/tenant_access_token/internal"
    payload = {"app_id": APP_ID, "app_secret": APP_SECRET}
    
    try:
        print(f"📡 发送令牌请求...")
        r = requests.post(url, json=payload, timeout=10)
        data = r.json()
        print(f"📥 令牌响应代码: {data.get('code', 'unknown')}")
        
        if data.get("code") != 0:
            error_msg = f"获取令牌失败: {data}"
            print(f"❌ {error_msg}")
            raise RuntimeError(error_msg)
        
        _token_cache["value"] = data["tenant_access_token"]
        _token_cache["expire"] = now + int(data.get("expire", 7200))
        print("✅ 令牌获取成功！")
        return _token_cache["value"]
        
    except Exception as e:
        error_msg = f"获取令牌时发生错误: {str(e)}"
        print(f"❌ {error_msg}")
        raise RuntimeError(error_msg)

# 从URL中提取文档token
def extract_token_from_url(url: str) -> str:
    if not url:
        return ""
    try:
        path = url.split("?", 1)[0]
        segs = [s for s in path.split("/") if s]
        token = segs[-1] if segs else ""
        print(f"🔗 从URL提取token: {token}")
        return token
    except Exception as e:
        print(f"❌ 提取token失败: {e}")
        return ""

# 调用飞书API
def lark_api(path: str, method="GET", token=None, json_data=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    url = f"{LARK_BASE}{path}"
    print(f"📡 调用飞书API: {method} {path}")
    
    try:
        r = requests.request(method, url, headers=headers, json=json_data, timeout=20)
        response_data = r.json()
        print(f"📥 API响应代码: {response_data.get('code', 'unknown')}")
        return response_data
    except Exception as e:
        error_msg = f"API调用失败: {str(e)}"
        print(f"❌ {error_msg}")
        raise RuntimeError(error_msg)

# 复制文件
def copy_file(file_token: str, folder_token: str, token: str):
    payload = {"file_token": file_token}
    if folder_token:
        payload["folder_token"] = folder_token
    print(f"📋 准备复制文件，参数: {payload}")
    return lark_api("/open-apis/drive/v1/files/copy", method="POST", token=token, json_data=payload)

# 健康检查
def health_check():
    return {
        "status": "API运行正常！",
        "message": "飞书文档分发API已启动",
        "version": "v1.0",
        "endpoints": {
            "health": "GET /api/distribute",
            "distribute": "POST /api/distribute"
        },
        "config_status": {
            "APP_ID": "✅ 已配置" if APP_ID else "❌ 未配置",
            "APP_SECRET": "✅ 已配置" if APP_SECRET else "❌ 未配置", 
            "TENANT_DOMAIN": TENANT_DOMAIN if TENANT_DOMAIN else "❌ 未配置",
            "DEFAULT_FOLDER_TOKEN": "✅ 已配置" if DEFAULT_FOLDER_TOKEN else "⚠️ 未配置"
        }
    }

# 处理分发请求
def handle_distribute(request_data):
    print("\n" + "="*50)
    print("🚀 收到文档分发请求！")
    print("="*50)
    
    # 检查环境变量
    print("🔧 检查配置:")
    print(f"   APP_ID: {'✅ 已配置' if APP_ID else '❌ 未配置'}")
    print(f"   APP_SECRET: {'✅ 已配置' if APP_SECRET else '❌ 未配置'}")
    print(f"   TENANT_DOMAIN: {TENANT_DOMAIN if TENANT_DOMAIN else '❌ 未配置'}")
    print(f"   DEFAULT_FOLDER_TOKEN: {'✅ 已配置' if DEFAULT_FOLDER_TOKEN else '⚠️  未配置'}")
    
    print(f"📥 请求数据: {request_data}")

    # 获取参数
    record_id = request_data.get("record_id", "")
    template_doc_url = request_data.get("template_doc_url", "")
    target_folder_url = request_data.get("target_folder_url", "")

    print(f"📝 解析参数:")
    print(f"   记录ID: {record_id}")
    print(f"   模板文档URL: {template_doc_url}")
    print(f"   目标文件夹URL: {target_folder_url}")

    # 提取token
    file_token = extract_token_from_url(template_doc_url)
    folder_token = extract_token_from_url(target_folder_url) or DEFAULT_FOLDER_TOKEN
    
    if not file_token:
        error_msg = "无法从模板文档URL提取文件token"
        print(f"❌ 错误：{error_msg}")
        raise ValueError(error_msg)

    print(f"🔑 提取的tokens:")
    print(f"   文件token: {file_token}")
    print(f"   文件夹token: {folder_token}")

    # 执行复制操作
    try:
        print("🔐 获取访问令牌...")
        token = get_tenant_access_token()
        
        print("📋 开始复制文件...")
        copy_res = copy_file(file_token, folder_token, token)
        
        # 提取新文档信息
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

        # 如果没有URL但有token，构造URL
        if not new_url and new_token and TENANT_DOMAIN:
            new_url = f"https://{TENANT_DOMAIN}/docx/{new_token}"

        # 构造返回结果
        result = {
            "ok": True,
            "record_id": record_id,
            "new_doc_token": new_token,
            "new_doc_url": new_url,
            "copy_raw": copy_res,
            "message": "文档复制成功！"
        }
        
        print("✅ 处理完成！")
        print(f"📄 新文档token: {new_token}")
        print(f"🔗 新文档URL: {new_url}")
        print("="*50 + "\n")
        
        return result
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ 处理请求时发生错误: {error_msg}")
        print("="*50 + "\n")
        raise RuntimeError(error_msg)

# Vercel 处理函数 - 这是关键！
class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        print(f"📥 GET 请求: {self.path}")
        
        # 健康检查
        response_data = health_check()
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        response_json = json.dumps(response_data, ensure_ascii=False, indent=2)
        self.wfile.write(response_json.encode('utf-8'))
    
    def do_POST(self):
        print(f"📥 POST 请求: {self.path}")
        
        try:
            # 读取请求体
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            # 解析JSON
            if post_data:
                request_data = json.loads(post_data.decode('utf-8'))
            else:
                request_data = {}
            
            # 处理分发请求
            result = handle_distribute(request_data)
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            response_json = json.dumps(result, ensure_ascii=False, indent=2)
            self.wfile.write(response_json.encode('utf-8'))
            
        except json.JSONDecodeError as e:
            error_response = {
                "ok": False,
                "error": "请求数据格式错误",
                "details": str(e)
            }
            self.send_response(400)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            response_json = json.dumps(error_response, ensure_ascii=False, indent=2)
            self.wfile.write(response_json.encode('utf-8'))
            
        except Exception as e:
            error_response = {
                "ok": False,
                "error": str(e),
                "message": "处理失败，请检查配置和权限"
            }
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            response_json = json.dumps(error_response, ensure_ascii=False, indent=2)
            self.wfile.write(response_json.encode('utf-8'))
    
    def do_OPTIONS(self):
        # 处理 CORS 预检请求
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
