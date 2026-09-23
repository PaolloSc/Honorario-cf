# Honorário C&F

Sistema interno do Carvalho & Furtado Advogados para montar contratos de honorários e colhê-los assinados.

## Language

### Pessoas do escritório

**Colaborador**:
Qualquer pessoa do escritório cadastrada no roster (sócio, advogado, estagiário, financeiro…), tenha ou não login.
_Avoid_: usuário (usuário é conta de login)

**Sócio**:
Colaborador com poder de representar o escritório; só ele pode assinar pelo escritório.
_Avoid_: responsável, dono

**Advogado**:
Colaborador inscrito na OAB que não é sócio; pode assinar o contrato como advogado, nunca pelo escritório.
_Avoid_: associado

**Área**:
Ramo do direito ao qual o contrato pertence (Cível, Trabalhista, Tributário…). As áreas não são fixas: existem as que o escritório cadastrar.
_Avoid_: setor, departamento

**Sócio responsável pela área**:
O sócio que, por padrão, dá a assinatura pelo escritório nos contratos daquela área. Cada área tem um só; um sócio pode responder por várias áreas.

### Assinatura

**Assinatura pelo escritório**:
A assinatura no bloco CONTRATADO, que vincula o Carvalho & Furtado; todo contrato tem exatamente uma, sempre dada por um sócio.
_Avoid_: assinatura do C&F, assinatura contrato@

**Advogado signatário**:
Advogado ou sócio que assina o contrato como advogado. Quando é sócio, a mesma assinatura cobre também a assinatura pelo escritório.
