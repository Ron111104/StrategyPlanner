import { useEffect, useRef } from 'react'
import { createChart, Time, LineData } from 'lightweight-charts'

interface Props {
  data: { time: string; value: number }[]
  height?: number
  title?: string
  color?: string
  unit?: string
}

export default function SpreadChart({ data, height = 300, title, color = '#8b5cf6', unit = 'bp' }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!containerRef.current || data.length === 0) return
    const chart = createChart(containerRef.current, {
      layout: { background: { color: '#111827' }, textColor: '#94a3b8', fontSize: 11, fontFamily: 'JetBrains Mono' },
      grid: { vertLines: { color: '#1e293b22' }, horzLines: { color: '#1e293b22' } },
      crosshair: { mode: 0 },
      rightPriceScale: { borderColor: '#1e293b' },
      timeScale: { borderColor: '#1e293b', timeVisible: true },
      width: containerRef.current.clientWidth,
      height,
    })

    const areaSeries = chart.addAreaSeries({
      topColor: `${color}40`, bottomColor: `${color}05`, lineColor: color, lineWidth: 2,
      priceFormat: { type: 'custom', formatter: (p: number) => `${p.toFixed(1)} ${unit}` },
    })
    areaSeries.setData(data.map(d => ({ time: d.time as Time, value: d.value })) as LineData<Time>[])
    chart.timeScale().fitContent()

    const resizeObserver = new ResizeObserver(() => {
      if (containerRef.current) chart.applyOptions({ width: containerRef.current.clientWidth })
    })
    resizeObserver.observe(containerRef.current)
    return () => { resizeObserver.disconnect(); chart.remove() }
  }, [data, height, color, unit])

  return (
    <div className="glass-panel p-1">
      {title && <div className="px-3 py-2 text-xs text-terminal-text-dim font-mono uppercase tracking-wider border-b border-terminal-border">{title}</div>}
      <div ref={containerRef} />
    </div>
  )
}
