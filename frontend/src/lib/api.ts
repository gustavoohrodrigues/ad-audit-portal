// Cliente HTTP com autenticação por cookie httpOnly + refresh transparente.
// O backend define cookies seguros; usamos credentials: 'include'.

const BASE = '/api/v1'

class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

let refreshing: Promise<boolean> | null = null

async function tryRefresh(): Promise<boolean> {
  if (!refreshing) {
    refreshing = fetch(`${BASE}/auth/refresh`, {
      method: 'POST',
      credentials: 'include',
    })
      .then((r) => r.ok)
      .catch(() => false)
      .finally(() => {
        setTimeout(() => (refreshing = null), 0)
      })
  }
  return refreshing
}

async function request<T>(
  path: string,
  opts: RequestInit = {},
  retry = true,
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...opts,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(opts.headers || {}),
    },
  })

  if (res.status === 401 && retry && !path.startsWith('/auth/')) {
    const ok = await tryRefresh()
    if (ok) return request<T>(path, opts, false)
  }

  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail || detail
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, detail)
  }

  const ct = res.headers.get('content-type') || ''
  if (ct.includes('application/json')) return res.json()
  return (await res.text()) as unknown as T
}

export const api = {
  get: <T>(p: string) => request<T>(p),
  post: <T>(p: string, body?: unknown) =>
    request<T>(p, { method: 'POST', body: body ? JSON.stringify(body) : undefined }),
  del: <T>(p: string) => request<T>(p, { method: 'DELETE' }),
  login: (username: string, password: string) =>
    request<{ roles: string[]; access_token: string; mfa_required?: boolean; mfa_token?: string }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),
  loginMfa: (mfa_token: string, code: string) =>
    request<{ roles: string[]; access_token: string }>('/auth/login/mfa', {
      method: 'POST',
      body: JSON.stringify({ mfa_token, code }),
    }),
  logout: () => request('/auth/logout', { method: 'POST' }),
  async download(path: string, body: unknown): Promise<Blob> {
    const res = await fetch(`${BASE}${path}`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (!res.ok) throw new ApiError(res.status, 'Falha na exportação')
    return res.blob()
  },
}

export { ApiError }
