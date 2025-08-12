from http.server import BaseHTTPRequestHandler
import json
import urllib.parse

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # 设置响应头
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        # 响应数据
        response_data = {
            "status": "✅ API运行正常！",
            "message": "使用POST方法进行文档分发",
            "method": "GET",
            "version": "v1.0"
        }
        
        # 发送响应
        self.wfile.write(json.dumps(response_data, ensure_ascii=False, indent=2).encode('utf-8'))
    
    def do_POST(self):
        # 设置响应头
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        try:
            # 读取请求体
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length > 0:
                post_data = self.rfile.read(content_length)
                try:
                    data = json.loads(post_data.decode('utf-8'))
                except json.JSONDecodeError:
                    data = {}
            else:
                data = {}
            
            # 响应数据（暂时只是测试）
            response_data = {
                "status": "✅ POST请求接收成功！",
                "message": "暂时只是测试版本，完整功能开发中",
                "method": "POST",
                "received_data": data,
                "next_step": "需要配置环境变量后才能实现完整功能"
            }
            
        except Exception as e:
            response_data = {
                "status": "❌ 处理失败",
                "error": str(e),
                "method": "POST"
            }
        
        # 发送响应
        self.wfile.write(json.dumps(response_data, ensure_ascii=False, indent=2).encode('utf-8'))
    
    def do_OPTIONS(self):
        # 处理CORS预检请求
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

# Vercel 需要这个名称
handler = Handler
