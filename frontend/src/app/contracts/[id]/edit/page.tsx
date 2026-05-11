"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { getContractFormData, type ContractFormDataResponse } from "@/app/lib/api";
import ContractWizard from "@/components/ContractWizard";
import type { ContratoFormData } from "@/types/contract";

export default function EditContractPage() {
  const { status: sessionStatus } = useSession();
  const params = useParams();
  const router = useRouter();
  const contractId = params.id as string;

  const [formData, setFormData] = useState<ContratoFormData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (sessionStatus !== "authenticated") return;
    async function load() {
      try {
        const result: ContractFormDataResponse = await getContractFormData(contractId);
        setFormData(result.form_data as unknown as ContratoFormData);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Erro ao carregar dados do contrato");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [contractId, sessionStatus]);

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-12 text-center text-muted">
        Carregando dados do contrato...
      </div>
    );
  }

  if (error || !formData) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-12">
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          {error || "Dados nao encontrados"}
        </div>
        <a href="/contracts" className="mt-4 inline-block text-sm text-primary hover:underline">
          Voltar para lista
        </a>
      </div>
    );
  }

  return (
    <div>
      <div className="max-w-4xl mx-auto px-4 pt-6">
        <a
          href={`/contracts/${contractId}`}
          className="text-sm text-muted hover:text-foreground transition"
        >
          &larr; Voltar ao contrato
        </a>
        <div className="mt-2 mb-4 p-3 rounded-lg bg-amber-50 border border-amber-200 text-sm text-amber-800">
          Editando contrato existente. Ao gerar, uma nova versao sera criada mantendo o historico anterior.
        </div>
      </div>
      <ContractWizard
        initialData={formData}
        editContractId={contractId}
        onSaveComplete={(contractId) => router.push(`/contracts/${contractId}`)}
      />
    </div>
  );
}
