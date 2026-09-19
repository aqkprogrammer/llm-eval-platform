import { useId } from "react";

export function LogoMark({ className = "size-7" }: { className?: string }) {
  const id = useId();
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden fill="none">
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
          <stop stopColor="#8b5cf6" />
          <stop offset="1" stopColor="#6d28d9" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="8" fill={`url(#${id})`} />
      <path d="M7.5 21.5 12.5 15l4 4 7-9.5" stroke="#fff" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="23.5" cy="9.5" r="2" fill="#fff" />
      <path d="M7.5 25h17" stroke="#fff" strokeOpacity=".35" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}
