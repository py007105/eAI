/** Animate emphasis, never intermediate numbers that the API did not report. */
export default function NumberTicker({ value }: { value: string }) {
  return <span key={value} className="tabular value-update">{value}</span>;
}
