import { NextResponse } from 'next/server'
import { MongoClient } from 'mongodb'
import { writeFile, mkdir } from 'fs/promises'
import path from 'path'

export const dynamic = 'force-dynamic'

const WORKER = process.env.PY_WORKER_URL || 'http://localhost:8001'
const DATA_DIR = process.env.DATA_DIR || '/app/data'

let clientPromise
function getClient() {
  if (!clientPromise) clientPromise = new MongoClient(process.env.MONGO_URL).connect()
  return clientPromise
}
async function getDb() {
  const c = await getClient()
  return c.db(process.env.DB_NAME)
}

const ok = (data, init = {}) => NextResponse.json(data, init)
const bad = (msg, code = 400) => NextResponse.json({ error: msg }, { status: code })

async function worker(route, options = {}) {
  const res = await fetch(`${WORKER}${route}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
  })
  if (!res.ok) throw new Error(`worker ${route} -> ${res.status} ${await res.text()}`)
  return res.json()
}

async function handler(request, ctx) {
  const resolved = await ctx.params
  const segs = resolved?.path || []
  const route = '/' + segs.join('/')
  const method = request.method
  const url = new URL(request.url)
  const qp = url.searchParams

  try {
    const db = await getDb()

    // ---------------- auth ----------------
    if (route === '/auth/login' && method === 'POST') {
      const { password } = await request.json()
      if (!password || password !== process.env.MASTER_PASSWORD) return bad('Неверный ключ доступа', 401)
      return ok({
        token: Buffer.from(`hub:${Date.now()}`).toString('base64'),
        user: { name: 'Проверяющий', role: 'admin' },
      })
    }

    // ---------------- health / stats ----------------
    if (route === '/health' && method === 'GET') {
      let w = null
      try { w = await worker('/health') } catch (e) { w = { ok: false, error: String(e.message) } }
      return ok({ ok: true, worker: w })
    }

    if (route === '/stats' && method === 'GET') {
      const P = db.collection('products')
      const [total, approved, pending, rejected, docs, facs, emb] = await Promise.all([
        P.countDocuments({}), P.countDocuments({ status: 'approved' }),
        P.countDocuments({ status: 'pending' }), P.countDocuments({ status: 'rejected' }),
        db.collection('documents').countDocuments({}),
        db.collection('factories').countDocuments({}),
        db.collection('product_embeddings').countDocuments({}),
      ])
      const agg = await P.aggregate([
        { $group: { _id: null, conf: { $avg: '$confidence' }, flagged: { $sum: { $cond: ['$anomaly', 1, 0] } } } },
      ]).toArray()
      return ok({
        products: total, approved, pending, rejected, documents: docs, factories: facs,
        embeddings: emb, avg_confidence: agg[0]?.conf || 0, flagged: agg[0]?.flagged || 0,
      })
    }

    // ---------------- pipeline control (proxy to DS sidecar) ----------------
    if (route === '/scan' && method === 'POST') {
      const body = await request.json()
      return ok(await worker('/scan', { method: 'POST', body: JSON.stringify(body) }))
    }
    if (route === '/ingest' && method === 'POST') {
      const body = await request.json()
      return ok(await worker('/ingest', { method: 'POST', body: JSON.stringify(body) }))
    }
    if (route === '/embed' && method === 'POST') {
      const body = await request.json().catch(() => ({}))
      return ok(await worker('/embed', { method: 'POST', body: JSON.stringify(body) }))
    }
    if (route === '/search' && method === 'POST') {
      const ct = request.headers.get('content-type') || ''
      if (ct.includes('multipart/form-data')) {
        const form = await request.formData()
        const res = await fetch(`${WORKER}/search`, { method: 'POST', body: form })
        return ok(await res.json())
      }
      const body = await request.json()
      return ok(await worker('/search', { method: 'POST', body: JSON.stringify(body) }))
    }

    // ---------------- tasks ----------------
    if (route === '/tasks' && method === 'GET') {
      const items = await db.collection('tasks')
        .find({}, { projection: { _id: 0, events: 0 } })
        .sort({ created_at: -1 }).limit(25).toArray()
      return ok({ items })
    }
    if (segs[0] === 'tasks' && segs[1] && method === 'GET') {
      const t = await db.collection('tasks').findOne({ id: segs[1] }, { projection: { _id: 0 } })
      if (!t) return bad('task not found', 404)
      return ok(t)
    }

    // ---------------- documents / factories ----------------
    if (route === '/documents' && method === 'GET') {
      const items = await db.collection('documents')
        .find({}, { projection: { _id: 0 } }).sort({ created_at: -1 }).toArray()
      return ok({ items })
    }
    if (route === '/factories' && method === 'GET') {
      const items = await db.collection('factories').find({}, { projection: { _id: 0 } }).toArray()
      return ok({ items })
    }

    // ---------------- products ----------------
    if (route === '/products/models' && method === 'GET') {
      const q = {}
      if (qp.get('doc_id')) q.doc_id = qp.get('doc_id')
      const rows = await db.collection('products').aggregate([
        { $match: q },
        { $group: { _id: '$model_name', n: { $sum: 1 }, min: { $min: '$price_min' }, max: { $max: '$price_max' } } },
        { $sort: { n: -1 } }, { $limit: 200 },
      ]).toArray()
      return ok({ items: rows.map(r => ({ model: r._id, n: r.n, min: r.min, max: r.max })) })
    }

    if (route === '/products/bulk' && method === 'POST') {
      const { ids, status } = await request.json()
      if (!Array.isArray(ids) || !status) return bad('ids and status required')
      const r = await db.collection('products').updateMany(
        { id: { $in: ids } }, { $set: { status, updated_at: new Date().toISOString() } })
      return ok({ modified: r.modifiedCount })
    }

    if (route === '/products' && method === 'GET') {
      const q = {}
      if (qp.get('doc_id')) q.doc_id = qp.get('doc_id')
      if (qp.get('status') && qp.get('status') !== 'all') q.status = qp.get('status')
      if (qp.get('model')) q.model_name = qp.get('model')
      if (qp.get('flagged') === 'true') q.anomaly = true
      const minVar = parseInt(qp.get('min_var') || '0')
      if (minVar > 0) q.n_variations = { $gte: minVar }
      const minConf = parseFloat(qp.get('min_conf') || '0')
      if (minConf > 0) q.confidence = { $gte: minConf }
      const term = (qp.get('q') || '').trim()
      if (term) {
        const rx = new RegExp(term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'i')
        q.$or = [{ model_name: rx }, { category: rx }, { dimension: rx }, { variant_code: rx }]
      }
      const sortKey = qp.get('sort') || 'best'
      const sortSpec = sortKey === 'page' ? { page: 1, confidence: -1 }
        : sortKey === 'price' ? { price_max: -1, confidence: -1 }
          : { confidence: -1, n_variations: -1, page: 1 }
      const limit = Math.min(parseInt(qp.get('limit') || '60'), 300)
      const skip = parseInt(qp.get('skip') || '0')
      const P = db.collection('products')
      const [items, total] = await Promise.all([
        P.find(q, { projection: { _id: 0 } })
          .sort(sortSpec).skip(skip).limit(limit).toArray(),
        P.countDocuments(q),
      ])
      return ok({ items, total, skip, limit })
    }

    if (segs[0] === 'products' && segs[1] && method === 'GET') {
      const p = await db.collection('products').findOne({ id: segs[1] }, { projection: { _id: 0 } })
      if (!p) return bad('product not found', 404)
      return ok(p)
    }

    if (segs[0] === 'products' && segs[1] && (method === 'PATCH' || method === 'PUT')) {
      const body = await request.json()
      const allow = ['status', 'reviewer_notes', 'model_name', 'category', 'dimension',
        'variant_code', 'price_min', 'price_max', 'currency', 'collection']
      const $set = { updated_at: new Date().toISOString() }
      for (const k of allow) if (k in body) $set[k] = body[k]
      if (Array.isArray(body.variations)) $set.variations = body.variations
      await db.collection('products').updateOne({ id: segs[1] }, { $set })
      const fresh = await db.collection('products').findOne({ id: segs[1] }, { projection: { _id: 0 } })
      return ok(fresh || {})
    }

    // ---------------- page raster (proxied from PyMuPDF) ----------------
    if (route === '/page-image' && method === 'GET') {
      const res = await fetch(`${WORKER}/page-image?doc_id=${qp.get('doc_id')}&page=${qp.get('page')}&dpi=${qp.get('dpi') || 120}`)
      if (!res.ok) return bad('render failed', res.status)
      const buf = await res.arrayBuffer()
      return new Response(buf, {
        headers: { 'Content-Type': 'image/png', 'Cache-Control': 'public, max-age=86400' },
      })
    }

    // ---------------- direct PDF upload ----------------
    if (route === '/upload' && method === 'POST') {
      const form = await request.formData()
      const files = form.getAll('files')
      const dir = path.join(DATA_DIR, 'uploads')
      await mkdir(dir, { recursive: true })
      const saved = []
      for (const f of files) {
        if (!f || typeof f === 'string') continue
        const safe = f.name.replace(/[^\w.\-]+/g, '_')
        const dest = path.join(dir, safe)
        await writeFile(dest, Buffer.from(await f.arrayBuffer()))
        saved.push({ name: safe, path: dest, size: f.size })
      }
      return ok({ files: saved })
    }

    return bad(`no route for ${method} ${route}`, 404)
  } catch (e) {
    return bad(`${e.name}: ${e.message}`, 500)
  }
}

export const GET = handler
export const POST = handler
export const PATCH = handler
export const PUT = handler
export const DELETE = handler
