"use client";

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
  // ponytail: conector elastico (flex-1) => sempre uma linha so, sem JS de medicao.
  return (
    <nav className="mb-8">
      <ol className="flex items-center gap-1.5">
        {steps.map((step, idx) => {
          const isActive = step.id === currentStep;
          const isCompleted = step.id < currentStep;
          return (
            <li key={step.id} className="flex items-center gap-1.5 flex-1 last:flex-none">
              <button
                type="button"
                onClick={() => onStepClick?.(step.id)}
                className="flex items-center gap-1.5 cursor-pointer hover:opacity-80 transition"
              >
                <span
                  className={`flex items-center justify-center w-7 h-7 shrink-0 rounded-full text-xs font-bold transition-all ${
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
                  className={`text-[10px] font-medium hidden md:inline whitespace-nowrap ${
                    isActive ? "text-primary" : isCompleted ? "text-success" : "text-muted"
                  }`}
                >
                  {step.title}
                </span>
              </button>
              {idx < steps.length - 1 && (
                <div
                  className={`flex-1 min-w-2 h-0.5 ${
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
