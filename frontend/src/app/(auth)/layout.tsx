import { Logo } from "@/components/shell";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-dvh flex-col items-center justify-center px-4 py-10">
      <div className="mb-8"><Logo /></div>
      <div className="w-full max-w-md rounded-2xl border border-line bg-surface p-6 shadow-sm sm:p-8">{children}</div>
      <p className="mt-6 max-w-md text-center text-xs text-ink-3">VisaReady AI is independent and not affiliated with any government. We do not provide legal advice or guarantee visa outcomes.</p>
    </div>
  );
}
