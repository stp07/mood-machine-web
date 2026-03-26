import { useState, useEffect, useRef, useCallback } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Progress } from "@/components/ui/progress"
import { Separator } from "@/components/ui/separator"
import { api } from "@/lib/api"
import type { Song, ScanProgress, LibraryStats, SavedPlaylist } from "@/lib/api"
import { SettingsDialog } from "@/components/SettingsDialog"
import { LoginScreen } from "@/components/LoginScreen"
import { Toaster, toast } from "sonner"
import {
  Play,
  Trash2,
  GripVertical,
  Moon,
  Sun,
  LogOut,
  ListMusic,
  Upload,
  Save,
  FolderSync,
  X,
  Loader2,
  Disc3,
  Library,
} from "lucide-react"

function formatDuration(seconds: number | null): string {
  if (!seconds) return "--:--"
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, "0")}`
}

export default function App() {
  const [authenticated, setAuthenticated] = useState<boolean | null>(null) // null = checking
  const [username, setUsername] = useState("")
  const [apiReady, setApiReady] = useState(false)
  const [stats, setStats] = useState<LibraryStats>({ total_songs: 0, total_artists: 0, total_albums: 0 })
  const [scanProgress, setScanProgress] = useState<ScanProgress>({ running: false, current: 0, total: 0, status: "" })
  const [prompt, setPrompt] = useState("")
  const [generating, setGenerating] = useState(false)
  const [currentSongs, setCurrentSongs] = useState<Song[]>([])
  const [currentFilters, setCurrentFilters] = useState<Record<string, unknown> | null>(null)
  const [playlistName, setPlaylistName] = useState("")
  const [savedPlaylists, setSavedPlaylists] = useState<SavedPlaylist[]>([])
  const [scanLimit] = useState("0")
  const [dark, setDark] = useState(true)
  const [activePlaylistId, setActivePlaylistId] = useState<number | null>(null)
  const scanIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Drag state
  const [dragIndex, setDragIndex] = useState<number | null>(null)
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null)

  // Dark mode
  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark)
  }, [dark])

  // Check auth on mount
  useEffect(() => {
    api.checkAuth().then((status) => {
      setAuthenticated(status.authenticated)
      if (status.username) setUsername(status.username)
    }).catch(() => setAuthenticated(false))
  }, [])

  // Load data once authenticated
  useEffect(() => {
    if (!authenticated) return
    setApiReady(true)
    api.getLibraryStats().then(setStats).catch((e) => {
      console.error("Stats error:", e)
      toast.error("Stats laden fehlgeschlagen", { description: String(e) })
    })
    api.getPlaylists().then(setSavedPlaylists).catch((e) => {
      console.error("Playlists error:", e)
      toast.error("Playlists laden fehlgeschlagen", { description: String(e) })
    })
    api.getScanProgress().then((scanState) => {
      setScanProgress(scanState)
      if (scanState.running) pollScan()
    }).catch((e) => console.error("ScanProgress error:", e))
  }, [authenticated])

  const handleLogin = (user: string) => {
    setUsername(user)
    setAuthenticated(true)
  }

  const handleLogout = async () => {
    await api.logout()
    setAuthenticated(false)
    setUsername("")
    setApiReady(false)
  }

  // Poll scan progress
  const pollScan = useCallback(() => {
    if (scanIntervalRef.current) return
    scanIntervalRef.current = setInterval(async () => {
      const p = await api.getScanProgress()
      setScanProgress(p)
      if (!p.running && scanIntervalRef.current) {
        clearInterval(scanIntervalRef.current)
        scanIntervalRef.current = null
        const s = await api.getLibraryStats()
        setStats(s)
        toast.success("Scan abgeschlossen", { description: p.status })
      }
    }, 1000)
  }, [])

  const handleStartScan = async () => {
    const limit = parseInt(scanLimit) || 0
    const result = await api.startScan(limit)
    if (result.success) {
      setScanProgress({ running: true, current: 0, total: 0, status: "Starte..." })
      pollScan()
      toast.info("Scan gestartet", { description: limit > 0 ? `Limit: ${limit} Songs` : "Komplette Bibliothek" })
    } else {
      toast.error("Scan fehlgeschlagen", { description: result.error })
    }
  }

  const [generateStatus, setGenerateStatus] = useState("")
  const generateIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const handleGenerate = async () => {
    if (!prompt.trim()) return
    setGenerating(true)
    setGenerateStatus("Starte...")
    const startResult = await api.generatePlaylist(prompt)
    if (!startResult.success) {
      toast.error("Playlist-Generierung fehlgeschlagen", { description: startResult.error })
      setGenerating(false)
      setGenerateStatus("")
      return
    }
    // Poll for result
    generateIntervalRef.current = setInterval(async () => {
      const status = await api.getGenerateStatus()
      setGenerateStatus(status.status)
      if (!status.running && status.result) {
        if (generateIntervalRef.current) {
          clearInterval(generateIntervalRef.current)
          generateIntervalRef.current = null
        }
        setGenerating(false)
        setGenerateStatus("")
        if (status.result.success && status.result.songs) {
          setCurrentSongs(status.result.songs)
          setCurrentFilters(status.result.filters || null)
          setPlaylistName("")
          setActivePlaylistId(null)
          toast.success(`${status.result.songs.length} Songs gefunden`)
        } else {
          toast.error("Playlist-Generierung fehlgeschlagen", { description: status.result.error })
          setCurrentSongs([])
        }
      }
    }, 1000)
  }

  const handleExportPlex = async () => {
    if (!playlistName.trim() || currentSongs.length === 0) return
    const ids = currentSongs.map((s) => s.id)
    const result = await api.exportPlex(playlistName, ids)
    if (result.success) {
      toast.success("Plex-Playlist erstellt!", { description: playlistName })
    } else {
      toast.error("Plex-Export fehlgeschlagen", { description: result.error })
    }
  }

  const handleSavePlaylist = async () => {
    if (!playlistName.trim() || currentSongs.length === 0) return
    const ids = currentSongs.map((s) => s.id)
    const filterStr = currentFilters ? JSON.stringify(currentFilters) : "{}"
    const result = await api.savePlaylist(playlistName, prompt, ids, filterStr)
    if (result.success) {
      toast.success("Playlist gespeichert!", { description: playlistName })
      const p = await api.getPlaylists()
      setSavedPlaylists(p)
    } else {
      toast.error("Speichern fehlgeschlagen", { description: result.error })
    }
  }

  const handleLoadPlaylist = async (pl: SavedPlaylist) => {
    const result = await api.loadPlaylist(pl.id)
    if (result.success && result.songs) {
      setCurrentSongs(result.songs)
      setCurrentFilters(result.filters || null)
      setPlaylistName(result.name || pl.name)
      setPrompt(result.description || "")
      setActivePlaylistId(pl.id)
      toast.info(`"${pl.name}" geladen`, { description: `${result.songs.length} Songs` })
    } else {
      toast.error("Laden fehlgeschlagen", { description: result.error })
    }
  }

  const handleDeletePlaylist = async (pl: SavedPlaylist, e: React.MouseEvent) => {
    e.stopPropagation()
    const result = await api.deletePlaylist(pl.id)
    if (result.success) {
      toast.success(`"${pl.name}" geloescht`)
      const p = await api.getPlaylists()
      setSavedPlaylists(p)
      if (activePlaylistId === pl.id) {
        setActivePlaylistId(null)
      }
    } else {
      toast.error("Loeschen fehlgeschlagen", { description: result.error })
    }
  }

  // Remove song from current playlist
  const handleRemoveSong = (index: number) => {
    setCurrentSongs((prev) => prev.filter((_, i) => i !== index))
  }

  // Drag & Drop handlers
  const handleDragStart = (index: number) => {
    setDragIndex(index)
  }

  const handleDragOver = (e: React.DragEvent, index: number) => {
    e.preventDefault()
    setDragOverIndex(index)
  }

  const handleDrop = (index: number) => {
    if (dragIndex === null || dragIndex === index) {
      setDragIndex(null)
      setDragOverIndex(null)
      return
    }
    setCurrentSongs((prev) => {
      const updated = [...prev]
      const [moved] = updated.splice(dragIndex, 1)
      updated.splice(index, 0, moved)
      return updated
    })
    setDragIndex(null)
    setDragOverIndex(null)
  }

  const handleDragEnd = () => {
    setDragIndex(null)
    setDragOverIndex(null)
  }

  const scanPercent = scanProgress.total > 0 ? Math.round((scanProgress.current / scanProgress.total) * 100) : 0

  // Auth gate: show loading or login screen
  if (authenticated === null) {
    return <div className="min-h-screen bg-background flex items-center justify-center">
      <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
    </div>
  }

  if (!authenticated) {
    return <LoginScreen onLogin={handleLogin} />
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Toaster
        position="bottom-right"
        richColors
        theme={dark ? "dark" : "light"}
        toastOptions={{ duration: 3000 }}
      />

      {/* Header */}
      <header className="border-b px-6 py-3 flex items-center justify-between bg-card">
        <div className="flex items-center gap-3">
          <Disc3 className="h-6 w-6 text-primary" />
          <h1 className="text-xl font-bold tracking-wider uppercase" style={{ fontFamily: "var(--font-retro)" }}>Mood Machine</h1>
          <Badge variant={apiReady ? "default" : "secondary"} className="text-xs">
            {apiReady ? "Verbunden" : "Verbinde..."}
          </Badge>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">{username}</span>
          <SettingsDialog apiReady={apiReady} />
          <Button variant="ghost" size="icon" onClick={() => setDark(!dark)} title={dark ? "Heller Modus" : "Dunkler Modus"}>
            {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </Button>
          <Button variant="ghost" size="icon" onClick={handleLogout} title="Abmelden">
            <LogOut className="h-4 w-4" />
          </Button>
        </div>
      </header>

      <div className="flex flex-1">
        {/* Sidebar */}
        <aside className="w-64 border-r p-4 space-y-4 bg-card/50">
          {/* Library Stats */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                <Library className="h-4 w-4" />
                Bibliothek
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-1 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Songs</span>
                <span className="font-mono">{stats.total_songs.toLocaleString()}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Kuenstler</span>
                <span className="font-mono">{stats.total_artists.toLocaleString()}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Alben</span>
                <span className="font-mono">{stats.total_albums.toLocaleString()}</span>
              </div>
            </CardContent>
          </Card>

          {/* Scan */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                <FolderSync className="h-4 w-4" />
                Scanner
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <Button
                size="sm"
                className="w-full"
                onClick={handleStartScan}
                disabled={!apiReady || scanProgress.running}
              >
                {scanProgress.running ? (
                  <>
                    <Loader2 className="h-3 w-3 animate-spin mr-1" />
                    Scannt...
                  </>
                ) : (
                  <>
                    <FolderSync className="h-3 w-3 mr-1" />
                    Bibliothek scannen
                  </>
                )}
              </Button>
              {scanProgress.running && (
                <div className="space-y-1.5">
                  {scanProgress.total > 0 && <Progress value={scanPercent} className="h-2" />}
                  <p className="text-xs text-muted-foreground truncate" title={scanProgress.status}>
                    {scanProgress.status || "Starte..."}
                  </p>
                  {scanProgress.total > 0 && (
                    <p className="text-xs font-mono text-muted-foreground text-center">
                      {scanProgress.current.toLocaleString()} / {scanProgress.total.toLocaleString()} ({scanPercent}%)
                    </p>
                  )}
                </div>
              )}
              {!scanProgress.running && (
                <p className="text-xs text-muted-foreground truncate" title={scanProgress.status || undefined}>
                  {scanProgress.status || `${stats.total_songs.toLocaleString()} Songs in der Bibliothek`}
                </p>
              )}
            </CardContent>
          </Card>

          <Separator />

          {/* Saved Playlists */}
          <div>
            <h3 className="text-sm font-medium mb-2 flex items-center gap-2">
              <ListMusic className="h-4 w-4" />
              Gespeicherte Playlists
            </h3>
            <ScrollArea className="h-48">
              {savedPlaylists.length === 0 ? (
                <p className="text-xs text-muted-foreground px-2">Keine Playlists</p>
              ) : (
                <div className="space-y-1">
                  {savedPlaylists.map((pl) => (
                    <div
                      key={pl.id}
                      className={`group text-sm p-2 rounded cursor-pointer flex items-center justify-between transition-colors ${
                        activePlaylistId === pl.id
                          ? "bg-primary/10 border border-primary/30"
                          : "hover:bg-muted"
                      }`}
                      onClick={() => handleLoadPlaylist(pl)}
                    >
                      <div className="min-w-0 flex-1">
                        <div className="font-medium truncate">{pl.name}</div>
                        {pl.description && (
                          <div className="text-xs text-muted-foreground truncate">{pl.description}</div>
                        )}
                      </div>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6 opacity-0 group-hover:opacity-100 shrink-0 ml-1 text-destructive hover:text-destructive"
                        onClick={(e) => handleDeletePlaylist(pl, e)}
                        title="Playlist loeschen"
                      >
                        <Trash2 className="h-3 w-3" />
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </ScrollArea>
          </div>
        </aside>

        {/* Main Content */}
        <main className="flex-1 p-6 space-y-4">
          {/* Prompt Input */}
          <Card>
            <CardContent className="pt-6">
              <div className="flex gap-2">
                <Input
                  placeholder="Beschreibe deine Playlist... z.B. 'Chillige Musik zum Arbeiten, keine Vocals'"
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && !generating && handleGenerate()}
                  className="flex-1"
                />
                <Button onClick={handleGenerate} disabled={!apiReady || generating || !prompt.trim()}>
                  {generating ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin mr-2" />
                      {generateStatus || "Generiere..."}
                    </>
                  ) : (
                    <>
                      <Play className="h-4 w-4 mr-2" />
                      Playlist erstellen
                    </>
                  )}
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Results */}
          {currentSongs.length > 0 && (
            <Card>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <CardTitle className="text-lg flex items-center gap-2">
                    <ListMusic className="h-5 w-5" />
                    Playlist ({currentSongs.length} Songs)
                  </CardTitle>
                  <div className="flex items-center gap-2">
                    <Input
                      placeholder="Playlist-Name"
                      value={playlistName}
                      onChange={(e) => setPlaylistName(e.target.value)}
                      className="w-48"
                    />
                    <Button variant="outline" size="sm" onClick={handleSavePlaylist} disabled={!playlistName.trim()} title="Lokal speichern">
                      <Save className="h-4 w-4 mr-1" />
                      Speichern
                    </Button>
                    <Button variant="outline" size="sm" onClick={handleExportPlex} disabled={!playlistName.trim()} title="An Plex senden">
                      <Upload className="h-4 w-4 mr-1" />
                      Plex
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <Tabs defaultValue="songs">
                  <TabsList>
                    <TabsTrigger value="songs">Songs</TabsTrigger>
                    <TabsTrigger value="filters">Filter</TabsTrigger>
                  </TabsList>
                  <TabsContent value="songs">
                    <ScrollArea className="h-[calc(100vh-340px)]">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b text-left text-muted-foreground">
                            <th className="py-2 w-6"></th>
                            <th className="py-2 pr-4 w-8">#</th>
                            <th className="py-2 pr-4">Titel</th>
                            <th className="py-2 pr-4">Kuenstler</th>
                            <th className="py-2 pr-4">Album</th>
                            <th className="py-2 pr-4 text-right">Dauer</th>
                            <th className="py-2 pr-4 text-right">BPM</th>
                            <th className="py-2 text-right">Energy</th>
                            <th className="py-2 w-8"></th>
                          </tr>
                        </thead>
                        <tbody>
                          {currentSongs.map((song, i) => (
                            <tr
                              key={`${song.id}-${i}`}
                              className={`border-b border-border/50 transition-colors ${
                                dragOverIndex === i ? "bg-primary/10" : "hover:bg-muted/50"
                              } ${dragIndex === i ? "opacity-40" : ""}`}
                              draggable
                              onDragStart={() => handleDragStart(i)}
                              onDragOver={(e) => handleDragOver(e, i)}
                              onDrop={() => handleDrop(i)}
                              onDragEnd={handleDragEnd}
                            >
                              <td className="py-1.5 cursor-grab active:cursor-grabbing text-muted-foreground/50 hover:text-muted-foreground">
                                <GripVertical className="h-4 w-4" />
                              </td>
                              <td className="py-1.5 pr-4 text-muted-foreground text-xs">{i + 1}</td>
                              <td className="py-1.5 pr-4 font-medium truncate max-w-48">{song.title || "Unbekannt"}</td>
                              <td className="py-1.5 pr-4 text-muted-foreground truncate max-w-36">{song.artist || "-"}</td>
                              <td className="py-1.5 pr-4 text-muted-foreground truncate max-w-36">{song.album || "-"}</td>
                              <td className="py-1.5 pr-4 text-right font-mono text-xs">{formatDuration(song.duration_seconds)}</td>
                              <td className="py-1.5 pr-4 text-right font-mono text-xs">{song.tempo_bpm?.toFixed(0) || "-"}</td>
                              <td className="py-1.5 text-right font-mono text-xs">{song.energy != null ? (song.energy * 100).toFixed(0) + "%" : "-"}</td>
                              <td className="py-1.5">
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  className="h-6 w-6 opacity-0 group-hover:opacity-100 text-destructive hover:text-destructive hover:bg-destructive/10"
                                  onClick={() => handleRemoveSong(i)}
                                  title="Song entfernen"
                                  style={{ opacity: undefined }}
                                  onMouseEnter={(e) => (e.currentTarget.style.opacity = "1")}
                                  onMouseLeave={(e) => (e.currentTarget.style.opacity = "0")}
                                >
                                  <X className="h-3 w-3" />
                                </Button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </ScrollArea>
                  </TabsContent>
                  <TabsContent value="filters">
                    <pre className="bg-muted rounded p-4 text-xs font-mono overflow-auto max-h-96">
                      {currentFilters ? JSON.stringify(currentFilters, null, 2) : "Keine Filter"}
                    </pre>
                  </TabsContent>
                </Tabs>
              </CardContent>
            </Card>
          )}

          {/* Empty state */}
          {currentSongs.length === 0 && !generating && (
            <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
              <Disc3 className="h-16 w-16 mb-4 opacity-20" />
              <p className="text-lg font-medium">Beschreibe deine Stimmung</p>
              <p className="text-sm">und lass dir eine passende Playlist generieren</p>
            </div>
          )}
        </main>
      </div>
    </div>
  )
}
