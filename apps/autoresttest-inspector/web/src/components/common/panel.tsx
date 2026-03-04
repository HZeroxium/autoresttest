import { PropsWithChildren, ReactNode } from "react";
import clsx from "clsx";

type PanelProps = PropsWithChildren<{
  title?: string;
  className?: string;
  actions?: ReactNode;
}>;

export function Panel({ title, className, actions, children }: PanelProps) {
  return (
    <section
      className={clsx(
        "rounded-3xl border border-line bg-panel/90 p-5 shadow-panel backdrop-blur-sm",
        className,
      )}
    >
      {(title || actions) && (
        <header className="mb-4 flex items-center justify-between gap-4">
          {title ? (
            <h2 className="font-display text-lg font-semibold text-ink">{title}</h2>
          ) : (
            <span />
          )}
          {actions}
        </header>
      )}
      {children}
    </section>
  );
}
