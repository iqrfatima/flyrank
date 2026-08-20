from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
import sqlite3


app = FastAPI(
    title="Task API",
    description="Simple CRUD API for managing tasks",
    version="1.0"
)


DATABASE = "tasks.db"


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():

    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            done BOOLEAN NOT NULL DEFAULT 0
        )
    """)

    count = conn.execute(
        "SELECT COUNT(*) FROM tasks"
    ).fetchone()[0]

    if count == 0:

        conn.executemany(
            "INSERT INTO tasks (title, done) VALUES (?, ?)",
            [
                ("Complete Assignment", False),
                ("Practice DSA", True),
                ("Read FastAPI Docs", False)
            ]
        )

    conn.commit()
    conn.close()


init_db()


class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1)


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    done: Optional[bool] = None


@app.get("/")
def root():

    return {
        "name": "Task API",
        "version": "1.0",
        "endpoints": ["/tasks"]
    }


@app.get("/health")
def health():

    return {"status": "ok"}


@app.get("/tasks")
def get_tasks():

    conn = get_db()

    rows = conn.execute(
        "SELECT * FROM tasks"
    ).fetchall()

    conn.close()

    return [dict(row) for row in rows]


@app.get("/tasks/{task_id}")
def get_task(task_id: int):

    conn = get_db()

    row = conn.execute(
        "SELECT * FROM tasks WHERE id = ?",
        (task_id,)
    ).fetchone()

    conn.close()

    if row is None:

        raise HTTPException(
            status_code=404,
            detail={"error": f"Task {task_id} not found"}
        )

    return dict(row)


@app.post("/tasks", status_code=201)
def create_task(task: TaskCreate):

    title = task.title.strip()

    if title == "":
        raise HTTPException(
            status_code=400,
            detail={"error": "Title cannot be empty"}
        )

    conn = get_db()

    cursor = conn.execute(
        "INSERT INTO tasks (title, done) VALUES (?, ?)",
        (title, False)
    )

    conn.commit()

    task_id = cursor.lastrowid

    row = conn.execute(
        "SELECT * FROM tasks WHERE id = ?",
        (task_id,)
    ).fetchone()

    conn.close()

    return dict(row)


@app.put("/tasks/{task_id}")
def update_task(task_id: int, updated: TaskUpdate):

    if updated.title is None and updated.done is None:

        raise HTTPException(
            status_code=400,
            detail={"error": "Request body cannot be empty"}
        )

    conn = get_db()

    existing = conn.execute(
        "SELECT * FROM tasks WHERE id = ?",
        (task_id,)
    ).fetchone()

    if existing is None:

        conn.close()

        raise HTTPException(
            status_code=404,
            detail={"error": f"Task {task_id} not found"}
        )

    if updated.title is not None:

        if updated.title.strip() == "":

            conn.close()

            raise HTTPException(
                status_code=400,
                detail={"error": "Title cannot be empty"}
            )

        conn.execute(
            "UPDATE tasks SET title = ? WHERE id = ?",
            (updated.title.strip(), task_id)
        )

    if updated.done is not None:

        conn.execute(
            "UPDATE tasks SET done = ? WHERE id = ?",
            (updated.done, task_id)
        )

    conn.commit()

    row = conn.execute(
        "SELECT * FROM tasks WHERE id = ?",
        (task_id,)
    ).fetchone()

    conn.close()

    return dict(row)

@app.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int):

    conn = get_db()

    existing = conn.execute(
        "SELECT * FROM tasks WHERE id = ?",
        (task_id,)
    ).fetchone()

    if existing is None:

        conn.close()

        raise HTTPException(
            status_code=404,
            detail={"error": f"Task {task_id} not found"}
        )

    conn.execute(
        "DELETE FROM tasks WHERE id = ?",
        (task_id,)
    )

    conn.commit()

    conn.close()

    return None