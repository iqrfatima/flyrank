from typing import Optional

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field

from postgres_repository import PostgresRepository
from auth import get_current_user, login_user

app = FastAPI(
    title="Dev Task Intelligence API",
    description="Authenticated task management API using Supabase",
    version="2.0"
)

repository = PostgresRepository()


class LoginRequest(BaseModel):
    email: str
    password: str


class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1)


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    done: Optional[bool] = None



@app.get("/")
def root():
    return {
        "name": "Dev Task Intelligence API",
        "version": "2.0",
        "authentication": "Supabase JWT",
        "endpoints": [
            "/auth/login",
            "/tasks"
        ]
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/auth/login")
def login(credentials: LoginRequest):
    return login_user(
        credentials.email,
        credentials.password
    )



@app.get("/tasks")
def get_tasks(user=Depends(get_current_user)):
    return repository.get_tasks(user.id)


@app.get("/tasks/{task_id}")
def get_task(task_id: int, user=Depends(get_current_user)):
    task = repository.get_task(task_id, user.id)

    if task is None:
        raise HTTPException(
            status_code=404,
            detail={"error": f"Task {task_id} not found"}
        )

    return task


@app.post("/tasks", status_code=201)
def create_task(task: TaskCreate, user=Depends(get_current_user)):
    title = task.title.strip()

    if title == "":
        raise HTTPException(
            status_code=400,
            detail={"error": "Title cannot be empty"}
        )

    return repository.create_task(title, user.id)


@app.put("/tasks/{task_id}")
def update_task(task_id: int, updated: TaskUpdate, user=Depends(get_current_user)):
    existing = repository.get_task(task_id, user.id)

    if existing is None:
        raise HTTPException(
            status_code=404,
            detail={"error": f"Task {task_id} not found"}
        )

    title = None

    if updated.title is not None:
        title = updated.title.strip()

        if title == "":
            raise HTTPException(
                status_code=400,
                detail={"error": "Title cannot be empty"}
            )

    return repository.update_task(
        task_id,
        user.id,
        title=title,
        done=updated.done
    )


@app.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int, user=Depends(get_current_user)):
    existing = repository.get_task(task_id, user.id)

    if existing is None:
        raise HTTPException(
            status_code=404,
            detail={"error": f"Task {task_id} not found"}
        )

    repository.delete_task(task_id, user.id)
    return None