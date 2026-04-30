"use client";
 
import { ReactNode } from "react";
 
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
      {hint && <p className="text-xs text-muted mb-1">{hint}</p>}
      {children}
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
        className={`relative inline-flex h-6 w-11 shrink-0 rounded-full transition-colors ${
          value ? "bg-primary" : "bg-gray-300"
        }`}
      >
        <span
          className={`inline-block h-5 w-5 transform rounded-full bg-white shadow-sm transition-transform mt-0.5 ${
            value ? "translate-x-5.5 ml-0.5" : "translate-x-0.5"
          }`}
        />
      </button>
      <span className="text-sm font-medium text-foreground">{label}</span>
    </label>
  );
}