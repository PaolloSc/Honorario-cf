"use client";

import { useState, useCallback, useRef, useEffect } from "react";

interface CurrencyInputProps {
  value: number | undefined;
  onChange: (value: number | undefined) => void;
  placeholder?: string;
  className?: string;
  error?: boolean;
}

const BRL_FORMATTER = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const BRL_PARSER = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  minimumFractionDigits: 0,
  maximumFractionDigits: 0,
});

function parseCurrencyInput(value: string): number | undefined {
  const digits = value.replace(/\D/g, "");
  if (!digits) return undefined;
  return parseInt(digits, 10) / 100;
}

export default function CurrencyInput({
  value,
  onChange,
  placeholder = "0,00",
  className = "",
  error,
}: CurrencyInputProps) {
  const [displayValue, setDisplayValue] = useState<string>("");
  const [isFocused, setIsFocused] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (value !== undefined && value !== null && !isFocused) {
      setDisplayValue(BRL_FORMATTER.format(value));
    } else if (value === undefined || value === null) {
      setDisplayValue("");
    }
  }, [value, isFocused]);

  const handleFocus = useCallback(() => {
    setIsFocused(true);
    if (value !== undefined && value !== null) {
      const plain = BRL_PARSER.format(value).replace(/[^\d,]/g, "");
      setDisplayValue(plain);
      inputRef.current?.setSelectionRange(0, displayValue.length);
    }
  }, [value, displayValue.length]);

  const handleBlur = useCallback(() => {
    setIsFocused(false);
    const parsed = parseCurrencyInput(displayValue);
    if (parsed === undefined) {
      onChange(undefined);
      setDisplayValue("");
      return;
    }

    onChange(parsed);
    setDisplayValue(BRL_FORMATTER.format(parsed));
  }, [displayValue, onChange]);

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const raw = e.target.value;
      const digits = raw.replace(/\D/g, "");
      if (digits === "") {
        setDisplayValue("");
        onChange(undefined);
        return;
      }
      const num = parseCurrencyInput(raw);
      if (num === undefined) return;
      onChange(num);
      setDisplayValue(BRL_FORMATTER.format(num));
    },
    [onChange]
  );

  return (
    <input
      ref={inputRef}
      type="text"
      inputMode="decimal"
      value={displayValue}
      onChange={handleChange}
      onFocus={handleFocus}
      onBlur={handleBlur}
      placeholder={placeholder}
      className={`w-full px-3 py-2 rounded-lg border ${
        error ? "border-danger" : "border-border"
      } bg-card text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-primary-light focus:border-primary-light transition ${className}`}
    />
  );
}
