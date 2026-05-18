import { useEffect, useRef } from 'react'
import { createChart, IChartApi, CandlestickData, LineData, Time } from 'lightweight-charts'

interface Props {
  data: { time: string; open: number; high: number; low: number; close: number }[]
  overlays?: { label: string; data: { time: string; value: number }[]; color: string }[]
  markers?: { time: string; position: 'aboveBar' | 'belowBar'; color: string; shape: 'arrowUp' | 'arrowDown' | 'circle'; text: string }[]
  height?: number
  title?: string
}

export default function CandlestickChart({ data, overlays = [], markers = [], height = 400, title }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)

  useEffect(() => {
    if (!containerRef.current) return
    const chart = createChart(containerRef.current, {
      layout: { background: { color: '#111827' }, textColor: '#94a3b8', fontSize: 11, fontFamily: 'JetBrains Mono' },
      grid: { vertLines: { color: '#1e293b22' }, horzLines: { color: '#1e293b22' } },
      crosshair: { mode: 0, vertLine: { color: '#3b82f6', width: 1, style: 2 }, horzLine: { color: '#3b82f6', width: 1, style: 2 } },
      rightPriceScale: { borderColor: '#1e293b', scaleMargins: { top: 0.1, bottom: 0.1 } },
      timeScale: { borderColor: '#1e293b', timeVisible: true, secondsVisible: false },
      width: containerRef.current.clientWidth,
      height,
    })
    chartRef.current = chart

    const candleSeries = chart.addCandlestickSeries({
      upColor: '#10b981', downColor: '#ef4444', borderUpColor: '#10b981', borderDownColor: '#ef4444',
      wickUpColor: '#10b981', wickDownColor: '#ef4444',
    })
    const formatted = data.map(d => ({ time: d.time as Time, open: d.open, high: d.high, low: d.low, close: d.close }))
    candleSeries.setData(formatted as CandlestickData<Time>[])

    if (markers.length > 0) {
      candleSeries.setMarkers(markers.map(m => ({ ...m, time: m.time as Time })))
    }

    overlays.forEach(ov => {
      const lineSeries = chart.addLineSeries({ color: ov.color, lineWidth: 1, title: ov.label, priceLineVisible: false })
      lineSeries.setData(ov.data.map(d => ({ time: d.time as Time, value: d.value })) as LineData<Time>[])
    })

    chart.timeScale().fitContent()

    const resizeObserver = new ResizeObserver(() => {
      if (containerRef.current) chart.applyOptions({ width: containerRef.current.clientWidth })
    })
    resizeObserver.observe(containerRef.current)

    return () => { resizeObserver.disconnect(); chart.remove() }
  }, [data, overlays, markers, height])

  return (
    <div className="glass-panel p-1">
      {title && <div className="px-3 py-2 text-xs text-terminal-text-dim font-mono uppercase tracking-wider border-b border-terminal-border">{title}</div>}
      <div ref={containerRef} />
    </div>
  )
}
