// Won (KRW) formatting helpers.

// 481915 -> "48만" ; 1135600 -> "114만" ; 2317348 -> "232만"
export function manWon(v: number): string {
  const man = v / 10_000
  if (man >= 100) return `${Math.round(man).toLocaleString('ko-KR')}만`
  return `${man.toFixed(1)}만`
}

// 481915 -> "481,915원"
export function won(v: number): string {
  return `${Math.round(v).toLocaleString('ko-KR')}원`
}

// signed percent for SHAP factors: 22.7 -> "+22.7%"
export function signedPct(v: number): string {
  return `${v > 0 ? '+' : ''}${v.toFixed(1)}%`
}

export type Verdict = { key: 'under' | 'fair' | 'over'; label: string; diffPct: number }

// Compare a quoted price against the cell's predicted 80% interval.
export function judge(quoted: number, pred: number, lo: number, hi: number): Verdict {
  const diffPct = (quoted / pred - 1) * 100
  if (quoted < lo) return { key: 'under', label: '저평가 · 좋은 조건', diffPct }
  if (quoted > hi) return { key: 'over', label: '고평가 · 비싼 편', diffPct }
  return { key: 'fair', label: '적정 범위', diffPct }
}
