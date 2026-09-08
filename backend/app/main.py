import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.evaluation import router as evaluation_router
from backend.app.api.handwritten import router as handwritten_router
from backend.app.api.materials import router as materials_router


app = FastAPI(
    title="Knowledge Grounded Assessment API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(evaluation_router)
app.include_router(handwritten_router)
app.include_router(materials_router)


@app.get("/")
def root():
    return {"message": "Backend is running"}


@app.get("/health")
def health():
    return {"status": "healthy"}