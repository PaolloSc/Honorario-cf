"use client";

import { ReactNode, useMemo, useRef, useState } from "react";
 
interface FormFieldProps {
  label: string;
  required?: boolean;
  hint?: string;
  error?: string;
  children: ReactNode;
}
 
export default function FormField({
  label,
  required,
  hint,
  error,
  children,
}: FormFieldProps) {
  return (
    <div className="mb-4">
      <label className="block text-sm font-semibold text-foreground mb-1">
        {label}
        {required && <span className="text-danger ml-1">*</span>}
      </label>
      {children}
      {hint && <p className="text-xs text-muted mt-1">{hint}</p>}
      {error && <p className="text-xs text-danger mt-1">{error}</p>}
    </div>
  );
}
 
interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  error?: boolean;
}
 
export function Input({ error, className = "", ...props }: InputProps) {
  return (
    <input
      className={`w-full px-3 py-2 rounded-lg border ${
        error ? "border-danger" : "border-border"
      } bg-card text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-primary-light focus:border-primary-light transition ${className}`}
      {...props}
    />
  );
}
 
interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  error?: boolean;
  options: Array<{ value: string; label: string }>;
  placeholder?: string;
}
 
export function Select({
  error,
  options,
  placeholder,
  className = "",
  ...props
}: SelectProps) {
  return (
    <select
      className={`w-full px-3 py-2 rounded-lg border ${
        error ? "border-danger" : "border-border"
      } bg-card text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-primary-light focus:border-primary-light transition ${className}`}
      {...props}
    >
      {placeholder && (
        <option value="" disabled>
          {placeholder}
        </option>
      )}
      {options.map((opt) => (
        <option key={opt.value} value={opt.value}>
          {opt.label}
        </option>
      ))}
    </select>
  );
}
 
interface TextAreaProps
  extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  error?: boolean;
}
 
export function TextArea({ error, className = "", ...props }: TextAreaProps) {
  return (
    <textarea
      className={`w-full px-3 py-2 rounded-lg border ${
        error ? "border-danger" : "border-border"
      } bg-card text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-primary-light focus:border-primary-light transition resize-y ${className}`}
      rows={3}
      {...props}
    />
  );
}
 
interface CheckboxProps {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  hint?: string;
}
 
export function Checkbox({ label, checked, onChange, hint }: CheckboxProps) {
  return (
    <label className="flex items-start gap-3 cursor-pointer py-1">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="mt-0.5 h-4 w-4 rounded border-border text-primary focus:ring-primary-light"
      />
      <div>
        <span className="text-sm text-foreground">{label}</span>
        {hint && <p className="text-xs text-muted mt-0.5">{hint}</p>}
      </div>
    </label>
  );
}
 
interface ToggleProps {
  label: string;
  value: boolean;
  onChange: (val: boolean) => void;
}
 
export function Toggle({ label, value, onChange }: ToggleProps) {
  return (
    <label className="flex items-center gap-3 cursor-pointer py-2">
      <button
        type="button"
        role="switch"
        aria-checked={value}
        onClick={() => onChange(!value)}
        className={`inline-flex h-6 w-11 shrink-0 items-center rounded-full border-2 border-transparent shadow-sm transition-colors ${
          value ? "bg-primary" : "bg-border/40"
        }`}
      >
        <span
          className={`pointer-events-none block h-5 w-5 transform rounded-full bg-white shadow-lg transition-transform ${
            value ? "translate-x-5" : "translate-x-0"
          }`}
        />
      </button>
      <span className="text-sm font-medium text-foreground">{label}</span>
    </label>
  );
}

interface ComboBoxProps {
  value: string;
  onChange: (value: string) => void;
  options: Array<{ value: string; label: string }>;
  placeholder?: string;
  error?: boolean;
}

// Select com busca: digitar filtra as opcoes por trecho do nome (ex.: "G" lista
// Gabriel, Gabriela...), em vez da lista suspensa nativa que exige rolar tudo.
export function ComboBox({ value, onChange, options, placeholder, error }: ComboBoxProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const blurTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);

  const selected = options.find((o) => o.value === value);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return options;
    return options.filter((o) => o.label.toLowerCase().includes(q));
  }, [options, query]);

  return (
    <div className="relative">
      <input
        type="text"
        value={open ? query : selected?.label ?? ""}
        onChange={(e) => {
          setQuery(e.target.value);
          if (e.target.value === "") onChange("");
        }}
        onFocus={() => {
          setOpen(true);
          setQuery("");
        }}
        onBlur={() => {
          blurTimeout.current = setTimeout(() => setOpen(false), 150);
        }}
        placeholder={placeholder}
        className={`w-full px-3 py-2 rounded-lg border ${
          error ? "border-danger" : "border-border"
        } bg-card text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-primary-light focus:border-primary-light transition`}
      />
      {open && (
        <ul className="absolute z-10 mt-1 max-h-56 w-full overflow-auto rounded-lg border border-border bg-card shadow-lg text-sm">
          {filtered.length === 0 ? (
            <li className="px-3 py-2 text-muted">Nenhum resultado</li>
          ) : (
            filtered.map((o) => (
              <li
                key={o.value}
                onMouseDown={(e) => {
                  e.preventDefault();
                  if (blurTimeout.current) clearTimeout(blurTimeout.current);
                  onChange(o.value);
                  setQuery("");
                  setOpen(false);
                }}
                className={`px-3 py-2 cursor-pointer hover:bg-primary/10 ${
                  o.value === value ? "bg-primary/[0.08] font-medium" : ""
                }`}
              >
                {o.label}
              </li>
            ))
          )}
        </ul>
      )}
    </div>
  );
}