from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
 
from app.config import settings
from app.routers import cnpj, contract, docuseal, email
 
app = FastAPI(
    title="Honorarios API",
    description="API para automacao de contratos de honorarios advocaticios - C&F Advogados",
    version="1.0.0",
)
 
origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
lan_origin_regex = (
    r"^https?://("
    r"localhost|127\.0\.0\.1|"
    r"10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
    r"192\.168\.\d{1,3}\.\d{1,3}|"
    r"172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}"
    r")(:\d+)?$"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=lan_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
 
app.include_router(contract.router)
app.include_router(email.router)
app.include_router(docuseal.router)
app.include_router(cnpj.router)
 
 
@app.get("/api/health")
async def health_check() -> dict:
    return {"status": "ok", "service": "honorarios-api"}