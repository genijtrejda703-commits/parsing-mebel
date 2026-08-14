'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import { Slider } from '@/components/ui/slider'
import {
  ResizablePanel, ResizablePanelGroup, ResizableHandle,
} from '@/components/ui/resizable'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import {
  Check, X, Loader2, Search, Crosshair, Maximize2, ZoomIn, ZoomOut, FileText,
  ShieldAlert, Save, ChevronUp, ChevronDown, Sparkles,
} from 'lucide-react'

const money = (v) => v == null ? '—' : new Intl.NumberFormat('ru-RU').format(v)
const statusDot = {
  approved: 'bg-emerald-400', rejected: 'bg-destructive', pending: 'bg-primary/60',
}
const STATUS_TABS = [
  ['all', 'Все'], ['pending', 'Ожидают'], ['approved', 'Одобрены'], ['rejected', 'Отклонены'],
]

const QaWorkbench = ({ seedTerm = '' }) => {
  const [docs, setDocs] = useState([])
  const [docId, setDocId] = useState('all')
  const [models, setModels] = useState([])
  const [model, setModel] = useState('all')
  const [status, setStatus] = useState('all')
  const [minConf, setMinConf] = useState([70])
  const [minVar, setMinVar] = useState(2)
  const [sort, setSort] = useState('best')
  const [term, setTerm] = useState(seedTerm)
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [sel, setSel] = useState(null)
  const [notes, setNotes] = useState('')
  const [draft, setDraft] = useState({})
  const [saving, setSaving] = useState(false)
  const [focus, setFocus] = useState(true)
  const [z, setZ] = useState(2.1)
  const viewRef = useRef(null)

  useEffect(() => { if (seedTerm) { setTerm(seedTerm); setMinConf([0]); setMinVar(0) } }, [seedTerm])

  useEffect(() => {
    fetch('/api/documents').then(r => r.json()).then(d => setDocs(d.items || []))
  }, [])

  useEffect(() => {
    const p = new URLSearchParams()
    if (docId !== 'all') p.set('doc_id', docId)
    fetch(`/api/products/models?${p}`).then(r => r.json()).then(d => setModels(d.items || []))
  }, [docId])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const p = new URLSearchParams({ limit: '150', sort })
      if (docId !== 'all') p.set('doc_id', docId)
      if (model !== 'all') p.set('model', model)
      if (status !== 'all') p.set('status', status)
      if (minConf[0] > 0) p.set('min_conf', String(minConf[0] / 100))
      if (minVar > 0) p.set('min_var', String(minVar))
      if (term) p.set('q', term)
      const d = await (await fetch(`/api/products?${p}`)).json()
      setItems(d.items || [])
      setTotal(d.total || 0)
      setSel(prev => {
        const still = (d.items || []).find(x => x.id === prev?.id)
        return still || (d.items || [])[0] || null
      })
    } finally {
      setLoading(false)
    }
  }, [docId, model, status, minConf, minVar, sort, term])

  useEffect(() => { const t = setTimeout(load, 250); return () => clearTimeout(t) }, [load])

  useEffect(() => {
    setNotes(sel?.reviewer_notes || '')
    setDraft({
      model_name: sel?.model_name || '', category: sel?.category || '',
      dimension: sel?.dimension || '', variant_code: sel?.variant_code || '',
      price_min: sel?.price_min ?? '', price_max: sel?.price_max ?? '',
    })
  }, [sel?.id])

  // центрируем область просмотра на всей восстановленной матрице
  useEffect(() => {
    if (!sel || !focus || !viewRef.current) return
    const el = viewRef.current
    const t = setTimeout(() => {
      const boxes = [
        ...(sel.bbox_cells || []),
        ...(sel.bbox_col_header || []),
        ...(sel.variations || []).map(v => v.bbox_row_label).filter(Boolean),
      ].filter(b => Array.isArray(b) && b.length === 4)
      const r = boxes.length ? [
        Math.min(...boxes.map(b => b[0])), Math.min(...boxes.map(b => b[1])),
        Math.max(...boxes.map(b => b[2])), Math.max(...boxes.map(b => b[3])),
      ] : (sel.bbox || [0, 0, 0, 0])
      el.scrollTo({
        left: Math.max(0, (r[0] + r[2]) / 2 * z - el.clientWidth / 2),
        top: Math.max(0, (r[1] + r[3]) / 2 * z - el.clientHeight / 2),
        behavior: 'smooth',
      })
    }, 120)
    return () => clearTimeout(t)
  }, [sel?.id, z, focus])

  const idx = useMemo(() => items.findIndex(i => i.id === sel?.id), [items, sel?.id])
  const step = (d) => { const n = items[idx + d]; if (n) setSel(n) }

  const patch = async (body, advance = false) => {
    if (!sel) return
    setSaving(true)
    try {
      const r = await fetch(`/api/products/${sel.id}`, {
        method: 'PATCH', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const fresh = await r.json()
      setItems(list => list.map(i => i.id === fresh.id ? fresh : i))
      if (advance && items[idx + 1]) setSel(items[idx + 1])
      else setSel(fresh)
    } finally {
      setSaving(false)
    }
  }

  useEffect(() => {
    const h = (e) => {
      if (['INPUT', 'TEXTAREA'].includes(e.target.tagName)) return
      if (e.key === 'a') patch({ status: 'approved', reviewer_notes: notes }, true)
      if (e.key === 'r') patch({ status: 'rejected', reviewer_notes: notes }, true)
      if (e.key === 'j') step(1)
      if (e.key === 'k') step(-1)
    }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [sel?.id, notes, idx, items])

  const W = sel?.page_width || 652
  const H = sel?.page_height || 842
  const imgSrc = sel ? `/api/page-image?doc_id=${sel.doc_id}&page=${sel.page}&dpi=150` : null

  return (
    <div className="h-[calc(100vh-73px)] flex flex-col">
      {/* ---- фильтры ---- */}
      <div className="border-b border-border px-4 py-2.5 flex items-center gap-2 flex-wrap shrink-0">
        <Select value={docId} onValueChange={setDocId}>
          <SelectTrigger className="h-8 w-[250px] text-xs bg-card/60">
            <SelectValue placeholder="документ" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Все документы</SelectItem>
            {docs.map(d => (
              <SelectItem key={d.id} value={d.id} className="text-xs">
                {d.name} · {d.products ?? 0}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select value={model} onValueChange={setModel}>
          <SelectTrigger className="h-8 w-[180px] text-xs bg-card/60">
            <SelectValue placeholder="модель" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Все модели</SelectItem>
            {models.map(m => (
              <SelectItem key={m.model} value={m.model} className="text-xs">
                {m.model} ({m.n})
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
          <SelectTrigger className="h-8 w-[160px] text-xs bg-card/60">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="best" className="text-xs">Сначала лучшие</SelectItem>
            <SelectItem value="page" className="text-xs">По страницам</SelectItem>
            <SelectItem value="price" className="text-xs">По цене</SelectItem>
          </SelectContent>
        </Select>

        <button onClick={() => setMinVar(v => (v ? 0 : 2))}
          className={`h-8 px-2.5 rounded-md border text-[11px] transition-colors ${minVar ? 'border-primary/50 text-primary bg-primary/10' : 'border-border text-muted-foreground hover:bg-accent/50'}`}>
          только матрицы
        </button>

        <div className="flex items-center gap-2 px-1">
          <span className="text-[10px] tracking-widest text-muted-foreground">ТОЧН ≥</span>
          <Slider value={minConf} onValueChange={setMinConf} max={99} step={1}
            className="w-[80px]" />
          <span className="text-[11px] text-primary tabular-nums w-8">{minConf[0]}%</span>
        </div>

        <div className="relative flex-1 min-w-[150px]">
          <Search className="absolute left-2.5 top-2 h-3.5 w-3.5 text-muted-foreground" />
          <Input value={term} onChange={e => setTerm(e.target.value)}
            placeholder="модель, категория, габариты, артикул…"
            className="h-8 pl-8 text-xs bg-card/60" />
        </div>

        <Badge variant="outline" className="text-[10px] border-border">
          {loading ? <Loader2 className="h-3 w-3 animate-spin" /> : `${items.length} / ${money(total)}`}
        </Badge>
      </div>

      <ResizablePanelGroup direction="horizontal" className="flex-1">
        {/* ---- список позиций ---- */}
        <ResizablePanel defaultSize={23} minSize={16}>
          <div className="hub-scroll h-full overflow-y-auto">
            {!items.length && !loading && (
              <div className="p-6 text-xs text-muted-foreground">
                Пока ничего не извлечено. Сначала запустите загрузку прайсов.
              </div>
            )}
            {items.map(p => (
              <button key={p.id} onClick={() => setSel(p)}
                className={`w-full text-left px-3 py-2.5 border-b border-border/50 hover:bg-accent/40 transition-colors ${sel?.id === p.id ? 'bg-primary/[0.09] border-l-2 border-l-primary' : ''}`}>
                <div className="flex items-center gap-2">
                  <span className={`h-1.5 w-1.5 rounded-full shrink-0 ${statusDot[p.status] || 'bg-muted'}`} />
                  <span className="text-xs truncate flex-1">{p.model_name}</span>
                  {p.anomaly && <ShieldAlert className="h-3 w-3 text-amber-500 shrink-0" />}
                  <span className="text-[10px] text-muted-foreground tabular-nums shrink-0">
                    {(p.confidence * 100).toFixed(0)}%
                  </span>
                </div>
                <div className="mt-1 text-[10px] text-muted-foreground truncate">
                  {[p.category, p.variant_code || p.dimension].filter(Boolean).join(' · ')}
                </div>
                <div className="mt-1 flex items-center justify-between">
                  <span className="text-[11px] text-primary tabular-nums">
                    {money(p.price_min)} – {money(p.price_max)} €
                  </span>
                  <span className="text-[10px] text-muted-foreground">с.{p.page + 1}</span>
                </div>
              </button>
            ))}
          </div>
        </ResizablePanel>

        <ResizableHandle className="bg-border hover:bg-primary/40 transition-colors" />

        {/* ---- исходная страница с геометрической подсветкой ---- */}
        <ResizablePanel defaultSize={44} minSize={25}>
          <div className="h-full flex flex-col">
            <div className="px-3 py-2 border-b border-border flex items-center gap-2 shrink-0">
              <FileText className="h-3.5 w-3.5 text-muted-foreground" />
              <span className="text-[11px] truncate flex-1">
                {sel ? `${sel.doc_name} — страница ${sel.page + 1}` : 'исходная страница'}
              </span>
              <Button size="sm" variant={focus ? 'default' : 'secondary'}
                onClick={() => { setFocus(true); setZ(2.1) }}
                className={`h-7 text-[10px] ${focus ? 'bg-primary text-primary-foreground' : ''}`}>
                <Crosshair className="h-3 w-3 mr-1" /> фокус
              </Button>
              <Button size="sm" variant={!focus ? 'default' : 'secondary'}
                onClick={() => { setFocus(false); setZ(1.05) }}
                className={`h-7 text-[10px] ${!focus ? 'bg-primary text-primary-foreground' : ''}`}>
                <Maximize2 className="h-3 w-3 mr-1" /> вся страница
              </Button>
              <Button size="icon" variant="ghost" className="h-7 w-7"
                onClick={() => setZ(v => Math.max(0.5, v - 0.25))}>
                <ZoomOut className="h-3.5 w-3.5" />
              </Button>
              <Button size="icon" variant="ghost" className="h-7 w-7"
                onClick={() => setZ(v => Math.min(4, v + 0.25))}>
                <ZoomIn className="h-3.5 w-3.5" />
              </Button>
            </div>

            <div ref={viewRef} className="hub-scroll flex-1 overflow-auto bg-[#0b0a09] p-4">
              {!sel ? (
                <div className="h-full grid place-items-center text-xs text-muted-foreground">
                  выберите позицию
                </div>
              ) : (
                <div className="relative mx-auto shadow-2xl"
                  style={{ width: W * z, height: H * z }}>
                  <img src={imgSrc} alt="" draggable={false}
                    style={{ width: '100%', height: '100%' }} className="bg-white" />
                  <svg viewBox={`0 0 ${W} ${H}`} className="absolute inset-0 h-full w-full pointer-events-none">
                    {(sel.bbox_col_header || []).map((b, i) => (
                      <rect key={`h${i}`} x={b[0] - 1.5} y={b[1] - 1} width={b[2] - b[0] + 3}
                        height={b[3] - b[1] + 2} fill="rgba(56,189,248,0.16)"
                        stroke="rgb(56,189,248)" strokeWidth="0.6" strokeDasharray="2 1.4" rx="1" />
                    ))}
                    {(sel.variations || []).map((v, i) => (
                      <g key={`v${i}`}>
                        {v.bbox_row_label && (
                          <rect x={v.bbox_row_label[0] - 1.5} y={v.bbox_row_label[1] - 1}
                            width={v.bbox_row_label[2] - v.bbox_row_label[0] + 3}
                            height={v.bbox_row_label[3] - v.bbox_row_label[1] + 2}
                            fill="rgba(52,211,153,0.13)" stroke="rgb(52,211,153)"
                            strokeWidth="0.5" strokeDasharray="2 1.4" rx="1" />
                        )}
                        <rect x={v.bbox[0] - 2} y={v.bbox[1] - 1.5}
                          width={v.bbox[2] - v.bbox[0] + 4} height={v.bbox[3] - v.bbox[1] + 3}
                          fill="rgba(212,168,88,0.22)" stroke="rgb(212,168,88)"
                          strokeWidth="0.8" rx="1" />
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
                <span className="h-2 w-2 rounded-sm" style={{ background: 'rgb(56,189,248)' }} /> заголовок столбца (сверху, x0 ±10px)
              </span>
              <span className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-sm" style={{ background: 'rgb(52,211,153)' }} /> подпись строки (слева, y0 ±10px)
              </span>
            </div>
          </div>
        </ResizablePanel>

        <ResizableHandle className="bg-border hover:bg-primary/40 transition-colors" />

        {/* ---- распознанная позиция / проверка ---- */}
        <ResizablePanel defaultSize={33} minSize={22}>
          <div className="hub-scroll h-full overflow-y-auto">
            {!sel ? (
              <div className="p-6 text-xs text-muted-foreground">ничего не выбрано</div>
            ) : (
              <div className="p-4 space-y-4">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <div className="text-[10px] tracking-widest text-muted-foreground">
                      РАСПОЗНАННАЯ ПОЗИЦИЯ
                    </div>
                    <h2 className="font-serif text-2xl mt-0.5">{sel.model_name}</h2>
                    <div className="text-xs text-muted-foreground">{sel.collection}</div>
                  </div>
                  <div className="flex flex-col items-end gap-1">
                    <Badge variant="outline"
                      className={`text-[10px] ${sel.confidence > 0.8 ? 'border-emerald-500/50 text-emerald-400' : 'border-amber-500/50 text-amber-400'}`}>
                      точность {(sel.confidence * 100).toFixed(1)}%
                    </Badge>
                    <div className="flex gap-1">
                      <Button size="icon" variant="ghost" className="h-6 w-6" onClick={() => step(-1)}>
                        <ChevronUp className="h-3.5 w-3.5" />
                      </Button>
                      <Button size="icon" variant="ghost" className="h-6 w-6" onClick={() => step(1)}>
                        <ChevronDown className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </div>
                </div>

                <Card className="p-4 bg-primary/[0.06] border-primary/25">
                  <div className="text-[10px] tracking-widest text-muted-foreground">
                    ДИАПАЗОН ЦЕН · ВАРИАНТОВ: {sel.n_variations}
                  </div>
                  <div className="mt-1 flex items-baseline gap-2">
                    <span className="font-serif text-3xl text-primary tabular-nums">
                      {money(sel.price_min)}
                    </span>
                    <span className="text-muted-foreground">–</span>
                    <span className="font-serif text-3xl text-primary tabular-nums">
                      {money(sel.price_max)} €
                    </span>
                  </div>
                  <div className="mt-3 h-1 rounded-full bg-primary/20 overflow-hidden">
                    <div className="h-full bg-primary" style={{
                      width: `${sel.price_max ? Math.max(6, (1 - sel.price_min / sel.price_max) * 100) : 0}%`,
                    }} />
                  </div>
                </Card>

                <div className="grid grid-cols-2 gap-3">
                  {[['model_name', 'МОДЕЛЬ'], ['category', 'КАТЕГОРИЯ'],
                    ['dimension', 'ГАБАРИТЫ'], ['variant_code', 'АРТИКУЛ']].map(([k, l]) => (
                    <div key={k}>
                      <Label className="text-[10px] tracking-widest text-muted-foreground">{l}</Label>
                      <Input value={draft[k] ?? ''} onChange={e => setDraft(d => ({ ...d, [k]: e.target.value }))}
                        className="mt-1 h-8 text-xs bg-background/60" />
                    </div>
                  ))}
                  <div>
                    <Label className="text-[10px] tracking-widest text-muted-foreground">ЦЕНА ОТ</Label>
                    <Input type="number" value={draft.price_min ?? ''}
                      onChange={e => setDraft(d => ({ ...d, price_min: e.target.value }))}
                      className="mt-1 h-8 text-xs bg-background/60" />
                  </div>
                  <div>
                    <Label className="text-[10px] tracking-widest text-muted-foreground">ЦЕНА ДО</Label>
                    <Input type="number" value={draft.price_max ?? ''}
                      onChange={e => setDraft(d => ({ ...d, price_max: e.target.value }))}
                      className="mt-1 h-8 text-xs bg-background/60" />
                  </div>
                </div>

                <div>
                  <div className="text-[10px] tracking-widest text-muted-foreground mb-1.5">
                    МАТРИЦА ЦЕН (отделка × цена)
                  </div>
                  <div className="rounded-md border border-border overflow-hidden">
                    {(sel.variations || []).map((v, i) => (
                      <div key={i}
                        className="flex items-center gap-2 px-3 py-1.5 text-xs border-b border-border/50 last:border-0 hover:bg-accent/30">
                        <span className="flex-1 truncate text-muted-foreground">{v.finish || '—'}</span>
                        <span className="tabular-nums">{money(v.price)} €</span>
                        <span className="text-[10px] text-emerald-400/80 tabular-nums w-9 text-right">
                          {(v.confidence * 100).toFixed(0)}%
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                {!!(sel.col_header_raw || []).length && (
                  <div>
                    <div className="text-[10px] tracking-widest text-muted-foreground mb-1.5">
                      ЦЕПОЧКА ЗАГОЛОВКОВ (над столбцом)
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {sel.col_header_raw.map((t, i) => (
                        <Badge key={i} variant="outline" className="text-[10px] border-sky-500/40 text-sky-300">
                          {t}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}

                <div>
                  <Label className="text-[10px] tracking-widest text-muted-foreground">
                    ЗАМЕТКИ ПРОВЕРЯЮЩЕГО
                  </Label>
                  <Textarea value={notes} onChange={e => setNotes(e.target.value)}
                    placeholder="Что распознано неверно: пропущенные отделки, не тот столбец…"
                    className="mt-1.5 min-h-[80px] text-xs bg-background/60" />
                </div>

                <div className="flex items-center gap-2">
                  <Button onClick={() => patch({ status: 'approved', reviewer_notes: notes, ...numeric(draft) }, true)}
                    disabled={saving}
                    className="flex-1 bg-emerald-600 hover:bg-emerald-600/90 text-white">
                    {saving ? <Loader2 className="h-4 w-4 animate-spin" /> :
                      <><Check className="h-4 w-4 mr-1.5" /> Одобрить</>}
                  </Button>
                  <Button onClick={() => patch({ status: 'rejected', reviewer_notes: notes }, true)}
                    disabled={saving} variant="destructive" className="flex-1">
                    <X className="h-4 w-4 mr-1.5" /> Отклонить
                  </Button>
                  <Button onClick={() => patch({ reviewer_notes: notes, ...numeric(draft) })}
                    disabled={saving} variant="secondary" size="icon" title="сохранить правки">
                    <Save className="h-4 w-4" />
                  </Button>
                </div>

                <div className="text-[10px] text-muted-foreground leading-relaxed border-t border-border pt-3">
                  <span className="text-primary">горячие клавиши</span> · A одобрить · R отклонить · J/K навигация
                  <br />
                  <span className="flex items-center gap-1 mt-1">
                    <Sparkles className="h-3 w-3 text-primary" />
                    оценка micrograd {(sel.confidence * 100).toFixed(2)}% · соседей в строке{' '}
                    {sel.variations?.[0]?.row_peers} · в столбце {sel.variations?.[0]?.col_peers}
                  </span>
                  <div className="mt-1 font-mono">
                    bbox [{(sel.bbox || []).join(', ')}] · стр. {sel.page + 1}
                  </div>
                </div>
              </div>
            )}
          </div>
        </ResizablePanel>
      </ResizablePanelGroup>
    </div>
  )
}

function numeric(d) {
  const out = { ...d }
  if (out.price_min !== '' && out.price_min != null) out.price_min = parseFloat(out.price_min)
  if (out.price_max !== '' && out.price_max != null) out.price_max = parseFloat(out.price_max)
  return out
}

export default QaWorkbench
