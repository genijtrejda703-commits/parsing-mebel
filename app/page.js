'use client';

import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Separator } from '@/components/ui/separator';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { toast } from 'sonner';
import {
  CloudDownload, Search, ClipboardCheck, LogOut, Loader2, FileText, CheckCircle2,
  XCircle, ImagePlus, Sparkles, Factory, Package, Layers, AlertCircle, Lock,
  UploadCloud, Database, Settings, ChevronLeft, ChevronRight, X, SlidersHorizontal, Play
} from 'lucide-react';

/* ------------------------------ constants ------------------------------ */

const CATEGORY_IMG = {
  'Sofa': 'https://images.unsplash.com/photo-1555041469-a586c61ea9bc?crop=entropy&cs=srgb&fm=jpg&q=85&w=800',
  'Armchair': 'https://images.unsplash.com/photo-1567538096630-e0c55bd6374c?crop=entropy&cs=srgb&fm=jpg&q=85&w=800',
  'Dining Table': 'https://images.unsplash.com/photo-1657524398377-567034729507?crop=entropy&cs=srgb&fm=jpg&q=85&w=800',
  'Coffee Table': 'https://images.unsplash.com/photo-1581428982868-e410dd047a90?crop=entropy&cs=srgb&fm=jpg&q=85&w=800',
  'Chair': 'https://images.unsplash.com/photo-1580480055273-228ff5388ef8?crop=entropy&cs=srgb&fm=jpg&q=85&w=800',
  'Bed': 'https://images.unsplash.com/photo-1617325247661-675ab4b64ae2?crop=entropy&cs=srgb&fm=jpg&q=85&w=800',
  'Sideboard': 'https://images.unsplash.com/photo-1718524767499-7fe3a6ab4f8c?crop=entropy&cs=srgb&fm=jpg&q=85&w=800',
  'Bookcase': 'https://images.unsplash.com/photo-1593430980369-68efc5a5eb34?crop=entropy&cs=srgb&fm=jpg&q=85&w=800',
  'Wardrobe': 'https://images.unsplash.com/photo-1672137233327-37b0c1049e77?crop=entropy&cs=srgb&fm=jpg&q=85&w=800',
};
const catImg = (c) => CATEGORY_IMG[c] || CATEGORY_IMG['Sofa'];

const fmtPrice = (v) => (v === null || v === undefined) ? '—'
  : new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(v);
const fmtDate = (v) => (v ? new Date(v).toLocaleString('ru-RU', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) : '—');
const matchPct = (distance) => Math.max(0, Math.min(100, ((2 - distance) / 2) * 100));

const TASK_META = {
  queued: { dot: '⚪', label: 'Queued', cls: 'bg-zinc-100 text-zinc-600 border-zinc-200' },
  downloading: { dot: '🟡', label: 'Downloading', cls: 'bg-amber-50 text-amber-700 border-amber-200' },
  parsing: { dot: '🔵', label: 'PDF Spatial Parsing', cls: 'bg-blue-50 text-blue-700 border-blue-200' },
  embedding: { dot: '🟣', label: 'Embedding Gen (512-d)', cls: 'bg-violet-50 text-violet-700 border-violet-200' },
  completed: { dot: '🟢', label: 'Completed', cls: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
  failed: { dot: '🔴', label: 'Failed', cls: 'bg-red-50 text-red-700 border-red-200' },
};

const FACTORY_STATUS = {
  pending: { label: 'Ожидание', cls: 'bg-zinc-100 text-zinc-600 border-zinc-200' },
  syncing: { label: 'Синхронизация', cls: 'bg-blue-50 text-blue-700 border-blue-200' },
  active: { label: 'Активна', cls: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
  error: { label: 'Ошибка', cls: 'bg-red-50 text-red-700 border-red-200' },
};

function useApi(token, onUnauthorized) {
  return useCallback(async (path, opts = {}) => {
    const headers = { ...(opts.headers || {}) };
    if (token) headers['Authorization'] = `Bearer ${token}`;
    if (opts.body && !(opts.body instanceof FormData)) headers['Content-Type'] = 'application/json';
    const res = await fetch(`/api${path}`, { ...opts, headers });
    if (res.status === 401) { onUnauthorized?.(); throw new Error('Сессия истекла'); }
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data?.detail || `Ошибка ${res.status}`);
    return data;
  }, [token, onUnauthorized]);
}

/* ------------------------------ login ------------------------------ */

function LoginView({ onLogin }) {
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || 'Ошибка входа');
      onLogin(data.token);
    } catch (err) { toast.error(err.message); }
    finally { setLoading(false); }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-zinc-50">
      <div className="w-full max-w-sm px-6">
        <div className="rounded-2xl border border-zinc-200 bg-white p-8 shadow-[0_1px_3px_rgba(0,0,0,0.05),0_20px_40px_-20px_rgba(0,0,0,0.1)]">
          <div className="mb-7 flex flex-col items-center">
            <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-zinc-900">
              <Database className="h-5 w-5 text-white" />
            </div>
            <h1 className="text-lg font-semibold tracking-tight">System Access</h1>
            <p className="mt-1 text-xs text-zinc-400">HOMEART Data Hub</p>
          </div>
          <form onSubmit={submit} className="space-y-3">
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-400" />
              <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter .env password" className="h-10 pl-9" data-testid="login-password" required />
            </div>
            <Button type="submit" className="h-10 w-full bg-zinc-900 text-white hover:bg-zinc-800" disabled={loading} data-testid="login-submit">
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Authenticate'}
            </Button>
          </form>
        </div>
        <p className="mt-5 text-center text-[11px] text-zinc-400">PostgreSQL · pgvector · FastAPI · Celery · Dropbox API v2</p>
      </div>
    </div>
  );
}

/* ------------------------------ task monitor card ------------------------------ */

function TaskCard({ task }) {
  const meta = TASK_META[task.status] || TASK_META.queued;
  const progress = task.status === 'completed' ? 100 : (task.progress || 0);
  const active = !['completed', 'failed'].includes(task.status);
  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-4 shadow-sm transition-shadow hover:shadow-md" data-testid="task-card">
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold">{task.factory_name || '—'}</p>
          <p className="mt-0.5 font-mono text-[10px] text-zinc-400">{task.id?.slice(0, 8)} · {task.source === 'dropbox' ? 'Dropbox' : 'Manual upload'} · {fmtDate(task.created_at)}</p>
        </div>
        <Badge variant="outline" className={`${meta.cls} shrink-0 gap-1 font-normal`}>
          <span>{meta.dot}</span> {meta.label}{task.status === 'downloading' ? ` (${progress}%)` : ''}
        </Badge>
      </div>
      <div className="mt-3">
        <Progress value={progress} className={`h-1.5 ${active ? 'animate-pulse' : ''}`} />
        <div className="mt-1.5 flex items-center justify-between text-[11px] text-zinc-500">
          <span className="truncate" data-testid="task-message">{task.error || task.message || '—'}</span>
          <span className="tabular-nums">{progress}%</span>
        </div>
      </div>
      {task.stats?.products_created !== undefined && (
        <p className="mt-2 text-[11px] text-zinc-500">
          PDF: <span className="font-medium text-zinc-800">{task.stats.files_processed}</span> ·
          товаров: <span className="font-medium text-zinc-800">{task.stats.products_created}</span>
        </p>
      )}
    </div>
  );
}

/* ------------------------------ ingestion (main dashboard) ------------------------------ */

function IngestionView({ api, token }) {
  const [factoryName, setFactoryName] = useState('');
  const [dropboxUrl, setDropboxUrl] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [uploadFactory, setUploadFactory] = useState('');
  const [uploading, setUploading] = useState(false);
  const [showUpload, setShowUpload] = useState(false);
  const [tasks, setTasks] = useState([]);
  const [liveTask, setLiveTask] = useState(null);
  const [stats, setStats] = useState(null);
  const fileRef = useRef(null);
  const esRef = useRef(null);
  const pollRef = useRef(null);

  const loadTasks = useCallback(async () => {
    try { setTasks(await api('/ingest/tasks')); } catch (e) { /* silent */ }
  }, [api]);
  const loadStats = useCallback(async () => {
    try { setStats(await api('/stats')); } catch (e) { /* silent */ }
  }, [api]);

  useEffect(() => {
    loadTasks(); loadStats();
    const t = setInterval(() => { loadTasks(); loadStats(); }, 5000);
    return () => clearInterval(t);
  }, [loadTasks, loadStats]);

  const stopWatch = () => {
    esRef.current?.close(); esRef.current = null;
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
  };

  const startPolling = useCallback((taskId) => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const t = await api(`/ingest/tasks/${taskId}`);
        setLiveTask(t);
        if (['completed', 'failed'].includes(t.status)) {
          clearInterval(pollRef.current); pollRef.current = null;
          loadTasks(); loadStats();
          t.status === 'completed' ? toast.success('Pipeline completed') : toast.error(`Ошибка: ${t.error || 'неизвестно'}`);
        }
      } catch (e) { /* keep polling */ }
    }, 2000);
  }, [api, loadTasks, loadStats]);

  const watchTask = useCallback((taskId) => {
    stopWatch();
    try {
      const es = new EventSource(`/api/ingest/tasks/${taskId}/stream?token=${encodeURIComponent(token)}`);
      esRef.current = es;
      es.onmessage = (e) => {
        const t = JSON.parse(e.data);
        setLiveTask((prev) => ({ ...prev, ...t }));
        if (['completed', 'failed'].includes(t.status)) {
          es.close(); esRef.current = null; loadTasks(); loadStats();
          t.status === 'completed' ? toast.success('Pipeline completed') : toast.error(`Ошибка: ${t.error || 'неизвестно'}`);
        }
      };
      es.onerror = () => { es.close(); esRef.current = null; startPolling(taskId); };
    } catch { startPolling(taskId); }
  }, [token, loadTasks, loadStats, startPolling]);

  useEffect(() => () => stopWatch(), []);

  const runPipeline = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const res = await api('/ingest/dropbox', { method: 'POST', body: JSON.stringify({ factory_name: factoryName, dropbox_url: dropboxUrl }) });
      toast.success(`Task queued · ${res.task_id.slice(0, 8)}`);
      setLiveTask({ id: res.task_id, status: 'queued', progress: 0, message: 'Queued', factory_name: factoryName, source: 'dropbox' });
      watchTask(res.task_id);
      loadTasks();
    } catch (err) { toast.error(err.message); }
    finally { setSubmitting(false); }
  };

  const submitUpload = async (e) => {
    e.preventDefault();
    const files = fileRef.current?.files;
    if (!files || files.length === 0) { toast.error('Выберите PDF-файлы'); return; }
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append('factory_name', uploadFactory);
      for (const f of files) fd.append('files', f);
      const res = await api('/ingest/upload', { method: 'POST', body: fd });
      toast.success(`Загружено файлов: ${res.files_saved}`);
      setLiveTask({ id: res.task_id, status: 'queued', progress: 0, message: 'Queued', factory_name: uploadFactory, source: 'manual' });
      watchTask(res.task_id);
      loadTasks();
    } catch (err) { toast.error(err.message); }
    finally { setUploading(false); }
  };

  const monitorTasks = useMemo(() => {
    const list = [...tasks];
    if (liveTask) {
      const i = list.findIndex((t) => t.id === liveTask.id);
      if (i >= 0) list[i] = { ...list[i], ...liveTask }; else list.unshift(liveTask);
    }
    return list.slice(0, 8);
  }, [tasks, liveTask]);

  const chips = [
    { icon: Factory, label: 'Фабрики', value: stats?.factories },
    { icon: Layers, label: 'Коллекции', value: stats?.collections },
    { icon: Package, label: 'Товары', value: stats?.products },
    { icon: ClipboardCheck, label: 'На QA', value: stats?.pending_qa },
  ];

  return (
    <div className="space-y-8">
      <div className="flex items-end justify-between">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">Data Ingestion</h2>
          <p className="mt-1 text-sm text-zinc-500">Dropbox → пространственный парсинг PDF → эмбеддинги → каталог</p>
        </div>
        <div className="flex gap-2">
          {chips.map((c) => (
            <div key={c.label} className="flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 shadow-sm">
              <c.icon className="h-3.5 w-3.5 text-zinc-400" />
              <span className="text-xs text-zinc-500">{c.label}</span>
              <span className="text-sm font-semibold tabular-nums">{c.value ?? '·'}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm">
        <form onSubmit={runPipeline} className="flex flex-wrap items-end gap-3">
          <div className="w-52 space-y-1.5">
            <Label className="text-xs text-zinc-500">Фабрика</Label>
            <Input value={factoryName} onChange={(e) => setFactoryName(e.target.value)} placeholder="Molteni & C" className="h-11" required data-testid="ingest-factory-name" />
          </div>
          <div className="min-w-[280px] flex-1 space-y-1.5">
            <Label className="text-xs text-zinc-500">Dropbox shared link (public, rlkey)</Label>
            <div className="relative">
              <CloudDownload className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-400" />
              <Input value={dropboxUrl} onChange={(e) => setDropboxUrl(e.target.value)} placeholder="https://www.dropbox.com/scl/fo/...?rlkey=..." className="h-11 pl-10" required data-testid="ingest-dropbox-url" />
            </div>
          </div>
          <Button type="submit" className="h-11 bg-zinc-900 px-6 text-white hover:bg-zinc-800" disabled={submitting} data-testid="ingest-submit">
            {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <><Play className="mr-2 h-4 w-4" /> Run Parsing Pipeline</>}
          </Button>
        </form>
        <button onClick={() => setShowUpload((v) => !v)} className="mt-4 flex items-center gap-1.5 text-xs text-zinc-500 transition-colors hover:text-zinc-800" data-testid="toggle-upload">
          <UploadCloud className="h-3.5 w-3.5" /> {showUpload ? 'Скрыть ручную загрузку' : 'Ссылка недоступна? Загрузите PDF вручную (fallback)'}
        </button>
        {showUpload && (
          <form onSubmit={submitUpload} className="mt-3 flex flex-wrap items-end gap-3 rounded-xl border border-dashed border-zinc-300 bg-zinc-50 p-4">
            <div className="w-52 space-y-1.5">
              <Label className="text-xs text-zinc-500">Фабрика</Label>
              <Input value={uploadFactory} onChange={(e) => setUploadFactory(e.target.value)} placeholder="Poliform" required data-testid="upload-factory-name" />
            </div>
            <div className="min-w-[240px] flex-1 space-y-1.5">
              <Label className="text-xs text-zinc-500">PDF-файлы</Label>
              <Input ref={fileRef} type="file" accept=".pdf" multiple className="cursor-pointer bg-white file:mr-3 file:rounded-md file:border-0 file:bg-zinc-100 file:px-3 file:py-1 file:text-xs" data-testid="upload-files" />
            </div>
            <Button type="submit" variant="outline" disabled={uploading} data-testid="upload-submit">
              {uploading ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Загрузить и обработать'}
            </Button>
          </form>
        )}
      </div>

      <div>
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-semibold uppercase tracking-wider text-zinc-500">Task Monitor</h3>
          <span className="text-[11px] text-zinc-400">live · SSE + polling fallback</span>
        </div>
        {monitorTasks.length === 0 ? (
          <div className="flex flex-col items-center rounded-2xl border border-dashed border-zinc-300 py-12 text-zinc-400">
            <CloudDownload className="mb-2 h-8 w-8" />
            <p className="text-sm">Задач пока нет — вставьте Dropbox-ссылку и запустите конвейер</p>
          </div>
        ) : (
          <div className="grid gap-3 md:grid-cols-2">
            {monitorTasks.map((t) => <TaskCard key={t.id} task={t} />)}
          </div>
        )}
      </div>
    </div>
  );
}

/* ------------------------------ QA review (split-screen) ------------------------------ */

function QAReviewView({ api, token }) {
  const [products, setProducts] = useState([]);
  const [idx, setIdx] = useState(0);
  const [loading, setLoading] = useState(true);
  const [acting, setActing] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const rows = await api('/qa/products?status=pending&limit=200');
      setProducts(rows); setIdx(0);
    } catch (e) { toast.error(e.message); }
    finally { setLoading(false); }
  }, [api]);

  useEffect(() => { load(); }, [load]);

  const current = products[idx];
  const pdfUrl = useMemo(() => {
    if (!current?.task_id || !current?.source_file) return null;
    const path = current.source_file.split('/').map(encodeURIComponent).join('/');
    return `/api/files/${current.task_id}/${path}?token=${encodeURIComponent(token)}#page=${current.source_page || 1}`;
  }, [current, token]);

  const review = async (action) => {
    if (!current) return;
    setActing(true);
    try {
      await api(`/qa/products/${current.id}/review`, { method: 'POST', body: JSON.stringify({ action }) });
      toast.success(action === 'approve' ? 'Опубликовано в каталог' : 'Отправлено на ручную правку');
      setProducts((ps) => {
        const next = ps.filter((p) => p.id !== current.id);
        setIdx((i) => Math.min(i, Math.max(0, next.length - 1)));
        return next;
      });
    } catch (e) { toast.error(e.message); }
    finally { setActing(false); }
  };

  if (loading) return <div className="flex justify-center py-24"><Loader2 className="h-6 w-6 animate-spin text-zinc-400" /></div>;

  if (!current) return (
    <div className="space-y-6">
      <h2 className="text-2xl font-semibold tracking-tight">QA Review</h2>
      <div className="flex flex-col items-center rounded-2xl border border-dashed border-zinc-300 py-20 text-zinc-400">
        <CheckCircle2 className="mb-3 h-10 w-10 text-emerald-400" />
        <p className="text-sm font-medium text-zinc-600">Все позиции проверены</p>
        <p className="mt-1 text-xs">Новые товары появятся здесь после следующего инжеста</p>
      </div>
    </div>
  );

  const matrix = current.variations_metadata?.price_matrix || {};
  const finishes = current.variations_metadata?.finishes || [];

  return (
    <div className="flex h-[calc(100vh-4rem)] flex-col space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">QA Review</h2>
          <p className="mt-0.5 text-sm text-zinc-500">Сверка извлечённых данных с исходным PDF</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => setIdx((i) => Math.max(0, i - 1))} disabled={idx === 0} data-testid="qa-prev">
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span className="text-sm tabular-nums text-zinc-500" data-testid="qa-counter">{idx + 1} из {products.length}</span>
          <Button variant="outline" size="sm" onClick={() => setIdx((i) => Math.min(products.length - 1, i + 1))} disabled={idx >= products.length - 1} data-testid="qa-next">
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <div className="grid min-h-0 flex-1 gap-4 lg:grid-cols-[1.2fr_1fr]">
        <div className="overflow-hidden rounded-2xl border border-zinc-200 bg-zinc-100 shadow-sm">
          {pdfUrl ? (
            <iframe key={pdfUrl} src={pdfUrl} className="h-full w-full" title="Source PDF" data-testid="qa-pdf-frame" />
          ) : (
            <div className="flex h-full flex-col items-center justify-center text-zinc-400">
              <FileText className="mb-2 h-8 w-8" />
              <p className="text-sm">PDF недоступен (временное хранилище очищено)</p>
            </div>
          )}
        </div>

        <div className="flex min-h-0 flex-col overflow-hidden rounded-2xl border border-zinc-200 bg-white shadow-sm">
          <div className="min-h-0 flex-1 overflow-y-auto p-6">
            <p className="text-[11px] font-medium uppercase tracking-widest text-zinc-400">{current.factory_name}</p>
            <h3 className="mt-1 text-xl font-semibold tracking-tight" data-testid="qa-model-name">{current.model_name}</h3>
            <p className="mt-0.5 text-sm text-zinc-500">{current.collection_name} · {current.designer_name || 'дизайнер не указан'}</p>

            <div className="mt-5 grid grid-cols-2 gap-3">
              <div className="rounded-lg bg-zinc-50 p-3">
                <p className="text-[10px] uppercase tracking-wider text-zinc-400">Категория</p>
                <p className="mt-0.5 text-sm font-medium">{current.category || '—'}</p>
              </div>
              <div className="rounded-lg bg-zinc-50 p-3">
                <p className="text-[10px] uppercase tracking-wider text-zinc-400">Габариты</p>
                <p className="mt-0.5 text-sm font-medium">{current.dimensions_raw || '—'}</p>
              </div>
              <div className="rounded-lg bg-zinc-50 p-3">
                <p className="text-[10px] uppercase tracking-wider text-zinc-400">Базовая цена</p>
                <p className="mt-0.5 text-sm font-semibold">{fmtPrice(current.base_price)}</p>
              </div>
              <div className="rounded-lg bg-zinc-50 p-3">
                <p className="text-[10px] uppercase tracking-wider text-zinc-400">Источник</p>
                <p className="mt-0.5 truncate text-xs font-medium" title={current.source_file}>стр. {current.source_page || 1} · {current.source_file?.split('/').pop()}</p>
              </div>
            </div>

            {Object.keys(matrix).length > 0 && (
              <div className="mt-5">
                <p className="mb-2 text-[10px] font-medium uppercase tracking-wider text-zinc-400">Матрица цен (комплектации)</p>
                <div className="overflow-hidden rounded-lg border border-zinc-200">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-zinc-50 text-left text-[11px] uppercase tracking-wider text-zinc-400">
                        <th className="px-3 py-2 font-medium">Комплектация</th>
                        <th className="px-3 py-2 text-right font-medium">Цена</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(matrix).map(([k, v]) => (
                        <tr key={k} className="border-t border-zinc-100">
                          <td className="px-3 py-2 text-zinc-600">{k}</td>
                          <td className="px-3 py-2 text-right font-medium tabular-nums">{fmtPrice(v)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {finishes.length > 0 && (
              <div className="mt-4">
                <p className="mb-2 text-[10px] font-medium uppercase tracking-wider text-zinc-400">Отделки</p>
                <div className="flex flex-wrap gap-1.5">
                  {finishes.map((f) => <Badge key={f} variant="outline" className="border-zinc-200 bg-zinc-50 font-normal text-zinc-600">{f}</Badge>)}
                </div>
              </div>
            )}
          </div>

          <div className="grid grid-cols-2 gap-3 border-t border-zinc-100 p-4">
            <Button className="h-11 bg-zinc-900 text-white hover:bg-zinc-800" onClick={() => review('approve')} disabled={acting} data-testid="qa-approve">
              <CheckCircle2 className="mr-2 h-4 w-4" /> Approve & Publish
            </Button>
            <Button variant="outline" className="h-11 border-red-200 text-red-600 hover:bg-red-50" onClick={() => review('reject')} disabled={acting} data-testid="qa-reject">
              <XCircle className="mr-2 h-4 w-4" /> Edit / Reject
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------ vector search hub ------------------------------ */

function VectorSearchView({ api }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState(null);
  const [mode, setMode] = useState(null); // 'semantic' | 'visual' | 'fulltext'
  const [loading, setLoading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [showFilters, setShowFilters] = useState(false);
  const [factories, setFactories] = useState([]);
  const [factoryId, setFactoryId] = useState('');
  const [designer, setDesigner] = useState('');
  const fileRef = useRef(null);

  useEffect(() => { api('/factories').then(setFactories).catch(() => {}); }, [api]);

  const runSemantic = async (e) => {
    e?.preventDefault();
    if (!query.trim()) return;
    setLoading(true); setMode('semantic'); setPreviewUrl(null);
    try { setResults(await api('/search/semantic', { method: 'POST', body: JSON.stringify({ query, limit: 12 }) })); }
    catch (err) { toast.error(err.message); }
    finally { setLoading(false); }
  };

  const runVisual = async (file) => {
    if (!file || !file.type?.startsWith('image/')) { toast.error('Перетащите изображение (PNG/JPG)'); return; }
    setLoading(true); setMode('visual');
    setPreviewUrl(URL.createObjectURL(file));
    try {
      const fd = new FormData();
      fd.append('image', file);
      setResults(await api('/search/visual', { method: 'POST', body: fd }));
    } catch (err) { toast.error(err.message); }
    finally { setLoading(false); }
  };

  const runFulltext = async (e) => {
    e?.preventDefault();
    setLoading(true); setMode('fulltext'); setPreviewUrl(null);
    try {
      const params = new URLSearchParams({ q: query, factory_id: factoryId, designer });
      setResults(await api(`/search?${params}`));
    } catch (err) { toast.error(err.message); }
    finally { setLoading(false); }
  };

  return (
    <div className="space-y-8">
      <div className="mx-auto max-w-3xl pt-6 text-center">
        <h2 className="text-2xl font-semibold tracking-tight">Vector Search</h2>
        <p className="mt-1 text-sm text-zinc-500">Семантический и визуальный поиск на pgvector · 512-d CLIP-эмбеддинги</p>

        <form onSubmit={runSemantic} className="mt-6">
          <div
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => { e.preventDefault(); setDragOver(false); runVisual(e.dataTransfer.files?.[0]); }}
            className={`relative rounded-2xl border-2 bg-white shadow-[0_2px_8px_rgba(0,0,0,0.04),0_12px_32px_-12px_rgba(0,0,0,0.1)] transition-all duration-200
              ${dragOver ? 'border-dashed border-zinc-900 bg-zinc-50 scale-[1.01]' : 'border-transparent'}`}
            data-testid="smart-search-zone">
            <Search className="pointer-events-none absolute left-5 top-1/2 h-5 w-5 -translate-y-1/2 text-zinc-400" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Опишите мебель текстом или перетащите сюда рендер..."
              className="h-16 w-full rounded-2xl bg-transparent pl-14 pr-28 text-base outline-none placeholder:text-zinc-400"
              data-testid="smart-search-input"
            />
            <div className="absolute right-3 top-1/2 flex -translate-y-1/2 items-center gap-1.5">
              <button type="button" onClick={() => fileRef.current?.click()}
                className="flex h-10 w-10 items-center justify-center rounded-xl text-zinc-400 transition-colors hover:bg-zinc-100 hover:text-zinc-700"
                title="Загрузить референс" data-testid="visual-upload-btn">
                <ImagePlus className="h-5 w-5" />
              </button>
              <Button type="submit" className="h-10 rounded-xl bg-zinc-900 px-4 text-white hover:bg-zinc-800" disabled={loading} data-testid="smart-search-submit">
                {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
              </Button>
            </div>
            <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={(e) => runVisual(e.target.files?.[0])} data-testid="visual-input" />
          </div>
        </form>

        {previewUrl && (
          <div className="mt-3 inline-flex items-center gap-2 rounded-full border border-zinc-200 bg-white py-1 pl-1 pr-3 shadow-sm">
            <img src={previewUrl} alt="ref" className="h-7 w-7 rounded-full object-cover" />
            <span className="text-xs text-zinc-500">Визуальный поиск по референсу</span>
            <button onClick={() => { setPreviewUrl(null); setResults(null); setMode(null); }} className="text-zinc-400 hover:text-zinc-700"><X className="h-3.5 w-3.5" /></button>
          </div>
        )}

        <button onClick={() => setShowFilters((v) => !v)} className="mx-auto mt-4 flex items-center gap-1.5 text-xs text-zinc-400 transition-colors hover:text-zinc-700" data-testid="toggle-filters">
          <SlidersHorizontal className="h-3.5 w-3.5" /> Классический поиск по фильтрам
        </button>
        {showFilters && (
          <form onSubmit={runFulltext} className="mx-auto mt-3 flex max-w-xl flex-wrap items-center justify-center gap-2">
            <select value={factoryId} onChange={(e) => setFactoryId(e.target.value)}
              className="h-9 rounded-md border border-zinc-200 bg-white px-3 text-sm shadow-sm focus:outline-none" data-testid="filter-factory">
              <option value="">Все фабрики</option>
              {factories.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
            </select>
            <Input value={designer} onChange={(e) => setDesigner(e.target.value)} placeholder="Дизайнер" className="h-9 w-40" data-testid="filter-designer" />
            <Button type="submit" variant="outline" size="sm" className="h-9" data-testid="filter-submit">Найти по каталогу</Button>
          </form>
        )}
      </div>

      {results && (
        <div>
          <p className="mb-4 text-xs text-zinc-400">
            {mode === 'semantic' && <>Семантическая выдача · косинусное расстояние <span className="font-mono">&lt;=&gt;</span> pgvector</>}
            {mode === 'visual' && <>Визуально похожие модели · image_embedding <span className="font-mono">&lt;=&gt;</span></>}
            {mode === 'fulltext' && <>Полнотекстовый поиск по каталогу</>}
            {' '}· {results.length} результатов
          </p>
          {results.length === 0 ? (
            <p className="py-10 text-center text-sm text-zinc-400">Ничего не найдено</p>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {results.map((p) => (
                <div key={p.id} className="group overflow-hidden rounded-2xl border border-zinc-200 bg-white shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lg" data-testid="search-result-card">
                  <div className="relative aspect-[4/3] overflow-hidden bg-zinc-100">
                    <img src={catImg(p.category)} alt={p.category || 'furniture'} loading="lazy"
                      className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105" />
                    {p.distance !== undefined && (
                      <span className="absolute right-2 top-2 rounded-full bg-zinc-900/85 px-2 py-0.5 text-[10px] font-medium text-white backdrop-blur" data-testid="match-badge">
                        Match {matchPct(p.distance).toFixed(0)}%
                      </span>
                    )}
                  </div>
                  <div className="p-4">
                    <p className="truncate font-semibold">{p.model_name}</p>
                    <p className="mt-0.5 truncate text-xs text-zinc-500">{p.factory_name} · {p.collection_name}</p>
                    <div className="mt-2.5 flex items-center justify-between">
                      <span className="text-[11px] text-zinc-400">{p.category || '—'}</span>
                      <span className="text-sm font-semibold">{fmtPrice(p.base_price)}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* ------------------------------ settings ------------------------------ */

function SettingsView({ api }) {
  const [health, setHealth] = useState(null);
  const [factories, setFactories] = useState([]);

  useEffect(() => {
    api('/health').then(setHealth).catch(() => setHealth({ status: 'error', database: 'down' }));
    api('/factories').then(setFactories).catch(() => {});
  }, [api]);

  const stack = [
    ['Frontend', 'Next.js 15 + Tailwind + shadcn/ui'],
    ['Backend', 'Python FastAPI (прокси /api → :8001)'],
    ['Database', 'PostgreSQL 15 + pgvector 0.8 (HNSW, cosine)'],
    ['Task Queue', 'Celery + Redis'],
    ['Ingestion', 'Dropbox API v2 · public links (dl=1, rlkey) · без OAuth'],
    ['Extraction', 'run_extraction_pipeline() — STUB для PyMuPDF + micrograd'],
    ['Embeddings', 'generate_text/image_embedding() — STUB 512-d для CLIP'],
  ];

  return (
    <div className="max-w-3xl space-y-8">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">Settings</h2>
        <p className="mt-1 text-sm text-zinc-500">Состояние системы и конфигурация</p>
      </div>

      <Card className="border-zinc-200 shadow-sm">
        <CardHeader className="pb-3"><CardTitle className="text-base">Статус сервисов</CardTitle></CardHeader>
        <CardContent className="space-y-2">
          <div className="flex items-center justify-between rounded-lg bg-zinc-50 px-4 py-2.5">
            <span className="text-sm text-zinc-600">FastAPI backend</span>
            <Badge variant="outline" className={health?.status === 'ok' ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-red-200 bg-red-50 text-red-700'}>
              {health?.status === 'ok' ? '● online' : '● offline'}
            </Badge>
          </div>
          <div className="flex items-center justify-between rounded-lg bg-zinc-50 px-4 py-2.5">
            <span className="text-sm text-zinc-600">PostgreSQL + pgvector</span>
            <Badge variant="outline" className={health?.database === 'up' ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-red-200 bg-red-50 text-red-700'}>
              {health?.database === 'up' ? '● up' : '● down'}
            </Badge>
          </div>
        </CardContent>
      </Card>

      <Card className="border-zinc-200 shadow-sm">
        <CardHeader className="pb-3"><CardTitle className="text-base">Стек платформы</CardTitle></CardHeader>
        <CardContent>
          <div className="divide-y divide-zinc-100">
            {stack.map(([k, v]) => (
              <div key={k} className="flex items-center justify-between py-2.5">
                <span className="text-xs font-medium uppercase tracking-wider text-zinc-400">{k}</span>
                <span className="text-sm text-zinc-700">{v}</span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card className="border-zinc-200 shadow-sm">
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Реестр фабрик</CardTitle>
          <CardDescription>Статус синхронизаций поставщиков</CardDescription>
        </CardHeader>
        <CardContent>
          {factories.length === 0 ? (
            <p className="py-6 text-center text-sm text-zinc-400">Фабрик пока нет</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead>Название</TableHead>
                  <TableHead>Статус</TableHead>
                  <TableHead className="text-right">Товаров</TableHead>
                  <TableHead>Последняя синхронизация</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {factories.map((f) => {
                  const st = FACTORY_STATUS[f.status] || FACTORY_STATUS.pending;
                  return (
                    <TableRow key={f.id} data-testid="factory-row">
                      <TableCell className="font-medium">{f.name}</TableCell>
                      <TableCell><Badge variant="outline" className={`${st.cls} font-normal`}>{st.label}</Badge></TableCell>
                      <TableCell className="text-right tabular-nums">{f.total_items}</TableCell>
                      <TableCell className="text-zinc-500">{fmtDate(f.last_synced)}</TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

/* ------------------------------ shell ------------------------------ */

const NAV = [
  { key: 'ingestion', label: 'Ingestion', icon: CloudDownload },
  { key: 'qa', label: 'QA Review', icon: ClipboardCheck },
  { key: 'search', label: 'Vector Search', icon: Sparkles },
  { key: 'settings', label: 'Settings', icon: Settings },
];

function App() {
  const [token, setToken] = useState(null);
  const [ready, setReady] = useState(false);
  const [view, setView] = useState('ingestion');

  useEffect(() => {
    setToken(localStorage.getItem('datahub_token'));
    setReady(true);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('datahub_token');
    setToken(null);
  }, []);

  const api = useApi(token, logout);

  if (!ready) return null;
  if (!token) return <LoginView onLogin={(t) => { localStorage.setItem('datahub_token', t); setToken(t); }} />;

  return (
    <div className="flex min-h-screen">
      <aside className="fixed inset-y-0 left-0 z-20 flex w-56 flex-col border-r border-zinc-200 bg-white">
        <div className="flex items-center gap-2.5 px-5 py-5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-zinc-900">
            <Database className="h-4 w-4 text-white" />
          </div>
          <div>
            <p className="text-sm font-semibold leading-none tracking-tight">HOMEART</p>
            <p className="mt-0.5 text-[10px] uppercase tracking-widest text-zinc-400">Data Hub</p>
          </div>
        </div>
        <Separator />
        <nav className="flex-1 space-y-0.5 p-3">
          {NAV.map((item) => (
            <button key={item.key} onClick={() => setView(item.key)}
              className={`flex w-full items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-all duration-150
                ${view === item.key ? 'bg-zinc-100 font-medium text-zinc-900' : 'text-zinc-500 hover:bg-zinc-50 hover:text-zinc-800'}`}
              data-testid={`nav-${item.key}`}>
              <item.icon className="h-4 w-4" />
              {item.label}
            </button>
          ))}
        </nav>
        <div className="p-3">
          <Separator className="mb-3" />
          <button onClick={logout}
            className="flex w-full items-center gap-2.5 rounded-md px-3 py-2 text-sm text-zinc-500 transition-colors hover:bg-zinc-50 hover:text-zinc-800"
            data-testid="logout-btn">
            <LogOut className="h-4 w-4" /> Выйти
          </button>
        </div>
      </aside>

      <main className="ml-56 flex-1">
        <div className="mx-auto max-w-7xl px-8 py-8">
          {view === 'ingestion' && <IngestionView api={api} token={token} />}
          {view === 'qa' && <QAReviewView api={api} token={token} />}
          {view === 'search' && <VectorSearchView api={api} />}
          {view === 'settings' && <SettingsView api={api} />}
        </div>
      </main>
    </div>
  );
}

export default App;
