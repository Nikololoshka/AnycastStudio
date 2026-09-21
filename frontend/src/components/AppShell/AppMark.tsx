export function AppMark() {
  return (
    <svg viewBox="0 0 28 28" className="size-7 text-accent" aria-hidden>
      <rect width="28" height="28" rx="8" className="fill-current" />
      <circle cx="9" cy="14" r="3" className="fill-accent-foreground" />
      <path
        d="M12 14 L20 7.5 M12 14 L21 12 M12 14 L21 16 M12 14 L20 20.5"
        className="stroke-accent-foreground"
        strokeWidth="1.8"
        strokeLinecap="round"
        fill="none"
      />
    </svg>
  );
}
