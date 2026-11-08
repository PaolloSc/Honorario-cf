"""Qualificacao das partes (nome, nacionalidade, documento, endereco) em texto corrido.

Peca usada pelos geradores de documento: contrato de consumidor, aditivo, distrato,
substabelecimento e contrato de honorarios. Funcoes puras: recebem a pessoa e devolvem o texto,
sem tocar no documento. Antes, cada gerador tinha a sua copia, ligadas por heranca.
"""
from __future__ import annotations

from app.models.contrato_consumidor import ContratanteConsumidorPJ, ContratoConsumidorRequest
from app.models.documentos_complementares import nome_contratante


def genero_de(contratante) -> str:
    """PJ concorda no feminino ('a empresa contratante')."""
    if isinstance(contratante, ContratanteConsumidorPJ):
        return "F"
    return contratante.genero


def genero_plural(data: ContratoConsumidorRequest) -> str:
    """'a' quando todas sao femininas; 'o' (masculino) em qualquer outro caso."""
    return "a" if all(genero_de(c) == "F" for c in data.contratantes) else "o"


def nacionalidade(informada: str, genero_f: bool) -> str:
    """"Brasileira (o)" e' o rotulo generico do formulario — no contrato precisa
    concordar com o genero. Nacionalidade estrangeira digitada e' preservada."""
    texto = informada.strip()
    generica = texto.lower().replace(" ", "") in {
        "",
        "brasileira(o)",
        "brasileiro(a)",
        "brasileira",
        "brasileiro",
    }
    return ("brasileira" if genero_f else "brasileiro") if generica else texto


def qualificar_pj(c: ContratanteConsumidorPJ) -> str:
    rep_f = c.representante_genero == "F"
    rep_nacionalidade = nacionalidade(c.representante_nacionalidade, rep_f)
    partes = [
        c.razao_social.upper(),
        "pessoa jurídica de direito privado",
        f"inscrita no CNPJ sob o n.º {c.cnpj}",
        f"com sede à {c.endereco}",
    ]
    if c.email:
        partes.append(f"email: {c.email}")
    partes.append(
        f"neste ato representada por {c.representante_nome.upper()}, {rep_nacionalidade}, "
        f"{'inscrita' if rep_f else 'inscrito'} no CPF sob o n.º {c.representante_cpf}"
    )
    return ", ".join(partes)


def qualificar_contratante(contratante, *, com_endereco: bool) -> str:
    """Contratante do contrato de consumidor (PF ou PJ)."""
    if isinstance(contratante, ContratanteConsumidorPJ):
        # A sede sempre acompanha a empresa: nao entra no agrupamento de domicilio.
        return qualificar_pj(contratante)

    genero_f = contratante.genero == "F"
    partes = [
        contratante.nome.upper(),
        nacionalidade(contratante.nacionalidade, genero_f),
        f"{'inscrita' if genero_f else 'inscrito'} no CPF sob o n.º {contratante.cpf}",
    ]
    if contratante.rg:
        partes.append(f"RG n.º {contratante.rg}")
    if com_endereco:
        residente = "residente e domiciliada" if genero_f else "residente e domiciliado"
        partes.append(f"{residente} à {contratante.endereco}")
        if contratante.email:
            partes.append(f"email: {contratante.email}")
        if contratante.celular:
            partes.append(f"celular: {contratante.celular}")
    return ", ".join(partes)


def cnpj_ou_cpf(c: dict) -> str:
    if c.get("cnpj"):
        return f"inscrita no CNPJ sob o n.º {c['cnpj']}"
    return f"CPF n.º {c.get('cpf', '')}"


def qualificar_do_contrato_de_origem(c: dict, *, com_representantes: bool = True) -> str:
    """Contratante a partir do form_data do contrato de origem (aditivo, distrato)."""
    nome = nome_contratante(c)
    if c.get("cnpj"):
        partes = [nome, "pessoa jurídica de direito privado", cnpj_ou_cpf(c)]
        if c.get("endereco"):
            partes.append(f"com sede em {c['endereco']}")
        reps = [r for r in (c.get("representantes") or []) if r.get("nome")] if com_representantes else []
        if reps:
            partes.append(
                "neste ato representada por "
                + "; e por ".join(
                    ", ".join(filter(None, [r["nome"], f"CPF {r['cpf']}" if r.get("cpf") else None]))
                    for r in reps
                )
            )
        return ", ".join(partes)
    partes = [nome, c.get("nacionalidade"), c.get("estado_civil"), c.get("profissao"), cnpj_ou_cpf(c)]
    if c.get("endereco"):
        partes.append(f"residente em {c['endereco']}")
    return ", ".join(p for p in partes if p)



def qualificar_substabelecido(s) -> str:
    """Sem genero (formulario atual) o texto sai neutro; com genero (legado), como antes."""
    if s.genero is None:
        return f"{s.nome}, inscrito(a) na {s.oab}"
    f = s.genero == "F"
    nacionalidade = s.nacionalidade.strip() or ("brasileira" if f else "brasileiro")
    partes = [f"{'Dra.' if f else 'Dr.'} {s.nome}", nacionalidade]
    if s.estado_civil.strip():
        partes.append(s.estado_civil.strip())
    partes.append(f"{'inscrita' if f else 'inscrito'} na {s.oab}")
    return ", ".join(partes)


def qualificar_representante(r) -> str:
    """Qualificacao do representante legal, omitindo campos vazios (sem ', ,')."""
    return ", ".join(filter(None, [
        r.nome.upper(),
        r.nacionalidade,
        r.profissao,
        r.estado_civil.value if r.estado_civil else None,
        f"CPF {r.cpf}" if r.cpf else None,
        f"e-mail: {r.email}" if r.email else None,
    ]))
