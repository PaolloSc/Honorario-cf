"""Rotaciona NFSE_KEK: decifra com OLD_KEK e re-cifra com NEW_KEK.

Uso:
  set OLD_KEK=<base64 atual>
  set NEW_KEK=<base64 novo>
  python -m backend.scripts.rotate_kek

Após sucesso, atualize a env NFSE_KEK no Render com NEW_KEK e remova OLD_KEK.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

from sqlalchemy import text

from app.database import SessionLocal
from app.services.crypto import CryptoBox, EncryptedBlob, InvalidCipherError


def main() -> int:
    old = os.environ.get("OLD_KEK")
    new = os.environ.get("NEW_KEK")
    if not old or not new:
        print("Defina OLD_KEK e NEW_KEK", file=sys.stderr)
        return 1
    if old == new:
        print("OLD_KEK == NEW_KEK; nada a fazer", file=sys.stderr)
        return 1

    src = CryptoBox(old)
    dst = CryptoBox(new)
    with SessionLocal() as db:
        rows = db.execute(
            text("""SELECT id, login_enc, nonce_login, senha_enc, nonce_senha
                    FROM credencial_pbh""")
        ).fetchall()
        for row in rows:
            cid, le, nl, se, ns = row
            try:
                login = src.decrypt(EncryptedBlob(nonce=nl, ciphertext=le))
                senha = src.decrypt(EncryptedBlob(nonce=ns, ciphertext=se))
            except InvalidCipherError as e:
                print(f"FALHA decrypt id={cid}: {e}", file=sys.stderr)
                return 2
            le2 = dst.encrypt(login)
            se2 = dst.encrypt(senha)
            db.execute(
                text("""UPDATE credencial_pbh
                        SET login_enc=:le, nonce_login=:nl,
                            senha_enc=:se, nonce_senha=:ns,
                            atualizado_em=:n
                        WHERE id=:id"""),
                {"le": le2.ciphertext, "nl": le2.nonce,
                 "se": se2.ciphertext, "ns": se2.nonce,
                 "n": datetime.now(timezone.utc), "id": cid},
            )
        db.commit()
    print(f"OK: {len(rows)} credenciais re-cifradas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
