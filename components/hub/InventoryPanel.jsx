'use client'

import { useCallback, useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import {
  Loader2, Search, FileSpreadsheet, RefreshCw, CloudDownload, CheckCircle2,
} from 'lucide-react'

const DROPBOX_URL = 'https://www.dropbox.com/scl/fo/zdr0zj97l9uegvot6wrcr/AIkREaJL0MZpb-PlUOAs278?rlkey=yaxees6jpkycf14khw1x011ny&st=bs82tsvc&dl=0'
const num = (v) => new Intl.NumberFormat('ru-RU').format(v || 0)
const typeColor = {
  'прайс-лист': 'border-emerald-500/40 text-emerald-400',
  'ткани и отделки': 'border-sky-500/40 text-sky-300',
  'технический': 'border-amber-500/40 text-amber-400',
  'маркетинг': 'border-fuchsia-500/40 text-fuchsia-300',
  'каталог': 'border-primary/40 text-primary',
  'прочее': 'border-border text-muted-foreground',
}

const InventoryPanel = ({ onTaskStart }) => {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [running, setRunning] = useState('')
  const [source, setSource] = useState('all')
  const [docType, setDocType] = useState('all')
  const [term, setTerm] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const p = new URLSearchParams()
      if (source !== 'all') p.set('source', source)
      if (docType !== 'all') p.set('doc_type', docType)
      if (term) p.set('q', term)
      setData(await (await fetch(`/api/inventory?${p}`)).json())
    } finally { setLoading(false) }
  }, [source, docType, term])

  useEffect(() => { const t = setTimeout(load, 250); return () => clearTimeout(t) }, [load])

  const run = async (body, tag) => {
    setRunning(tag)
    try {
      const r = await fetch('/api/inventory', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const d = await r.json()
      if (d.task_id && onTaskStart) onTaskStart(d.task_id)
    } finally { setRunning('') }
  }

  const items = data?.items || []

  return (
    <div className="h-[calc(100vh-73px)] flex flex-col">
      <div className="border-b border-border px-4 py-2.5 flex items-center gap-2 flex-wrap shrink-0">
        <Button size="sm" variant="secondary" className="h-8 text-[11px]"
          disabled={!!running} onClick={() => run({ source: 'local' }, 'local')}>
          {running === 'local' ? <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" /> :
            <RefreshCw className="h-3.5 w-3.5 mr-1.5" />}
          Пересчитать локально
        </Button>
        <Button size="sm" className="h-8 text-[11px] bg-primary text-primary-foreground"
          disabled={!!running}
          onClick={() => run({ source: 'dropbox', url: DROPBOX_URL, ingest_new: true }, 'dropbox')}
          title="Скачать всю папку Dropbox во временное хранилище, классифицировать и удалить (read-only транзит)">
          {running === 'dropbox' ? <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" /> :
            <CloudDownload className="h-3.5 w-3.5 mr-1.5" />}
          Полная инвентаризация Dropbox
        </Button>
        <div className="w-px h-6 bg-border mx-1" />
        <Select value={source} onValueChange={setSource}>
          <SelectTrigger className="h-8 w-[150px] text-xs bg-card/60"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Все источники</SelectItem>
            <SelectItem value="local">Локальные</SelectItem>
            <SelectItem value="dropbox">Dropbox</SelectItem>
          </SelectContent>
        </Select>
        <Select value={docType} onValueChange={setDocType}>
          <SelectTrigger className="h-8 w-[170px] text-xs bg-card/60"><SelectValue placeholder="тип" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Все типы</SelectItem>
            {(data?.by_type || []).map(t => (
              <SelectItem key={t.doc_type} value={t.doc_type} className="text-xs">
                {t.doc_type} ({t.n})
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <div className="relative flex-1 min-w-[150px]">
          <Search className="absolute left-2.5 top-2 h-3.5 w-3.5 text-muted-foreground" />
          <Input value={term} onChange={e => setTerm(e.target.value)}
            placeholder="файл, заголовок…" className="h-8 pl-8 text-xs bg-card/60" />
        </div>
        <Badge variant="outline" className="text-[10px] border-border">
          {loading ? <Loader2 className="h-3 w-3 animate-spin" /> : `${items.length} / ${num(data?.total)}`}
        </Badge>
        <Button size="sm" variant="secondary" className="h-8 text-[11px]"
          onClick={() => window.open('/api/inventory/export', '_blank')}>
          <FileSpreadsheet className="h-3.5 w-3.5 mr-1.5" /> Экспорт .xlsx
        </Button>
      </div>

      <div className="px-4 py-3 grid grid-cols-2 md:grid-cols-5 gap-3 shrink-0">
        {[
          ['Всего файлов', data?.total],
          ['Актуальных прайс-листов', data?.current_listini],
          ['Разобрано', data?.ingested],
          ['Типов документов', (data?.by_type || []).length],
          ['Источник Dropbox', items.some(i => i.source === 'dropbox') ? 'подключён' : '—'],
        ].map(([l, v]) => (
          <Card key={l} className="p-3 bg-card/50">
            <div className="text-[10px] tracking-widest text-muted-foreground">{l.toUpperCase()}</div>
            <div className="mt-1 font-serif text-2xl tabular-nums">
              {typeof v === 'number' ? num(v) : (v ?? '—')}
            </div>
          </Card>
        ))}
      </div>

      <div className="hub-scroll flex-1 overflow-auto px-4 pb-4">
        <table className="w-full text-xs border-collapse">
          <thead className="sticky top-0 bg-background">
            <tr className="text-[10px] tracking-widest text-muted-foreground border-b border-border">
              {['ФАЙЛ', 'ТИП', 'ГОД', 'ВАЛ', 'СТР.', 'АКТУ.', 'РАЗОБ.', 'ВАР-ЦЕН', 'ЗАМЕНА'].map(h => (
                <th key={h} className="text-left font-normal py-2 px-2">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {items.map(r => (
              <tr key={r.id} className="border-b border-border/40 hover:bg-accent/30">
                <td className="py-1.5 px-2 max-w-[360px]">
                  <div className="truncate">{r.name}</div>
                  {r.sample_title && <div className="text-[10px] text-muted-foreground truncate">{r.sample_title}</div>}
                </td>
                <td className="px-2">
                  <Badge variant="outline" className={`text-[9px] ${typeColor[r.doc_type] || ''}`}>{r.doc_type}</Badge>
                </td>
                <td className="px-2 tabular-nums text-muted-foreground">{r.year || '—'}</td>
                <td className="px-2 text-muted-foreground">{r.currency || '—'}</td>
                <td className="px-2 tabular-nums">{num(r.pages)}</td>
                <td className="px-2">{r.is_current_listino ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" /> : '—'}</td>
                <td className="px-2">{r.ingested ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" /> : '—'}</td>
                <td className="px-2 tabular-nums text-primary">{r.variant_prices != null ? num(r.variant_prices) : '—'}</td>
                <td className="px-2 text-[10px] text-amber-400/80 max-w-[160px] truncate">{r.superseded_by || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!items.length && !loading && (
          <div className="p-6 text-xs text-muted-foreground">
            Инвентаризация пуста. Запустите «Пересчитать локально» или «Полная инвентаризация Dropbox».
          </div>
        )}
      </div>
    </div>
  )
}

export default InventoryPanel
