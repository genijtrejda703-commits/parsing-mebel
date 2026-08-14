'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Loader2, ArrowRight, ScanText, Boxes, Sparkles } from 'lucide-react'

const HERO = 'https://images.unsplash.com/photo-1663811397207-418a92396ad5?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjAzMjV8MHwxfHNlYXJjaHwyfHxsdXh1cnklMjBtb2Rlcm4lMjBpbnRlcmlvcnxlbnwwfHx8YmxhY2t8MTc4NjY5NzA5Mnww&ixlib=rb-4.1.0&q=85'

const FEATURES = [
  [ScanText, 'Геометрический разбор', 'реконструкция вложенных таблиц по bbox и кеглю шрифта'],
  [Sparkles, 'Нейросеть аномалий micrograd', 'отсеивает номера страниц, сноски и размеры чертежей'],
  [Boxes, 'Двойной CLIP, 512 измерений', 'мультиязычный поиск по тексту и по изображению'],
]

const LoginScreen = ({ onAuthed }) => {
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  const submit = async (e) => {
    e?.preventDefault()
    setBusy(true); setErr('')
    try {
      const r = await fetch('/api/auth/login', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password }),
      })
      const d = await r.json()
      if (!r.ok) throw new Error(d.error || 'Доступ запрещён')
      localStorage.setItem('hub_token', d.token)
      onAuthed(d.user)
    } catch (e2) {
      setErr(e2.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="min-h-screen grid lg:grid-cols-[1.15fr_1fr]">
      <div className="relative hidden lg:block overflow-hidden">
        <img src={HERO} alt="" className="absolute inset-0 h-full w-full object-cover" />
        <div className="absolute inset-0 bg-gradient-to-t from-background via-background/70 to-background/30" />
        <div className="absolute inset-0 bg-gradient-to-r from-transparent to-background/90" />
        <div className="relative h-full flex flex-col justify-between p-12">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-md bg-primary/90 grid place-items-center">
              <Boxes className="h-5 w-5 text-primary-foreground" />
            </div>
            <div className="leading-none">
              <div className="font-serif text-lg tracking-[0.28em] text-foreground">HOMEART</div>
              <div className="text-[10px] tracking-[0.3em] text-muted-foreground mt-1">DATA HUB</div>
            </div>
          </div>

          <div className="max-w-lg">
            <h1 className="font-serif text-5xl leading-[1.05] text-foreground">
              Матрицы цен,<br />
              <span className="text-primary">извлечённые геометрически.</span>
            </h1>
            <p className="mt-5 text-sm leading-relaxed text-muted-foreground">
              Собственный движок на PyMuPDF читает прайс-листы премиальной мебели так же,
              как человек — по координатам, а не догадками OCR. Каждая цена привязана
              к заголовку своего столбца и подписи строки, а затем оценена нейросетью micrograd.
            </p>
            <div className="mt-8 grid gap-3">
              {FEATURES.map(([Icon, t, d], i) => (
                <div key={i} className="flex items-start gap-3">
                  <Icon className="h-4 w-4 mt-0.5 text-primary shrink-0" />
                  <div>
                    <div className="text-xs font-medium text-foreground">{t}</div>
                    <div className="text-xs text-muted-foreground">{d}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
          <div className="text-[10px] tracking-widest text-muted-foreground/70">
            MOLTENI &amp; C · DADA · GLISS MASTER · И ЕЩЁ 40+ ФАБРИК
          </div>
        </div>
      </div>

      <div className="flex items-center justify-center p-8 hub-grid">
        <form onSubmit={submit} className="w-full max-w-sm">
          <div className="lg:hidden mb-8 flex items-center gap-3">
            <div className="h-9 w-9 rounded-md bg-primary grid place-items-center">
              <Boxes className="h-5 w-5 text-primary-foreground" />
            </div>
            <div className="font-serif tracking-[0.28em]">HOMEART</div>
          </div>

          <div className="text-xs tracking-[0.28em] text-primary mb-3">ЗАКРЫТЫЙ ДОСТУП</div>
          <h2 className="font-serif text-3xl mb-2">Вход в Data Hub</h2>
          <p className="text-sm text-muted-foreground mb-8">
            Единый мастер-ключ открывает права проверяющего и администратора.
          </p>

          <div className="space-y-2">
            <Label htmlFor="pw" className="text-xs tracking-wider text-muted-foreground">
              МАСТЕР-КЛЮЧ ДОСТУПА
            </Label>
            <Input
              id="pw" type="password" autoFocus value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••••••"
              className="h-11 bg-card/60 border-border focus-visible:ring-primary"
            />
          </div>

          {err && (
            <div className="mt-3 text-xs text-destructive border border-destructive/40 bg-destructive/10 rounded-md px-3 py-2">
              {err}
            </div>
          )}

          <Button type="submit" disabled={busy || !password}
            className="mt-6 w-full h-11 bg-primary text-primary-foreground hover:bg-primary/90 group">
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : (
              <span className="flex items-center gap-2">
                Открыть рабочее пространство
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
              </span>
            )}
          </Button>

          <div className="mt-10 text-[11px] text-muted-foreground/70 leading-relaxed">
            FastAPI DS-сайдкар · PyMuPDF 1.28 · sentence-transformers CLIP ViT-B/32 ·
            autograd micrograd · MongoDB
          </div>
        </form>
      </div>
    </div>
  )
}

export default LoginScreen
