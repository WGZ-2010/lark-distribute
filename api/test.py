from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/', methods=['GET'])
def hello():
    return jsonify({
        "message": "Hello from Vercel!",
        "status": "working"
    })

@app.route('/api/test', methods=['GET'])
def test():
    return jsonify({
        "message": "API test endpoint working!",
        "status": "success"
    })

# This is needed for Vercel
def handler(event, context):
    return app(event, context)

if __name__ == '__main__':
    app.run(debug=True)
