import type { ButtonHTMLAttributes, PropsWithChildren } from "react";

type IconButtonProps = PropsWithChildren<
  Omit<ButtonHTMLAttributes<HTMLButtonElement>, "aria-label"> & {
    ariaLabel: string;
  }
>;

export function IconButton({ ariaLabel, children, type = "button", ...props }: IconButtonProps) {
  return (
    <button className="icon-button" type={type} aria-label={ariaLabel} {...props}>
      {children}
    </button>
  );
}
