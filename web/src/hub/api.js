const BASE = import.meta.env.VITE_BACKEND_URL || '';

export async function hubApi(token, path, body, signal) {
  const response = await fetch(`${BASE}/api/hub${path}`, {
    method: body ? 'POST' : 'GET',
    headers: { Authorization: `Bearer ${token}`, ...(body ? { 'Content-Type': 'application/json' } : {}) },
    body: body ? JSON.stringify(body) : undefined,
    signal,
  });
  const data = await response.json();
  if (!response.ok) {
    const error = new Error(typeof data.detail === 'string' ? data.detail : 'Zeus could not accept this request. Check your input and try again.');
    error.status = response.status;
    throw error;
  }
  return data;
}
