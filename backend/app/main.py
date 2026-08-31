from fastapi import FastAPI

from backend.app.api.evaluation import router as evaluation_router


app = FastAPI(
    title="Knowledge Grounded Assessment API",
    version="1.0.0",
)

app.include_router(evaluation_router)


@app.get("/")
def root():
    return {"message": "Backend is running"}


@app.get("/health")
def health():
    return {"status": "healthy"}