import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Separator } from "@/components/ui/separator"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Settings } from "lucide-react"
import { api } from "@/lib/api"
import type { AppSettings } from "@/lib/api"

const EMPTY_SETTINGS: AppSettings = {
  music_source_path: "",
  plex_url: "",
  plex_token: "",
  plex_library_name: "Music",
  ollama_url: "http://ollama:11434",
  ollama_model: "mistral",
  db_path: "",
  analysis_batch_size: 50,
}

interface SettingsField {
  key: keyof AppSettings
  label: string
  type?: "text" | "password" | "number"
  placeholder?: string
}

const SECTIONS: { title: string; description: string; fields: SettingsField[] }[] = [
  {
    title: "Musikquelle",
    description: "Pfad zum Samba-Share mit der Musikbibliothek",
    fields: [
      { key: "music_source_path", label: "Netzwerkpfad", placeholder: "\\\\OPENMEDIAVAULT\\Musik" },
    ],
  },
  {
    title: "Plex",
    description: "Verbindung zum Plex Media Server",
    fields: [
      { key: "plex_url", label: "Server-URL", placeholder: "http://192.168.178.97:32400" },
      { key: "plex_token", label: "Token", type: "password", placeholder: "Plex-Token" },
      { key: "plex_library_name", label: "Bibliotheksname", placeholder: "Music" },
    ],
  },
  {
    title: "Ollama (LLM)",
    description: "Lokales Sprachmodell fuer Playlist-Generierung",
    fields: [
      { key: "ollama_url", label: "URL", placeholder: "http://localhost:11434" },
      { key: "ollama_model", label: "Modell", placeholder: "mistral" },
    ],
  },
  {
    title: "Datenbank & Analyse",
    description: "Speicherort und Analyse-Einstellungen",
    fields: [
      { key: "db_path", label: "Datenbank-Pfad", placeholder: "~/.mood-machine/library.db" },
      { key: "analysis_batch_size", label: "Batch-Groesse", type: "number", placeholder: "50" },
    ],
  },
]

interface SettingsDialogProps {
  apiReady: boolean
}

export function SettingsDialog({ apiReady }: SettingsDialogProps) {
  const [open, setOpen] = useState(false)
  const [settings, setSettings] = useState<AppSettings>(EMPTY_SETTINGS)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState("")

  useEffect(() => {
    if (open && apiReady) {
      api.getConfig().then(setSettings)
      setMessage("")
    }
  }, [open, apiReady])

  const handleChange = (key: keyof AppSettings, value: string) => {
    setSettings((prev) => ({
      ...prev,
      [key]: key === "analysis_batch_size" ? Number(value) || 0 : value,
    }))
  }

  const handleSave = async () => {
    setSaving(true)
    setMessage("")
    const result = await api.saveConfig(settings)
    setSaving(false)
    if (result.success) {
      setMessage("Einstellungen gespeichert!")
      setTimeout(() => setOpen(false), 800)
    } else {
      setMessage(`Fehler: ${result.error}`)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={<Button variant="ghost" size="icon" title="Einstellungen" />}
      >
        <Settings className="h-4 w-4" />
      </DialogTrigger>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Einstellungen</DialogTitle>
          <DialogDescription>
            Konfiguration fuer Mood Machine. Aenderungen werden in config.yaml gespeichert.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 py-4">
          {SECTIONS.map((section, si) => (
            <div key={si}>
              {si > 0 && <Separator className="mb-4" />}
              <h3 className="text-sm font-semibold mb-1">{section.title}</h3>
              <p className="text-xs text-muted-foreground mb-3">{section.description}</p>
              <div className="space-y-3">
                {section.fields.map((field) => (
                  <div key={field.key} className="grid grid-cols-[140px_1fr] items-center gap-3">
                    <Label htmlFor={field.key} className="text-sm text-right">
                      {field.label}
                    </Label>
                    <Input
                      id={field.key}
                      type={field.type || "text"}
                      placeholder={field.placeholder}
                      value={String(settings[field.key] ?? "")}
                      onChange={(e) => handleChange(field.key, e.target.value)}
                    />
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        {message && (
          <p className={`text-sm ${message.startsWith("Fehler") ? "text-destructive" : "text-green-500"}`}>
            {message}
          </p>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>
            Abbrechen
          </Button>
          <Button onClick={handleSave} disabled={saving}>
            {saving ? "Speichere..." : "Speichern"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
