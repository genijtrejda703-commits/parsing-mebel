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
      const [total, approved, pending, rejected, docs, facs, emb,
        posTotal, posApproved, posPending, posFlagged, varTotal] = await Promise.all([
        P.countDocuments({}), P.countDocuments({ status: 'approved' }),
        P.countDocuments({ status: 'pending' }), P.countDocuments({ status: 'rejected' }),
        db.collection('documents').countDocuments({}),
        db.collection('factories').countDocuments({}),
        db.collection('product_embeddings').countDocuments({}),
        db.collection('positions').countDocuments({}),
        db.collection('positions').countDocuments({ status: 'approved' }),
        db.collection('positions').countDocuments({ status: 'pending' }),
        db.collection('positions').countDocuments({ flagged: true }),
        db.collection('variant_prices').countDocuments({}),
      ])
      const agg = await P.aggregate([
        { $group: { _id: null, conf: { $avg: '$confidence' }, flagged: { $sum: { $cond: ['$anomaly', 1, 0] } } } },
      ]).toArray()
      const pagg = await db.collection('positions').aggregate([
        { $group: { _id: null, conf: { $avg: '$avg_confidence' } } },
      ]).toArray()
      return ok({
        products: total, approved, pending, rejected, documents: docs, factories: facs,
        embeddings: emb, avg_confidence: agg[0]?.conf || 0, flagged: agg[0]?.flagged || 0,
        positions: posTotal, positions_approved: posApproved, positions_pending: posPending,
        positions_flagged: posFlagged, variant_prices: varTotal,
        positions_avg_confidence: pagg[0]?.conf || 0,
      })
    }

    // ---------------- positions (Directive 1: Position -> Variant -> Price) ----------------
    if (route === '/positions/facets' && method === 'GET') {
      const POS = db.collection('positions')
      const [cats, docsFacet] = await Promise.all([
        POS.aggregate([
          { $unwind: '$categories' },
          { $group: { _id: '$categories', n: { $sum: 1 } } },
          { $sort: { n: -1 } }, { $limit: 60 },
        ]).toArray(),
        db.collection('documents').find({}, { projection: { _id: 0, id: 1, name: 1, positions: 1, variant_prices: 1 } })
          .sort({ name: 1 }).toArray(),
      ])
      return ok({
        categories: cats.map(c => ({ category: c._id, n: c.n })),
        documents: docsFacet,
      })
    }

    if (route === '/positions' && method === 'GET') {
      const q = {}
      if (qp.get('status') && qp.get('status') !== 'all') q.status = qp.get('status')
      if (qp.get('flagged') === 'true') q.flagged = true
      if (qp.get('category')) q.categories = qp.get('category')
      const minVar = parseInt(qp.get('min_variants') || '0')
      if (minVar > 0) q.n_variants = { $gte: minVar }
      const term = (qp.get('q') || '').trim()
      if (term) {
        const rx = new RegExp(term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'i')
        q.$or = [{ name: rx }, { norm_name: rx }, { categories: rx }]
      }
      if (qp.get('doc_id')) q.doc_ids = qp.get('doc_id')
      const sortKey = qp.get('sort') || 'best'
      const sortSpec = sortKey === 'name' ? { name: 1 }
        : sortKey === 'variants' ? { n_variants: -1, name: 1 }
          : sortKey === 'price' ? { price_max: -1 }
            : { avg_confidence: -1, n_variants: -1, name: 1 }
      const limit = Math.min(parseInt(qp.get('limit') || '60'), 300)
      const skip = parseInt(qp.get('skip') || '0')
      const POS = db.collection('positions')
      const [items, total] = await Promise.all([
        POS.find(q, { projection: { _id: 0 } }).sort(sortSpec).skip(skip).limit(limit).toArray(),
        POS.countDocuments(q),
      ])
      return ok({ items, total, skip, limit })
    }

    if (segs[0] === 'positions' && segs[1] && method === 'GET') {
      const pos = await db.collection('positions').findOne({ id: segs[1] }, { projection: { _id: 0 } })
      if (!pos) return bad('position not found', 404)
      const variants = await db.collection('variant_prices')
        .find({ position_id: segs[1] }, { projection: { _id: 0 } })
        .sort({ doc_name: 1, page: 1, variant_code: 1, finish: 1 }).limit(5000).toArray()
      // group by (doc, page) so the QA split-screen can raster one page at a time
      const byPage = {}
      for (const v of variants) {
        const key = `${v.doc_id}__${v.page}`
        if (!byPage[key]) byPage[key] = { doc_id: v.doc_id, doc_name: v.doc_name, page: v.page, page_width: v.page_width, page_height: v.page_height, variants: [] }
        byPage[key].variants.push(v)
      }
      const docs = await db.collection('documents')
        .find({ id: { $in: [...new Set(variants.map(v => v.doc_id))] } }, { projection: { _id: 0, id: 1, name: 1, collection: 1 } }).toArray()
      return ok({ position: pos, variants, pages: Object.values(byPage), documents: docs })
    }

    if (segs[0] === 'positions' && segs[1] && (method === 'PATCH' || method === 'PUT')) {
      const body = await request.json()
      const allow = ['status', 'reviewer_notes', 'name']
      const $set = { updated_at: new Date().toISOString() }
      for (const k of allow) if (k in body) $set[k] = body[k]
      await db.collection('positions').updateOne({ id: segs[1] }, { $set })
      if (body.cascade_status && body.status) {
        await db.collection('variant_prices').updateMany(
          { position_id: segs[1] }, { $set: { status: body.status } })
      }
      const fresh = await db.collection('positions').findOne({ id: segs[1] }, { projection: { _id: 0 } })
      return ok(fresh || {})
    }

    if (route === '/positions/bulk' && method === 'POST') {
      const { ids, status } = await request.json()
      if (!Array.isArray(ids) || !status) return bad('ids and status required')
      const r = await db.collection('positions').updateMany(
        { id: { $in: ids } }, { $set: { status, updated_at: new Date().toISOString() } })
      return ok({ modified: r.modifiedCount })
    }

    // ---------------- pipeline control (proxy to DS sidecar) ----------------
    // ---------------- Приёмка (Directive 3: поячеечная сверка) ----------------
    if (route === '/acceptance/sample' && method === 'POST') {
      const body = await request.json().catch(() => ({}))
      const perDoc = Math.min(Math.max(parseInt(body.per_doc || 2), 1), 6)
      const cpp = Math.min(Math.max(parseInt(body.cells_per_page || 16), 4), 40)
      const VP = db.collection('variant_prices')
      const docs = await db.collection('documents')
        .find({ variant_prices: { $gt: 0 } }, { projection: { _id: 0, id: 1, name: 1 } }).toArray()
      const sample = []
      for (const d of docs) {
        const pages = await VP.aggregate([
          { $match: { doc_id: d.id } },
          { $group: { _id: '$page', n: { $sum: 1 } } },
          { $match: { n: { $gte: 3 } } },
          { $sample: { size: perDoc } },
        ]).toArray()
        for (const pg of pages) {
          const cells = await VP.aggregate([
            { $match: { doc_id: d.id, page: pg._id } },
            { $sample: { size: cpp } },
          ]).toArray()
          for (const c of cells) {
            sample.push({
              id: c.id, doc_id: d.id, doc_name: d.name, page: c.page,
              page_width: c.page_width, page_height: c.page_height,
              position_id: c.position_id, position_name: c.position_name,
              variant_code: c.variant_code, dimension: c.dimension, finish: c.finish,
              price: c.price, bbox: c.bbox, bbox_row_label: c.bbox_row_label,
              bbox_col_header: c.bbox_col_header,
              verdict: null, note: '', sampled_at: new Date().toISOString(),
            })
          }
        }
      }
      await db.collection('acceptance_cells').deleteMany({})
      if (sample.length) await db.collection('acceptance_cells').insertMany(sample)
      return ok({ sampled: sample.length, documents: docs.length, per_doc: perDoc })
    }

    if (route === '/acceptance' && method === 'GET') {
      const cells = await db.collection('acceptance_cells')
        .find({}, { projection: { _id: 0 } }).sort({ doc_name: 1, page: 1 }).toArray()
      const total = cells.length
      const checked = cells.filter(c => c.verdict).length
      const errors = cells.filter(c => c.verdict && c.verdict !== 'ok').length
      const byVerdict = {}
      const perDoc = {}
      const pages = {}
      for (const c of cells) {
        if (c.verdict) byVerdict[c.verdict] = (byVerdict[c.verdict] || 0) + 1
        const dk = c.doc_name || '—'
        perDoc[dk] = perDoc[dk] || { total: 0, checked: 0, errors: 0 }
        perDoc[dk].total++
        if (c.verdict) perDoc[dk].checked++
        if (c.verdict && c.verdict !== 'ok') perDoc[dk].errors++
        const pk = `${c.doc_id}__${c.page}`
        if (!pages[pk]) pages[pk] = { doc_id: c.doc_id, doc_name: c.doc_name, page: c.page, page_width: c.page_width, page_height: c.page_height, cells: [] }
        pages[pk].cells.push(c)
      }
      return ok({
        cells, pages: Object.values(pages),
        stats: { total, checked, errors, error_rate: checked ? errors / checked : 0, by_verdict: byVerdict, per_doc: perDoc },
      })
    }

    if (segs[0] === 'acceptance' && segs[1] && segs[1] !== 'sample' && (method === 'PATCH' || method === 'PUT')) {
      const body = await request.json()
      const $set = {}
      if ('verdict' in body) $set.verdict = body.verdict
      if ('note' in body) $set.note = body.note
      await db.collection('acceptance_cells').updateOne({ id: segs[1] }, { $set })
      return ok({ ok: true })
    }

    // ---------------- inventory + coverage (Directive 2) ----------------
    if (route === '/inventory' && method === 'POST') {
      const body = await request.json().catch(() => ({}))
      return ok(await worker('/inventory', { method: 'POST', body: JSON.stringify(body) }))
    }

    if (route === '/inventory' && method === 'GET') {
      const q = {}
      if (qp.get('source')) q.source = qp.get('source')
      if (qp.get('doc_type')) q.doc_type = qp.get('doc_type')
      if (qp.get('current') === 'true') q.is_current_listino = true
      if (qp.get('ingested') === 'true') q.ingested = true
      const term = (qp.get('q') || '').trim()
      if (term) {
        const rx = new RegExp(term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'i')
        q.$or = [{ name: rx }, { sample_title: rx }, { group_key: rx }]
      }
      const INV = db.collection('file_inventory')
      const [items, total, byType, curCount, ingCount] = await Promise.all([
        INV.find(q, { projection: { _id: 0 } }).sort({ doc_type: 1, year: -1, name: 1 })
          .limit(Math.min(parseInt(qp.get('limit') || '600'), 1000)).toArray(),
        INV.countDocuments(q),
        INV.aggregate([{ $match: q }, { $group: { _id: '$doc_type', n: { $sum: 1 } } }, { $sort: { n: -1 } }]).toArray(),
        INV.countDocuments({ ...q, is_current_listino: true }),
        INV.countDocuments({ ...q, ingested: true }),
      ])
      return ok({
        items, total,
        by_type: byType.map(t => ({ doc_type: t._id, n: t.n })),
        current_listini: curCount, ingested: ingCount,
      })
    }

    if (route === '/coverage' && method === 'GET') {
      const docs = await db.collection('documents')
        .find({}, { projection: { _id: 0, id: 1, name: 1, collection: 1, pages: 1, positions: 1, variant_prices: 1, coverage: 1, status: 1 } })
        .sort({ variant_prices: -1 }).toArray()
      const invCount = await db.collection('file_inventory').countDocuments({})
      const inv = await db.collection('file_inventory')
        .find({}, { projection: { _id: 0, name: 1, doc_type: 1, ingested: 1, pages: 1, year: 1, currency: 1 } }).toArray()
      const tot = { pages_total: 0, pages_with_matrix: 0, pages_parsed: 0, pages_skipped: 0, positions: 0, variant_prices: 0, rejected_cells: 0 }
      for (const d of docs) {
        const c = d.coverage || {}
        for (const k of Object.keys(tot)) tot[k] += (c[k] || 0)
      }
      // разобрано vs классифицировано без разбора
      const classifiedOnly = inv.filter(x => !x.ingested)
      return ok({
        documents: docs,
        totals: tot,
        files_inventoried: invCount,
        files_parsed: docs.length,
        files_classified_only: classifiedOnly.length,
        classified_only: classifiedOnly.slice(0, 400),
      })
    }

    if (route === '/inventory/export' && method === 'GET') {
      const res = await fetch(`${WORKER}/export-inventory`)
      if (!res.ok) return bad(`export failed: ${await res.text()}`, res.status)
      const buf = await res.arrayBuffer()
      const name = `HOMEART_inventory_${new Date().toISOString().slice(0, 10)}.xlsx`
      return new Response(buf, {
        headers: {
          'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
          'Content-Disposition': `attachment; filename="${name}"; filename*=UTF-8''${encodeURIComponent(name)}`,
        },
      })
    }

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

    if (route === '/photos' && method === 'POST') {
      return ok(await worker('/photos', { method: 'POST', body: '{}' }))
    }
    if (route === '/anomaly-scan' && method === 'POST') {
      return ok(await worker('/anomalies', { method: 'POST', body: '{}' }))
    }

    // ---------------- anomaly review lane ----------------
    if (route === '/anomalies' && method === 'GET') {
      const q = {}
      if (qp.get('doc_id')) q.doc_id = qp.get('doc_id')
      if (qp.get('reason')) q.reason = qp.get('reason')
      if (qp.get('zone')) q.zone = qp.get('zone')
      const term = (qp.get('q') || '').trim()
      if (term) {
        const rx = new RegExp(term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'i')
        q.$or = [{ text: rx }, { model_name: rx }, { category: rx },
          { above_text: rx }, { left_text: rx }]
      }
      const limit = Math.min(parseInt(qp.get('limit') || '100'), 400)
      const skip = parseInt(qp.get('skip') || '0')
      const A = db.collection('anomalies')
      const [items, total, reasons] = await Promise.all([
        A.find(q, { projection: { _id: 0 } })
          .sort({ confidence: -1, page: 1 }).skip(skip).limit(limit).toArray(),
        A.countDocuments(q),
        A.aggregate([{ $group: { _id: '$reason', n: { $sum: 1 } } },
          { $sort: { n: -1 } }]).toArray(),
      ])
      return ok({
        items, total, skip, limit,
        reasons: reasons.map(r => ({ reason: r._id, n: r.n })),
      })
    }

    // ---------------- excel export ----------------
    if (route === '/export-positions' && method === 'GET') {
      const p = new URLSearchParams({ status: qp.get('status') || 'all' })
      if (qp.get('doc_id')) p.set('doc_id', qp.get('doc_id'))
      if (qp.get('factory')) p.set('factory', qp.get('factory'))
      const res = await fetch(`${WORKER}/export-positions?${p}`)
      if (!res.ok) return bad(`export failed: ${await res.text()}`, res.status)
      const buf = await res.arrayBuffer()
      const stamp = new Date().toISOString().slice(0, 10)
      const name = `HOMEART_positions_${qp.get('status') || 'all'}_${stamp}.xlsx`
      return new Response(buf, {
        headers: {
          'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
          'Content-Disposition': `attachment; filename="${name}"; filename*=UTF-8''${encodeURIComponent(name)}`,
          'X-Rows': res.headers.get('X-Rows') || '0',
          'X-Positions': res.headers.get('X-Positions') || '0',
        },
      })
    }

    if (route === '/export' && method === 'GET') {
      const p = new URLSearchParams({
        status: qp.get('status') || 'approved',
        mode: qp.get('mode') || 'product',
      })
      if (qp.get('doc_id')) p.set('doc_id', qp.get('doc_id'))
      if (qp.get('factory')) p.set('factory', qp.get('factory'))
      const res = await fetch(`${WORKER}/export?${p}`)
      if (!res.ok) return bad(`export failed: ${await res.text()}`, res.status)
      const buf = await res.arrayBuffer()
      const stamp = new Date().toISOString().slice(0, 10)
      const name = `HOMEART_catalog_${qp.get('status') || 'approved'}_${stamp}.xlsx`
      return new Response(buf, {
        headers: {
          'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
          'Content-Disposition': `attachment; filename="${name}"; filename*=UTF-8''${encodeURIComponent(name)}`,
          'X-Rows': res.headers.get('X-Rows') || '0',
        },
      })
    }

    // ---------------- product illustration crop ----------------
    if (route === '/product-photo' && method === 'GET') {
      const res = await fetch(`${WORKER}/photo?product_id=${qp.get('product_id')}&dpi=${qp.get('dpi') || 130}`)
      if (!res.ok) return bad('no illustration', res.status)
      const buf = await res.arrayBuffer()
      return new Response(buf, {
        headers: { 'Content-Type': 'image/png', 'Cache-Control': 'public, max-age=604800' },
      })
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
