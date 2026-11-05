"use client";

import FormField, { Input } from "@/components/ui/FormField";
import DatePicker from "@/components/ui/DatePicker";
import { diaDaData, dividirParcelas } from "@/app/lib/parcelas";

const brl = (v: number) => v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

/** Parcelamento mensal automático: nº de parcelas, 1ª parcela em data fixa e dia de vencimento.
 *  O valor de cada parcela é calculado (a última absorve os centavos) e mostrado aqui. */
export default function ParcelasCampos({
  total,
  numero,
  data,
  dia,
  onChange,
}: {
  total: number;
  numero?: number;
  data?: string;
  dia?: number;
  onChange: (p: { numero?: number; data?: string; dia?: number; valorParcela: number }) => void;
}) {
  const emitir = (p: { numero?: number; data?: string; dia?: number }) => {
    const n = "numero" in p ? p.numero : numero;
    onChange({
      numero: n,
      data: "data" in p ? p.data : data,
      dia: "dia" in p ? p.dia : dia,
      valorParcela: dividirParcelas(total, n ?? 0)[0] ?? 0,
    });
  };
  const valores = dividirParcelas(total, numero ?? 0);
  const iguais = valores.length > 0 && valores[0] === valores[valores.length - 1];
  return (
    <>
      <FormField label="Número de parcelas" required>
        <Input
          type="number"
          value={numero || ""}
          onChange={(e) => emitir({ numero: parseInt(e.target.value) || 0 })}
          placeholder="0"
        />
      </FormField>
      <FormField label="Vencimento da 1ª parcela (data)" required>
        <DatePicker value={data} onChange={(v) => emitir({ data: v })} />
      </FormField>
      <FormField
        label="Dia de vencimento das demais"
        hint={diaDaData(data) ? `Em branco: dia ${diaDaData(data)}.` : "Em branco: o dia da 1ª parcela."}
      >
        <Input
          type="number"
          min={1}
          max={31}
          value={dia || ""}
          onChange={(e) => emitir({ dia: parseInt(e.target.value) || undefined })}
          placeholder={String(diaDaData(data) ?? "")}
        />
      </FormField>
      {valores.length > 0 && (
        <p className="text-sm text-muted md:col-span-2">
          {iguais
            ? `${valores.length} parcelas de ${brl(valores[0])}`
            : `${valores.length - 1} parcelas de ${brl(valores[0])} e a última de ${brl(valores[valores.length - 1])}`}{" "}
          (calculado automaticamente).
        </p>
      )}
    </>
  );
}
