"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { getContract, getContractFormData, type ContractFormDataResponse, type ContractDetail } from "@/app/lib/api";
import ContractWizard from "@/components/ContractWizard";
import type { ContratoFormData } from "@/types/contract";

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function EditContractPage() {
  const { status: sessionStatus } = useSession();
  const params = useParams();
  const router = useRouter();
  const contractId = params.id as string;

  const [contract, setContract] = useState<ContractDetail | null>(null);
  const [formData, setFormData] = useState<ContratoFormData | null>(null);
  const [selectedVersion, setSelectedVersion] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Load contract detail (to show versions)
  useEffect(() => {
    if (sessionStatus !== "authenticated") return;
    async function loadContract() {
      try {
        const data = await getContract(contractId);
        setContract(data);
      } catch (e) {
        // Non-critical - versions panel just won't show
      }
    }
    loadContract();
  }, [contractId, sessionStatus]);

  // Load form data (latest or selected version)
  useEffect(() => {
    if (sessionStatus !== "authenticated") return;
    async function loadFormData() {
      setLoading(true);
      try {
        const result: ContractFormDataResponse = await getContractFormData(
          contractId,
          selectedVersion || undefined
        );
        setFormData(result.form_data as unknown as ContratoFormData);
        if (!selectedVersion) {
          setSelectedVersion(result.version_number);
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Erro ao carregar dados do contrato");
      } finally {
        setLoading(false);
      }
    }
    loadFormData();
  }, [contractId, sessionStatus, selectedVersion]);

  const handleVersionChange = (version: number) => {
    if (version === selectedVersion) return;
    setFormData(null);
    setSelectedVersion(version);
  };

  if (loading && !formData) {
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

        {/* Version selector */}
        {contract && contract.versions.length > 1 && (
          <div className="mt-3 mb-2 p-4 rounded-lg bg-blue-50 border border-blue-200">
            <h4 className="text-sm font-medium text-blue-900 mb-2">
              Selecionar versao para editar
            </h4>
            <div className="flex flex-wrap gap-2">
              {contract.versions.map((v) => (
                <button
                  key={v.version_number}
                  onClick={() => handleVersionChange(v.version_number)}
                  className={`px-3 py-1.5 text-xs font-medium rounded-md border transition ${
                    selectedVersion === v.version_number
                      ? "bg-primary text-white border-primary"
                      : "bg-white text-foreground border-border hover:border-primary/50"
                  }`}
                >
                  v{v.version_number}
                  {v.version_number === contract.current_version && " (atual)"}
                  <span className="ml-1 opacity-60">{formatDate(v.created_at)}</span>
                </button>
              ))}
            </div>
            {selectedVersion && selectedVersion !== contract.current_version && (
              <p className="mt-2 text-xs text-blue-700">
                Editando versao {selectedVersion}. Ao salvar, uma nova versao sera criada com base nestes dados.
              </p>
            )}
          </div>
        )}

        <div className="mt-2 mb-4 p-3 rounded-lg bg-amber-50 border border-amber-200 text-sm text-amber-800">
          Editando contrato existente. Ao gerar, uma nova versao sera criada mantendo o historico anterior.
        </div>
      </div>
      <ContractWizard
        key={selectedVersion || "latest"}
        initialData={formData}
        editContractId={contractId}
        onSaveComplete={(contractId) => router.push(`/contracts/${contractId}`)}
      />
    </div>
  );
}
