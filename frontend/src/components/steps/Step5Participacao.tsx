"use client";
 
import FormField, { Input, TextArea, Toggle } from "@/components/ui/FormField";
import type { Participacao } from "@/types/contract";
 
interface Step5Props {
  participacao: Participacao;
  onChange: (participacao: Participacao) => void;
}
 
export default function Step5Participacao({
  participacao,
  onChange,
}: Step5Props) {
  return (
    <div>
      <h2 className="text-xl font-bold text-primary mb-2">
        5. Participações (Ficha Interna)
      </h2>
      <p className="text-sm text-muted mb-2">
        Informações internas sobre participação. O cliente{" "}
        <strong>não terá acesso</strong> a estes dados.
      </p>
      <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 mb-6">
        <p className="text-xs text-yellow-800 font-medium">
          Atenção: Esta ficha é apenas para fins internos do escritório.
        </p>
      </div>
 
      <div className="bg-card border border-border rounded-xl p-6 shadow-sm space-y-4">
        <Toggle
          label="Este contrato terá participação?"
          value={participacao.tem_participacao}
          onChange={(v) =>
            onChange({ ...participacao, tem_participacao: v })
          }
        />
 
        {participacao.tem_participacao && (
          <div className="space-y-4 mt-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <FormField label="Percentual ou valor da participação">
                <Input
                  value={participacao.percentual_ou_valor || ""}
                  onChange={(e) =>
                    onChange({
                      ...participacao,
                      percentual_ou_valor: e.target.value,
                    })
                  }
                  placeholder="Ex: 10% ou R$ 5.000,00"
                />
              </FormField>
 
              <FormField label="Para quem?">
                <Input
                  value={participacao.para_quem || ""}
                  onChange={(e) =>
                    onChange({
                      ...participacao,
                      para_quem: e.target.value,
                    })
                  }
                  placeholder="Nome do beneficiário"
                />
              </FormField>
 
              <FormField label="Natureza da participação">
                <Input
                  value={participacao.natureza || ""}
                  onChange={(e) =>
                    onChange({
                      ...participacao,
                      natureza: e.target.value,
                    })
                  }
                  placeholder="Ex: captação, performance, projeto"
                />
              </FormField>
            </div>
 
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <FormField label="Responsável pela captação">
                <Input
                  value={participacao.responsavel_captacao || ""}
                  onChange={(e) =>
                    onChange({
                      ...participacao,
                      responsavel_captacao: e.target.value,
                    })
                  }
                />
              </FormField>
 
              <FormField label="Responsável pela gestão do contrato">
                <Input
                  value={participacao.responsavel_gestao || ""}
                  onChange={(e) =>
                    onChange({
                      ...participacao,
                      responsavel_gestao: e.target.value,
                    })
                  }
                />
              </FormField>
 
              <FormField label="Contato do responsável financeiro do cliente">
                <TextArea
                  value={participacao.contato_financeiro_cliente || ""}
                  onChange={(e) =>
                    onChange({
                      ...participacao,
                      contato_financeiro_cliente: e.target.value,
                    })
                  }
                  placeholder="Nome, e-mail e telefone..."
                />
              </FormField>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}