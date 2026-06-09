export function JsonView({ data }: { data: unknown }) {
  if (data === null || data === undefined) {
    return <span className="muted">—</span>
  }
  return <pre className="json">{JSON.stringify(data, null, 2)}</pre>
}
