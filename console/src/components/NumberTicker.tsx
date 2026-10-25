/** Shows the API-provided value exactly. No animated in-between counts: every number on screen is one the API reported. */
export default function NumberTicker({ value }: { value: string }) {
  return <span className="tabular">{value}</span>;
}
