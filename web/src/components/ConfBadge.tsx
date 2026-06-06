import type { Cell } from '../lib/grid'

const MAP: Record<Cell['conf'], { cls: string; text: string }> = {
  상: { cls: 'hi', text: '신뢰도 높음' },
  중: { cls: 'mid', text: '신뢰도 보통' },
  하: { cls: 'lo', text: '신뢰도 낮음 · 참고용' },
}

export default function ConfBadge({ conf, nearestM }: { conf: Cell['conf']; nearestM: number }) {
  const m = MAP[conf]
  return (
    <span className={`conf conf--${m.cls}`} title={`가장 가까운 학습 정류장 ${nearestM.toLocaleString('ko-KR')}m`}>
      ● {m.text}
    </span>
  )
}
