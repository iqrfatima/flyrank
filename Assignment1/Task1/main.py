from fastapi import FastAPI

app = FastAPI(
    title="Task API",
    description="Simple CRUD API for managing tasks",
    version="1.0"
)

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