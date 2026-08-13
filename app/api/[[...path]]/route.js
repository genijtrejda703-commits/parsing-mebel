// Transparent streaming proxy: Next.js /api/* -> FastAPI (Python backend)
// Python backend is the system of record (PostgreSQL + pgvector + Celery)
const BACKEND = process.env.FASTAPI_URL || 'http://127.0.0.1:8001';

async function proxy(request, { params }) {
  const resolved = await params;
  const segments = resolved?.path || [];
  const url = new URL(request.url);
  const target = `${BACKEND}/api/${segments.map(encodeURIComponent).join('/')}${url.search}`;

  const headers = new Headers(request.headers);
  headers.delete('host');
  headers.delete('connection');
  headers.delete('content-length');

  const init = { method: request.method, headers, redirect: 'manual' };
  if (!['GET', 'HEAD'].includes(request.method)) {
    init.body = request.body;
    init.duplex = 'half';
  }

  try {
    const res = await fetch(target, init);
    const respHeaders = new Headers(res.headers);
    respHeaders.delete('content-encoding');
    respHeaders.delete('content-length');
    respHeaders.delete('transfer-encoding');
    return new Response(res.body, { status: res.status, headers: respHeaders });
  } catch (e) {
    return Response.json({ detail: 'Python backend unavailable: ' + e.message }, { status: 502 });
  }
}

export const GET = proxy;
export const HEAD = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
export const dynamic = 'force-dynamic';
