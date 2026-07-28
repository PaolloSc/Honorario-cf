#!/usr/bin/env python3
"""Reintroduz cada bug conhecido e confirma que o teste correspondente fica VERMELHO.

Teste que passa mesmo com o bug de volta nao testa nada. Quando o teste e'
escrito depois da correcao — o caso normal aqui, porque o bug chega como print
de um advogado — ninguem o viu falhar, e um teste que so confirma o presente
passa despercebido. Na primeira execucao deste script, 2 dos 8 testes nao
pegavam o proprio bug que motivou sua escrita.

Uso (a partir da raiz do repo):
    python3 .claude/skills/contrato-cf/scripts/verifica_vermelho.py

Ao corrigir um bug novo, acrescente a mutacao correspondente em MUTACOES:
o trecho corrigido, o trecho com o bug e o teste que deve ficar vermelho.
"""
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[4]

# (nome, arquivo, trecho_correto, trecho_com_bug, teste_que_deve_ficar_vermelho)
MUTACOES = [
    (
        "lista de nomes sem separador",
        "backend/app/utils/participacao.py",
        'linhas.append(("Para quem", ", ".join(para_quem)))',
        'linhas.append(("Para quem", str(para_quem)))',
        "tests/test_participacao_ficha_formato.py::test_para_quem_sai_separado_por_virgula",
    ),
    (
        "criterio lendo so o campo legado",
        "backend/app/utils/participacao.py",
        '    tipo = p.get("valor_tipo")',
        '    tipo = None  # BUG: ignora os campos estruturados',
        "tests/test_participacao_ficha_formato.py::test_criterio_usa_os_campos_novos_do_wizard",
    ),
    (
        "celula da assinatura como texto unico",
        "backend/app/routers/contract.py",
        'return "<br>".join(linha for linha in linhas if linha)',
        'return escape(_clean_preview_text(cell.text))',
        "tests/test_contract_generator_fidelidade.py::test_preview_nao_junta_rotulo_com_a_linha_de_assinatura",
    ),
    (
        "tag do DocuSeal virando underscores",
        "backend/app/routers/contract.py",
        'return _SIG_TAG.sub("", text)',
        'return _SIG_TAG.sub("_" * 40, text)',
        "tests/test_contract_generator_fidelidade.py::test_preview_nao_junta_rotulo_com_a_linha_de_assinatura",
    ),
    (
        "numero da clausula escrito no texto",
        "backend/app/services/contract_generator.py",
        '        self._add_clausula(\n            doc,\n            "Ressalvada a hipótese de prazo específico',
        '        doc.add_paragraph(\n            "8.1. Ressalvada a hipótese de prazo específico',
        "tests/test_contract_generator_fidelidade.py::test_clausulas_sao_numeradas_pelo_word_e_nao_no_texto",
    ),
    (
        "subclausulas do bloco de honorario desligadas",
        "backend/app/services/contract_generator.py",
        "        varios = len(blocos) > 1",
        "        varios = False  # BUG: ignora ter mais de um honorario",
        "tests/test_contract_generator_fidelidade.py::test_secao3_varios_honorarios_usam_subclausulas",
    ),
    (
        "contratante unico voltando a ser 'CONTRATANTE 1'",
        "backend/app/services/contract_generator.py",
        '            rotulo = "CONTRATANTE" if unico else f"CONTRATANTE {i}"',
        '            rotulo = f"CONTRATANTE {i}"',
        "tests/test_contract_generator_fidelidade.py::test_qualificacao_sem_virgula_dupla_com_campo_vazio",
    ),
    (
        "assinatura justificada pelo padrao do modelo",
        "backend/app/services/contract_generator.py",
        "            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER",
        "            pass  # BUG: herda o w:jc=both do modelo",
        "tests/test_contract_generator_fidelidade.py::test_assinaturas_centralizadas_sem_espaco_sobrando",
    ),
    (
        "5.6 (sucumbencia) saindo sem exito",
        "backend/app/services/contract_generator.py",
        "        if has_exito:\n            clauses.append(",
        "        if True:  # BUG: sai sempre\n            clauses.append(",
        "tests/test_contract_generator_fidelidade.py::test_secao5_reembolsos_completos",
    ),
]


def roda(teste: str) -> bool:
    """True se o teste passou."""
    r = subprocess.run(
        ["uv", "run", "pytest", teste, "-q", "--no-header", "-x"],
        cwd=RAIZ / "backend", capture_output=True, text=True,
    )
    return r.returncode == 0


def main() -> int:
    falhas = []
    for nome, arquivo, correto, com_bug, teste in MUTACOES:
        caminho = RAIZ / arquivo
        original = caminho.read_text(encoding="utf-8")
        if correto not in original:
            print(f"?? {nome}: trecho nao encontrado em {arquivo} — mutacao desatualizada")
            falhas.append(nome)
            continue
        try:
            caminho.write_text(original.replace(correto, com_bug, 1), encoding="utf-8")
            passou = roda(teste)
        finally:
            caminho.write_text(original, encoding="utf-8")

        if passou:
            print(f"FALSO POSITIVO  {nome}: o teste passou COM o bug de volta")
            falhas.append(nome)
        else:
            print(f"vermelho ok     {nome}")

    print()
    if falhas:
        print(f"{len(falhas)} de {len(MUTACOES)} nao pegaram o bug: {', '.join(falhas)}")
        return 1
    print(f"todos os {len(MUTACOES)} testes ficam vermelhos quando o bug volta")
    return 0


if __name__ == "__main__":
    sys.exit(main())
