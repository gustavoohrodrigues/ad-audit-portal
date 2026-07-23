// Sparkline SVG minúsculo (linha + área com degradê). Leve, sem Recharts.
export function Sparkline({ data, color, width = 120, height = 34 }: {
  data: number[]; color: string; width?: number; height?: number
}) {
  if (!data.length) return <svg width={width} height={height} />
  const max = Math.max(...data, 1)
  const min = Math.min(...data, 0)
  const span = max - min || 1
  const stepX = data.length > 1 ? width / (data.length - 1) : width
  const y = (v: number) => height - 3 - ((v - min) / span) * (height - 6)
  const pts = data.map((v, i) => `${(i * stepX).toFixed(1)},${y(v).toFixed(1)}`)
  const line = `M${pts.join(' L')}`
  const area = `${line} L${width},${height} L0,${height} Z`
  const gid = `sl-${color.replace(/[^a-z0-9]/gi, '')}`
  const lastX = (data.length - 1) * stepX
  const lastY = y(data[data.length - 1])
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" style={{ display: 'block' }}>
      <defs>
        <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity={0.35} />
          <stop offset="100%" stopColor={color} stopOpacity={0} />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#${gid})`} />
      <path d={line} fill="none" stroke={color} strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={lastX} cy={lastY} r={2.4} fill={color} />
    </svg>
  )
}
