from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from api.auth import router as auth_router

app = FastAPI(title="Finance A/R System API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For development; change to frontend URL in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/auth", tags=["auth"])

@app.get("/")
def root():
    return {"message": "Welcome to Finance A/R System API"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
