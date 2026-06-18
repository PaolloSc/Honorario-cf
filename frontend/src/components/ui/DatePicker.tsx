"use client";

import { useState, useRef, useEffect } from "react";
import { DayPicker } from "react-day-picker";
import { format, parseISO } from "date-fns";
import { ptBR } from "date-fns/locale";
import "react-day-picker/dist/style.css";

interface DatePickerProps {
  value?: string;
  onChange: (value: string | undefined) => void;
  placeholder?: string;
  required?: boolean;
  className?: string;
}

function toISO(d?: Date): string | undefined {
  return d ? format(d, "yyyy-MM-dd") : undefined;
}

function fromISO(s?: string): Date | undefined {
  if (!s) return undefined;
  try {
    return parseISO(s);
  } catch {
    return undefined;
  }
}

function formatBR(d?: Date): string {
  return d ? format(d, "dd/MM/yyyy", { locale: ptBR }) : "";
}

export default function DatePicker({
  value,
  onChange,
  placeholder = "Selecione...",
  className = "",
}: DatePickerProps) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const selected = fromISO(value);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div ref={containerRef} className={`relative ${className}`}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full px-3 py-2 rounded-lg border border-border bg-card text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-primary-light cursor-pointer text-left"
      >
        {formatBR(selected) || <span className="text-muted">{placeholder}</span>}
      </button>
      {open && (
        <div className="absolute z-50 mt-1 bg-card border border-border rounded-lg shadow-lg p-2">
          <DayPicker
            mode="single"
            selected={selected}
            onSelect={(d) => {
              onChange(toISO(d));
              setOpen(false);
            }}
            locale={ptBR}
          />
        </div>
      )}
    </div>
  );
}
