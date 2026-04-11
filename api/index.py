"""Vercel stub - chỉ để thoả mãn Vercel build.
Toàn bộ logic bot chạy local qua main.py (long polling).
Vercel chỉ giữ connection với KV/Redis.
"""

from flask import Flask

app = Flask(__name__)


@app.route("/api/index", methods=["GET"])
def index():
    return {
        "status": "ok",
        "message": "Bot chạy ở local qua long polling. Đây chỉ là stub cho Vercel.",
    }
