from flask import Flask

app = Flask(__name__)


@app.route("/api/index", methods=["GET"])
def index():
    return {"status": "ok", "message": "Bot đang chạy trên máy build (long polling)."}
