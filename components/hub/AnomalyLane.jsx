'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import {
  ShieldAlert, Search, RefreshCw, Loader2, ChevronLeft, ChevronRight, FileText,
} from 'lucide-react'

const money = (v) => new Intl.NumberFormat('ru-RU').format(v || 0)
const PAGE = 60

const AnomalyLane = () => {
  const [docs, setDocs] = useState([])
  const [docId, setDocId] = useState('all')
  const [reason, setReason] = useState('all')
  const [term, setTerm] = useState('')
  const [items, setItems] = useState([])
  const [reasons, setReasons] = useState([])
  const [total, setTotal] = useState(0)
  const [skip, setSkip] = useState(0)
  const [loading, setLoading] = useState(false)
  const [task, setTask] = useState(null)
  const [scanning, setScanning] = useState(false)
  const pollRef = useRef(null)

  useEffect(() => {
    fetch('/api/documents').then(r => r.json()).then(d => setDocs(d.items || []))
    return () => clearInterval(pollRef.current)
  }, [])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const p = new URLSearchParams({ limit: String(PAGE), skip: String(skip) })
      if (docId !== 'all') p.set('doc_id', docId)
      if (reason !== 'all') p.set('reason', reason)
      if (term) p.set('q', term)
      const d = await (await fetch(`/api/anomalies?${p}`)).json()
      setItems(d.items || [])
      setTotal(d.total || 0)
      setReasons(d.reasons || [])
    } finally {
      setLoading(false)
    }
  }, [docId, reason, term, skip])

  useEffect(() => { const t = setTimeout(load, 250); return () => clearTimeout(t) }, [load])
  useEffect(() => { setSkip(0) }, [docId, reason, term])

  const rescan = async () => {
    setScanning(true)
    try {
      const r = await fetch('/api/anomaly-scan', { method: 'POST' })
      const { task_id } = await r.json()
      clearInterval(pollRef.current)
      pollRef.current = setInterval(async () => {
        const t = await (await fetch(`/api/tasks/${task_id}`)).json()
        setTask(t)
        if (t.status === 'done' || t.status === 'error') {
          clearInterval(pollRef.current)
          setScanning(false)
          load()
        }
      }, 2500)
    } catch {
      setScanning(false)
    }
  }

  const confColor = (c) => c >= 0.35 ? 'text-amber-400'
    : c > 0 ? 'text-orange-400' : 'text-muted-foreground'

  return (
    <div className="h-[calc(100vh-73px)] flex flex-col">
      <div className="border-b border-border px-4 py-2.5 flex items-center gap-2 flex-wrap shrink-0">
        <Select value={docId} onValueChange={setDocId}>
          <SelectTrigger className="h-8 w-[250px] text-xs bg-card/60"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Все документы</SelectItem>
            {docs.map(d => (
              <SelectItem key={d.id} value={d.id} className="text-xs">{d.name}</SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select value={reason} onValueChange={setReason}>
          <SelectTrigger className="h-8 w-[330px] text-xs bg-card/60">
            <SelectValue placeholder="причина" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Все причины</SelectItem>
            {reasons.map(r => (
              <SelectItem key={r.reason} value={r.reason} className="text-xs">
                {r.reason} ({money(r.n)})
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <div className="relative flex-1 min-w-[160px]">
          <Search className="absolute left-2.5 top-2 h-3.5 w-3.5 text-muted-foreground" />
          <Input value={term} onChange={e => setTerm(e.target.value)}
            placeholder="текст блока, модель, заголовок…"
            className="h-8 pl-8 text-xs bg-card/60" />
        </div>

        <Badge variant="outline" className="text-[10px] border-border">
          {loading ? <Loader2 className="h-3 w-3 animate-spin" /> : `${money(total)} блоков`}
        </Badge>

        <Button size="sm" variant="secondary" onClick={rescan} disabled={scanning}
          className="h-8 text-xs">
          {scanning ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> :
            <><RefreshCw className="h-3.5 w-3.5 mr-1.5" /> Пересчитать журнал</>}
        </Button>
      </div>

      {scanning && task && (
        <div className="px-4 py-2 border-b border-border bg-primary/[0.05] shrink-0">
          <div className="flex items-center justify-between text-xs mb-1.5">
            <span className="text-muted-foreground truncate">
              {task.events?.slice(-1)[0]?.msg || 'пересчёт журнала…'}
            </span>
            <span className="text-primary tabular-nums">{Math.round(task.progress || 0)}%</span>
          </div>
          <Progress value={task.progress || 0} className="h-1" />
        </div>
      )}

      <div className="grid lg:grid-cols-[300px_1fr] flex-1 min-h-0">
        {/* причины */}
        <div className="border-r border-border hub-scroll overflow-y-auto">
          <div className="px-4 py-3 text-[10px] tracking-widest text-muted-foreground border-b border-border">
            ПРИЧИНЫ ОТСЕВА
          </div>
          <button onClick={() => setReason('all')}
            className={`w-full text-left px-4 py-2.5 border-b border-border/50 hover:bg-accent/40 ${reason === 'all' ? 'bg-primary/[0.09] border-l-2 border-l-primary' : ''}`}>
            <div className="flex items-center justify-between">
              <span className="text-xs">Все причины</span>
              <span className="text-[11px] text-muted-foreground tabular-nums">
                {money(reasons.reduce((a, r) => a + r.n, 0))}
              </span>
            </div>
          </button>
          {reasons.map(r => (
            <button key={r.reason} onClick={() => setReason(r.reason)}
              className={`w-full text-left px-4 py-2.5 border-b border-border/50 hover:bg-accent/40 ${reason === r.reason ? 'bg-primary/[0.09] border-l-2 border-l-primary' : ''}`}>
              <div className="flex items-start justify-between gap-2">
                <span className="text-[11px] leading-snug">{r.reason}</span>
                <span className="text-[11px] text-primary tabular-nums shrink-0">{money(r.n)}</span>
              </div>
            </button>
          ))}
          {!reasons.length && (
            <div className="p-4 text-xs text-muted-foreground">
              Журнал пуст — нажмите «Пересчитать журнал», чтобы задокументировать
              все отсеянные блоки.
            </div>
          )}
        </div>

        {/* таблица */}
        <div className="flex flex-col min-h-0">
          <div className="hub-scroll flex-1 overflow-auto">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-background/95 backdrop-blur border-b border-border">
                <tr className="text-[10px] tracking-widest text-muted-foreground">
                  <th className="text-left font-normal px-3 py-2.5 w-[110px]">БЛОК ТЕКСТА</th>
                  <th className="text-left font-normal px-3 py-2.5 w-[150px]">УВЕРЕННОСТЬ (MICROGRAD)</th>
                  <th className="text-left font-normal px-3 py-2.5">ПРИЧИНА</th>
                  <th className="text-left font-normal px-3 py-2.5 w-[150px]">ЗАГОЛОВОК СВЕРХУ</th>
                  <th className="text-left font-normal px-3 py-2.5 w-[150px]">ПОДПИСЬ СЛЕВА</th>
                  <th className="text-left font-normal px-3 py-2.5 w-[190px]">ДОКУМЕНТ</th>
                </tr>
              </thead>
              <tbody>
                {items.map((a, i) => (
                  <tr key={a.id || i} className="border-b border-border/40 hover:bg-accent/25">
                    <td className="px-3 py-2 font-mono text-primary">{a.text}</td>
                    <td className="px-3 py-2">
                      <div className="flex items-center gap-2">
                        <span className={`tabular-nums ${confColor(a.confidence)}`}>
                          {(a.confidence * 100).toFixed(1)}%
                        </span>
                        <div className="h-1 w-16 rounded-full bg-muted overflow-hidden">
                          <div className="h-full bg-amber-500"
                            style={{ width: `${Math.max(2, a.confidence * 100)}%` }} />
                        </div>
                      </div>
                      <div className="text-[10px] text-muted-foreground mt-0.5">
                        соседей: {a.row_peers ?? 0} / {a.col_peers ?? 0}
                      </div>
                    </td>
                    <td className="px-3 py-2 text-muted-foreground">{a.reason}</td>
                    <td className="px-3 py-2 text-muted-foreground truncate max-w-[150px]">
                      {a.above_text || '—'}
                    </td>
                    <td className="px-3 py-2 text-muted-foreground truncate max-w-[150px]">
                      {a.left_text || '—'}
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex items-center gap-1.5 text-muted-foreground">
                        <FileText className="h-3 w-3 shrink-0" />
                        <span className="truncate max-w-[130px]">{a.doc_name}</span>
                        <span className="shrink-0">с.{(a.page ?? 0) + 1}</span>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!items.length && !loading && (
              <div className="p-6 text-xs text-muted-foreground">
                Нет записей по выбранным фильтрам.
              </div>
            )}
          </div>

          <div className="border-t border-border px-4 py-2 flex items-center justify-between shrink-0">
            <span className="text-[11px] text-muted-foreground">
              {money(skip + 1)}–{money(Math.min(skip + PAGE, total))} из {money(total)}
            </span>
            <div className="flex items-center gap-1">
              <Button size="icon" variant="ghost" className="h-7 w-7" disabled={skip <= 0}
                onClick={() => setSkip(s => Math.max(0, s - PAGE))}>
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <Button size="icon" variant="ghost" className="h-7 w-7"
                disabled={skip + PAGE >= total}
                onClick={() => setSkip(s => s + PAGE)}>
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default AnomalyLane
