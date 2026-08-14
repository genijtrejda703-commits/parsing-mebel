'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import {
  ResizablePanel, ResizablePanelGroup, ResizableHandle,
} from '@/components/ui/resizable'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import {
  Check, X, Loader2, Search, Crosshair, Maximize2, ZoomIn, ZoomOut, FileText,
  ShieldAlert, Save, Layers, FileSpreadsheet, AlertTriangle,
} from 'lucide-react'

const money = (v) => v == null ? '—' : new Intl.NumberFormat('ru-RU').format(v)
const statusDot = {
  approved: 'bg-emerald-400', rejected: 'bg-destructive', pending: 'bg-primary/60',
}
const STATUS_TABS = [
  ['all', 'Все'], ['pending', 'Ожидают'], ['approved', 'Одобрены'], ['rejected', 'Отклонены'],
]

const PositionWorkbench = ({ seedTerm = '' }) => {
  const [cats, setCats] = useState([])
  const [category, setCategory] = useState('all')
  const [status, setStatus] = useState('all')
  const [flaggedOnly, setFlaggedOnly] = useState(false)
  const [minVar, setMinVar] = useState(0)
  const [sort, setSort] = useState('best')
  const [term, setTerm] = useState(seedTerm)
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)

  const [selId, setSelId] = useState(null)
  const [detail, setDetail] = useState(null)      // {position, variants, pages, documents}
  const [pageIdx, setPageIdx] = useState(0)
  const [notes, setNotes] = useState('')
  const [saving, setSaving] = useState(false)
  const [focus, setFocus] = useState(false)
  const [z, setZ] = useState(1.15)
  const viewRef = useRef(null)

  useEffect(() => { if (seedTerm) setTerm(seedTerm) }, [seedTerm])

  useEffect(() => {
    fetch('/api/positions/facets').then(r => r.json())
      .then(d => setCats(d.categories || [])).catch(() => {})
  }, [])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const p = new URLSearchParams({ limit: '200', sort })
      if (status !== 'all') p.set('status', status)
      if (flaggedOnly) p.set('flagged', 'true')
      if (category !== 'all') p.set('category', category)
      if (minVar > 0) p.set('min_variants', String(minVar))
      if (term) p.set('q', term)
      const d = await (await fetch(`/api/positions?${p}`)).json()
      setItems(d.items || [])
      setTotal(d.total || 0)
      setSelId(prev => (d.items || []).some(x => x.id === prev) ? prev : (d.items || [])[0]?.id || null)
    } finally {
      setLoading(false)
    }
  }, [status, flaggedOnly, category, minVar, sort, term])

  useEffect(() => { const t = setTimeout(load, 250); return () => clearTimeout(t) }, [load])

  useEffect(() => {
    if (!selId) { setDetail(null); return }
    let alive = true
    fetch(`/api/positions/${selId}`).then(r => r.json()).then(d => {
      if (!alive) return
      setDetail(d)
      setNotes(d.position?.reviewer_notes || '')
      setPageIdx(0)
    })
    return () => { alive = false }
  }, [selId])

  const pos = detail?.position
  const pages = detail?.pages || []
  const pg = pages[pageIdx] || null
  const W = pg?.page_width || 652
  const H = pg?.page_height || 842
  const imgSrc = pg ? `/api/page-image?doc_id=${pg.doc_id}&page=${pg.page}&dpi=150` : null

  useEffect(() => {
    if (!pg || !focus || !viewRef.current) return
    const el = viewRef.current
    const t = setTimeout(() => {
      const boxes = pg.variants.flatMap(v => [v.bbox, v.bbox_row_label].filter(Boolean))
        .filter(b => Array.isArray(b) && b.length === 4)
      if (!boxes.length) return
      const r = [
        Math.min(...boxes.map(b => b[0])), Math.min(...boxes.map(b => b[1])),
        Math.max(...boxes.map(b => b[2])), Math.max(...boxes.map(b => b[3])),
      ]
      el.scrollTo({
        left: Math.max(0, (r[0] + r[2]) / 2 * z - el.clientWidth / 2),
        top: Math.max(0, (r[1] + r[3]) / 2 * z - el.clientHeight / 2),
        behavior: 'smooth',
      })
    }, 120)
    return () => clearTimeout(t)
  }, [pageIdx, selId, z, focus])

  const patch = async (body) => {
    if (!pos) return
    setSaving(true)
    try {
      const r = await fetch(`/api/positions/${pos.id}`, {
        method: 'PATCH', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const fresh = await r.json()
      setItems(list => list.map(i => i.id === fresh.id ? { ...i, ...fresh } : i))
      setDetail(d => d ? { ...d, position: { ...d.position, ...fresh } } : d)
    } finally {
      setSaving(false)
    }
  }

  const colHeaders = useMemo(() => {
    if (!pg) return []
    const seen = new Set(); const out = []
    for (const v of pg.variants) {
      const b = v.bbox_col_header
      if (Array.isArray(b)) for (const box of b) {
        const k = (box || []).join(',')
        if (!seen.has(k)) { seen.add(k); out.push(box) }
      }
    }
    return out
  }, [pg])

  return (
    <div className="h-[calc(100vh-73px)] flex flex-col">
      {/* ---- фильтры ---- */}
      <div className="border-b border-border px-4 py-2.5 flex items-center gap-2 flex-wrap shrink-0">
        <Select value={category} onValueChange={setCategory}>
          <SelectTrigger className="h-8 w-[220px] text-xs bg-card/60">
            <SelectValue placeholder="категория" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Все категории</SelectItem>
            {cats.map(c => (
              <SelectItem key={c.category} value={c.category} className="text-xs">
                {c.category} ({c.n})
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <div className="flex rounded-md border border-border overflow-hidden">
          {STATUS_TABS.map(([s, l]) => (
            <button key={s} onClick={() => setStatus(s)}
              className={`px-2.5 h-8 text-[11px] transition-colors ${status === s ? 'bg-primary text-primary-foreground' : 'hover:bg-accent/50 text-muted-foreground'}`}>
              {l}
            </button>
          ))}
        </div>

        <Select value={sort} onValueChange={setSort}>
          <SelectTrigger className="h-8 w-[170px] text-xs bg-card/60">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="best" className="text-xs">Сначала лучшие</SelectItem>
            <SelectItem value="variants" className="text-xs">Больше вариантов</SelectItem>
            <SelectItem value="name" className="text-xs">По имени</SelectItem>
            <SelectItem value="price" className="text-xs">По цене</SelectItem>
          </SelectContent>
        </Select>

        <button onClick={() => setFlaggedOnly(v => !v)}
          className={`h-8 px-2.5 rounded-md border text-[11px] transition-colors ${flaggedOnly ? 'border-amber-500/60 text-amber-400 bg-amber-500/10' : 'border-border text-muted-foreground hover:bg-accent/50'}`}>
          <AlertTriangle className="h-3 w-3 inline mr-1" /> помеченные
        </button>
        <button onClick={() => setMinVar(v => (v ? 0 : 3))}
          className={`h-8 px-2.5 rounded-md border text-[11px] transition-colors ${minVar ? 'border-primary/50 text-primary bg-primary/10' : 'border-border text-muted-foreground hover:bg-accent/50'}`}>
          ≥3 вариантов
        </button>

        <div className="relative flex-1 min-w-[150px]">
          <Search className="absolute left-2.5 top-2 h-3.5 w-3.5 text-muted-foreground" />
          <Input value={term} onChange={e => setTerm(e.target.value)}
            placeholder="модель, категория…"
            className="h-8 pl-8 text-xs bg-card/60" />
        </div>

        <Badge variant="outline" className="text-[10px] border-border">
          {loading ? <Loader2 className="h-3 w-3 animate-spin" /> : `${items.length} / ${money(total)}`}
        </Badge>

        <Button size="sm" variant="secondary" className="h-8 text-[11px]"
          onClick={() => window.open('/api/export-positions?status=all', '_blank')}
          title="Выгрузить позиции в Excel (Позиции / Цены / Сводка)">
          <FileSpreadsheet className="h-3.5 w-3.5 mr-1.5" /> Экспорт .xlsx
        </Button>
      </div>

      <ResizablePanelGroup direction="horizontal" className="flex-1">
        {/* ---- список позиций ---- */}
        <ResizablePanel defaultSize={24} minSize={16}>
          <div className="hub-scroll h-full overflow-y-auto">
            {!items.length && !loading && (
              <div className="p-6 text-xs text-muted-foreground">
                Пока ничего не извлечено. Запустите загрузку прайсов.
              </div>
            )}
            {items.map(p => (
              <button key={p.id} onClick={() => setSelId(p.id)}
                className={`w-full text-left px-3 py-2.5 border-b border-border/50 hover:bg-accent/40 transition-colors ${selId === p.id ? 'bg-primary/[0.09] border-l-2 border-l-primary' : ''}`}>
                <div className="flex items-center gap-2">
                  <span className={`h-1.5 w-1.5 rounded-full shrink-0 ${statusDot[p.status] || 'bg-muted'}`} />
                  <span className="text-xs truncate flex-1">{p.name || '— без имени —'}</span>
                  {p.flagged && <ShieldAlert className="h-3 w-3 text-amber-500 shrink-0" />}
                  <span className="text-[10px] text-muted-foreground tabular-nums shrink-0">
                    {((p.avg_confidence || 0) * 100).toFixed(0)}%
                  </span>
                </div>
                <div className="mt-1 text-[10px] text-muted-foreground truncate">
                  {(p.categories || []).slice(0, 2).join(' · ')}
                </div>
                <div className="mt-1 flex items-center justify-between">
                  <span className="text-[11px] text-primary tabular-nums">
                    {money(p.price_min)} – {money(p.price_max)} €
                  </span>
                  <span className="text-[10px] text-muted-foreground flex items-center gap-1">
                    <Layers className="h-3 w-3" /> {p.n_variants}
                  </span>
                </div>
              </button>
            ))}
          </div>
        </ResizablePanel>

        <ResizableHandle className="bg-border hover:bg-primary/40 transition-colors" />

        {/* ---- исходная страница ---- */}
        <ResizablePanel defaultSize={43} minSize={25}>
          <div className="h-full flex flex-col">
            <div className="px-3 py-2 border-b border-border flex items-center gap-2 shrink-0 flex-wrap">
              <FileText className="h-3.5 w-3.5 text-muted-foreground" />
              <span className="text-[11px] truncate flex-1">
                {pg ? `${pg.doc_name} — страница ${pg.page + 1}` : 'исходная страница'}
              </span>
              {pages.length > 1 && (
                <Select value={String(pageIdx)} onValueChange={v => setPageIdx(parseInt(v))}>
                  <SelectTrigger className="h-7 w-[190px] text-[10px] bg-card/60">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {pages.map((pp, i) => (
                      <SelectItem key={i} value={String(i)} className="text-[10px]">
                        с.{pp.page + 1} · {pp.variants.length} цен · {pp.doc_name?.slice(0, 22)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
              <Button size="sm" variant={focus ? 'default' : 'secondary'}
                onClick={() => { setFocus(true); setZ(2.0) }}
                className={`h-7 text-[10px] ${focus ? 'bg-primary text-primary-foreground' : ''}`}>
                <Crosshair className="h-3 w-3 mr-1" /> фокус
              </Button>
              <Button size="sm" variant={!focus ? 'default' : 'secondary'}
                onClick={() => { setFocus(false); setZ(1.1) }}
                className={`h-7 text-[10px] ${!focus ? 'bg-primary text-primary-foreground' : ''}`}>
                <Maximize2 className="h-3 w-3 mr-1" /> вся страница
              </Button>
              <Button size="icon" variant="ghost" className="h-7 w-7"
                onClick={() => setZ(v => Math.max(0.5, v - 0.2))}>
                <ZoomOut className="h-3.5 w-3.5" />
              </Button>
              <Button size="icon" variant="ghost" className="h-7 w-7"
                onClick={() => setZ(v => Math.min(4, v + 0.2))}>
                <ZoomIn className="h-3.5 w-3.5" />
              </Button>
            </div>

            <div ref={viewRef} className="hub-scroll flex-1 overflow-auto bg-[#0b0a09] p-4">
              {!pg ? (
                <div className="h-full grid place-items-center text-xs text-muted-foreground">
                  выберите позицию
                </div>
              ) : (
                <div className="relative mx-auto shadow-2xl"
                  style={{ width: W * z, height: H * z }}>
                  <img src={imgSrc} alt="" draggable={false}
                    style={{ width: '100%', height: '100%' }} className="bg-white" />
                  <svg viewBox={`0 0 ${W} ${H}`} className="absolute inset-0 h-full w-full pointer-events-none">
                    {colHeaders.map((b, i) => (
                      <rect key={`h${i}`} x={b[0] - 1.5} y={b[1] - 1} width={b[2] - b[0] + 3}
                        height={b[3] - b[1] + 2} fill="rgba(56,189,248,0.16)"
                        stroke="rgb(56,189,248)" strokeWidth="0.6" strokeDasharray="2 1.4" rx="1" />
                    ))}
                    {pg.variants.map((v, i) => (
                      <g key={`v${i}`}>
                        {v.bbox_row_label && (
                          <rect x={v.bbox_row_label[0] - 1.5} y={v.bbox_row_label[1] - 1}
                            width={v.bbox_row_label[2] - v.bbox_row_label[0] + 3}
                            height={v.bbox_row_label[3] - v.bbox_row_label[1] + 2}
                            fill="rgba(52,211,153,0.13)" stroke="rgb(52,211,153)"
                            strokeWidth="0.5" strokeDasharray="2 1.4" rx="1" />
                        )}
                        {Array.isArray(v.bbox) && (
                          <rect x={v.bbox[0] - 2} y={v.bbox[1] - 1.5}
                            width={v.bbox[2] - v.bbox[0] + 4} height={v.bbox[3] - v.bbox[1] + 3}
                            fill="rgba(212,168,88,0.22)" stroke="rgb(212,168,88)"
                            strokeWidth="0.8" rx="1" />
                        )}
                      </g>
                    ))}
                  </svg>
                </div>
              )}
            </div>

            <div className="px-3 py-1.5 border-t border-border flex items-center gap-4 shrink-0 text-[10px] text-muted-foreground flex-wrap">
              <span className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-sm" style={{ background: 'rgb(212,168,88)' }} /> ячейка цены
              </span>
              <span className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-sm" style={{ background: 'rgb(56,189,248)' }} /> заголовок столбца (габариты/артикул)
              </span>
              <span className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-sm" style={{ background: 'rgb(52,211,153)' }} /> подпись строки (отделка)
              </span>
            </div>
          </div>
        </ResizablePanel>

        <ResizableHandle className="bg-border hover:bg-primary/40 transition-colors" />

        {/* ---- позиция / варианты / проверка ---- */}
        <ResizablePanel defaultSize={33} minSize={22}>
          <div className="hub-scroll h-full overflow-y-auto">
            {!pos ? (
              <div className="p-6 text-xs text-muted-foreground">ничего не выбрано</div>
            ) : (
              <div className="p-4 space-y-4">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="text-[10px] tracking-widest text-muted-foreground">ПОЗИЦИЯ</div>
                    <h2 className="font-serif text-2xl mt-0.5 break-words">{pos.name || '— без имени —'}</h2>
                    <div className="text-xs text-muted-foreground">
                      {(pos.categories || []).join(' · ')}
                    </div>
                  </div>
                  <Badge variant="outline"
                    className={`text-[10px] shrink-0 ${(pos.avg_confidence || 0) > 0.8 ? 'border-emerald-500/50 text-emerald-400' : 'border-amber-500/50 text-amber-400'}`}>
                    точность {((pos.avg_confidence || 0) * 100).toFixed(1)}%
                  </Badge>
                </div>

                <Card className="p-4 bg-primary/[0.06] border-primary/25">
                  <div className="text-[10px] tracking-widest text-muted-foreground">
                    ДИАПАЗОН ЦЕН · ВАРИАНТОВ-ЦЕН: {pos.n_variants} · ДОКУМЕНТОВ: {pos.n_docs}
                  </div>
                  <div className="mt-1 flex items-baseline gap-2">
                    <span className="font-serif text-3xl text-primary tabular-nums">{money(pos.price_min)}</span>
                    <span className="text-muted-foreground">–</span>
                    <span className="font-serif text-3xl text-primary tabular-nums">{money(pos.price_max)} €</span>
                  </div>
                </Card>

                <div>
                  <div className="text-[10px] tracking-widest text-muted-foreground mb-1.5">
                    ВАРИАНТЫ (артикул · габариты · отделка → цена)
                  </div>
                  <div className="rounded-md border border-border overflow-hidden max-h-[340px] overflow-y-auto hub-scroll">
                    {(detail?.variants || []).map((v, i) => (
                      <button key={i}
                        onClick={() => {
                          const idx = pages.findIndex(pp => pp.doc_id === v.doc_id && pp.page === v.page)
                          if (idx >= 0) setPageIdx(idx)
                        }}
                        className="w-full flex items-center gap-2 px-3 py-1.5 text-xs border-b border-border/50 last:border-0 hover:bg-accent/40 text-left">
                        <span className="text-[10px] text-sky-300 tabular-nums w-16 truncate shrink-0">
                          {v.variant_code || '—'}
                        </span>
                        <span className="flex-1 truncate text-muted-foreground">{v.finish || v.dimension || '—'}</span>
                        <span className="tabular-nums">{money(v.price)} €</span>
                        <span className="text-[9px] text-muted-foreground w-8 text-right">с.{v.page + 1}</span>
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <Label className="text-[10px] tracking-widest text-muted-foreground">
                    ЗАМЕТКИ ПРОВЕРЯЮЩЕГО
                  </Label>
                  <Textarea value={notes} onChange={e => setNotes(e.target.value)}
                    placeholder="Что распознано неверно…"
                    className="mt-1.5 min-h-[70px] text-xs bg-background/60" />
                </div>

                <div className="flex items-center gap-2">
                  <Button onClick={() => patch({ status: 'approved', reviewer_notes: notes, cascade_status: true })}
                    disabled={saving}
                    className="flex-1 bg-emerald-600 hover:bg-emerald-600/90 text-white">
                    {saving ? <Loader2 className="h-4 w-4 animate-spin" /> :
                      <><Check className="h-4 w-4 mr-1.5" /> Одобрить</>}
                  </Button>
                  <Button onClick={() => patch({ status: 'rejected', reviewer_notes: notes, cascade_status: true })}
                    disabled={saving} variant="destructive" className="flex-1">
                    <X className="h-4 w-4 mr-1.5" /> Отклонить
                  </Button>
                  <Button onClick={() => patch({ reviewer_notes: notes })}
                    disabled={saving} variant="secondary" size="icon" title="сохранить заметки">
                    <Save className="h-4 w-4" />
                  </Button>
                </div>

                {!!(pos.name_variants || []).length && pos.name_variants.length > 1 && (
                  <div className="text-[10px] text-amber-400/90 border-t border-border pt-2">
                    <AlertTriangle className="h-3 w-3 inline mr-1" />
                    печатных вариантов имени: {pos.name_variants.length} — проверьте на «Не сошлось»
                  </div>
                )}
              </div>
            )}
          </div>
        </ResizablePanel>
      </ResizablePanelGroup>
    </div>
  )
}

export default PositionWorkbench
