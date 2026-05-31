from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from api.auth import router as auth_router
from api.dashboard import router as dashboard_router
from api import auth, registration, lookups, scholarships, operations, dashboard, reports, statement, policies, fawry, d365, reconciliation, bulk, batches, email

app = FastAPI(title="Finance A/R API")

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(registration.router, prefix="/api/registration", tags=["registration"])
app.include_router(lookups.router, prefix="/api/lookups", tags=["lookups"])
app.include_router(scholarships.router, prefix="/api/scholarships", tags=["scholarships"])
app.include_router(operations.router, prefix="/api/operations", tags=["operations"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])
app.include_router(statement.router, prefix="/api/statement", tags=["statement"])
app.include_router(policies.router, prefix="/api/policies", tags=["policies"])
app.include_router(fawry.router, prefix="/api/fawry", tags=["fawry"])
app.include_router(d365.router, prefix="/api/d365", tags=["d365"])
app.include_router(reconciliation.router, prefix="/api/reconciliation", tags=["reconciliation"])
app.include_router(bulk.router, prefix="/api/bulk", tags=["bulk"])
app.include_router(batches.router, prefix="/api/batches", tags=["batches"])
app.include_router(email.router, prefix="/api/email", tags=["email"])

@app.get("/")
def root():
    return {"message": "Welcome to Finance A/R System API"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
