"use client";

import { useEffect, useRef } from "react";

interface Step {
  id: number;
  title: string;
}

interface StepIndicatorProps {
  steps: Step[];
  currentStep: number;
  onStepClick?: (stepId: number) => void;
}

export default function StepIndicator({
  steps,
  currentStep,
  onStepClick,
}: StepIndicatorProps) {
  const olRef = useRef<HTMLOListElement>(null);

  // ponytail: invisible (nao hidden) para nao mexer no layout e nao oscilar o wrap.
  useEffect(() => {
    const ol = olRef.current;
    if (!ol) return;
    const update = () => {
      const items = Array.from(ol.children) as HTMLElement[];
      items.forEach((li, i) => {
        const next = items[i + 1];
        li
          .querySelector("[data-connector]")
          ?.classList.toggle("invisible", !next || next.offsetTop > li.offsetTop);
      });
    };
    update();
    const ro = new ResizeObserver(update);
    ro.observe(ol);
    return () => ro.disconnect();
  }, [steps.length, currentStep]);

  // ponytail: sem scroll horizontal; as etapas quebram linha quando nao cabem.
  return (
    <nav className="mb-8">
      <ol ref={olRef} className="flex flex-wrap items-center justify-center gap-y-3 gap-x-1.5">
        {steps.map((step, idx) => {
          const isActive = step.id === currentStep;
          const isCompleted = step.id < currentStep;
          return (
            <li key={step.id} className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={() => onStepClick?.(step.id)}
                className="flex items-center gap-1.5 cursor-pointer hover:opacity-80 transition"
              >
                <span
                  className={`flex items-center justify-center w-7 h-7 rounded-full text-xs font-bold transition-all ${
                    isActive
                      ? "bg-primary text-white shadow-md"
                      : isCompleted
                        ? "bg-success text-white"
                        : "bg-gray-200 text-muted"
                  }`}
                >
                  {isCompleted ? (
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                    </svg>
                  ) : (
                    step.id
                  )}
                </span>
                <span
                  className={`text-[11px] font-medium hidden sm:inline whitespace-nowrap ${
                    isActive ? "text-primary" : isCompleted ? "text-success" : "text-muted"
                  }`}
                >
                  {step.title}
                </span>
              </button>
              {idx < steps.length - 1 && (
                <div
                  data-connector
                  className={`w-4 h-0.5 ${
                    isCompleted ? "bg-success" : "bg-gray-200"
                  }`}
                />
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
