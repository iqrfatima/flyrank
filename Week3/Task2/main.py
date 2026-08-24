from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from postgres_repository import PostgresRepository


app = FastAPI(
    title="Task API",
    description="Simple CRUD API for managing tasks",
    version="1.0"
)


# Create repository
repository = PostgresRepository()


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
    return repository.get_tasks()


@app.get("/tasks/{task_id}")
def get_task(task_id: int):

    task = repository.get_task(task_id)

    if task is None:
        raise HTTPException(
            status_code=404,
            detail={"error": f"Task {task_id} not found"}
        )

    return task


@app.post("/tasks", status_code=201)
def create_task(task: TaskCreate):

    title = task.title.strip()

    if title == "":
        raise HTTPException(
            status_code=400,
            detail={"error": "Title cannot be empty"}
        )

    return repository.create_task(title)


@app.put("/tasks/{task_id}")
def update_task(task_id: int, updated: TaskUpdate):

    if updated.title is None and updated.done is None:
        raise HTTPException(
            status_code=400,
            detail={"error": "Request body cannot be empty"}
        )

    # Check whether task exists
    existing = repository.get_task(task_id)

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
        title=title,
        done=updated.done
    )


@app.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int):

    existing = repository.get_task(task_id)

    if existing is None:
        raise HTTPException(
            status_code=404,
            detail={"error": f"Task {task_id} not found"}
        )

    repository.delete_task(task_id)

    return None