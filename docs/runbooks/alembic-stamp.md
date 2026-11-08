# Carimbar um banco existente no Alembic (`alembic stamp 0017`)

Quando usar: o banco tem as tabelas (criadas pelo `create_all` e pelas migrations 0001-0017 aplicadas à mão), mas não tem a tabela `alembic_version`. Enquanto não houver carimbo, o passo de deploy (`backend/scripts/deploy_migrar.py`) avisa e não faz nada.

O carimbo escreve **só** a linha de versão em `alembic_version`. Não altera tabela nem dado.

Produção só com OK do Paollo. Homolog (dados fictícios) pode ser carimbado no QA.

## Passo a passo (por ambiente)
1. Conferir o esquema (só leitura): `DATABASE_URL=<url do ambiente> python backend/scripts/comparar_esquema.py`. Diferenças conhecidas e inofensivas em produção em 08/11/2026: `colaboradores.areas` (coluna que a 0011 remove e nunca rodou lá) e `nfse_recebidas.chave_acesso` (índice único em vez de constraint). Qualquer outra diferença: parar e avisar.
2. Backup do Neon do ambiente (produção: obrigatório).
3. Carimbar: `cd backend && DATABASE_URL=<url> alembic stamp 0017`.
4. Conferir: `python -m app.migrar` imprime `upgrade` (nada pendente) e `SELECT version_num FROM alembic_version` devolve a cabeça atual.
5. Fazer um deploy: o log do build mostra `migrar: upgrade`.

## Voltar atrás
`DROP TABLE alembic_version;` no ambiente. Volta ao estado anterior (sem carimbo); o app não depende da tabela.

## Depois do carimbo
Migration nova passa a ser aplicada sozinha no deploy de `production` (produção e homolog, cada um no seu banco). Preview e local nunca migram. Só então vale discutir tirar o `create_all` do `init_db`.
