import os
os.environ["DATABASE_URL"] = "sqlite:///test.db"
# Dados do escritorio nao tem mais valor padrao no codigo: nos testes, ficticios.
os.environ.setdefault("FINANCEIRO_EMAIL", "financeiro@exemplo.test")
os.environ.setdefault("CF_SIGNER_EMAIL", "assinatura@exemplo.test")
os.environ.setdefault("TESTEMUNHA1_NOME", "Testemunha Ficticia")
os.environ.setdefault("TESTEMUNHA1_EMAIL", "testemunha@exemplo.test")
os.environ.setdefault("BANK_ACCOUNT_INFO", "Banco Exemplo, agência 0000, conta 00000-0")
os.environ.pop("VERCEL_ENV", None)

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import Base, engine

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def client():
    return TestClient(app)
