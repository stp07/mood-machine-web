/**
 * Type-safe HTTP API client for Mood Machine Web.
 */

export interface Song {
  id: number
  file_path: string
  relative_path: string
  title: string | null
  artist: string | null
  album: string | null
  year: number | null
  duration_seconds: number | null
  tempo_bpm: number | null
  energy: number | null
  danceability: number | null
  valence: number | null
  mood_happy: number | null
  mood_sad: number | null
  mood_aggressive: number | null
  mood_relaxed: number | null
}

export interface ScanProgress {
  running: boolean
  current: number
  total: number
  status: string
}

export interface LibraryStats {
  total_songs: number
  total_artists: number
  total_albums: number
}

export interface PlaylistResult {
  success: boolean
  filters?: Record<string, unknown>
  songs?: Song[]
  count?: number
  error?: string
}

export interface SavedPlaylist {
  id: number
  name: string
  description: string | null
  created_at: string
}

export interface AppSettings {
  music_source_path: string
  plex_url: string
  plex_token: string
  plex_library_name: string
  ollama_url: string
  ollama_model: string
  db_path: string
  analysis_batch_size: number
}

async function post<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  return res.json()
}

async function get<T>(url: string): Promise<T> {
  const res = await fetch(url)
  return res.json()
}

async function del<T>(url: string): Promise<T> {
  const res = await fetch(url, { method: "DELETE" })
  return res.json()
}

async function put<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  return res.json()
}

export interface AuthStatus {
  authenticated: boolean
  username?: string
}

export const api = {
  // Auth
  login: (username: string, password: string) =>
    post<{ success: boolean; username?: string; error?: string }>("/api/auth/login", { username, password }),

  logout: () =>
    post<{ success: boolean }>("/api/auth/logout", {}),

  checkAuth: () =>
    get<AuthStatus>("/api/auth/check"),

  // App
  startScan: (limit: number = 0) =>
    post<{ success: boolean; error?: string }>("/api/scan/start", { limit }),

  getScanProgress: () =>
    get<ScanProgress>("/api/scan/progress"),

  getLibraryStats: () =>
    get<LibraryStats>("/api/library/stats"),

  generatePlaylist: (prompt: string) =>
    post<{ success: boolean; error?: string }>("/api/playlist/generate", { prompt }),

  getGenerateStatus: () =>
    get<{ running: boolean; status: string; result: PlaylistResult | null }>("/api/playlist/generate/status"),

  exportPlex: (name: string, songIds: number[]) =>
    post<{ success: boolean; error?: string }>("/api/export/plex", { name, song_ids: songIds }),

  getConfig: () =>
    get<AppSettings>("/api/config"),

  saveConfig: (settings: AppSettings) =>
    put<{ success: boolean; error?: string }>("/api/config", settings),

  savePlaylist: (name: string, description: string, songIds: number[], filterJson: string) =>
    post<{ success: boolean; playlist_id?: number; error?: string }>("/api/playlist/save", {
      name,
      description,
      song_ids: songIds,
      filter_json: filterJson,
    }),

  getPlaylists: () =>
    get<SavedPlaylist[]>("/api/playlists"),

  loadPlaylist: (playlistId: number) =>
    get<{
      success: boolean
      name?: string
      description?: string
      filters?: Record<string, unknown>
      songs?: Song[]
      error?: string
    }>(`/api/playlist/${playlistId}`),

  deletePlaylist: (playlistId: number) =>
    del<{ success: boolean; error?: string }>(`/api/playlist/${playlistId}`),
}
