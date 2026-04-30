"use client";
 
interface Step {
  id: number;
  title: string;
}
 
interface StepIndicatorProps {
  steps: Step[];
  currentStep: number;
}
 
export default function StepIndicator({
  steps,
  currentStep,
}: StepIndicatorProps) {
  return (
    <nav className="mb-8">
      <ol className="flex items-center gap-2">
        {steps.map((step, idx) => {
          const isActive = step.id === currentStep;
          const isCompleted = step.id < currentStep;
          return (
            <li key={step.id} className="flex items-center gap-2">
              <div className="flex items-center gap-2">
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
                  className={`text-xs font-medium hidden sm:inline ${
                    isActive ? "text-primary" : isCompleted ? "text-success" : "text-muted"
                  }`}
                >
                  {step.title}
                </span>
              </div>
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