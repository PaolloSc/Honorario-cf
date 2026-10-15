from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.config import settings
from app.database import init_db
from app.routers import admin_credenciais, clientes, cnpj, colaboradores, contract, contracts, docuseal, drafts, email, emissor, faturamento, legalone_opcoes, nfse, nfse_internal, participacoes, tax_codes, testemunhas, users

init_db()

limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.validate_critical()
    yield


app = FastAPI(
    title="Honorarios API",
    description="API para automacao de contratos de honorarios advocaticios - C&F Advogados",
    version="2.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.exception_handler(RequestValidationError)
async def _validacao_sem_eco(request: Request, exc: RequestValidationError):
    """422 padrao do FastAPI devolve o valor recebido ('input'). Em rotas com senha ou
    certificado isso ecoaria o segredo na resposta: devolve so onde e por que falhou."""
    erros = [{"loc": e.get("loc"), "msg": e.get("msg"), "type": e.get("type")} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": erros})
app.add_middleware(SlowAPIMiddleware)

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
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Accept",
        "Idempotency-Key",
        "X-Dev-User-Email",
        "X-Dev-User-Role",
        "X-Dev-User-Name",
    ],
)

app.include_router(contract.router)
app.include_router(contracts.router)
app.include_router(drafts.router)
app.include_router(clientes.router)
app.include_router(email.router)
app.include_router(docuseal.router)
app.include_router(cnpj.router)
app.include_router(users.router)
app.include_router(participacoes.router)
app.include_router(nfse.router)
app.include_router(emissor.router)
app.include_router(emissor.emitidas_router)
app.include_router(faturamento.router)
app.include_router(admin_credenciais.router)
app.include_router(nfse_internal.router)
app.include_router(tax_codes.router)
app.include_router(testemunhas.router)
app.include_router(colaboradores.router)
app.include_router(legalone_opcoes.router)


@app.get("/api/health")
async def health_check() -> dict:
    return {"status": "ok", "service": "honorarios-api"}
