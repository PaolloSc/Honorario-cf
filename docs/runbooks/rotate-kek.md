# Rotacionar NFSE_KEK

## Quando rotacionar

- Suspeita de vazamento (commit acidental, dump do banco em mãos erradas, ex-colaborador com acesso a env).
- Política trimestral preventiva.

## Pré-requisitos

- Acesso ao Render dashboard.
- KEK atual em mãos (será necessário como `OLD_KEK`).
- Banco em quiesce (poucos writes simultâneos) ou janela de manutenção.

## Procedimento

1. Gere novo KEK:
   ```powershell
   python -c "import os,base64; print(base64.b64encode(os.urandom(32)).decode())"
   ```
2. Conecte ao container/servidor com `OLD_KEK` (NFSE_KEK atual) e `NEW_KEK` definidos:
   ```powershell
   $env:OLD_KEK = "<atual>"
   $env:NEW_KEK = "<novo>"
   python -m backend.scripts.rotate_kek
   ```
3. Após `OK: N credenciais re-cifradas.`, troque `NFSE_KEK` no Render para o NOVO valor e redeploy.
4. Smoke: `GET /api/nfse/credenciais/<cnpj>` com worker token deve retornar login/senha corretamente.
5. Apague variável temporária `OLD_KEK` do ambiente onde rotacionou.
6. Anote no audit log da empresa.

## Rollback

Se o passo 4 falhar, troque `NFSE_KEK` de volta para o valor antigo e investigue.
