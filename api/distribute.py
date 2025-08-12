import os, time
import requests
from flask import Flask, request, jsonify

# 从环境变量获取配置
APP_ID = os.getenv("APP_ID", "")
APP_SECRET = os.getenv("APP_SECRET", "")
DEFAULT_FOLDER_TOKEN = os.getenv("DEFAULT_FOLDER_TOKEN", "")
TENANT_DOMAIN = os.getenv("TENANT_DOMAIN", "")
LARK_BASE = "https://open.larksuite.com"

app = Flask(__name__)
_token_cache = {"value": None, "expire": 0}

# 健康检查接口 - 用于测试API是否正常
@app.route("/", methods=["GET"])
def health_check():
    return jsonify({
        "status": "API运行正常！",
        "message": "飞书文档分发API已启动",
        "config_status": {
            "APP_ID": "已配置" if APP_ID else "未配置 ❌",
            "APP_SECRET": "已配置" if APP_SECRET else "未配置 ❌", 
            "TENANT_DOMAIN": TENANT_DOMAIN if TENANT_DOMAIN else "未配置 ❌",
            "DEFAULT_FOLDER_TOKEN": "已配置" if DEFAULT_FOLDER_TOKEN else "未配置"
        }
    })

# 获取飞书访问令牌
def get_tenant_access_token():
    print(f"🔑 开始获取访问令牌...")
    
    # 检查必要参数
    if not APP_ID or not APP_SECRET:
        print("❌ 错误：APP_ID 或 APP_SECRET 未配置")
        raise RuntimeError("APP_ID 或 APP_SECRET 未配置")
    
    now = time.time()
    if _token_cache["value"] and now < _token_cache["expire"] - 60:
        print("✅ 使用缓存的令牌")
        return _token_cache["value"]
    
    url = f"{LARK_BASE}/open-apis/auth/v3/tenant_access_token/internal"
    payload = {"app_id": APP_ID, "app_secret": APP_SECRET}
    
    try:
        print(f"📡 发送令牌请求到: {url}")
        r = requests.post(url, json=payload, timeout=10)
        data = r.json()
        print(f"📥 令牌响应: {data}")
        
        if data.get("code") != 0:
            print(f"❌ 获取令牌失败: {data}")
            raise RuntimeError(f"获取令牌失败: {data}")
        
        _token_cache["value"] = data["tenant_access_token"]
        _token_cache["expire"] = now + int(data.get("expire", 7200))
        print("✅ 令牌获取成功！")
        return _token_cache["value"]
        
    except Exception as e:
        print(f"❌ 获取令牌时发生错误: {e}")
        raise

# 从URL中提取文档token
def extract_token_from_url(url: str) -> str:
    if not url:
        return ""
    # 去除URL参数
    path = url.split("?", 1)[0]
    # 分割路径
    segs = [s for s in path.split("/") if s]
    token = segs[-1] if segs else ""
    print(f"🔗 从URL提取token: {url} -> {token}")
    return token

# 调用飞书API
def lark_api(path: str, method="GET", token=None, json=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    url = f"{LARK_BASE}{path}"
    print(f"📡 调用飞书API: {method} {url}")
    
    try:
        r = requests.request(method, url, headers=headers, json=json, timeout=20)
        response_data = r.json()
        print(f"📥 API响应: {response_data}")
        return response_data
    except Exception as e:
        print(f"❌ API调用失败: {e}")
        raise

# 复制文件
def copy_file(file_token: str, folder_token: str, token: str):
    payload = {"file_token": file_token}
    if folder_token:
        payload["folder_token"] = folder_token
    print(f"📋 准备复制文件，参数: {payload}")
    return lark_api("/open-apis/drive/v1/files/copy", method="POST", token=token, json=payload)

# 主要的分发接口
@app.route("/api/distribute", methods=["POST"])
def distribute():
    print("\n" + "="*50)
    print("🚀 收到文档分发请求！")
    print("="*50)
    
    # 检查环境变量
    print("🔧 检查配置:")
    print(f"   APP_ID: {'✅ 已配置' if APP_ID else '❌ 未配置'}")
    print(f"   APP_SECRET: {'✅ 已配置' if APP_SECRET else '❌ 未配置'}")
    print(f"   TENANT_DOMAIN: {TENANT_DOMAIN if TENANT_DOMAIN else '❌ 未配置'}")
    print(f"   DEFAULT_FOLDER_TOKEN: {'✅ 已配置' if DEFAULT_FOLDER_TOKEN else '⚠️  未配置'}")
    
    # 解析请求数据
    try:
        data = request.get_json(force=True) or {}
        print(f"📥 请求数据: {data}")
    except Exception as e:
        print(f"❌ JSON解析失败: {e}")
        return jsonify({"ok": False, "error": "请求数据格式错误"}), 400

    # 获取参数
    record_id = data.get("record_id", "")
    template_doc_url = data.get("template_doc_url", "")
    target_folder_url = data.get("target_folder_url", "")

    print(f"📝 解析参数:")
    print(f"   记录ID: {record_id}")
    print(f"   模板文档URL: {template_doc_url}")
    print(f"   目标文件夹URL: {target_folder_url}")

    # 提取token
    file_token = extract_token_from_url(template_doc_url)
    folder_token = extract_token_from_url(target_folder_url) or DEFAULT_FOLDER_TOKEN
    
    if not file_token:
        print("❌ 错误：无法从模板文档URL提取文件token")
        return jsonify({"ok": False, "error": "模板文档URL无效"}), 400

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
        
        return jsonify(result)
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ 处理请求时发生错误: {error_msg}")
        print("="*50 + "\n")
        
        return jsonify({
            "ok": False, 
            "error": error_msg,
            "record_id": record_id,
            "message": "处理失败，请检查配置和权限"
        }), 500

# Vercel 需要的处理函数
def handler(request):
    return app(request.environ, lambda status, headers: None)

# 启动应用
if __name__ == "__main__":
    app.run(debug=True)
