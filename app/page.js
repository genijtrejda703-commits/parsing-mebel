'use client'

import { useEffect, useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import LoginScreen from '@/components/hub/LoginScreen'
import IngestPanel from '@/components/hub/IngestPanel'
import TaskMonitor from '@/components/hub/TaskMonitor'
import QaWorkbench from '@/components/hub/QaWorkbench'
import {
  Boxes, DownloadCloud, FolderInput, LayoutGrid, LogOut, Radar, Activity,
} from 'lucide-react'

const NAV = [
  { id: 'ingest', label: 'Ingest', icon: FolderInput, ready: true },
  { id: 'monitor', label: 'Task Monitor', icon: Activity, ready: true },
  { id: 'catalog', label: 'QA Workbench', icon: LayoutGrid, ready: true },
  { id: 'spotlight', label: 'Spotlight Search', icon: Radar, ready: false },
  { id: 'export', label: 'Excel Export', icon: DownloadCloud, ready: false },
]

const App = () => {
  const [authed, setAuthed] = useState(false)
  const [booted, setBooted] = useState(false)
  const [view, setView] = useState('ingest')
  const [activeTask, setActiveTask] = useState(null)
  const [stats, setStats] = useState(null)
  const [worker, setWorker] = useState(null)

  useEffect(() => {
    setAuthed(!!localStorage.getItem('hub_token'))
    setBooted(true)
  }, [])

  useEffect(() => {
    if (!authed) return
    const tick = async () => {
      try {
        const [s, h] = await Promise.all([
          fetch('/api/stats').then(r => r.json()),
          fetch('/api/health').then(r => r.json()),
        ])
        setStats(s); setWorker(h.worker)
      } catch {}
    }
    tick()
    const iv = setInterval(tick, 6000)
    return () => clearInterval(iv)
  }, [authed, view])

  if (!booted) return <div className="min-h-screen bg-background" />
  if (!authed) return <LoginScreen onAuthed={() => setAuthed(true)} />

  const title = {
    ingest: 'Document ingestion',
    monitor: 'Pipeline task monitor',
    catalog: 'Quality assurance workbench',
  }[view] || view

  return (
    <div className="min-h-screen flex bg-background">
      {/* ---- rail ---- */}
      <aside className="w-[236px] shrink-0 border-r border-border flex flex-col">
        <div className="px-5 py-4 border-b border-border">
          <div className="flex items-center gap-2.5">
            <div className="h-8 w-8 rounded-md bg-primary grid place-items-center">
              <Boxes className="h-4 w-4 text-primary-foreground" />
            </div>
            <div className="leading-none">
              <div className="font-serif text-sm tracking-[0.24em]">HOMEART</div>
              <div className="text-[9px] tracking-[0.28em] text-muted-foreground mt-1">DATA HUB</div>
            </div>
          </div>
        </div>

        <nav className="p-2 space-y-0.5">
          {NAV.map(n => (
            <button key={n.id} disabled={!n.ready}
              onClick={() => n.ready && setView(n.id)}
              className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-md text-xs transition-colors
                ${view === n.id ? 'bg-primary/[0.12] text-foreground' : 'text-muted-foreground hover:bg-accent/40 hover:text-foreground'}
                ${!n.ready ? 'opacity-40 cursor-not-allowed' : ''}`}>
              <n.icon className={`h-4 w-4 ${view === n.id ? 'text-primary' : ''}`} />
              <span className="flex-1 text-left">{n.label}</span>
              {!n.ready && <span className="text-[8px] tracking-wider text-muted-foreground">NEXT</span>}
            </button>
          ))}
        </nav>

        <div className="mt-auto p-4 space-y-3 border-t border-border">
          <div className="space-y-1.5">
            {[
              ['Products', stats?.products ?? 0],
              ['Approved', stats?.approved ?? 0],
              ['Flagged', stats?.flagged ?? 0],
              ['Documents', stats?.documents ?? 0],
            ].map(([l, v]) => (
              <div key={l} className="flex items-center justify-between text-[11px]">
                <span className="text-muted-foreground">{l}</span>
                <span className="tabular-nums">{new Intl.NumberFormat().format(v)}</span>
              </div>
            ))}
          </div>
          <div className="flex items-center gap-2 text-[10px]">
            <span className={`h-1.5 w-1.5 rounded-full ${worker?.ok ? 'bg-emerald-400' : 'bg-destructive'}`} />
            <span className="text-muted-foreground">
              DS worker {worker?.ok ? 'online' : 'offline'}
              {worker?.queue ? ` · ${worker.queue} queued` : ''}
            </span>
          </div>
          <Button variant="ghost" size="sm"
            onClick={() => { localStorage.removeItem('hub_token'); setAuthed(false) }}
            className="w-full h-7 text-[11px] text-muted-foreground justify-start px-2">
            <LogOut className="h-3.5 w-3.5 mr-2" /> Sign out
          </Button>
        </div>
      </aside>

      {/* ---- main ---- */}
      <main className="flex-1 min-w-0">
        <header className="h-[73px] border-b border-border px-6 flex items-center justify-between">
          <div>
            <h1 className="font-serif text-xl">{title}</h1>
            <p className="text-[11px] text-muted-foreground mt-0.5">
              Molteni &amp; C · geometric PyMuPDF extraction · micrograd anomaly scoring
            </p>
          </div>
          <div className="flex items-center gap-2">
            {stats?.avg_confidence ? (
              <Badge variant="outline" className="text-[10px] border-emerald-500/40 text-emerald-400">
                mean confidence {(stats.avg_confidence * 100).toFixed(1)}%
              </Badge>
            ) : null}
            <Badge variant="outline" className="text-[10px] border-border text-muted-foreground">
              {stats?.pending ?? 0} pending review
            </Badge>
          </div>
        </header>

        {view === 'ingest' && (
          <IngestPanel onTaskStart={(id) => { setActiveTask(id); setView('monitor') }} />
        )}
        {view === 'monitor' && (
          <TaskMonitor activeTaskId={activeTask} onOpenCatalog={() => setView('catalog')} />
        )}
        {view === 'catalog' && <QaWorkbench />}
      </main>
    </div>
  )
}

export default App
