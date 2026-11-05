// Verificação do passo 1 do wizard (não há runner de testes no frontend):
//   node src/app/lib/validarContratantes.check.ts
import assert from "node:assert/strict";
import { cnpjValido } from "./cnpj.ts";
import { consultaCompleta, validarContratantes as v } from "./validarContratantes.ts";

const CPF = "529.982.247-25"; // CPF valido de teste
const CNPJ = "11.222.333/0001-81";
const pf = { tipo: "PF" as const, nome: "Maria", cpf: CPF, estado_civil: "Solteiro(a)", email: "m@x.com", endereco: "Rua A, 1" };
const pj = { tipo: "PJ" as const, cnpj: CNPJ, razao_social: "ACME LTDA", endereco: "Rua B, 2", email: "c@acme.com" };
const rep = { nome: "Jose", cpf: CPF, email: "j@acme.com", nacionalidade: "Brasileira", profissao: "Empresário" };
const erros = (c: any[]) => v({ contratantes: c }, cnpjValido);

// PF
assert.deepEqual(erros([pf]), []);
assert.deepEqual(erros([{ ...pf, endereco: " " }]), ["Contratante 1: informe o endereço completo."]);
// PJ sem representante, com 1 PF-representante, com 2; o representante NAO tem endereco proprio
assert.deepEqual(erros([pj]), []);
assert.deepEqual(erros([{ ...pj, representantes: [rep] }]), []);
assert.deepEqual(erros([{ ...pj, representantes: [rep, { ...rep, nome: "Ana", email: "a@acme.com" }] }]), []);
// Linha de representante so com os padroes (nacionalidade/profissao) e' ignorada
assert.deepEqual(erros([{ ...pj, representantes: [{ nome: "", nacionalidade: "Brasileira", profissao: "Empresário" }] }]), []);
// Representante: nome e e-mail obrigatorios quando ha dados; CPF opcional mas validado
assert.deepEqual(erros([{ ...pj, representantes: [{ ...rep, email: "" }] }]),
  ["Contratante 1: informe o e-mail do representante Jose (ele assina o contrato)."]);
assert.deepEqual(erros([{ ...pj, representantes: [{ ...rep, nome: "" }] }]), ["Contratante 1: informe o nome do representante 1."]);
assert.deepEqual(erros([{ ...pj, representantes: [{ ...rep, cpf: "" }] }]), []);
assert.deepEqual(erros([{ ...pj, representantes: [{ ...rep, cpf: "111.111.111-11" }] }]), ["Contratante 1: CPF inválido do representante Jose."]);
// PJ: endereco da sede e razao social obrigatorios, com mensagem
assert.deepEqual(erros([{ ...pj, endereco: "", razao_social: "" }]),
  ["Contratante 1: busque o CNPJ ou informe a Razão Social.", "Contratante 1: busque o CNPJ ou informe o endereço."]);
assert.deepEqual(erros([]), ["Adicione pelo menos um contratante."]);
// PJ + PF juntos, cada um com seu rotulo
assert.deepEqual(erros([pj, { ...pf, email: "x" }]), ["Contratante 2: informe um e-mail válido."]);
// CPF vazio pede o CPF; CPF errado continua "inválido"
assert.deepEqual(erros([{ ...pf, cpf: "" }]), ["Contratante 1: informe o CPF."]);
assert.deepEqual(erros([{ ...pf, cpf: "111.111.111-11" }]), ["Contratante 1: CPF inválido."]);
// Consulta de CNPJ com endereço (ou razão) vazio não trava os campos
assert.equal(consultaCompleta({ razao_social: "ACME", endereco: "" }), false);
assert.equal(consultaCompleta({ razao_social: "", endereco: "Rua A" }), false);
assert.equal(consultaCompleta({ razao_social: "ACME", endereco: "Rua A, 1" }), true);
console.log("validarContratantes.ts ok");
