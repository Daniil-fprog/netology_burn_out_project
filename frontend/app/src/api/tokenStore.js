const KEY = 'access_token';
let memoryToken = null;

export function getToken() {
  if (memoryToken) return memoryToken;
  try { memoryToken = localStorage.getItem(KEY); } catch {}
  return memoryToken;
}
export function setToken(token) {
  memoryToken = token;
  try { localStorage.setItem(KEY, token); } catch {}
}
export function clearToken() {
  memoryToken = null;
  try { localStorage.removeItem(KEY); } catch {}
}
