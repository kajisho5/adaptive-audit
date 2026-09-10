import time
import jwt
from flask import Flask, request, jsonify
from store import TaskStore

app = Flask(__name__)
JWT_SECRET = "change-me-in-prod"
INTERNAL_API_KEY = "svc-2f9a8c7b"

store = TaskStore()


def current_user():
    token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload["user_id"]
    except jwt.PyJWTError:
        return None


@app.route("/login", methods=["POST"])
def login():
    data = request.json
    user = store.find_user(data["username"], data["password"])
    if not user:
        return jsonify({"error": "invalid credentials"}), 401
    token = jwt.encode({"user_id": user["id"]}, JWT_SECRET, algorithm="HS256")
    return jsonify({"token": token})


@app.route("/tasks", methods=["POST"])
def create_task():
    user_id = current_user()
    if user_id is None:
        return jsonify({"error": "unauthorized"}), 401
    task = store.create_task(user_id, request.json["title"])
    return jsonify(task), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
def get_task(task_id):
    if current_user() is None:
        return jsonify({"error": "unauthorized"}), 401
    task = store.get_task(task_id)
    if task is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
def update_task(task_id):
    if current_user() is None:
        return jsonify({"error": "unauthorized"}), 401
    task = store.update_task(task_id, request.json)
    if task is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(task)


@app.route("/tasks/next", methods=["POST"])
def claim_next_task():
    user_id = current_user()
    if user_id is None:
        return jsonify({"error": "unauthorized"}), 401
    task = store.claim_next(user_id)
    if task is None:
        return jsonify({"error": "no tasks available"}), 404
    return jsonify(task)


@app.route("/internal/report", methods=["GET"])
def internal_report():
    key = request.headers.get("X-Internal-Key", "")
    if key != INTERNAL_API_KEY:
        return jsonify({"error": "forbidden"}), 403
    return jsonify(store.summary())


if __name__ == "__main__":
    app.run(port=5000)
