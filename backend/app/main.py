from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import auth, questions, exam_events, variants, ledger, devices, print_jobs, dashboard, override, users, exam_centres, custodians, centre_operators



app = FastAPI(title="Pardarshi", version="0.2.0")

# Allow the frontend dev servers to call this API. In production this
# list should be your real deployed frontend URL(s), not a wildcard —
# a wildcard combined with credentials (Bearer tokens) is a real
# security gap, not just a formality.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(questions.router, prefix="/api/v1")
app.include_router(exam_events.router, prefix="/api/v1")
app.include_router(exam_centres.router, prefix="/api/v1")
app.include_router(variants.router, prefix="/api/v1")
app.include_router(ledger.router, prefix="/api/v1")
app.include_router(devices.router, prefix="/api/v1")
app.include_router(print_jobs.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(override.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(custodians.router, prefix="/api/v1")
app.include_router(centre_operators.router, prefix="/api/v1")


@app.get("/")
def root():
    return {"service": "Pardarshi", "status": "running"}