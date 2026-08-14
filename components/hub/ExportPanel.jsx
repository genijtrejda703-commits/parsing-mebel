'use client'

import { useCallback, useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Label } from '@/components/ui/label'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import {
  DownloadCloud, FileSpreadsheet, Loader2, CheckCircle2, Rows3, Layers,
} from 'lucide-react'

const money = (v) => new Intl.NumberFormat('ru-RU').format(v || 0)

const STATUSES = [
  ['approved', 'Одобрены'], ['pending', 'Ожидают'],
  ['rejected', 'Отклонены'], ['all', 'Все статусы'],
]

const ExportPanel = ({ stats }) => {
  const [docs, setDocs] = useState([])
  const [docId, setDocId] = useState('all')
  const [status, setStatus] = useState('approved')
  const [mode, setMode] = useState('product')
  const [count, setCount] = useState(null)
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState(null)

  useEffect(() => {
    fetch('/api/documents').then(r => r.json()).then(d => setDocs(d.items || []))
  }, [])

  const preview = useCallback(async () => {
    const p = new URLSearchParams({ limit: '1' })
    if (docId !== 'all') p.set('doc_id', docId)
    if (status !== 'all') p.set('status', status)
    const d = await (await fetch(`/api/products?${p}`)).json()
    setCount(d.total ?? 0)
  }, [docId, status])

  useEffect(() => { preview() }, [preview])

  const download = async () => {
    setBusy(true); setDone(null)
    try {
      const p = new URLSearchParams({ status, mode })
      if (docId !== 'all') p.set('doc_id', docId)
      const res = await fetch(`/api/export?${p}`)
      if (!res.ok) throw new Error(await res.text())
      const blob = await res.blob()
      const rows = res.headers.get('X-Rows') || '0'
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `HOMEART_catalog_${status}_${new Date().toISOString().slice(0, 10)}.xlsx`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
      setDone(`Файл сформирован: ${money(parseInt(rows))} позиций`)
    } catch (e) {
      setDone(`Ошибка: ${String(e.message).slice(0, 160)}`)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="hub-scroll h-[calc(100vh-73px)] overflow-y-auto">
      <div className="p-6 max-w-[1200px] grid gap-5 lg:grid-cols-[1.25fr_1fr]">
        <Card className="p-5 bg-card/70 border-border">
          <div className="flex items-center gap-2 mb-1">
            <FileSpreadsheet className="h-4 w-4 text-primary" />
            <h3 className="font-serif text-lg">Экспорт каталога в Excel</h3>
          </div>
          <p className="text-xs text-muted-foreground mb-5">
            Формируется файл .xlsx с сохранением структуры данных:
            Фабрика → Коллекция → Модель → Категория → Габариты → Цена мин/макс.
            Кодировка UTF-8, русские заголовки корректно открываются в MS Excel.
          </p>

          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <Label className="text-[10px] tracking-widest text-muted-foreground">ДОКУМЕНТ</Label>
              <Select value={docId} onValueChange={setDocId}>
                <SelectTrigger className="mt-1.5 h-10 text-xs bg-background/60">
                  <SelectValue />
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
            </div>
            <div>
              <Label className="text-[10px] tracking-widest text-muted-foreground">СТАТУС</Label>
              <Select value={status} onValueChange={setStatus}>
                <SelectTrigger className="mt-1.5 h-10 text-xs bg-background/60">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {STATUSES.map(([v, l]) => (
                    <SelectItem key={v} value={v} className="text-xs">{l}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="mt-4">
            <Label className="text-[10px] tracking-widest text-muted-foreground">ФОРМАТ СТРОК</Label>
            <div className="mt-1.5 grid grid-cols-2 gap-2">
              <button onClick={() => setMode('product')}
                className={`rounded-md border p-3 text-left transition-colors ${mode === 'product' ? 'border-primary/60 bg-primary/[0.08]' : 'border-border hover:bg-accent/40'}`}>
                <div className="flex items-center gap-2 text-xs">
                  <Layers className="h-3.5 w-3.5 text-primary" /> По позициям
                </div>
                <div className="text-[10px] text-muted-foreground mt-1">
                  одна строка = позиция с диапазоном цен
                </div>
              </button>
              <button onClick={() => setMode('variation')}
                className={`rounded-md border p-3 text-left transition-colors ${mode === 'variation' ? 'border-primary/60 bg-primary/[0.08]' : 'border-border hover:bg-accent/40'}`}>
                <div className="flex items-center gap-2 text-xs">
                  <Rows3 className="h-3.5 w-3.5 text-primary" /> По вариантам
                </div>
                <div className="text-[10px] text-muted-foreground mt-1">
                  одна строка = отделка и её цена
                </div>
              </button>
            </div>
          </div>

          <div className="mt-5 flex items-center gap-3">
            <Button onClick={download} disabled={busy || !count}
              className="h-11 bg-primary text-primary-foreground hover:bg-primary/90">
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> :
                <><DownloadCloud className="h-4 w-4 mr-1.5" /> Скачать .xlsx</>}
            </Button>
            <div className="text-xs text-muted-foreground">
              {count === null ? 'подсчёт…' : <>к выгрузке: <span className="text-primary tabular-nums">{money(count)}</span> позиций</>}
            </div>
          </div>

          {done && (
            <div className="mt-3 flex items-center gap-2 text-xs text-emerald-400">
              <CheckCircle2 className="h-3.5 w-3.5" /> {done}
            </div>
          )}
          {!count && count !== null && (
            <p className="mt-3 text-[11px] text-amber-400">
              По выбранным фильтрам позиций нет. Одобрите позиции в разделе
              «Контроль качества» или выберите другой статус.
            </p>
          )}
        </Card>

        <div className="space-y-5">
          <Card className="p-5 bg-card/70 border-border">
            <h3 className="font-serif text-lg mb-4">Статусы проверки</h3>
            <div className="space-y-2.5">
              {[
                ['Одобрено', stats?.approved ?? 0, 'text-emerald-400'],
                ['Ожидают', stats?.pending ?? 0, 'text-primary'],
                ['Отклонено', stats?.rejected ?? 0, 'text-destructive'],
                ['Всего позиций', stats?.products ?? 0, 'text-foreground'],
              ].map(([l, v, cls]) => (
                <div key={l} className="flex items-center justify-between">
                  <span className="text-xs text-muted-foreground">{l}</span>
                  <span className={`text-sm tabular-nums ${cls}`}>{money(v)}</span>
                </div>
              ))}
            </div>
          </Card>

          <Card className="p-5 bg-card/70 border-border">
            <h3 className="font-serif text-lg mb-3">Что внутри файла</h3>
            <ul className="space-y-2 text-xs text-muted-foreground">
              {[
                'Лист «Каталог» — все выгруженные позиции с автофильтром и закреплённой шапкой',
                'Лист «Сводка» — агрегаты по моделям: количество, минимальная и максимальная цена',
                'Колонки: Фабрика, Коллекция, Модель, Категория, Габариты, Артикул, Цена мин/макс, Точность, Статус, Заметки проверяющего',
                'Числовой формат цен и валюта EUR, готово к отправке клиенту',
              ].map((t, i) => (
                <li key={i} className="flex gap-2">
                  <span className="text-primary">•</span><span>{t}</span>
                </li>
              ))}
            </ul>
            <Badge variant="outline" className="mt-4 text-[10px] border-primary/40 text-primary">
              openpyxl · UTF-8 · xlsx
            </Badge>
          </Card>
        </div>
      </div>
    </div>
  )
}

export default ExportPanel
