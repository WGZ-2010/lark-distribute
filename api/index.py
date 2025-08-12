import os
import json

# 从环境变量获取配置
APP_ID = os.getenv("APP_ID", "")
APP_SECRET = os.getenv("APP_SECRET", "")
DEFAULT_FOLDER_TOKEN = os.getenv("DEFAULT_FOLDER_TOKEN", "")
TENANT_DOMAIN = os.getenv("TENANT_DOMAIN", "")

def handler(request):
    """Vercel 函数处理器"""
    
    # 设置响应头
    headers = {
        'Content-Type': 'application/json; charset=utf-8',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type'
    }
    
    # 处理 CORS 预检请求
    if request.method == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({'message': 'CORS preflight'})
        }
    
    # 健康检查响应
    response_data = {
        "status": "✅ API运行正常！",
        "message": "飞书文档分发API已启动",
        "version": "v1.0",
        "request_info": {
            "method": request.method,
            "url": str(request.url) if hasattr(request, 'url') else 'unknown'
        },
        "endpoints": {
            "health_check": "GET /api/index 或 GET /",
            "distribute": "POST /api/distribute"
        },
        "config_status": {
            "APP_ID": "✅ 已配置" if APP_ID else "❌ 未配置",
            "APP_SECRET": "✅ 已配置" if APP_SECRET else "❌ 未配置", 
            "TENANT_DOMAIN": TENANT_DOMAIN if TENANT_DOMAIN else "❌ 未配置",
            "DEFAULT_FOLDER_TOKEN": "✅ 已配置" if DEFAULT_FOLDER_TOKEN else "⚠️ 未配置"
        },
        "next_steps": [
            "1. 配置环境变量（APP_ID, APP_SECRET 等）",
            "2. 使用 POST 方法调用 /api/distribute 进行文档分发"
        ]
    }
    
    return {
        'statusCode': 200,
        'headers': headers,
        'body': json.dumps(response_data, ensure_ascii=False, indent=2)
    }
