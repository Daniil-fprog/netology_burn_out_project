const KEY = 'access_token';
let memoryToken = null;

export function getToken() {
  if (memoryToken) return memoryToken;
  try { memoryToken = localStorage.getItem(KEY); } catch { /* приватный режим */ }
  return memoryToken;
}
export function setToken(token) {
  memoryToken = token;
  try { localStorage.setItem(KEY, token); } catch { /* ignore */ }
}
export function clearToken() {
  memoryToken = null;
  try { localStorage.removeItem(KEY); } catch { /* ignore */ }
}
