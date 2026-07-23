import { useEffect, useRef, useState } from 'react'

/** Número com animação de contagem (count-up). */
export function AnimatedNumber({
  value,
  duration = 900,
  decimals = 0,
}: {
  value: number
  duration?: number
  decimals?: number
}) {
  const [display, setDisplay] = useState(0)
  const ref = useRef<number>(0)

  useEffect(() => {
    const start = performance.now()
    const from = ref.current
    let raf = 0
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration)
      const eased = 1 - Math.pow(1 - t, 3)
      const cur = from + (value - from) * eased
      setDisplay(cur)
      if (t < 1) raf = requestAnimationFrame(tick)
      else ref.current = value
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [value, duration])

  return <>{display.toLocaleString('pt-BR', { maximumFractionDigits: decimals, minimumFractionDigits: decimals })}</>
}

/** Medidor radial (semicírculo) para o score de segurança. */
export function ScoreGauge({ score, grade }: { score: number; grade: string }) {
  const size = 200
  const stroke = 16
  const r = (size - stroke) / 2
  const cx = size / 2
  const cy = size / 2
  // arco de 270° (de -225° a +45°)
  const circumference = 2 * Math.PI * r
  const arcFraction = 0.75 // 270/360
  const arcLen = circumference * arcFraction
  const [progress, setProgress] = useState(0)

  useEffect(() => {
    const id = requestAnimationFrame(() => setProgress(score / 100))
    return () => cancelAnimationFrame(id)
  }, [score])

  const color = score >= 80 ? '#37d67a' : score >= 60 ? '#ffb020' : score >= 40 ? '#ff7a2d' : '#ff2d43'
  const dash = arcLen * progress
  const gap = circumference - dash

  return (
    <div className="gauge-wrap">
      <svg width={size} height={size * 0.72} viewBox={`0 0 ${size} ${size * 0.78}`}>
        <defs>
          <linearGradient id="gaugeGrad" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor={color} />
            <stop offset="100%" stopColor={color} stopOpacity={0.65} />
          </linearGradient>
        </defs>
        {/* trilha */}
        <circle
          cx={cx} cy={cy} r={r} fill="none" style={{ stroke: 'var(--bg-3)' }} strokeWidth={stroke}
          strokeLinecap="round" strokeDasharray={`${arcLen} ${circumference}`}
          transform={`rotate(135 ${cx} ${cy})`}
        />
        {/* progresso */}
        <circle
          cx={cx} cy={cy} r={r} fill="none" stroke="url(#gaugeGrad)" strokeWidth={stroke}
          strokeLinecap="round" strokeDasharray={`${dash} ${gap}`}
          transform={`rotate(135 ${cx} ${cy})`}
          style={{ transition: 'stroke-dasharray 1.2s cubic-bezier(.2,.8,.2,1)', filter: `drop-shadow(0 0 6px ${color}66)` }}
        />
        <text x={cx} y={cy - 2} textAnchor="middle" fontSize="42" fontWeight="800" fill={color}>
          {Math.round(score * progress)}
        </text>
        <text x={cx} y={cy + 22} textAnchor="middle" fontSize="12" style={{ fill: 'var(--text-2)' }} letterSpacing="2">
          / 100
        </text>
      </svg>
      <div className="gauge-grade">
        Grade <span style={{ color, fontWeight: 800, fontSize: 16 }}>{grade}</span>
      </div>
    </div>
  )
}
