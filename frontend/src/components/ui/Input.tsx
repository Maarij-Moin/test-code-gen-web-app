import { forwardRef, type InputHTMLAttributes } from "react";

type InputProps = InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  error?: string;
};

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, className = "", id, ...props }, ref) => {
    const inputId = id ?? props.name ?? label;

    return (
      <label className="block text-sm font-medium text-text" htmlFor={inputId}>
        <span>{label}</span>
        <input
          ref={ref}
          id={inputId}
          className={`focus-ring mt-2 h-11 w-full rounded-md border border-border bg-panel px-3 text-sm text-text placeholder:text-muted ${className}`}
          {...props}
        />
        {error ? <span className="mt-2 block text-xs text-danger">{error}</span> : null}
      </label>
    );
  },
);

Input.displayName = "Input";
