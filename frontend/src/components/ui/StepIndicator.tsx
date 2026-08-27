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
  // overflow-x-auto: em mobile as 7 etapas nao cabem; rola a barra, nao a pagina.
  return (
    <nav className="mb-8 overflow-x-auto">
      <ol className="flex items-center gap-2 w-max">
        {steps.map((step, idx) => {
          const isActive = step.id === currentStep;
          const isCompleted = step.id < currentStep;
          return (
            <li key={step.id} className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => onStepClick?.(step.id)}
                className="flex items-center gap-2 cursor-pointer hover:opacity-80 transition"
              >
                <span
                  className={`flex items-center justify-center w-8 h-8 rounded-full text-sm font-bold transition-all ${
                    isActive
                      ? "bg-primary text-white shadow-md"
                      : isCompleted
                        ? "bg-success text-white"
                        : "bg-gray-200 text-muted"
                  }`}
                >
                  {isCompleted ? (
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                    </svg>
                  ) : (
                    step.id
                  )}
                </span>
                <span
                  className={`text-xs font-medium hidden sm:inline whitespace-nowrap ${
                    isActive ? "text-primary" : isCompleted ? "text-success" : "text-muted"
                  }`}
                >
                  {step.title}
                </span>
              </button>
              {idx < steps.length - 1 && (
                <div
                  className={`w-8 h-0.5 ${
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
