# Vercel serverless entrypoint. Vercel detecta o ASGI `app` e serve tudo via rewrites.
from app.main import app  # noqa: F401
