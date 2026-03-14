import { useState, useMemo } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Textarea } from "@/components/ui/textarea"
import { Input } from "@/components/ui/input"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog"
import { RefreshCw, Server, Search, ChevronRight, ChevronLeft, Trash2, Plus } from "lucide-react"
import { useModels, useProviders, syncProviderModels, updateModel } from "@/lib/api"
import { ErrorState } from "@/components/error-state"
import { ScrollArea } from "@/components/ui/scroll-area"

function ProviderModelManager({ providerId, providerModels, mutateModels }: { providerId: string, providerModels: any[], mutateModels: () => void }) {
    const [search, setSearch] = useState<Record<string, string>>({ available: "", lite: "", base: "", thinking: "" })
    const [selection, setSelection] = useState<Record<string, Set<string>>>({
        available: new Set(),
        lite: new Set(),
        base: new Set(),
        thinking: new Set()
    })
    const [isUpdating, setIsUpdating] = useState(false)
    const [showAddDialog, setShowAddDialog] = useState(false)
    const [addModelText, setAddModelText] = useState("")
    const [isAdding, setIsAdding] = useState(false)

    // Derived lists
    const groupedModels = useMemo(() => {
        const available: any[] = []
        const lite: any[] = []
        const base: any[] = []
        const thinking: any[] = []

        providerModels.forEach(m => {
            if (m.tier === "lite") lite.push(m)
            else if (m.tier === "base") base.push(m)
            else if (m.tier === "thinking") thinking.push(m)
            else available.push(m)
        })
        return { available, lite, base, thinking }
    }, [providerModels])

    const handleSearch = (tier: string, value: string) => {
        setSearch(prev => ({ ...prev, [tier]: value }))
    }

    const toggleSelection = (tier: string, modelId: string) => {
        setSelection(prev => {
            const newSet = new Set(prev[tier])
            if (newSet.has(modelId)) {
                newSet.delete(modelId)
            } else {
                newSet.add(modelId)
            }
            return { ...prev, [tier]: newSet }
        })
    }

    const moveModels = async (fromTier: string, toTier: string) => {
        const selectedIds = Array.from(selection[fromTier])
        if (selectedIds.length === 0) return

        setIsUpdating(true)
        try {
            await Promise.all(selectedIds.map(id => {
                const targetTier = toTier === "available" ? "" : toTier
                // Find model DB ID from model_id
                const model = providerModels.find(m => m.model_id === id)
                if (model) {
                    return updateModel(model.id, { tier: targetTier })
                }
                return Promise.resolve()
            }))

            // clear selection and refetch
            setSelection(prev => ({ ...prev, [fromTier]: new Set() }))
            await mutateModels()
        } catch (e) {
            console.error("Failed to move models", e)
        } finally {
            setIsUpdating(false)
        }
    }

    const moveSelectedToAvailable = async () => {
        const selectedLite = Array.from(selection["lite"])
        const selectedBase = Array.from(selection["base"])
        const selectedThinking = Array.from(selection["thinking"])

        const allSelected = [
            ...selectedLite.map(id => ({ id, from: "lite" })),
            ...selectedBase.map(id => ({ id, from: "base" })),
            ...selectedThinking.map(id => ({ id, from: "thinking" }))
        ]

        if (allSelected.length === 0) return

        setIsUpdating(true)
        try {
            await Promise.all(allSelected.map(sel => {
                const model = providerModels.find(m => m.model_id === sel.id)
                if (model) {
                    return updateModel(model.id, { tier: "" })
                }
                return Promise.resolve()
            }))

            // Clear selections before mutating to avoid stale state
            setSelection(prev => ({
                ...prev,
                lite: new Set(),
                base: new Set(),
                thinking: new Set()
            }))

            // Refresh data to show models in "All Available"
            await mutateModels()
        } catch (e) {
            console.error("Failed to remove models", e)
        } finally {
            setIsUpdating(false)
        }
    }

    const deleteSelectedAvailable = async () => {
        const selectedIds = Array.from(selection["available"])
        if (selectedIds.length === 0) return

        setIsUpdating(true)
        try {
            await Promise.all(selectedIds.map(id => {
                const model = providerModels.find(m => m.model_id === id)
                if (model) return updateModel(model.id, { enabled: false })
                return Promise.resolve()
            }))
            setSelection(prev => ({ ...prev, available: new Set() }))
            await mutateModels()
        } catch (e) {
            console.error("Failed to unselect models", e)
        } finally {
            setIsUpdating(false)
        }
    }

    const addModels = async () => {
        const modelIds = addModelText.split(/[\n,]+/).map(s => s.trim()).filter(Boolean)
        if (modelIds.length === 0) return
        setIsAdding(true)
        try {
            await Promise.all(modelIds.map(modelId =>
                fetch(`/api/admin/models`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include',
                    body: JSON.stringify({ provider_id: providerId, model_id: modelId, tier: "", cost_in_1m: 0, cost_out_1m: 0, enabled: true })
                })
            ))
            setAddModelText("")
            setShowAddDialog(false)
            await mutateModels()
        } catch (e) {
            console.error("Failed to add models", e)
        } finally {
            setIsAdding(false)
        }
    }

    const toggleAllSelection = (tier: string, itemsToSelect: any[]) => {
        setSelection(prev => {
            const currentSelected = prev[tier].size
            if (currentSelected === itemsToSelect.length && itemsToSelect.length > 0) {
                // If all are selected, deselect all
                return { ...prev, [tier]: new Set() }
            } else {
                // Otherwise select all currently filtered items
                const newSet = new Set(itemsToSelect.map(m => m.model_id))
                return { ...prev, [tier]: newSet }
            }
        })
    }

    const renderListBox = (title: string, tier: 'available' | 'lite' | 'base' | 'thinking') => {
        const searchTokens = search[tier].toLowerCase().split(/\s+/).filter(Boolean)
        const items = groupedModels[tier].filter(m => {
            const id = m.model_id.toLowerCase()
            return searchTokens.every(token => id.includes(token))
        })
        const selected = selection[tier]

        return (
            <div className="flex flex-col flex-1 border rounded-md overflow-hidden bg-background">
                <div className="p-2 border-b bg-muted/50 font-medium text-sm text-center">
                    {title} ({groupedModels[tier].length})
                </div>
                <div className="p-2 border-b">
                    <div className="relative mb-2">
                        <Search className="absolute left-2 top-2 h-4 w-4 text-muted-foreground" />
                        <Input
                            placeholder="Search..."
                            className="h-8 pl-8 text-xs"
                            value={search[tier]}
                            onChange={(e) => handleSearch(tier, e.target.value)}
                        />
                    </div>
                    <div className="flex justify-between items-center text-xs">
                        <span className="text-muted-foreground">{selected.size} selected</span>
                        <Button
                            variant="ghost"
                            size="sm"
                            className="h-6 text-xs px-2"
                            onClick={() => toggleAllSelection(tier, items)}
                            disabled={items.length === 0}
                        >
                            {selected.size === items.length && items.length > 0 ? "Deselect All" : "Select All"}
                        </Button>
                    </div>
                </div>
                <ScrollArea className="h-64">
                    <div className="p-1">
                        {items.length === 0 ? (
                            <div className="text-xs text-muted-foreground p-4 text-center">No models found</div>
                        ) : (
                            items.map(m => (
                                <div
                                    key={m.model_id}
                                    onClick={() => toggleSelection(tier, m.model_id)}
                                    className={`text-sm font-medium p-2 mb-1 rounded-sm cursor-pointer select-none transition-colors border ${selected.has(m.model_id) ? 'bg-primary/10 border-primary/50 text-foreground' : 'border-transparent hover:bg-muted text-foreground'}`}
                                >
                                    <div className="truncate" title={m.model_id}>{m.model_id}</div>
                                </div>
                            ))
                        )}
                    </div>
                </ScrollArea>
            </div>
        )
    }

    return (
        <div className="relative">
            {isUpdating && (
                <div className="absolute inset-0 z-10 bg-background/50 flex flex-col items-center justify-center rounded-md backdrop-blur-[1px]">
                    <RefreshCw className="h-6 w-6 animate-spin text-primary" />
                    <span className="text-xs mt-2 font-medium">Updating...</span>
                </div>
            )}
            <div className="flex gap-4 items-stretch">
                {/* Available List */}
                <div className="w-1/4 flex flex-col">
                    {renderListBox("All Available", "available")}
                </div>

                {/* Left/Right Buttons */}
                <div className="flex flex-col justify-center gap-2">
                    <Button
                        size="sm"
                        variant="secondary"
                        className="text-xs w-full justify-between"
                        onClick={() => moveModels("available", "lite")}
                        disabled={selection.available.size === 0 || isUpdating}
                    >
                        To Lite <ChevronRight className="h-3 w-3 ml-1" />
                    </Button>
                    <Button
                        size="sm"
                        variant="secondary"
                        className="text-xs w-full justify-between"
                        onClick={() => moveModels("available", "base")}
                        disabled={selection.available.size === 0 || isUpdating}
                    >
                        To Base <ChevronRight className="h-3 w-3 ml-1" />
                    </Button>
                    <Button
                        size="sm"
                        variant="secondary"
                        className="text-xs w-full justify-between"
                        onClick={() => moveModels("available", "thinking")}
                        disabled={selection.available.size === 0 || isUpdating}
                    >
                        To Thinking <ChevronRight className="h-3 w-3 ml-1" />
                    </Button>
                    <div className="h-px bg-border my-2" />
                    <Button
                        size="sm"
                        variant="outline"
                        className="text-xs w-full justify-between"
                        onClick={moveSelectedToAvailable}
                        disabled={(selection.lite.size === 0 && selection.base.size === 0 && selection.thinking.size === 0) || isUpdating}
                    >
                        <ChevronLeft className="h-3 w-3 mr-1" /> Remove
                    </Button>
                    <Button
                        size="sm"
                        variant="destructive"
                        className="text-xs w-full justify-between"
                        onClick={deleteSelectedAvailable}
                        disabled={selection.available.size === 0 || isUpdating}
                    >
                        <Trash2 className="h-3 w-3 mr-1" /> Unselect
                    </Button>
                    <div className="h-px bg-border my-2" />
                    <Button
                        size="sm"
                        variant="outline"
                        className="text-xs w-full justify-between"
                        onClick={() => setShowAddDialog(true)}
                    >
                        <Plus className="h-3 w-3 mr-1" /> Add Model
                    </Button>
                </div>

                {/* Tier Lists */}
                <div className="flex-1 flex gap-4">
                    {renderListBox("Lite", "lite")}
                    {renderListBox("Base", "base")}
                    {renderListBox("Thinking", "thinking")}
                </div>
            </div>

            {/* Add Model Dialog */}
            <Dialog open={showAddDialog} onOpenChange={setShowAddDialog}>
                <DialogContent className="sm:max-w-md">
                    <DialogHeader>
                        <DialogTitle>Add Models Manually</DialogTitle>
                    </DialogHeader>
                    <div className="space-y-3 py-2">
                        <p className="text-xs text-muted-foreground">Enter one model ID per line (or comma-separated). They will be added to Available models.</p>
                        <Textarea
                            className="font-mono text-sm min-h-[160px]"
                            placeholder={"gpt-4o\nclaude-3-5-sonnet-20241022\ngemini-2.0-flash"}
                            value={addModelText}
                            onChange={e => setAddModelText(e.target.value)}
                        />
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setShowAddDialog(false)}>Cancel</Button>
                        <Button onClick={addModels} disabled={isAdding || !addModelText.trim()}>
                            {isAdding ? <RefreshCw className="h-4 w-4 mr-2 animate-spin" /> : <Plus className="h-4 w-4 mr-2" />}
                            Add Models
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    )
}

export function Models() {
    const { models, isLoading: modelsLoading, isError: modelsError, mutate: mutateModels } = useModels()
    const { providers, isLoading: provLoading, isError: provError } = useProviders()

    const [syncing, setSyncing] = useState<Record<string, boolean>>({})
    const [syncResult, setSyncResult] = useState<{ id: string, msg: string, error?: boolean } | null>(null)

    async function handleSync(providerId: string) {
        setSyncing(prev => ({ ...prev, [providerId]: true }))
        setSyncResult(null)
        try {
            const res = await syncProviderModels(providerId)
            setSyncResult({ id: providerId, msg: `Synced ${res.total} models (${res.inserted} new)` })
            await mutateModels()
        } catch (err: any) {
            setSyncResult({ id: providerId, msg: err.message || "Sync failed", error: true })
        } finally {
            setSyncing(prev => ({ ...prev, [providerId]: false }))
        }
    }

    if (modelsLoading || provLoading) return <div className="p-8 justify-center flex mt-20"><RefreshCw className="animate-spin text-muted-foreground" /></div>
    if (modelsError || provError) return <ErrorState />

    const modelsByProvider = (models || []).reduce((acc: any, m: any) => {
        if (!acc[m.provider_id]) acc[m.provider_id] = []
        acc[m.provider_id].push(m)
        return acc
    }, {})

    return (
        <div className="p-8 space-y-8">
            <div>
                <h2 className="text-3xl font-bold tracking-tight">Provider Models</h2>
                <p className="text-muted-foreground pt-1">Sync and manage models for each configured provider.</p>
            </div>

            <div className="space-y-8">
                {providers?.filter((p: any) => p.enabled).map((provider: any) => {
                    const allProviderModels = modelsByProvider[provider.id] || []
                    const providerModels = allProviderModels.filter((m: any) => m.enabled)
                    const disabledCount = allProviderModels.length - providerModels.length
                    const isSyncing = syncing[provider.id]

                    return (
                        <Card key={provider.id}>
                            <CardHeader className="flex flex-row items-center justify-between pb-4">
                                <div className="space-y-1">
                                    <CardTitle className="flex items-center gap-2">
                                        <Server className="h-5 w-5 text-muted-foreground" />
                                        {provider.display_name}
                                    </CardTitle>
                                    <CardDescription>
                                        {providerModels.length} selected model{providerModels.length !== 1 ? 's' : ''} cached locally.
                                        {disabledCount > 0 && (
                                            <span className="ml-1 text-muted-foreground/70">
                                                ({disabledCount} unselected — restore in{' '}
                                                <a href="/model-management" className="underline hover:text-foreground">Model Management</a>)
                                            </span>
                                        )}
                                    </CardDescription>
                                    {syncResult && syncResult.id === provider.id && (
                                        <p className={`text-sm ${syncResult.error ? 'text-destructive' : 'text-green-600'}`}>
                                            {syncResult.msg}
                                        </p>
                                    )}
                                </div>
                                <Button
                                    variant="outline"
                                    onClick={() => handleSync(provider.id)}
                                    disabled={isSyncing}
                                    className="gap-2"
                                >
                                    <RefreshCw className={`h-4 w-4 ${isSyncing ? 'animate-spin' : ''}`} />
                                    {isSyncing ? "Syncing..." : "Sync Models"}
                                </Button>
                            </CardHeader>
                            <CardContent>
                                {providerModels.length > 0 ? (
                                    <ProviderModelManager
                                        providerId={provider.id}
                                        providerModels={providerModels}
                                        mutateModels={mutateModels}
                                    />
                                ) : (
                                    <div className="text-center py-6 text-sm text-muted-foreground border rounded-md border-dashed">
                                        {allProviderModels.length > 0
                                            ? `All ${allProviderModels.length} model${allProviderModels.length !== 1 ? 's' : ''} are unselected. Select them in Model Management.`
                                            : `No models synced yet. Click "Sync Models" to fetch from ${provider.display_name}.`
                                        }
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    )
                })}

                {providers?.filter((p: any) => p.enabled).length === 0 && (
                    <div className="text-center py-12 text-muted-foreground border rounded-lg">
                        No enabled providers configured. Go to Providers to enable one.
                    </div>
                )}
            </div>
        </div>
    )
}
