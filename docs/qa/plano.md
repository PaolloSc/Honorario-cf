# Plano de testes — primeira rodada (out/2026)

Escopo: 4 fluxos críticos. Arquivos em `e2e/tests/`.

| # | Fluxo | Casos | Prioridade | Estado |
|---|---|---|---|---|
| 01 | Login/convite | link válido entra; token falso é recusado; área interna sem sessão vai ao login; API recusa sem token | Alta | automatizado |
| 02 | Contrato até a prévia | PF + escopo + mensalidade passam os 7 passos; responsável obrigatório trava o "Próximo"; revisão mostra CPF e R$ 2.500,00/mês; prévia traz o texto do contrato | Alta | automatizado |
| 03 | Distrato | sem valor = quitação integral e ressalva de êxito marcada; sem ressalva = quitação total; com valor = multa 10%, juros 1% a.m., correção, art. 784 III (e "4.000" lido como R$ 4.000,00); valor sem data não gera prévia; contencioso trava o substabelecimento e gera os dois documentos | Alta | automatizado |
| 04 | Substabelecimento | CNJ mostra o tribunal; CNJ com dígito errado é recusado; importação de CSV; prévia com processo | Alta | automatizado |

## Fica para a próxima rodada
| Fluxo | Por quê |
|---|---|
| Wizard com PJ, participação, desconto, êxito | muitas combinações; priorizar pelo uso real dos sócios |
| Aditivo | mesmo formulário do distrato; cobrir quando houver mudança |
| Edição de contrato e versões (#146) | exige contrato gerado, e gerar dispara e-mail de ficha |
| Partes pelo CNJ via Legal One | precisa de credencial Legal One |
| Envio para assinatura, e-mail, DocuSeal | proibido em homolog; só com mock |
| Login Microsoft | senha/MFA, não automatizável |
| Mobile, acessibilidade, desempenho | sem demanda ainda |

## Como rodar
Ver `e2e/README.md`.
