import os
import time
import requests
import json

# 配置
APP_ID = os.getenv("APP_ID", "")
APP_SECRET = os.getenv("APP_SECRET", "")
DEFAULT_FOLDER_TOKEN = os.getenv("DEFAULT_FOLDER_TOKEN", "")
TENANT_DOMAIN = os.getenv("TENANT_DOMAIN", "")
LARK_BASE = "https://open.larksuite.com"

_token_cache = {"value": None, "expire": 0}

def get_tenant_access_token():
    """获取飞书访问令牌"""
    if not APP_ID or not APP_SECRET:
        raise RuntimeError("APP_ID 或 APP_SECRET 未配置")
    
    now = time.time()
    if _token_cache["value"] and now < _token_cache["expire"] - 60:
        return _token_cache["value"]
    
    url = f"{LARK_BASE}/open-apis/auth/v3/tenant_access_token/internal"
    payload = {"app_id": APP_ID, "app_secret": APP_SECRET}
    
    r = requests.post(url, json=payload, timeout=10)
    data = r.json()
    
    if data.get("code") != 0:
        raise RuntimeError(f"获取令牌失败: {data}")
    
    _token_cache["value"] = data["tenant_access_token"]
    _token_cache["expire"] = now + int(data.get("expire", 7200))
    return _token_cache["value"]

def extract_token_from_url(url: str) -> str:
    """从URL中提取token"""
    if not url:
        return ""
    path = url.split("?", 1)[0]
    segs = [s for s in path.split("/") if s]
    return segs[-1] if segs else ""

def copy_file(file_token: str, folder_token: str, token: str):
    """复制文件"""
    payload = {"file_token": file_token}
    if folder_token:
        payload["folder_token"] = folder_token
    
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{LARK_BASE}/open-apis/drive/v1/files/copy"
    
    r = requests.post(url, headers=headers, json=payload, timeout=20)
    return r.json()

def handler(request):
    """Vercel 函数入口"""
    
    # 设置响应头
    headers = {
        'Content-Type': 'application/json; charset=utf-8',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type'
    }
    
    try:
        # 处理 CORS 预检请求
        if request.method == 'OPTIONS':
            return {
                'statusCode': 200,
                'headers': headers,
                'body': json.dumps({'message': 'CORS preflight'})
            }
        
        # GET 请求 - 健康检查
        elif request.method == 'GET':
            response_data = {
                "status": "✅ 飞书分发API运行正常！",
                "message": "使用POST方法发送分发请求",
                "version": "v1.0",
                "config_status": {
                    "APP_ID": "✅ 已配置" if APP_ID else "❌ 未配置",
                    "APP_SECRET": "✅ 已配置" if APP_SECRET else "❌ 未配置",
                    "TENANT_DOMAIN": TENANT_DOMAIN if TENANT_DOMAIN else "❌ 未配置",
                    "DEFAULT_FOLDER_TOKEN": "✅ 已配置" if DEFAULT_FOLDER_TOKEN else "⚠️ 未配置"
                }
            }
            
            return {
                'statusCode': 200,
                'headers': headers,
                'body': json.dumps(response_data, ensure_ascii=False, indent=2)
            }
        
        # POST 请求 - 文档分发
        elif request.method == 'POST':
            try:
                # 获取请求数据
                if hasattr(request, 'json') and request.json:
                    data = request.json
                elif hasattr(request, 'body') and request.body:
                    data = json.loads(request.body)
                else:
                    data = {}
                
                # 获取参数
                record_id = data.get("record_id", "")
                template_doc_url = data.get("template_doc_url", "")
                target_folder_url = data.get("target_folder_url", "")
                
                # 提取tokens
                file_token = extract_token_from_url(template_doc_url)
                folder_token = extract_token_from_url(target_folder_url) or DEFAULT_FOLDER_TOKEN
                
                if not file_token:
                    raise ValueError("无法从模板文档URL提取文件token")
                
                # 执行复制
                token = get_tenant_access_token()
                copy_res = copy_file(file_token, folder_token, token)
                
                # 提取结果
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
                
                # 返回成功结果
                result = {
                    "ok": True,
                    "record_id": record_id,
                    "new_doc_token": new_token,
                    "new_doc_url": new_url,
                    "copy_raw": copy_res,
                    "message": "✅ 文档复制成功！"
                }
                
                return {
                    'statusCode': 200,
                    'headers': headers,
                    'body': json.dumps(result, ensure_ascii=False, indent=2)
                }
                
            except Exception as e:
                # 返回错误
                error_result = {
                    "ok": False,
                    "error": str(e),
                    "record_id": data.get("record_id", "") if 'data' in locals() else "",
                    "message": "❌ 处理失败"
                }
                
                return {
                    'statusCode': 500,
                    'headers': headers,
                    'body': json.dumps(error_result, ensure_ascii=False, indent=2)
                }
        
        # 不支持的方法
        else:
            return {
                'statusCode': 405,
                'headers': headers,
                'body': json.dumps({
                    "ok": False,
                    "error": f"不支持的HTTP方法: {request.method}",
                    "supported_methods": ["GET", "POST", "OPTIONS"]
                }, ensure_ascii=False, indent=2)
            }
            
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({
                "ok": False,
                "error": "服务器内部错误",
                "details": str(e)
            }, ensure_ascii=False, indent=2)
        }
