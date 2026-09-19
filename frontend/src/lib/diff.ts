export type DiffOp = { type: "same" | "add" | "del"; text: string; a?: number; b?: number };

/** Line diff via longest common subsequence (O(n*m), fine for prompt-sized inputs). */
export function lineDiff(before: string, after: string): DiffOp[] {
  const a = before.split("\n");
  const b = after.split("\n");
  const n = a.length;
  const m = b.length;
  const dp: Uint32Array[] = Array.from({ length: n + 1 }, () => new Uint32Array(m + 1));
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
    }
  }
  const out: DiffOp[] = [];
  let i = 0;
  let j = 0;
  while (i < n && j < m) {
    if (a[i] === b[j]) {
      out.push({ type: "same", text: a[i], a: i + 1, b: j + 1 });
      i++;
      j++;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      out.push({ type: "del", text: a[i], a: i + 1 });
      i++;
    } else {
      out.push({ type: "add", text: b[j], b: j + 1 });
      j++;
    }
  }
  while (i < n) out.push({ type: "del", text: a[i], a: ++i });
  while (j < m) out.push({ type: "add", text: b[j], b: ++j });
  return out;
}
