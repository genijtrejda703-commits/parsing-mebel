'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import {
  ResizablePanel, ResizablePanelGroup, ResizableHandle,
} from '@/components/ui/resizable'
import { Loader2, RefreshCw, FileText, ClipboardCheck, AlertTriangle } from 'lucide-react'

const VERDICTS = [
  ['ok', 'Верно', 'bg-emerald-600 hover:bg-emerald-600/90'],
  ['wrong_price', 'Неверная цена', 'bg-destructive hover:bg-destructive/90'],
  ['wrong_row', 'Неверная подпись строки', 'bg-amber-600 hover:bg-amber-600/90'],
  ['wrong_col', 'Неверный заголовок столбца', 'bg-amber-600 hover:bg-amber-600/90'],
  ['missed', 'Пропущенная ячейка', 'bg-sky-700 hover:bg-sky-700/90'],
  ['false_cell', 'Ложная ячейка', 'bg-fuchsia-700 hover:bg-fuchsia-700/90'],
]
const VERD_RU = Object.fromEntries(VERDICTS.map(([k, l]) => [k, l]))
const dot = (v) => v === 'ok' ? 'bg-emerald-400' : v ? 'bg-destructive' : 'bg-muted'
const num = (v) => new Intl.NumberFormat('ru-RU').format(v || 0)

const AcceptancePanel = () => {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [sampling, setSampling] = useState(false)
  const [selId, setSelId] = useState(null)
  const [note, setNote] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const d = await (await fetch('/api/acceptance')).json()
      setData(d)
      setSelId(prev => (d.cells || []).some(c => c.id === prev) ? prev : (d.cells || [])[0]?.id || null)
    } finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  const makeSample = async () => {
    setSampling(true)
    try {
      await fetch('/api/acceptance/sample', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ per_doc: 2, cells_per_page: 14 }),
      })
      await load()
    } finally { setSampling(false) }
  }

  const cells = data?.cells || []
  const st = data?.stats || { total: 0, checked: 0, errors: 0, error_rate: 0, by_verdict: {}, per_doc: {} }
  const cur = useMemo(() => cells.find(c => c.id === selId) || null, [cells, selId])
  useEffect(() => { setNote(cur?.note || '') }, [selId]) // eslint-disable-line

  const pg = useMemo(() => (data?.pages || []).find(p => p.doc_id === cur?.doc_id && p.page === cur?.page) || null, [data, cur])
  const W = cur?.page_width || 652, H = cur?.page_height || 842
  const imgSrc = cur ? `/api/page-image?doc_id=${cur.doc_id}&page=${cur.page}&dpi=150` : null

  const setVerdict = async (verdict) => {
    if (!cur) return
    setData(d => ({ ...d, cells: d.cells.map(c => c.id === cur.id ? { ...c, verdict, note } : c) }))
    await fetch(`/api/acceptance/${cur.id}`, {
      method: 'PATCH', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ verdict, note }),
    })
    // jump to next unchecked
    const idx = cells.findIndex(c => c.id === cur.id)
    const next = cells.slice(idx + 1).find(c => !c.verdict) || cells[idx + 1]
    if (next) setSelId(next.id)
    load()
  }

  return (
    <div className="h-[calc(100vh-73px)] flex flex-col">
      <div className="border-b border-border px-4 py-2.5 flex items-center gap-3 flex-wrap shrink-0">
        <Button size="sm" className="h-8 text-[11px] bg-primary text-primary-foreground"
          disabled={sampling} onClick={makeSample}
          title="Стратифицированная случайная выборка страниц-матриц по всем документам (кухни и гардеробы включены)">
          {sampling ? <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5 mr-1.5" />}
          Сформировать выборку
        </Button>
        <Badge variant="outline" className="text-[10px] border-border">
          проверено {num(st.checked)} / {num(st.total)}
        </Badge>
        <Badge variant="outline" className="text-[10px] border-destructive/50 text-destructive">
          ошибок {num(st.errors)} · доля {(st.error_rate * 100).toFixed(1)}%
        </Badge>
        {Object.entries(st.by_verdict).map(([k, v]) => (
          <span key={k} className="text-[10px] text-muted-foreground">{VERD_RU[k] || k}: {v}</span>
        ))}
      </div>

      <ResizablePanelGroup direction="horizontal" className="flex-1">
        {/* список ячеек выборки */}
        <ResizablePanel defaultSize={26} minSize={18}>
          <div className="hub-scroll h-full overflow-y-auto">
            {loading && <div className="p-6"><Loader2 className="h-5 w-5 animate-spin text-muted-foreground" /></div>}
            {!loading && !cells.length && (
              <div className="p-6 text-xs text-muted-foreground">
                Выборка пуста. Нажмите «Сформировать выборку» — система случайно наберёт страницы-матрицы из всех документов (включая кухни Dada и гардеробы Gliss Master).
              </div>
            )}
            {cells.map(c => (
              <button key={c.id} onClick={() => setSelId(c.id)}
                className={`w-full text-left px-3 py-2 border-b border-border/50 hover:bg-accent/40 ${selId === c.id ? 'bg-primary/[0.09] border-l-2 border-l-primary' : ''}`}>
                <div className="flex items-center gap-2">
                  <span className={`h-1.5 w-1.5 rounded-full shrink-0 ${dot(c.verdict)}`} />
                  <span className="text-xs truncate flex-1">{c.position_name || '—'}</span>
                  <span className="text-[11px] text-primary tabular-nums">{num(c.price)} €</span>
                </div>
                <div className="mt-0.5 text-[10px] text-muted-foreground truncate">
                  {c.variant_code || '—'} · {c.finish || c.dimension || '—'} · с.{c.page + 1} · {c.doc_name?.slice(0, 20)}
                </div>
              </button>
            ))}
          </div>
        </ResizablePanel>

        <ResizableHandle className="bg-border hover:bg-primary/40" />

        {/* страница прайса */}
        <ResizablePanel defaultSize={45} minSize={28}>
          <div className="h-full flex flex-col">
            <div className="px-3 py-2 border-b border-border flex items-center gap-2 shrink-0">
              <FileText className="h-3.5 w-3.5 text-muted-foreground" />
              <span className="text-[11px] truncate">{cur ? `${cur.doc_name} — страница ${cur.page + 1}` : 'страница прайса'}</span>
            </div>
            <div className="hub-scroll flex-1 overflow-auto bg-[#0b0a09] p-4">
              {!cur ? <div className="h-full grid place-items-center text-xs text-muted-foreground">выберите ячейку</div> : (
                <div className="relative mx-auto shadow-2xl" style={{ width: W * 1.5, height: H * 1.5 }}>
                  <img src={imgSrc} alt="" draggable={false} style={{ width: '100%', height: '100%' }} className="bg-white" />
                  <svg viewBox={`0 0 ${W} ${H}`} className="absolute inset-0 h-full w-full pointer-events-none">
                    {(pg?.cells || []).map((c, i) => Array.isArray(c.bbox) && c.id !== cur.id && (
                      <rect key={i} x={c.bbox[0] - 1} y={c.bbox[1] - 1} width={c.bbox[2] - c.bbox[0] + 2}
                        height={c.bbox[3] - c.bbox[1] + 2} fill="rgba(212,168,88,0.10)" stroke="rgba(212,168,88,0.5)" strokeWidth="0.4" rx="1" />
                    ))}
                    {cur.bbox_row_label && (
                      <rect x={cur.bbox_row_label[0] - 1.5} y={cur.bbox_row_label[1] - 1}
                        width={cur.bbox_row_label[2] - cur.bbox_row_label[0] + 3} height={cur.bbox_row_label[3] - cur.bbox_row_label[1] + 2}
                        fill="rgba(52,211,153,0.15)" stroke="rgb(52,211,153)" strokeWidth="0.6" rx="1" />
                    )}
                    {Array.isArray(cur.bbox_col_header) && cur.bbox_col_header.map((b, i) => (
                      <rect key={`h${i}`} x={b[0] - 1.5} y={b[1] - 1} width={b[2] - b[0] + 3} height={b[3] - b[1] + 2}
                        fill="rgba(56,189,248,0.15)" stroke="rgb(56,189,248)" strokeWidth="0.6" rx="1" />
                    ))}
                    {Array.isArray(cur.bbox) && (
                      <rect x={cur.bbox[0] - 2.5} y={cur.bbox[1] - 2} width={cur.bbox[2] - cur.bbox[0] + 5}
                        height={cur.bbox[3] - cur.bbox[1] + 4} fill="rgba(212,168,88,0.30)" stroke="rgb(212,168,88)" strokeWidth="1.1" rx="1" />
                    )}
                  </svg>
                </div>
              )}
            </div>
          </div>
        </ResizablePanel>

        <ResizableHandle className="bg-border hover:bg-primary/40" />

        {/* вердикт */}
        <ResizablePanel defaultSize={29} minSize={20}>
          <div className="hub-scroll h-full overflow-y-auto p-4">
            {!cur ? <div className="text-xs text-muted-foreground">ничего не выбрано</div> : (
              <div className="space-y-4">
                <div>
                  <div className="text-[10px] tracking-widest text-muted-foreground">СВЕРЯЕМАЯ ЯЧЕЙКА</div>
                  <h2 className="font-serif text-xl mt-0.5 break-words">{cur.position_name}</h2>
                </div>
                <Card className="p-3 bg-primary/[0.06] border-primary/25 space-y-1 text-xs">
                  <div className="flex justify-between"><span className="text-muted-foreground">Артикул</span><span className="text-sky-300">{cur.variant_code || '—'}</span></div>
                  <div className="flex justify-between"><span className="text-muted-foreground">Габариты</span><span>{cur.dimension || '—'}</span></div>
                  <div className="flex justify-between"><span className="text-muted-foreground">Отделка</span><span className="text-emerald-300">{cur.finish || '—'}</span></div>
                  <div className="flex justify-between text-base pt-1"><span className="text-muted-foreground">Цена</span><span className="font-serif text-primary tabular-nums">{num(cur.price)} €</span></div>
                </Card>
                <div className="text-[11px] text-muted-foreground">
                  Сверьте эти значения с подсвеченной ячейкой на странице слева: цена (янтарь), заголовок столбца (голубой), подпись строки (зелёный).
                </div>
                <div className="grid grid-cols-1 gap-1.5">
                  {VERDICTS.map(([k, l, cls]) => (
                    <Button key={k} onClick={() => setVerdict(k)}
                      className={`justify-start text-white text-[12px] h-9 ${cls} ${cur.verdict === k ? 'ring-2 ring-offset-1 ring-offset-background ring-white/70' : ''}`}>
                      {l}
                    </Button>
                  ))}
                </div>
                <div>
                  <div className="text-[10px] tracking-widest text-muted-foreground mb-1">ЗАМЕТКА</div>
                  <Textarea value={note} onChange={e => setNote(e.target.value)} placeholder="Что именно не так…" className="min-h-[60px] text-xs bg-background/60" />
                </div>
                {cur.verdict && (
                  <div className={`text-[11px] flex items-center gap-1.5 ${cur.verdict === 'ok' ? 'text-emerald-400' : 'text-destructive'}`}>
                    {cur.verdict !== 'ok' && <AlertTriangle className="h-3.5 w-3.5" />}
                    <ClipboardCheck className="h-3.5 w-3.5" /> вердикт: {VERD_RU[cur.verdict]}
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

export default AcceptancePanel
