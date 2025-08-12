from http.server import BaseHTTPRequestHandler
import json
import os
import time
import requests
import urllib.parse

# 从环境变量获取配置
APP_ID = os.getenv("APP_ID", "")
APP_SECRET = os.getenv("APP_SECRET", "")
DEFAULT_FOLDER_TOKEN = os.getenv("DEFAULT_FOLDER_TOKEN", "")
TENANT_DOMAIN = os.getenv("TENANT_DOMAIN", "")
LARK_BASE = "https://open.larksuite.com"

_token_cache = {"value": None, "expire": 0}

def get_tenant_access_token():
    """获取飞书访问令牌"""
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

def extract_token_from_url(url: str) -> str:
    """从URL中提取文档token"""
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

def copy_file(file_token: str, folder_token: str, token: str):
    """复制文件到指定文件夹"""
    payload = {"file_token": file_token}
    if folder_token:
        payload["folder_token"] = folder_token
    
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{LARK_BASE}/open-apis/drive/v1/files/copy"
    
    print(f"📋 准备复制文件，参数: {payload}")
    
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=20)
        response_data = r.json()
        print(f"📥 复制API响应: {response_data}")
        return response_data
    except Exception as e:
        print(f"❌ 复制文件失败: {e}")
        raise RuntimeError(f"复制文件失败: {str(e)}")

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """处理GET请求 - 健康检查"""
        print(f"📥 收到GET请求")
        
        # 设置响应头
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        # 构造响应数据
        response_data = {
            "status": "✅ 飞书文档分发API运行正常！",
            "message": "使用POST方法发送分发请求",
            "version": "v1.0",
            "timestamp": int(time.time()),
            "config_status": {
                "APP_ID": "✅ 已配置" if APP_ID else "❌ 未配置",
                "APP_SECRET": "✅ 已配置" if APP_SECRET else "❌ 未配置",
                "TENANT_DOMAIN": TENANT_DOMAIN if TENANT_DOMAIN else "❌ 未配置",
                "DEFAULT_FOLDER_TOKEN": "✅ 已配置" if DEFAULT_FOLDER_TOKEN else "⚠️ 未配置"
            },
            "usage": {
                "endpoint": "POST /api/distribute",
                "required_fields": ["record_id", "template_doc_url"],
                "optional_fields": ["target_folder_url"]
            }
        }
        
        # 发送响应
        self.wfile.write(json.dumps(response_data, ensure_ascii=False, indent=2).encode('utf-8'))
    
    def do_POST(self):
        """处理POST请求 - 文档分发"""
        print(f"\n" + "="*50)
        print("🚀 收到文档分发请求！")
        print("="*50)
        
        # 设置响应头
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        try:
            # 读取请求体
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length > 0:
                post_data = self.rfile.read(content_length)
                try:
                    data = json.loads(post_data.decode('utf-8'))
                    print(f"📥 请求数据: {data}")
                except json.JSONDecodeError as e:
                    print(f"❌ JSON解析失败: {e}")
                    error_response = {
                        "ok": False,
                        "error": "请求数据格式错误",
                        "details": str(e)
                    }
                    self.wfile.write(json.dumps(error_response, ensure_ascii=False, indent=2).encode('utf-8'))
                    return
            else:
                data = {}
            
            # 检查配置状态
            print("🔧 检查配置:")
            print(f"   APP_ID: {'✅ 已配置' if APP_ID else '❌ 未配置'}")
            print(f"   APP_SECRET: {'✅ 已配置' if APP_SECRET else '❌ 未配置'}")
            print(f"   TENANT_DOMAIN: {TENANT_DOMAIN if TENANT_DOMAIN else '❌ 未配置'}")
            print(f"   DEFAULT_FOLDER_TOKEN: {'✅ 已配置' if DEFAULT_FOLDER_TOKEN else '⚠️  未配置'}")
            
            # 获取参数
            record_id = data.get("record_id", "")
            template_doc_url = data.get("template_doc_url", "")
            target_folder_url = data.get("target_folder_url", "")

            print(f"📝 解析参数:")
            print(f"   记录ID: {record_id}")
            print(f"   模板文档URL: {template_doc_url}")
            print(f"   目标文件夹URL: {target_folder_url}")

            # 提取tokens
            file_token = extract_token_from_url(template_doc_url)
            folder_token = extract_token_from_url(target_folder_url) or DEFAULT_FOLDER_TOKEN
            
            if not file_token:
                error_msg = "无法从模板文档URL提取文件token"
                print(f"❌ 错误：{error_msg}")
                error_response = {
                    "ok": False,
                    "error": "模板文档URL无效",
                    "details": error_msg,
                    "record_id": record_id
                }
                self.wfile.write(json.dumps(error_response, ensure_ascii=False, indent=2).encode('utf-8'))
                return

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

                # 构造成功响应
                result = {
                    "ok": True,
                    "record_id": record_id,
                    "new_doc_token": new_token,
                    "new_doc_url": new_url,
                    "copy_raw": copy_res,
                    "message": "✅ 文档复制成功！",
                    "timestamp": int(time.time())
                }
                
                print("✅ 处理完成！")
                print(f"📄 新文档token: {new_token}")
                print(f"🔗 新文档URL: {new_url}")
                print("="*50 + "\n")
                
                self.wfile.write(json.dumps(result, ensure_ascii=False, indent=2).encode('utf-8'))
                
            except Exception as e:
                error_msg = str(e)
                print(f"❌ 处理请求时发生错误: {error_msg}")
                print("="*50 + "\n")
                
                error_response = {
                    "ok": False,
                    "error": error_msg,
                    "record_id": record_id,
                    "message": "❌ 处理失败，请检查配置和权限",
                    "timestamp": int(time.time())
                }
                
                self.wfile.write(json.dumps(error_response, ensure_ascii=False, indent=2).encode('utf-8'))
        
        except Exception as e:
            print(f"❌ 处理POST请求时发生意外错误: {e}")
            error_response = {
                "ok": False,
                "error": "服务器内部错误",
                "details": str(e),
                "timestamp": int(time.time())
            }
            self.wfile.write(json.dumps(error_response, ensure_ascii=False, indent=2).encode('utf-8'))
    
    def do_OPTIONS(self):
        """处理CORS预检请求"""
        print(f"📥 收到OPTIONS请求")
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

# Vercel 导出
handler = Handler
