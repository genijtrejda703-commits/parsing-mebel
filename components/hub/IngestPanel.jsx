'use client'

import { useEffect, useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Checkbox } from '@/components/ui/checkbox'
import { Card } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import {
  Loader2, FolderTree, Play, UploadCloud, FileText, Search, CheckCheck, X,
} from 'lucide-react'

const DEFAULT_URL = 'https://www.dropbox.com/scl/fo/zdr0zj97l9uegvot6wrcr/AIkREaJL0MZpb-PlUOAs278?rlkey=yaxees6jpkycf14khw1x011ny&st=bs82tsvc&dl=0'

const IngestPanel = ({ onTaskStart }) => {
  const [url, setUrl] = useState(DEFAULT_URL)
  const [factory, setFactory] = useState('Molteni & C')
  const [maxPages, setMaxPages] = useState('0')
  const [scanTask, setScanTask] = useState(null)
  const [scanning, setScanning] = useState(false)
  const [files, setFiles] = useState([])
  const [picked, setPicked] = useState([])
  const [filter, setFilter] = useState('')
  const [uploading, setUploading] = useState(false)
  const [starting, setStarting] = useState(false)
  const fileRef = useRef(null)
  const pollRef = useRef(null)

  useEffect(() => () => clearInterval(pollRef.current), [])

  const scan = async () => {
    setScanning(true); setFiles([]); setPicked([])
    try {
      const r = await fetch('/api/scan', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      })
      const { task_id } = await r.json()
      clearInterval(pollRef.current)
      pollRef.current = setInterval(async () => {
        const t = await (await fetch(`/api/tasks/${task_id}`)).json()
        setScanTask(t)
        if (t.status === 'done' || t.status === 'error') {
          clearInterval(pollRef.current)
          setScanning(false)
          const fs = t.result?.files || []
          setFiles(fs)
          setPicked(fs.filter(f => f.is_price_list).map(f => f.rel))
        }
      }, 1500)
    } catch (e) {
      setScanning(false)
    }
  }

  const ingest = async (payload) => {
    setStarting(true)
    try {
      const r = await fetch('/api/ingest', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          factory, max_pages: parseInt(maxPages) || null, cleanup: false, ...payload,
        }),
      })
      const d = await r.json()
      if (d.task_id) onTaskStart(d.task_id)
    } finally {
      setStarting(false)
    }
  }

  const upload = async (fl) => {
    if (!fl?.length) return
    setUploading(true)
    try {
      const fd = new FormData()
      Array.from(fl).forEach(f => fd.append('files', f))
      const r = await fetch('/api/upload', { method: 'POST', body: fd })
      const d = await r.json()
      const paths = (d.files || []).map(f => f.path)
      if (paths.length) await ingest({ source: 'local', paths })
    } finally {
      setUploading(false)
    }
  }

  const shown = files.filter(f =>
    !filter || f.name.toLowerCase().includes(filter.toLowerCase()) ||
    f.folder.toLowerCase().includes(filter.toLowerCase()))
  const toggle = (rel) =>
    setPicked(p => p.includes(rel) ? p.filter(x => x !== rel) : [...p, rel])

  return (
    <div className="p-6 space-y-5 max-w-[1500px]">
      <div className="grid gap-5 lg:grid-cols-[1.35fr_1fr]">
        {/* -------- dropbox source -------- */}
        <Card className="p-5 bg-card/70 border-border">
          <div className="flex items-center gap-2 mb-1">
            <FolderTree className="h-4 w-4 text-primary" />
            <h3 className="font-serif text-lg">Dropbox shared folder</h3>
          </div>
          <p className="text-xs text-muted-foreground mb-4">
            The folder is traversed as a single archive (<code className="text-primary">dl=1</code>),
            nested sub-folders included. Cyrillic paths are handled.
          </p>

          <Label className="text-[10px] tracking-widest text-muted-foreground">SHARE LINK</Label>
          <div className="flex gap-2 mt-1.5">
            <Input value={url} onChange={e => setUrl(e.target.value)}
              className="bg-background/60 font-mono text-xs h-10" />
            <Button onClick={scan} disabled={scanning || !url}
              className="h-10 shrink-0 bg-primary text-primary-foreground hover:bg-primary/90">
              {scanning ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Traverse'}
            </Button>
          </div>

          {scanning && (
            <div className="mt-4 rounded-md border border-border bg-background/60 p-3">
              <div className="flex items-center justify-between text-xs mb-2">
                <span className="text-muted-foreground">
                  {scanTask?.events?.slice(-1)[0]?.msg || 'contacting Dropbox…'}
                </span>
                <span className="text-primary">{Math.round(scanTask?.progress || 0)}%</span>
              </div>
              <Progress value={scanTask?.progress || 0} className="h-1" />
              <p className="mt-2 text-[11px] text-muted-foreground">
                First traversal downloads the archive once, then it is cached on disk.
              </p>
            </div>
          )}

          {!!files.length && (
            <div className="mt-4">
              <div className="flex items-center gap-2 mb-2">
                <div className="relative flex-1">
                  <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
                  <Input value={filter} onChange={e => setFilter(e.target.value)}
                    placeholder="filter documents…" className="h-9 pl-8 bg-background/60 text-xs" />
                </div>
                <Button variant="secondary" size="sm" className="h-9 text-xs"
                  onClick={() => setPicked(files.filter(f => f.is_price_list).map(f => f.rel))}>
                  <CheckCheck className="h-3.5 w-3.5 mr-1" /> price lists
                </Button>
                <Button variant="ghost" size="sm" className="h-9 text-xs"
                  onClick={() => setPicked([])}><X className="h-3.5 w-3.5" /></Button>
              </div>

              <div className="hub-scroll max-h-[320px] overflow-y-auto rounded-md border border-border divide-y divide-border/60">
                {shown.map(f => (
                  <button key={f.rel} onClick={() => toggle(f.rel)}
                    className={`w-full text-left flex items-center gap-3 px-3 py-2 hover:bg-accent/40 transition-colors ${picked.includes(f.rel) ? 'bg-primary/[0.07]' : ''}`}>
                    <Checkbox checked={picked.includes(f.rel)} className="pointer-events-none" />
                    <FileText className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                    <div className="min-w-0 flex-1">
                      <div className="text-xs truncate">{f.name}</div>
                      <div className="text-[10px] text-muted-foreground truncate">{f.folder}</div>
                    </div>
                    {f.is_price_list && (
                      <Badge variant="outline"
                        className="text-[9px] border-primary/40 text-primary shrink-0">PRICE LIST</Badge>
                    )}
                    <span className="text-[10px] text-muted-foreground shrink-0 w-14 text-right">
                      {(f.size / 1e6).toFixed(1)} MB
                    </span>
                  </button>
                ))}
              </div>

              <div className="mt-3 flex items-center justify-between">
                <span className="text-xs text-muted-foreground">
                  {picked.length} of {files.length} selected
                </span>
                <Button disabled={!picked.length || starting}
                  onClick={() => ingest({ source: 'dropbox', url, rels: picked })}
                  className="bg-primary text-primary-foreground hover:bg-primary/90">
                  {starting ? <Loader2 className="h-4 w-4 animate-spin" /> :
                    <><Play className="h-4 w-4 mr-1.5" /> Extract {picked.length} document(s)</>}
                </Button>
              </div>
            </div>
          )}
        </Card>

        {/* -------- options + upload -------- */}
        <div className="space-y-5">
          <Card className="p-5 bg-card/70 border-border">
            <h3 className="font-serif text-lg mb-4">Run configuration</h3>
            <div className="space-y-4">
              <div>
                <Label className="text-[10px] tracking-widest text-muted-foreground">FACTORY</Label>
                <Input value={factory} onChange={e => setFactory(e.target.value)}
                  className="mt-1.5 h-10 bg-background/60" />
              </div>
              <div>
                <Label className="text-[10px] tracking-widest text-muted-foreground">PAGE SCOPE</Label>
                <div className="mt-1.5 grid grid-cols-3 gap-2">
                  {[['0', 'All pages'], ['60', 'First 60'], ['150', 'First 150']].map(([v, l]) => (
                    <Button key={v} variant={maxPages === v ? 'default' : 'secondary'}
                      onClick={() => setMaxPages(v)}
                      className={`h-9 text-xs ${maxPages === v ? 'bg-primary text-primary-foreground' : ''}`}>
                      {l}
                    </Button>
                  ))}
                </div>
                <p className="mt-2 text-[11px] text-muted-foreground">
                  Molteni price lists run 400+ pages each. Use a scope for a fast demo pass.
                </p>
              </div>
            </div>
          </Card>

          <Card className="p-5 bg-card/70 border-border">
            <h3 className="font-serif text-lg mb-1">Direct upload</h3>
            <p className="text-xs text-muted-foreground mb-4">Drop a PDF price list to parse it immediately.</p>
            <div
              onDragOver={e => e.preventDefault()}
              onDrop={e => { e.preventDefault(); upload(e.dataTransfer.files) }}
              onClick={() => fileRef.current?.click()}
              className="cursor-pointer rounded-lg border border-dashed border-border hover:border-primary/60 hover:bg-primary/[0.04] transition-colors p-8 text-center">
              {uploading ? <Loader2 className="h-6 w-6 mx-auto animate-spin text-primary" /> :
                <UploadCloud className="h-6 w-6 mx-auto text-muted-foreground" />}
              <div className="mt-3 text-xs text-foreground">Drop PDFs here or click to browse</div>
              <div className="text-[10px] text-muted-foreground mt-1">parsed with the same geometric engine</div>
            </div>
            <input ref={fileRef} type="file" accept="application/pdf" multiple hidden
              onChange={e => upload(e.target.files)} />
          </Card>
        </div>
      </div>
    </div>
  )
}

export default IngestPanel
