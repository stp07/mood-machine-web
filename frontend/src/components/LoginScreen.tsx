import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { api } from "@/lib/api"
import { Disc3, Loader2 } from "lucide-react"

interface LoginScreenProps {
  onLogin: (username: string) => void
}

export function LoginScreen({ onLogin }: LoginScreenProps) {
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!username.trim() || !password) return

    setLoading(true)
    setError("")

    const result = await api.login(username, password)
    setLoading(false)

    if (result.success) {
      onLogin(result.username || username)
    } else {
      setError(result.error || "Anmeldung fehlgeschlagen")
    }
  }

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <Card className="w-full max-w-sm">
        <CardHeader className="text-center space-y-2">
          <Disc3 className="h-10 w-10 mx-auto text-primary" />
          <CardTitle className="text-2xl tracking-wider uppercase" style={{ fontFamily: "var(--font-retro)" }}>
            Mood Machine
          </CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Input
                placeholder="Benutzername"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                autoFocus
              />
              <Input
                type="password"
                placeholder="Passwort"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
              />
            </div>
            {error && (
              <p className="text-sm text-destructive text-center">{error}</p>
            )}
            <Button type="submit" className="w-full" disabled={loading || !username.trim() || !password}>
              {loading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  Anmelden...
                </>
              ) : (
                "Anmelden"
              )}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
