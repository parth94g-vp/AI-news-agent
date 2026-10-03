export default function Spinner({ label }) {
  return (
    <div className="flex items-center gap-3 text-sm" style={{ color: 'var(--muted)' }}>
      <span className="inline-block h-4 w-4 rounded-full border-2 animate-spin"
            style={{ borderColor: 'var(--border)', borderTopColor: 'var(--accent)' }} />
      {label}
    </div>
  )
}
