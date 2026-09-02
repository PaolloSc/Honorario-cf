"use client";

import { useState, useRef, useEffect } from "react";
import { DayPicker } from "react-day-picker";
import { differenceInCalendarMonths, format, parseISO } from "date-fns";
import { ptBR } from "date-fns/locale";
import "react-day-picker/dist/style.css";

interface DateRangePickerProps {
  dataInicio?: string;
  dataFim?: string;
  onChange: (dataInicio: string | undefined, dataFim: string | undefined, duracaoMeses: number | undefined) => void;
  required?: boolean;
}

function toISO(d?: Date): string | undefined {
  return d ? format(d, "yyyy-MM-dd") : undefined;
}

function fromISO(s?: string): Date | undefined {
  return s ? parseISO(s) : undefined;
}

function calcDuracaoMeses(inicio?: Date, fim?: Date): number | undefined {
  if (!inicio || !fim) return undefined;
  return differenceInCalendarMonths(fim, inicio) + 1;
}

function formatBR(d?: Date): string {
  return d ? format(d, "dd/MM/yyyy", { locale: ptBR }) : "";
}

export default function DateRangePicker({
  dataInicio,
  dataFim,
  onChange,
  required,
}: DateRangePickerProps) {
  const [openInicio, setOpenInicio] = useState(false);
  const [openFim, setOpenFim] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const inicio = fromISO(dataInicio);
  const fim = fromISO(dataFim);
  const duracao = calcDuracaoMeses(inicio, fim);
  const erroOrdem = inicio && fim && fim < inicio;

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpenInicio(false);
        setOpenFim(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const inputClass = "w-full px-3 py-2 rounded-lg border border-border bg-card text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-primary-light cursor-pointer";

  return (
    <div ref={containerRef} className="grid grid-cols-1 md:grid-cols-3 gap-3">
      <div className="relative">
        <label className="block text-sm font-semibold text-foreground mb-1">
          Data de início{required && <span className="text-danger ml-1">*</span>}
        </label>
        <button
          type="button"
          onClick={() => { setOpenInicio((v) => !v); setOpenFim(false); }}
          className={inputClass + " text-left"}
        >
          {formatBR(inicio) || <span className="text-muted">Selecione...</span>}
        </button>
        {openInicio && (
          <div className="absolute z-50 mt-1 bg-card border border-border rounded-lg shadow-lg p-2">
            <DayPicker
              mode="single"
              selected={inicio}
              onSelect={(d) => {
                onChange(toISO(d), dataFim, calcDuracaoMeses(d, fim));
                setOpenInicio(false);
              }}
              locale={ptBR}
            />
          </div>
        )}
      </div>

      <div className="relative">
        <label className="block text-sm font-semibold text-foreground mb-1">
          Data de término{required && <span className="text-danger ml-1">*</span>}
        </label>
        {/* Prazo indeterminado e' o padrao: sem data de termino preenchida. */}
        <label className="flex items-center gap-2 text-sm text-muted mb-1 cursor-pointer">
          <input
            type="checkbox"
            checked={!fim}
            onChange={(e) => {
              if (e.target.checked) onChange(dataInicio, undefined, undefined);
              else setOpenFim(true);
            }}
          />
          Prazo indeterminado
        </label>
        <button
          type="button"
          onClick={() => { setOpenFim((v) => !v); setOpenInicio(false); }}
          className={inputClass + " text-left"}
        >
          {formatBR(fim) || <span className="text-muted">Prazo indeterminado</span>}
        </button>
        {openFim && (
          <div className="absolute z-50 mt-1 bg-card border border-border rounded-lg shadow-lg p-2">
            <DayPicker
              mode="single"
              selected={fim}
              onSelect={(d) => {
                onChange(dataInicio, toISO(d), calcDuracaoMeses(inicio, d));
                setOpenFim(false);
              }}
              disabled={inicio ? { before: inicio } : undefined}
              locale={ptBR}
            />
          </div>
        )}
        {erroOrdem && (
          <p className="text-xs text-danger mt-1">Data de término deve ser maior ou igual à de início.</p>
        )}
      </div>

      <div>
        <label className="block text-sm font-semibold text-foreground mb-1">
          Duração (meses)
        </label>
        <input
          readOnly
          value={duracao ?? ""}
          placeholder="—"
          className="w-full px-3 py-2 rounded-lg border border-muted bg-border/35 text-muted text-sm cursor-not-allowed"
        />
      </div>
    </div>
  );
}
