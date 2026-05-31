from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from api.auth import router as auth_router
from api.dashboard import router as dashboard_router
from api.statement import router as statement_router
from api.reports import router as reports_router
from api.operations import router as operations_router
from api.lookups import router as lookups_router
from api.policies import router as policies_router
from api.scholarships import router as scholarships_router

app = FastAPI(title="Finance A/R System API")

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(dashboard_router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(statement_router, prefix="/api/statement", tags=["statement"])
app.include_router(reports_router, prefix="/api/reports", tags=["reports"])
app.include_router(operations_router, prefix="/api/operations", tags=["operations"])
app.include_router(lookups_router, prefix="/api/lookups", tags=["lookups"])
app.include_router(policies_router, prefix="/api/policies", tags=["policies"])
app.include_router(scholarships_router, prefix="/api/scholarships", tags=["scholarships"])

@app.get("/")
def root():
    return {"message": "Welcome to Finance A/R System API"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
