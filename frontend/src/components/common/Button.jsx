import { classNames } from "../../utils/helpers.js";

export default function Button({
  variant = "default",
  className,
  children,
  ...props
}) {
  return (
    <button
      className={classNames(
        "btn",
        variant === "primary" && "btn-primary",
        className
      )}
      {...props}
    >
      {children}
    </button>
  );
}
