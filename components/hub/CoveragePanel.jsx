'use client'

import { useEffect, useState } from 'react'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { FileSpreadsheet, Loader2 } from 'lucide-react'

const num = (v) => new Intl.NumberFormat('ru-RU').format(v || 0)
const pct = (a, b) => (b > 0 ? Math.round((a / b) * 100) : 0)

const Bar = ({ value, max, color }) => (
  <div className="h-1.5 rounded-full bg-muted/40 overflow-hidden w-full">
    <div className={`h-full ${color}`} style={{ width: `${pct(value, max)}%` }} />
  </div>
)

const CoveragePanel = () => {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    fetch('/api/coverage').then(r => r.json()).then(d => { setData(d); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  if (loading) {
    return <div className="h-[calc(100vh-73px)] grid place-items-center text-muted-foreground">
      <Loader2 className="h-5 w-5 animate-spin" />
    </div>
  }

  const t = data?.totals || {}
  const docs = data?.documents || []

  return (
    <div className="h-[calc(100vh-73px)] flex flex-col">
      <div className="px-4 py-3 flex items-center justify-between shrink-0 border-b border-border">
        <div className="text-[11px] text-muted-foreground">
          Разобрано документов: <span className="text-foreground">{data?.files_parsed}</span> ·
          {' '}классифицировано без разбора: <span className="text-amber-400">{data?.files_classified_only}</span> ·
          {' '}в инвентаре: <span className="text-foreground">{data?.files_inventoried}</span>
        </div>
        <Button size="sm" variant="secondary" className="h-8 text-[11px]"
          onClick={() => window.open('/api/inventory/export', '_blank')}>
          <FileSpreadsheet className="h-3.5 w-3.5 mr-1.5" /> Экспорт покрытия
        </Button>
      </div>

      <div className="px-4 py-3 grid grid-cols-2 md:grid-cols-6 gap-3 shrink-0">
        {[
          ['Страниц всего', t.pages_total],
          ['С матрицами', t.pages_with_matrix],
          ['Разобрано страниц', t.pages_parsed],
          ['Пропущено', t.pages_skipped],
          ['Позиций', t.positions],
          ['Вариантов-цен', t.variant_prices],
        ].map(([l, v]) => (
          <Card key={l} className="p-3 bg-card/50">
            <div className="text-[10px] tracking-widest text-muted-foreground">{l.toUpperCase()}</div>
            <div className="mt-1 font-serif text-2xl tabular-nums">{num(v)}</div>
          </Card>
        ))}
      </div>

      <div className="px-4 pb-2 shrink-0">
        <Card className="p-3 bg-primary/[0.05] border-primary/20">
          <div className="flex items-center justify-between text-[11px]">
            <span className="text-muted-foreground">Покрытие по фабрике (страниц с матрицами → разобрано)</span>
            <span className="tabular-nums text-primary">
              {pct(t.pages_parsed, t.pages_with_matrix)}% · {num(t.pages_parsed)} / {num(t.pages_with_matrix)}
            </span>
          </div>
          <div className="mt-2"><Bar value={t.pages_parsed} max={t.pages_with_matrix} color="bg-primary" /></div>
        </Card>
      </div>

      <div className="hub-scroll flex-1 overflow-auto px-4 pb-4">
        <table className="w-full text-xs border-collapse">
          <thead className="sticky top-0 bg-background">
            <tr className="text-[10px] tracking-widest text-muted-foreground border-b border-border">
              {['ДОКУМЕНТ', 'СТР.', 'С МАТРИЦАМИ', 'РАЗОБРАНО', 'ПРОПУЩЕНО', 'ПОКРЫТИЕ', 'ПОЗИЦИЙ', 'ВАР-ЦЕН'].map(h => (
                <th key={h} className="text-left font-normal py-2 px-2">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {docs.map(d => {
              const c = d.coverage || {}
              const wm = c.pages_with_matrix || 0
              const pp = c.pages_parsed || 0
              return (
                <tr key={d.id} className="border-b border-border/40 hover:bg-accent/30">
                  <td className="py-1.5 px-2 max-w-[340px] truncate">{d.name}</td>
                  <td className="px-2 tabular-nums text-muted-foreground">{num(c.pages_total || d.pages)}</td>
                  <td className="px-2 tabular-nums">{num(wm)}</td>
                  <td className="px-2 tabular-nums text-emerald-400">{num(pp)}</td>
                  <td className="px-2 tabular-nums text-amber-400/80">{num(c.pages_skipped)}</td>
                  <td className="px-2 w-[140px]">
                    <div className="flex items-center gap-2">
                      <Bar value={pp} max={wm} color={pct(pp, wm) >= 60 ? 'bg-emerald-400' : 'bg-amber-400'} />
                      <span className="tabular-nums text-[10px] w-8 text-right">{pct(pp, wm)}%</span>
                    </div>
                  </td>
                  <td className="px-2 tabular-nums">{num(d.positions)}</td>
                  <td className="px-2 tabular-nums text-primary">{num(d.variant_prices)}</td>
                </tr>
              )
            })}
          </tbody>
        </table>

        {!!(data?.classified_only || []).length && (
          <div className="mt-4">
            <div className="text-[10px] tracking-widest text-muted-foreground mb-2">
              КЛАССИФИЦИРОВАНО БЕЗ РАЗБОРА ({data.files_classified_only})
            </div>
            <div className="flex flex-wrap gap-1.5">
              {data.classified_only.map((f, i) => (
                <Badge key={i} variant="outline" className="text-[10px] border-border text-muted-foreground">
                  {f.name} · {f.doc_type}
                </Badge>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default CoveragePanel
