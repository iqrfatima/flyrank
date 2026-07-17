from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional

app = FastAPI(
    title="Task API",
    description="Simple CRUD API for managing tasks",
    version="1.0"
)

tasks = [
    {"id": 1, "title": "Complete Assignment", "done": False},
    {"id": 2, "title": "Practice DSA", "done": True},
    {"id": 3, "title": "Read FastAPI Docs", "done": False},
]


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


@app.get(
    "/tasks",
    summary="Get All Tasks",
    description="Returns the complete list of tasks."
)
def get_tasks():
    return tasks

@app.get("/tasks/{task_id}")
def get_task(task_id: int):

    for task in tasks:
        if task["id"] == task_id:
            return task

    raise HTTPException(
        status_code=404,
        detail={"error": f"Task {task_id} not found"}
    )


@app.post("/tasks", status_code=201)
def create_task(task: TaskCreate):

    title = task.title.strip()

    if title == "":
        raise HTTPException(
            status_code=400,
            detail={"error": "Title cannot be empty"}
        )

    new_task = {
        "id": len(tasks) + 1,
        "title": title,
        "done": False
    }

    tasks.append(new_task)

    return new_task


@app.put("/tasks/{task_id}")
def update_task(task_id: int, updated: TaskUpdate):

    for task in tasks:

        if task["id"] == task_id:

            if updated.title is None and updated.done is None:
                raise HTTPException(
                    status_code=400,
                    detail={"error": "Request body cannot be empty"}
                )

            if updated.title is not None:

                if updated.title.strip() == "":
                    raise HTTPException(
                        status_code=400,
                        detail={"error": "Title cannot be empty"}
                    )

                task["title"] = updated.title

            if updated.done is not None:
                task["done"] = updated.done

            return task

    raise HTTPException(
        status_code=404,
        detail={"error": f"Task {task_id} not found"}
    )


@app.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int):

    for task in tasks:
        if task["id"] == task_id:
            tasks.remove(task)
            return JSONResponse(
                status_code=status.HTTP_204_NO_CONTENT,
                content=None
            )

    raise HTTPException(
        status_code=404,
        detail={"error": f"Task {task_id} not found"}
    )