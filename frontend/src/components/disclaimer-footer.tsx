export function DisclaimerFooter() {
  return (
    <footer className="mt-12 border-t border-line bg-surface/60">
      <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6 lg:px-8">
        <div className="flex items-start gap-3 text-xs leading-relaxed text-ink-muted">
          <span
            aria-hidden
            className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-warn-tint text-[11px] text-warn"
          >
            ⚠
          </span>
          <p>
            MedExplain AI is an educational tool, not a medical device. It does not diagnose
            conditions, recommend treatments, or prescribe medication. Reference ranges vary between
            laboratories.{" "}
            <span className="font-semibold text-ink">
              Consult a licensed healthcare professional for medical advice.
            </span>
          </p>
        </div>
      </div>
    </footer>
  );
}
