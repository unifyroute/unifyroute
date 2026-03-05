import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { Switch } from "@/components/ui/switch"
import { Trash2, Key, Check, Copy, Edit2, X, Eye, EyeOff } from "lucide-react"
import { useGatewayKeys, createGatewayKey, deleteGatewayKey, getAuthToken, setAuthToken, updateGatewayKey, revealGatewayKey } from "@/lib/api"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"

export function Settings() {
    const { keys, isLoading, mutate } = useGatewayKeys()
    const [activeToken, setActiveToken] = useState("")
    const [createOpen, setCreateOpen] = useState(false)
    const [refreshingAdmin, setRefreshingAdmin] = useState(false)
    const [newLabel, setNewLabel] = useState("")
    const [creating, setCreating] = useState(false)
    const [createdToken, setCreatedToken] = useState<string | null>(null)
    const [editingId, setEditingId] = useState<string | null>(null)
    const [editLabel, setEditLabel] = useState("")
    const [revealedKeys, setRevealedKeys] = useState<{ [id: string]: string }>({})

    useEffect(() => {
        setActiveToken(getAuthToken())
    }, [])

    function handleSaveActiveToken() {
        setAuthToken(activeToken)
        window.location.reload() // Reload app to use new token
    }

    async function handleCreate(e: React.FormEvent) {
        e.preventDefault()
        if (!newLabel) return
        setCreating(true)
        try {
            const res = await createGatewayKey({ label: newLabel, scopes: ["api"] })
            setCreatedToken(res.token)
            await mutate()
        } catch (err: any) {
            alert(err.message || "Failed to create API key")
        } finally {
            setCreating(false)
        }
    }

    async function handleRefreshAdminToken() {
        if (!confirm("Generate a new Admin Token? The current one will be immediately revoked from the database and you will be automatically logged in with the new one.")) return
        setRefreshingAdmin(true)
        try {
            const res = await createGatewayKey({ label: `Web Dashboard (Auto)`, scopes: ["admin"] })
            setAuthToken(res.token)
            window.location.reload()
        } catch (err: any) {
            alert(err.message || "Failed to refresh Admin key")
            setRefreshingAdmin(false)
        }
    }

    function closeCreate() {
        setCreateOpen(false)
        setCreatedToken(null)
        setNewLabel("")
    }

    async function handleDelete(id: string) {
        if (!confirm("Revoke this key? Downstream clients using it will be blocked immediately.")) return
        try {
            await deleteGatewayKey(id)
            await mutate()
        } catch (err: any) {
            alert(err.message || "Failed to revoke key")
        }
    }

    async function handleSaveEdit(id: string) {
        if (!editLabel) return
        try {
            await updateGatewayKey(id, { label: editLabel })
            setEditingId(null)
            await mutate()
        } catch (err: any) {
            alert(err.message || "Failed to update key label")
        }
    }

    async function handleReveal(id: string) {
        if (revealedKeys[id]) {
            const copy = { ...revealedKeys }
            delete copy[id]
            setRevealedKeys(copy)
            return
        }
        try {
            const res = await revealGatewayKey(id)
            setRevealedKeys(prev => ({ ...prev, [id]: res.reveal_info }))
        } catch (err: any) {
            alert(err.message || "Failed to reveal key")
        }
    }

    return (
        <div className="p-8 space-y-8">
            <div>
                <h2 className="text-3xl font-bold tracking-tight">Settings</h2>
                <p className="text-muted-foreground pt-1">Manage global gateway configuration and API keys.</p>
            </div>

            <div className="grid gap-6 animate-in fade-in-50 duration-500">
                {/* ── Active GUI Token ── */}
                <Card className="border-primary/20 bg-primary/5">
                    <CardHeader>
                        <CardTitle className="text-primary flex items-center gap-2">
                            <Key className="h-5 w-5" /> Active Web Dashboard Token
                        </CardTitle>
                        <CardDescription>
                            This is the token the browser currently uses to communicate with the API Gateway backend.
                            If you get authentication errors, verify this matches a valid Gateway API Key.
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="flex items-center gap-4">
                            <Input
                                type="password"
                                value={activeToken}
                                onChange={e => setActiveToken(e.target.value)}
                                className="max-w-[400px] font-mono"
                                placeholder="sk-..."
                            />
                            <Button variant="default" onClick={handleSaveActiveToken} disabled={activeToken === getAuthToken()}>
                                <Check className="h-4 w-4 mr-2" /> Save & Reload
                            </Button>
                            <Button variant="outline" onClick={handleRefreshAdminToken} disabled={refreshingAdmin}>
                                {refreshingAdmin ? "Refreshing..." : "Refresh Web Token"}
                            </Button>
                        </div>
                    </CardContent>
                </Card>

                {/* ── Gateway Keys ── */}
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0">
                        <div className="space-y-1">
                            <CardTitle>Gateway API Keys</CardTitle>
                            <CardDescription>Authentication keys used by downstream clients and UnifyRouter to connect to this router.</CardDescription>
                        </div>
                        <Button onClick={() => setCreateOpen(true)}>Generate New Key</Button>
                    </CardHeader>
                    <CardContent>
                        <div className="rounded-md border">
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead>Label</TableHead>
                                        <TableHead>Key Preview / Hash</TableHead>
                                        <TableHead className="w-[100px]">Status</TableHead>
                                        <TableHead className="text-right">Actions</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {isLoading && (
                                        <TableRow><TableCell colSpan={4} className="text-center py-8">Loading keys...</TableCell></TableRow>
                                    )}
                                    {keys?.map((k: any) => (
                                        <TableRow key={k.id}>
                                            <TableCell className="font-medium">
                                                {editingId === k.id ? (
                                                    <div className="flex items-center gap-2">
                                                        <Input
                                                            value={editLabel}
                                                            onChange={e => setEditLabel(e.target.value)}
                                                            className="h-8 w-[200px]"
                                                            autoFocus
                                                            onKeyDown={e => e.key === 'Enter' && handleSaveEdit(k.id)}
                                                        />
                                                        <Button variant="ghost" size="sm" onClick={() => handleSaveEdit(k.id)} className="h-8 w-8 p-0 text-green-600">
                                                            <Check className="h-4 w-4" />
                                                        </Button>
                                                        <Button variant="ghost" size="sm" onClick={() => setEditingId(null)} className="h-8 w-8 p-0">
                                                            <X className="h-4 w-4" />
                                                        </Button>
                                                    </div>
                                                ) : (
                                                    <div className="flex items-center gap-2 group">
                                                        <span>{k.label}</span>
                                                        {k.scopes?.includes('admin') && <Badge variant="outline" className="font-normal">Admin</Badge>}
                                                        <Button
                                                            variant="ghost"
                                                            size="sm"
                                                            onClick={() => { setEditingId(k.id); setEditLabel(k.label); }}
                                                            className="h-6 w-6 p-0 opacity-0 group-hover:opacity-100 transition-opacity"
                                                        >
                                                            <Edit2 className="h-3 w-3" />
                                                        </Button>
                                                    </div>
                                                )}
                                            </TableCell>
                                            <TableCell className="font-mono text-xs text-muted-foreground">
                                                <div className="flex items-center gap-2">
                                                    <span>{revealedKeys[k.id] || "••••••••••••••••••••••••••••••••"}</span>
                                                    <Button
                                                        variant="ghost"
                                                        size="sm"
                                                        onClick={() => handleReveal(k.id)}
                                                        className="h-6 w-6 p-0"
                                                        title={revealedKeys[k.id] ? "Hide Key" : "Reveal partial key"}
                                                    >
                                                        {revealedKeys[k.id] ? <EyeOff className="h-3 w-3" /> : <Eye className="h-3 w-3" />}
                                                    </Button>
                                                    {revealedKeys[k.id] && (
                                                        <Button
                                                            variant="ghost"
                                                            size="sm"
                                                            onClick={() => navigator.clipboard.writeText(revealedKeys[k.id])}
                                                            className="h-6 w-6 p-0"
                                                            title="Copy Key"
                                                        >
                                                            <Copy className="h-3 w-3" />
                                                        </Button>
                                                    )}
                                                </div>
                                            </TableCell>
                                            <TableCell>
                                                {k.enabled ? <Badge className="bg-green-500">Active</Badge> : <Badge variant="secondary">Disabled</Badge>}
                                            </TableCell>
                                            <TableCell className="text-right">
                                                <Button variant="ghost" size="sm" className="text-destructive hover:text-destructive" onClick={() => handleDelete(k.id)}>
                                                    <Trash2 className="h-4 w-4" />
                                                </Button>
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                    {keys?.length === 0 && (
                                        <TableRow>
                                            <TableCell colSpan={4} className="text-center text-muted-foreground py-8">
                                                No keys defined. Generate one above to allow connections.
                                            </TableCell>
                                        </TableRow>
                                    )}
                                </TableBody>
                            </Table>
                        </div>
                    </CardContent>
                </Card>

                {/* ── Polling ── */}
                <Card>
                    <CardHeader>
                        <CardTitle>Polling Configuration</CardTitle>
                        <CardDescription>Background worker intervals for synchronization.</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-6">
                        <div className="flex items-center space-x-2 border p-4 rounded-lg bg-slate-50 dark:bg-slate-900">
                            <Switch id="auto-refresh" defaultChecked />
                            <div className="grid gap-1.5 leading-none">
                                <Label htmlFor="auto-refresh">Auto-Refresh Dashboard Data</Label>
                                <p className="text-sm text-muted-foreground">Keep charts and tables updated in real-time</p>
                            </div>
                        </div>
                    </CardContent>
                </Card>
            </div>

            {/* Create Dialog */}
            <Dialog open={createOpen} onOpenChange={(v: boolean) => !v && closeCreate()}>
                <DialogContent>
                    {!createdToken ? (
                        <form onSubmit={handleCreate}>
                            <DialogHeader>
                                <DialogTitle>Generate Gateway API Key</DialogTitle>
                                <DialogDescription>Create a new API key for a downstream application interacting with the API.</DialogDescription>
                            </DialogHeader>
                            <div className="grid gap-4 py-6">
                                <div className="space-y-2">
                                    <Label>Key Label</Label>
                                    <Input value={newLabel} onChange={e => setNewLabel(e.target.value)} placeholder="e.g. UnifyRouter Production" autoFocus />
                                </div>
                            </div>
                            <DialogFooter>
                                <Button type="button" variant="outline" onClick={closeCreate}>Cancel</Button>
                                <Button type="submit" disabled={!newLabel || creating}>
                                    {creating ? "Generating..." : "Generate Key"}
                                </Button>
                            </DialogFooter>
                        </form>
                    ) : (
                        <div className="space-y-6">
                            <DialogHeader>
                                <DialogTitle>Key Generated</DialogTitle>
                                <DialogDescription>Save this key now. For security reasons, it will never be printed again.</DialogDescription>
                            </DialogHeader>
                            <div className="flex items-center gap-2 p-3 bg-slate-100 dark:bg-slate-900 rounded border">
                                <code className="text-sm font-mono flex-1">{createdToken}</code>
                                <Button size="sm" variant="secondary" onClick={() => navigator.clipboard.writeText(createdToken)}>
                                    <Copy className="h-4 w-4" />
                                </Button>
                            </div>
                            <DialogFooter>
                                <Button onClick={closeCreate}>Done</Button>
                            </DialogFooter>
                        </div>
                    )}
                </DialogContent>
            </Dialog>
        </div>
    )
}
