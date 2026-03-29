import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import {
    Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter
} from "@/components/ui/dialog"
import { Plus, Pencil, Trash2, Sparkles } from "lucide-react"
import { useProviders, createProvider, updateProvider, deleteProvider, seedProviders, getProviderSeeds } from "@/lib/api"
import { ErrorState } from "@/components/error-state"

type OAuthMeta = {
    client_id: string
    client_secret: string
    auth_url: string
    token_url: string
    scopes: string
}

type ProviderForm = {
    name: string
    display_name: string
    auth_type: string
    enabled: boolean
    oauth_meta: OAuthMeta
}

const defaultOAuthMeta: OAuthMeta = {
    client_id: "", client_secret: "", auth_url: "", token_url: "", scopes: ""
}

const defaultForm: ProviderForm = {
    name: "", display_name: "", auth_type: "api_key", enabled: true, oauth_meta: defaultOAuthMeta
}

type Mode = "add" | "edit" | "delete" | "seed" | null

function buildPayload(form: ProviderForm) {
    const payload: any = {
        name: form.name,
        display_name: form.display_name,
        auth_type: form.auth_type,
        enabled: form.enabled,
    }
    if (form.auth_type === "oauth2") {
        payload.oauth_meta = form.oauth_meta
    }
    return payload
}

export function Providers() {
    const { providers, isLoading, isError, mutate } = useProviders()
    const [mode, setMode] = useState<Mode>(null)
    const [selected, setSelected] = useState<any>(null)
    const [form, setForm] = useState<ProviderForm>(defaultForm)
    const [saving, setSaving] = useState(false)
    const [error, setError] = useState<string | null>(null)

    // Bulk operations state
    const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())

    // Seed operations state
    const [seeds, setSeeds] = useState<any[]>([])
    const [selectedSeeds, setSelectedSeeds] = useState<Set<string>>(new Set())

    function openAdd() {
        setForm(defaultForm)
        setError(null)
        setMode("add")
    }

    function openEdit(provider: any) {
        setSelected(provider)
        setForm({
            name: provider.name,
            display_name: provider.display_name,
            auth_type: provider.auth_type,
            enabled: provider.enabled,
            oauth_meta: {
                client_id: provider.oauth_meta?.client_id ?? "",
                client_secret: provider.oauth_meta?.client_secret ?? "",
                auth_url: provider.oauth_meta?.auth_url ?? "",
                token_url: provider.oauth_meta?.token_url ?? "",
                scopes: provider.oauth_meta?.scopes ?? "",
            }
        })
        setError(null)
        setMode("edit")
    }

    function openDelete(provider: any) {
        setSelected(provider)
        setError(null)
        setMode("delete")
    }

    async function openSeed() {
        try {
            const data = await getProviderSeeds()
            setSeeds(data || [])
            setSelectedSeeds(new Set())
            setMode("seed")
            setError(null)
        } catch (err: any) {
            alert("Failed to load generic providers")
        }
    }

    async function handleBulkToggle(enabled: boolean) {
        if (selectedIds.size === 0) return
        setSaving(true)
        try {
            await Promise.all(
                Array.from(selectedIds).map(id => updateProvider(id, { enabled }))
            )
            await mutate()
            setSelectedIds(new Set())
        } catch (err: any) {
            alert(err.message || "Bulk update failed")
        } finally {
            setSaving(false)
        }
    }

    async function handleAdd(e: React.FormEvent) {
        e.preventDefault()
        if (!form.name || !form.display_name) return
        setSaving(true)
        setError(null)
        try {
            await createProvider(buildPayload(form))
            await mutate()
            setMode(null)
        } catch (err: any) {
            setError(err.message || "Failed to create provider")
        } finally {
            setSaving(false)
        }
    }

    async function handleEdit(e: React.FormEvent) {
        e.preventDefault()
        if (!selected) return
        setSaving(true)
        setError(null)
        try {
            await updateProvider(selected.id, buildPayload(form))
            await mutate()
            setMode(null)
        } catch (err: any) {
            setError(err.message || "Failed to update provider")
        } finally {
            setSaving(false)
        }
    }

    async function handleDelete() {
        if (!selected) return
        setSaving(true)
        setError(null)
        try {
            await deleteProvider(selected.id)
            await mutate()
            setMode(null)
        } catch (err: any) {
            setError(err.message || "Failed to delete provider")
        } finally {
            setSaving(false)
        }
    }

    async function handleSeedConfirm() {
        if (selectedSeeds.size === 0) return
        setSaving(true)
        setError(null)
        try {
            await seedProviders(Array.from(selectedSeeds))
            await mutate()
            setMode(null)
        } catch (err: any) {
            setError(err.message || "Seed failed")
        } finally {
            setSaving(false)
        }
    }

    if (isLoading) return <div className="p-8">Loading providers...</div>
    if (isError) return <ErrorState />

    return (
        <div className="p-8 space-y-8">
            <div className="flex justify-between items-center">
                <div>
                    <h2 className="text-3xl font-bold tracking-tight">Providers</h2>
                    <p className="text-muted-foreground pt-1">Manage upstream LLM providers.</p>
                </div>
                <div className="flex gap-2">
                    {selectedIds.size > 0 && (
                        <>
                            <Button variant="outline" onClick={() => handleBulkToggle(true)} disabled={saving}>
                                Enable Selected
                            </Button>
                            <Button variant="outline" onClick={() => handleBulkToggle(false)} disabled={saving}>
                                Disable Selected
                            </Button>
                        </>
                    )}
                    <Button variant="secondary" onClick={openSeed}>
                        <Sparkles className="mr-2 h-4 w-4" />
                        Seed Providers
                    </Button>
                    <Button onClick={openAdd}>
                        <Plus className="mr-2 h-4 w-4" /> Add Provider
                    </Button>
                </div>
            </div>

            <div className="rounded-md border">
                <Table>
                    <TableHeader>
                        <TableRow>
                            <TableHead className="w-[40px]">
                                <Checkbox
                                    checked={providers?.length > 0 && selectedIds.size === providers?.length}
                                    onCheckedChange={(checked) => {
                                        if (checked) {
                                            setSelectedIds(new Set(providers?.map((p: any) => p.id)))
                                        } else {
                                            setSelectedIds(new Set())
                                        }
                                    }}
                                />
                            </TableHead>
                            <TableHead>System Name</TableHead>
                            <TableHead>Display Name</TableHead>
                            <TableHead>Auth Type</TableHead>
                            <TableHead>Status</TableHead>
                            <TableHead className="text-right">Actions</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {providers?.map((provider: any) => (
                            <TableRow key={provider.id}>
                                <TableCell>
                                    <Checkbox
                                        checked={selectedIds.has(provider.id)}
                                        onCheckedChange={(checked) => {
                                            const newSet = new Set(selectedIds)
                                            if (checked) newSet.add(provider.id)
                                            else newSet.delete(provider.id)
                                            setSelectedIds(newSet)
                                        }}
                                    />
                                </TableCell>
                                <TableCell className="font-medium">{provider.name}</TableCell>
                                <TableCell>{provider.display_name}</TableCell>
                                <TableCell>
                                    <Badge variant="outline">{provider.auth_type}</Badge>
                                </TableCell>
                                <TableCell>
                                    {provider.enabled ? (
                                        <Badge className="bg-green-500 hover:bg-green-600">Active</Badge>
                                    ) : (
                                        <Badge variant="secondary">Disabled</Badge>
                                    )}
                                </TableCell>
                                <TableCell className="text-right space-x-1">
                                    <Button variant="ghost" size="sm" onClick={() => openEdit(provider)}>
                                        <Pencil className="h-3.5 w-3.5 mr-1" /> Edit
                                    </Button>
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        className="text-destructive hover:text-destructive"
                                        onClick={() => openDelete(provider)}
                                    >
                                        <Trash2 className="h-3.5 w-3.5 mr-1" /> Delete
                                    </Button>
                                </TableCell>
                            </TableRow>
                        ))}
                        {providers?.length === 0 && (
                            <TableRow>
                                <TableCell colSpan={6} className="text-center text-muted-foreground py-8">
                                    No providers yet. Add one to get started.
                                </TableCell>
                            </TableRow>
                        )}
                    </TableBody>
                </Table>
            </div>

            {/* ── Add Provider Dialog ── */}
            <Dialog open={mode === "add"} onOpenChange={(open: boolean) => !open && setMode(null)}>
                <DialogContent className="sm:max-w-md max-h-[90vh] overflow-y-auto">
                    <DialogHeader>
                        <DialogTitle>Add Provider</DialogTitle>
                        <DialogDescription>Register a new upstream LLM provider.</DialogDescription>
                    </DialogHeader>
                    <form onSubmit={handleAdd} className="space-y-4 py-2">
                        <ProviderFields form={form} setForm={setForm} />
                        {error && <p className="text-sm text-destructive">{error}</p>}
                        <DialogFooter>
                            <Button type="button" variant="outline" onClick={() => setMode(null)}>Cancel</Button>
                            <Button type="submit" disabled={saving || !form.name || !form.display_name}>
                                {saving ? "Saving..." : "Add Provider"}
                            </Button>
                        </DialogFooter>
                    </form>
                </DialogContent>
            </Dialog>

            {/* ── Edit Provider Dialog ── */}
            <Dialog open={mode === "edit"} onOpenChange={(open: boolean) => !open && setMode(null)}>
                <DialogContent className="sm:max-w-md max-h-[90vh] overflow-y-auto">
                    <DialogHeader>
                        <DialogTitle>Edit Provider</DialogTitle>
                        <DialogDescription>Update details for <strong>{selected?.display_name}</strong>.</DialogDescription>
                    </DialogHeader>
                    <form onSubmit={handleEdit} className="space-y-4 py-2">
                        <ProviderFields form={form} setForm={setForm} />
                        {error && <p className="text-sm text-destructive">{error}</p>}
                        <DialogFooter>
                            <Button type="button" variant="outline" onClick={() => setMode(null)}>Cancel</Button>
                            <Button type="submit" disabled={saving || !form.name || !form.display_name}>
                                {saving ? "Saving..." : "Save Changes"}
                            </Button>
                        </DialogFooter>
                    </form>
                </DialogContent>
            </Dialog>

            <Dialog open={mode === "delete"} onOpenChange={(open: boolean) => !open && setMode(null)}>
                <DialogContent className="sm:max-w-sm">
                    <DialogHeader>
                        <DialogTitle>Delete Provider</DialogTitle>
                        <DialogDescription>
                            Are you sure you want to delete <strong>{selected?.display_name}</strong>?
                            This will also delete all associated credentials and models.
                        </DialogDescription>
                    </DialogHeader>
                    {error && <p className="text-sm text-destructive">{error}</p>}
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setMode(null)}>Cancel</Button>
                        <Button variant="destructive" onClick={handleDelete} disabled={saving}>
                            {saving ? "Deleting..." : "Delete"}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* ── Seed Provider Dialog ── */}
            <Dialog open={mode === "seed"} onOpenChange={(open: boolean) => !open && setMode(null)}>
                <DialogContent className="sm:max-w-md max-h-[90vh] overflow-y-auto">
                    <DialogHeader>
                        <DialogTitle>Seed Providers</DialogTitle>
                        <DialogDescription>
                            Select the providers you wish to enable from the catalog.
                        </DialogDescription>
                    </DialogHeader>
                    <div className="space-y-2 py-4 max-h-[400px] overflow-y-auto">
                        {seeds.map((seed: any) => (
                            <div key={seed.name} className="flex items-center space-x-2">
                                <Checkbox
                                    id={`seed-${seed.name}`}
                                    checked={selectedSeeds.has(seed.name)}
                                    onCheckedChange={(checked) => {
                                        const newSet = new Set(selectedSeeds)
                                        if (checked) newSet.add(seed.name)
                                        else newSet.delete(seed.name)
                                        setSelectedSeeds(newSet)
                                    }}
                                />
                                <Label htmlFor={`seed-${seed.name}`}>{seed.display_name} ({seed.name})</Label>
                            </div>
                        ))}
                    </div>
                    {error && <p className="text-sm text-destructive">{error}</p>}
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setMode(null)}>Cancel</Button>
                        <Button
                            onClick={handleSeedConfirm}
                            disabled={saving || selectedSeeds.size === 0}
                        >
                            {saving ? "Seeding..." : "Seed Selected"}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    )
}

function ProviderFields({ form, setForm }: {
    form: ProviderForm
    setForm: React.Dispatch<React.SetStateAction<ProviderForm>>
}) {
    const isOAuth = form.auth_type === "oauth2"

    function setOAuth(field: keyof OAuthMeta, value: string) {
        setForm(f => ({ ...f, oauth_meta: { ...f.oauth_meta, [field]: value } }))
    }

    return (
        <>
            <div className="space-y-1.5">
                <Label htmlFor="pname">System Name</Label>
                <Input
                    id="pname"
                    placeholder="e.g. openai"
                    value={form.name}
                    onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                />
                <p className="text-xs text-muted-foreground">Lowercase slug used internally.</p>
            </div>
            <div className="space-y-1.5">
                <Label htmlFor="display_name">Display Name</Label>
                <Input
                    id="display_name"
                    placeholder="e.g. OpenAI"
                    value={form.display_name}
                    onChange={e => setForm(f => ({ ...f, display_name: e.target.value }))}
                />
            </div>
            <div className="space-y-1.5">
                <Label>Auth Type</Label>
                <Select value={form.auth_type} onValueChange={v => setForm(f => ({ ...f, auth_type: v }))}>
                    <SelectTrigger>
                        <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="api_key">API Key</SelectItem>
                        <SelectItem value="oauth2">OAuth 2.0</SelectItem>
                    </SelectContent>
                </Select>
            </div>

            {isOAuth && (
                <div className="space-y-3 rounded-md border p-3 bg-muted/40">
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">OAuth App Config</p>
                    <div className="space-y-1.5">
                        <Label htmlFor="client_id">Client ID</Label>
                        <Input id="client_id" value={form.oauth_meta.client_id}
                            onChange={e => setOAuth("client_id", e.target.value)} placeholder="Your OAuth app client ID" />
                    </div>
                    <div className="space-y-1.5">
                        <Label htmlFor="client_secret">Client Secret</Label>
                        <Input id="client_secret" type="password" value={form.oauth_meta.client_secret}
                            onChange={e => setOAuth("client_secret", e.target.value)} placeholder="Your OAuth app client secret" />
                    </div>
                    <div className="space-y-1.5">
                        <Label htmlFor="auth_url">Authorization URL</Label>
                        <Input id="auth_url" value={form.oauth_meta.auth_url}
                            onChange={e => setOAuth("auth_url", e.target.value)} placeholder="https://provider.com/oauth/authorize" />
                    </div>
                    <div className="space-y-1.5">
                        <Label htmlFor="token_url">Token URL</Label>
                        <Input id="token_url" value={form.oauth_meta.token_url}
                            onChange={e => setOAuth("token_url", e.target.value)} placeholder="https://provider.com/oauth/token" />
                    </div>
                    <div className="space-y-1.5">
                        <Label htmlFor="scopes">Scopes</Label>
                        <Input id="scopes" value={form.oauth_meta.scopes}
                            onChange={e => setOAuth("scopes", e.target.value)} placeholder="read write (space-separated)" />
                    </div>
                </div>
            )}

            <div className="flex items-center gap-2">
                <input
                    type="checkbox"
                    id="enabled"
                    checked={form.enabled}
                    onChange={e => setForm(f => ({ ...f, enabled: e.target.checked }))}
                    className="h-4 w-4"
                />
                <Label htmlFor="enabled">Enabled</Label>
            </div>
        </>
    )
}
