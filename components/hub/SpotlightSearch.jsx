'use client'

import { useEffect, useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import {
  Loader2, Search, ImageIcon, Sparkles, Radar, Database, ArrowRight, X, Languages,
} from 'lucide-react'

const money = (v) => v == null ? '—' : new Intl.NumberFormat('ru-RU').format(v)

const EXAMPLES = [
  'диван из кожи', 'кожаный диван с шезлонгом', 'пуф из ткани',
  'кухонный модуль с ящиками', 'ящики для кухни', 'кровать', 'dining table oak',
]

// CLIP text-text similarity lives in a much higher band than image-text similarity,
// so the badge is calibrated per query mode instead of showing a raw cosine.
const matchPct = (score, mode) => {
  const lo = mode === 'image' ? 0.08 : 0.30
  const hi = mode === 'image' ? 0.38 : 0.92
  return Math.max(1, Math.min(99, Math.round(((score - lo) / (hi - lo)) * 100)))
}

const SpotlightSearch = ({ stats, onOpenInQa }) => {
  const [q, setQ] = useState('')
  const [busy, setBusy] = useState(false)
  const [res, setRes] = useState(null)
  const [mode, setMode] = useState('text')
  const [preview, setPreview] = useState(null)
  const [embedTask, setEmbedTask] = useState(null)
  const [indexing, setIndexing] = useState(false)
  const fileRef = useRef(null)
  const pollRef = useRef(null)

  const embedded = stats?.embeddings ?? 0
  const products = stats?.products ?? 0
  const coverage = products ? Math.round((embedded / products) * 100) : 0

  useEffect(() => () => clearInterval(pollRef.current), [])

  const buildIndex = async () => {
    setIndexing(true)
    try {
      const r = await fetch('/api/embed', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}',
      })
      const { task_id } = await r.json()
      clearInterval(pollRef.current)
      pollRef.current = setInterval(async () => {
        const t = await (await fetch(`/api/tasks/${task_id}`)).json()
        setEmbedTask(t)
        if (t.status === 'done' || t.status === 'error') {
          clearInterval(pollRef.current)
          setIndexing(false)
        }
      }, 2000)
    } catch {
      setIndexing(false)
    }
  }

  const searchText = async (query) => {
    const text = (query ?? q).trim()
    if (!text) return
    setBusy(true); setMode('text'); setPreview(null)
    try {
      const r = await fetch('/api/search', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ q: text, top_k: 24 }),
      })
      setRes(await r.json())
    } finally {
      setBusy(false)
    }
  }

  const searchImage = async (file) => {
    if (!file) return
    setBusy(true); setMode('image')
    setPreview(URL.createObjectURL(file))
    try {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('top_k', '24')
      const r = await fetch('/api/search', { method: 'POST', body: fd })
      setRes(await r.json())
    } finally {
      setBusy(false)
    }
  }

  const results = res?.results || []
  const resMode = res?.mode || mode

  return (
    <div className="hub-scroll h-[calc(100vh-73px)] overflow-y-auto">
      <div className="p-6 space-y-5 max-w-[1600px]">
        {/* ---------- индекс ---------- */}
        <div className="grid gap-5 lg:grid-cols-[1fr_360px]">
          <Card className="p-5 bg-card/70 border-border">
            <div className="flex items-center gap-2 mb-1">
              <Radar className="h-4 w-4 text-primary" />
              <h3 className="font-serif text-lg">Умный поиск по каталогу</h3>
            </div>
            <p className="text-xs text-muted-foreground mb-4">
              Текстовый запрос кодируется мультиязычной моделью
              <code className="text-primary mx-1">clip-ViT-B-32-multilingual-v1</code>,
              изображение — моделью <code className="text-primary mx-1">clip-ViT-B-32</code>.
              Обе дают вектор из 512 чисел в одном пространстве, поэтому запрос на русском
              сравнивается с каталогом напрямую.
            </p>

            <div className="flex gap-2">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                <Input value={q} onChange={e => setQ(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && searchText()}
                  placeholder="Опишите мебель на русском или английском…"
                  className="h-11 pl-9 bg-background/60" />
              </div>
              <Button onClick={() => searchText()} disabled={busy || !q.trim()}
                className="h-11 bg-primary text-primary-foreground hover:bg-primary/90">
                {busy && resMode === 'text' ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Найти'}
              </Button>
              <Button variant="secondary" className="h-11" onClick={() => fileRef.current?.click()}>
                <ImageIcon className="h-4 w-4 mr-1.5" /> По фото
              </Button>
              <input ref={fileRef} type="file" accept="image/*" hidden
                onChange={e => searchImage(e.target.files?.[0])} />
            </div>

            <div className="mt-3 flex flex-wrap gap-1.5">
              {EXAMPLES.map(x => (
                <button key={x} onClick={() => { setQ(x); searchText(x) }}
                  className="px-2.5 py-1 rounded-full border border-border text-[11px] text-muted-foreground hover:border-primary/50 hover:text-primary transition-colors">
                  {x}
                </button>
              ))}
            </div>

            <div
              onDragOver={e => e.preventDefault()}
              onDrop={e => { e.preventDefault(); searchImage(e.dataTransfer.files?.[0]) }}
              onClick={() => fileRef.current?.click()}
              className="mt-4 cursor-pointer rounded-lg border border-dashed border-border hover:border-primary/60 hover:bg-primary/[0.04] transition-colors p-6 text-center">
              {preview ? (
                <div className="flex items-center justify-center gap-4">
                  <img src={preview} alt="" className="h-24 w-24 object-cover rounded-md border border-border" />
                  <div className="text-left">
                    <div className="text-xs text-foreground">Поиск по этому изображению</div>
                    <div className="text-[10px] text-muted-foreground mt-1">
                      кодировщик изображений CLIP ViT-B/32 · 512 измерений
                    </div>
                    <Button variant="ghost" size="sm" className="h-6 mt-1.5 text-[10px] px-2"
                      onClick={(e) => { e.stopPropagation(); setPreview(null); setRes(null) }}>
                      <X className="h-3 w-3 mr-1" /> сбросить
                    </Button>
                  </div>
                </div>
              ) : (
                <>
                  <ImageIcon className="h-6 w-6 mx-auto text-muted-foreground" />
                  <div className="mt-2 text-xs text-foreground">
                    Перетащите фото мебели — например, комода — чтобы найти похожие позиции
                  </div>
                  <div className="text-[10px] text-muted-foreground mt-1">
                    сравнение изображения с текстовыми векторами каталога (zero-shot CLIP)
                  </div>
                </>
              )}
            </div>
          </Card>

          <Card className="p-5 bg-card/70 border-border">
            <div className="flex items-center gap-2 mb-3">
              <Database className="h-4 w-4 text-primary" />
              <h3 className="font-serif text-lg">Векторный индекс</h3>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="font-serif text-3xl tabular-nums text-primary">{money(embedded)}</span>
              <span className="text-xs text-muted-foreground">из {money(products)} позиций</span>
            </div>
            <Progress value={coverage} className="h-1.5 mt-3" />
            <div className="mt-2 flex items-center justify-between text-[11px] text-muted-foreground">
              <span>качественных позиций: {coverage}%</span>
              <span>512-мерные векторы, CPU</span>
            </div>

            {indexing && embedTask && (
              <div className="mt-4 rounded-md border border-border bg-background/60 p-3">
                <div className="flex items-center justify-between text-xs mb-2">
                  <span className="text-muted-foreground truncate">
                    {embedTask.events?.slice(-1)[0]?.msg || 'векторизация…'}
                  </span>
                  <span className="text-primary tabular-nums">
                    {Math.round(embedTask.progress || 0)}%
                  </span>
                </div>
                <Progress value={embedTask.progress || 0} className="h-1" />
              </div>
            )}

            <Button onClick={buildIndex} disabled={indexing}
              className="mt-4 w-full bg-primary text-primary-foreground hover:bg-primary/90">
              {indexing ? <Loader2 className="h-4 w-4 animate-spin" /> :
                <><Sparkles className="h-4 w-4 mr-1.5" /> Проиндексировать каталог</>}
            </Button>
            <p className="mt-2 text-[11px] text-muted-foreground leading-relaxed">
              В индекс попадают только позиции с точностью ≥ 60% — служебные страницы
              и юридический текст исключены намеренно, чтобы не засорять поиск.
              Индексируются лишь новые позиции; поиск — косинусная близость в памяти (numpy).
            </p>
          </Card>
        </div>

        {/* ---------- результаты ---------- */}
        {res && (
          <div>
            <div className="flex items-center gap-3 mb-3 flex-wrap">
              <h3 className="font-serif text-lg">Результаты</h3>
              <Badge variant="outline" className="text-[10px] border-primary/40 text-primary">
                <Languages className="h-3 w-3 mr-1" />
                {resMode === 'image' ? 'поиск по изображению · CLIP ViT-B/32'
                  : 'текстовый запрос · мультиязычный CLIP'}
              </Badge>
              <span className="text-xs text-muted-foreground">
                просканировано векторов: {money(res.searched || 0)} · найдено {results.length}
              </span>
            </div>

            {!results.length && (
              <Card className="p-6 bg-card/70 border-border text-sm text-muted-foreground">
                {res.note === 'no embeddings yet'
                  ? 'Индекс пуст — нажмите «Проиндексировать каталог».'
                  : 'Ничего не найдено. Попробуйте другой запрос.'}
              </Card>
            )}

            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
              {results.map(p => (
                <Card key={p.id}
                  className="overflow-hidden bg-card/70 border-border hover:border-primary/40 transition-colors group">
                  <div className="relative h-[132px] bg-[#0b0a09] overflow-hidden">
                    <img
                      src={`/api/page-image?doc_id=${p.doc_id}&page=${p.page}&dpi=45`}
                      alt="" loading="lazy"
                      className="w-full h-full object-cover object-top opacity-80 group-hover:opacity-100 transition-opacity" />
                    <div className="absolute top-2 right-2">
                      <div className="rounded-md bg-primary px-2 py-1 text-[11px] font-medium text-primary-foreground tabular-nums shadow-lg">
                        {matchPct(p.score, resMode)}% совпадение
                      </div>
                    </div>
                    <div className="absolute bottom-2 left-2">
                      <Badge variant="outline"
                        className="text-[9px] bg-background/80 border-border backdrop-blur">
                        стр. {p.page + 1} · cos {p.score?.toFixed(3)}
                      </Badge>
                    </div>
                  </div>
                  <div className="p-3">
                    <div className="text-xs font-medium truncate">{p.model_name}</div>
                    <div className="text-[10px] text-muted-foreground truncate mt-0.5">
                      {[p.category, p.variant_code || p.dimension].filter(Boolean).join(' · ')}
                    </div>
                    <div className="mt-2 flex items-center justify-between">
                      <span className="text-sm text-primary tabular-nums">
                        {money(p.price_min)} – {money(p.price_max)} €
                      </span>
                      <span className="text-[10px] text-muted-foreground">
                        {p.n_variations} вар.
                      </span>
                    </div>
                    <div className="text-[10px] text-muted-foreground truncate mt-1">
                      {p.collection}
                    </div>
                    <Button variant="secondary" size="sm"
                      onClick={() => onOpenInQa?.(p)}
                      className="mt-2 w-full h-7 text-[10px]">
                      Открыть в контроле качества <ArrowRight className="h-3 w-3 ml-1" />
                    </Button>
                  </div>
                </Card>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default SpotlightSearch
