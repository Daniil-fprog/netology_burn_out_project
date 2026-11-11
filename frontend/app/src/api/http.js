// Единая точка обращения к API. В режиме заглушек запросы уходят в mock/router.js,
// иначе — fetch к backend. Страницы не знают, какой режим включён.
import { ApiError } from './errors';
import { getToken, clearToken } from './tokenStore';

export const API_MODE = import.meta.env.VITE_API_MODE === 'real' ? 'real' : 'mock';
const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';

let onUnauthorized = () => {};
export const setUnauthorizedHandler = (fn) => { onUnauthorized = fn; };

function buildQuery(query) {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(query ?? {})) {
    if (v === undefined || v === null || v === '') continue;
    sp.set(k, String(v));
  }
  const s = sp.toString();
  return s ? `?${s}` : '';
}

function errorMessage(payload, status) {
  const detail = payload?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map((d) => d.msg).join('; ');
  return `Ошибка сервера (${status})`;
}

async function realFetch({ method, path, query, body, token, signal }) {
  const headers = { Accept: 'application/json' };
  if (token) headers.Authorization = `Bearer ${token}`;
  let payload = body;
  if (body !== undefined && !(body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
    payload = JSON.stringify(body);
  }
  const res = await fetch(`${BASE_URL}${path}${buildQuery(query)}`, { method, headers, body: payload, signal });
  const isJson = res.headers.get('content-type')?.includes('application/json');
  const data = isJson ? await res.json() : await res.blob();
  if (!res.ok) throw new ApiError(res.status, errorMessage(isJson ? data : null, res.status), data);
  return data;
}

export async function request(method, path, { query, body, signal } = {}) {
  const token = getToken();
  try {
    if (API_MODE === 'mock') {
      const { mockFetch } = await import('./mock/router');
      return await mockFetch({ method, path, query, body, token });
    }
    return await realFetch({ method, path, query, body, token, signal });
  } catch (e) {
    if (e instanceof ApiError && e.status === 401 && token) {
      clearToken();
      onUnauthorized();
    }
    throw e;
  }
}
