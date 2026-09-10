import itertools

_id_counter = itertools.count(1)


class TaskStore:
    def __init__(self):
        self._users = {
            1: {"id": 1, "username": "alice", "password": "alice123"},
            2: {"id": 2, "username": "bob", "password": "bob123"},
        }
        self._tasks = {}

    def find_user(self, username, password):
        for user in self._users.values():
            if user["username"] == username and user["password"] == password:
                return user
        return None

    def create_task(self, owner_id, title):
        task_id = next(_id_counter)
        task = {"id": task_id, "owner_id": owner_id, "title": title, "status": "open", "claimed_by": None}
        self._tasks[task_id] = task
        return task

    def get_task(self, task_id):
        return self._tasks.get(task_id)

    def update_task(self, task_id, fields):
        task = self._tasks.get(task_id)
        if task is None:
            return None
        task.update({k: v for k, v in fields.items() if k in ("title", "status")})
        return task

    def claim_next(self, user_id):
        available = [t for t in self._tasks.values() if t["status"] == "open"]
        if not available:
            return None
        task = available[0]
        task["status"] = "claimed"
        task["claimed_by"] = user_id
        return task

    def summary(self):
        return {
            "total_tasks": len(self._tasks),
            "open": sum(1 for t in self._tasks.values() if t["status"] == "open"),
            "claimed": sum(1 for t in self._tasks.values() if t["status"] == "claimed"),
        }
