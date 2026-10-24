export interface Sample {
  at: number;
  value: number | null;
}
export function appendSample(
  buffer: Sample[],
  value: number | undefined,
  at: number,
  limit = 60,
): Sample[] {
  const next = [
    ...buffer,
    {
      at,
      value: typeof value === "number" && Number.isFinite(value) ? value : null,
    },
  ];
  return next.slice(-Math.max(1, limit));
}
