'use client'

import { useEffect, useRef, useState } from 'react'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { LineChart, Line, ResponsiveContainer, YAxis, Tooltip } from 'recharts'
import {
  Activity, CheckCircle2, XCircle, Loader2, Clock, Layers, Boxes, ShieldAlert,
  Brain, ArrowRight,
} from 'lucide-react'

const statusStyle = {
  queued: 'text-muted-foreground border-border',
  running: 'text-primary border-primary/50',
  done: 'text-emerald-400 border-emerald-500/40',
  error: 'text-destructive border-destructive/50',
}
const levelColor = {
  info: 'text-muted-foreground', success: 'text-emerald-400', error: 'text-destructive',
}

const TaskMonitor = ({ activeTaskId, onOpenCatalog }) => {
  const [tasks, setTasks] = useState([])
  const [sel, setSel] = useState(activeTaskId || null)
  const [task, setTask] = useState(null)
  const logRef = useRef(null)

  useEffect(() => { if (activeTaskId) setSel(activeTaskId) }, [activeTaskId])

  useEffect(() => {
    let stop = false
    const tick = async () => {
      try {
        const d = await (await fetch('/api/tasks')).json()
        if (!stop) {
          setTasks(d.items || [])
          if (!sel && d.items?.length) setSel(d.items[0].id)
        }
      } catch {}
    }
    tick()
    const iv = setInterval(tick, 2500)
    return () => { stop = true; clearInterval(iv) }
  }, [sel])

  useEffect(() => {
    if (!sel) return
    let stop = false
    const tick = async () => {
      try {
        const t = await (await fetch(`/api/tasks/${sel}`)).json()
        if (!stop) setTask(t)
      } catch {}
    }
    tick()
    const iv = setInterval(tick, 1300)
    return () => { stop = true; clearInterval(iv) }
  }, [sel])

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
  }, [task?.events?.length])

  const st = task?.stats || {}
  const loss = (st.micrograd_loss || task?.result?.micrograd?.loss_curve || [])
    .map((v, i) => ({ i, loss: v }))
  const acc = (st.micrograd_acc || [])
  const elapsed = task ?
    Math.max(0, (new Date(task.updated_at) - new Date(task.created_at)) / 1000) : 0

  const tiles = [
    ['Documents', `${st.docs_done ?? 0} / ${st.docs_total ?? (task?.meta?.n ?? 0)}`, Layers],
    ['Products', st.products ?? task?.result?.products ?? 0, Boxes],
    ['Anomalies rejected', st.rejected ?? task?.result?.rejected ?? 0, ShieldAlert],
    ['Elapsed', `${elapsed.toFixed(0)}s`, Clock],
  ]

  return (
    <div className="grid lg:grid-cols-[300px_1fr] h-[calc(100vh-73px)]">
      {/* task list */}
      <div className="border-r border-border hub-scroll overflow-y-auto">
        <div className="px-4 py-3 text-[10px] tracking-widest text-muted-foreground border-b border-border">
          PIPELINE RUNS
        </div>
        {!tasks.length && (
          <div className="p-4 text-xs text-muted-foreground">No runs yet — start one from Ingest.</div>
        )}
        {tasks.map(t => (
          <button key={t.id} onClick={() => setSel(t.id)}
            className={`w-full text-left px-4 py-3 border-b border-border/60 hover:bg-accent/40 transition-colors ${sel === t.id ? 'bg-primary/[0.08] border-l-2 border-l-primary' : ''}`}>
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs truncate">{t.title}</span>
              {t.status === 'running' ? <Loader2 className="h-3 w-3 animate-spin text-primary shrink-0" />
                : t.status === 'done' ? <CheckCircle2 className="h-3 w-3 text-emerald-400 shrink-0" />
                  : t.status === 'error' ? <XCircle className="h-3 w-3 text-destructive shrink-0" />
                    : <Clock className="h-3 w-3 text-muted-foreground shrink-0" />}
            </div>
            <div className="mt-1 flex items-center gap-2">
              <span className="text-[10px] uppercase tracking-wider text-muted-foreground">{t.type}</span>
              <span className="text-[10px] text-muted-foreground">
                {new Date(t.created_at).toLocaleTimeString()}
              </span>
            </div>
            {t.status === 'running' && <Progress value={t.progress} className="h-0.5 mt-2" />}
          </button>
        ))}
      </div>

      {/* detail */}
      <div className="hub-scroll overflow-y-auto p-6 space-y-5">
        {!task ? (
          <div className="text-sm text-muted-foreground">Select a run.</div>
        ) : (
          <>
            <div className="flex items-start justify-between gap-4 flex-wrap">
              <div>
                <div className="flex items-center gap-3">
                  <h2 className="font-serif text-2xl">{task.title}</h2>
                  <Badge variant="outline" className={`text-[10px] ${statusStyle[task.status]}`}>
                    {task.status.toUpperCase()}
                  </Badge>
                </div>
                <p className="text-xs text-muted-foreground mt-1 font-mono">{task.id}</p>
              </div>
              {task.status === 'done' && task.type === 'ingest' && (
                <Button onClick={onOpenCatalog}
                  className="bg-primary text-primary-foreground hover:bg-primary/90">
                  Open QA workbench <ArrowRight className="h-4 w-4 ml-1.5" />
                </Button>
              )}
            </div>

            <div>
              <div className="flex items-center justify-between text-xs mb-1.5">
                <span className="text-muted-foreground flex items-center gap-1.5">
                  <Activity className="h-3.5 w-3.5" /> pipeline progress
                </span>
                <span className="text-primary tabular-nums">{Math.round(task.progress)}%</span>
              </div>
              <Progress value={task.progress} className="h-1.5" />
            </div>

            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
              {tiles.map(([label, val, Icon]) => (
                <Card key={label} className="p-4 bg-card/70 border-border">
                  <div className="flex items-center gap-2 text-[10px] tracking-widest text-muted-foreground">
                    <Icon className="h-3.5 w-3.5" /> {label.toUpperCase()}
                  </div>
                  <div className="mt-2 font-serif text-2xl tabular-nums">{val}</div>
                </Card>
              ))}
            </div>

            {!!loss.length && (
              <Card className="p-5 bg-card/70 border-border">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <Brain className="h-4 w-4 text-primary" />
                    <h3 className="font-serif text-lg">micrograd training</h3>
                  </div>
                  <div className="text-xs text-muted-foreground">
                    MLP(8, [8, 8, 1]) · max-margin loss · reverse-mode autograd
                    {acc.length ? <span className="text-emerald-400 ml-2">
                      acc {(acc[acc.length - 1] * 100).toFixed(0)}%</span> : null}
                  </div>
                </div>
                <div className="h-[130px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={loss}>
                      <YAxis hide domain={[0, 'dataMax']} />
                      <Tooltip contentStyle={{
                        background: 'hsl(30 7% 10%)', border: '1px solid hsl(32 6% 18%)',
                        borderRadius: 8, fontSize: 11,
                      }} />
                      <Line type="monotone" dataKey="loss" stroke="hsl(38 60% 60%)"
                        strokeWidth={2} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </Card>
            )}

            <Card className="bg-[#0b0a09] border-border overflow-hidden">
              <div className="px-4 py-2.5 border-b border-border flex items-center justify-between">
                <span className="text-[10px] tracking-widest text-muted-foreground">LIVE PARSER STREAM</span>
                <span className="text-[10px] text-muted-foreground">{task.events?.length || 0} events</span>
              </div>
              <div ref={logRef} className="hub-scroll h-[300px] overflow-y-auto p-4 font-mono text-[11px] leading-relaxed">
                {(task.events || []).map((e, i) => (
                  <div key={i} className="flex gap-3">
                    <span className="text-muted-foreground/50 shrink-0">
                      {new Date(e.ts).toLocaleTimeString()}
                    </span>
                    <span className={levelColor[e.level] || 'text-muted-foreground'}>{e.msg}</span>
                  </div>
                ))}
                {task.status === 'running' && (
                  <div className="flex gap-2 items-center text-primary mt-1">
                    <Loader2 className="h-3 w-3 animate-spin" /> working…
                  </div>
                )}
              </div>
            </Card>
          </>
        )}
      </div>
    </div>
  )
}

export default TaskMonitor
