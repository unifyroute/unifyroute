import { useState, useEffect, useMemo } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import {
    Save, RefreshCw, AlertCircle, CheckCircle2, Zap, Cpu, BookOpen,
    Settings2, Activity, Search, Globe
} from "lucide-react"
import { useRoutingConfig, saveRoutingConfig, useProviders, useModels } from "@/lib/api"
import * as yaml from "js-yaml"

// ── Types ─────────────────────────────────────────────────────────────────────

type TierKey = "auto" | "lite" | "base" | "thinking"

interface RoutingModel {
    provider: string
    model: string
}

interface RoutingTier {
    strategy?: string
    fallback_on?: (number | string)[]
    models?: RoutingModel[]
}

interface RoutingConfig {
    tiers?: {
        auto?: RoutingTier
        lite?: RoutingTier
        base?: RoutingTier
        thinking?: RoutingTier
        [key: string]: RoutingTier | undefined
    }
}

interface ModelEntry {
    fullId: string        // "providerName::modelId"
    modelId: string
    providerName: string
    providerDisplayName: string
}

// ── Column config ─────────────────────────────────────────────────────────────

const TIER_COLUMNS: Array<{
    key: TierKey
    label: string
    icon: React.ElementType
    headerClass: string
    titleClass: string
    borderClass: string
    description: string
}> = [
    {
        key: "auto",
        label: "Auto",
        icon: Globe,
        headerClass: "bg-emerald-50 dark:bg-emerald-950/30 border-b border-emerald-100 dark:border-emerald-900/50",
        titleClass: "text-emerald-700 dark:text-emerald-300",
        borderClass: "border-emerald-200 dark:border-emerald-900",
        description: "Fallback pool — the router picks from these when no explicit tier matches.",
    },
    {
        key: "lite",
        label: "Simple Ask (Lite)",
        icon: Zap,
        headerClass: "bg-sky-50 dark:bg-sky-950/30 border-b border-sky-100 dark:border-sky-900/50",
        titleClass: "text-sky-700 dark:text-sky-300",
        borderClass: "border-sky-200 dark:border-sky-900",
        description: "Fast and cheap models for quick questions and high-volume tasks.",
    },
    {
        key: "base",
        label: "Better Model (Base)",
        icon: Cpu,
        headerClass: "bg-violet-50 dark:bg-violet-950/30 border-b border-violet-100 dark:border-violet-900/50",
        titleClass: "text-violet-700 dark:text-violet-300",
        borderClass: "border-violet-200 dark:border-violet-900",
        description: "Capable models for balanced, everyday intelligent tasks and light coding.",
    },
    {
        key: "thinking",
        label: "Reasoning Model (Thinking)",
        icon: BookOpen,
        headerClass: "bg-amber-50 dark:bg-amber-950/30 border-b border-amber-100 dark:border-amber-900/50",
        titleClass: "text-amber-700 dark:text-amber-300",
        borderClass: "border-amber-200 dark:border-amber-900",
        description: "Large, intelligent models for complex reasoning, planning, and advanced coding.",
    },
]

// ── Helper ─────────────────────────────────────────────────────────────────────

function buildFullId(provider: string, model: string) {
    return `${provider}::${model}`
}

function parseFullId(fullId: string): { provider: string; model: string } {
    const [provider, ...rest] = fullId.split("::")
    return { provider, model: rest.join("::") }
}

// ── ModelColumn ────────────────────────────────────────────────────────────────

interface ModelColumnProps {
    col: typeof TIER_COLUMNS[number]
    allModels: ModelEntry[]
    selected: Set<string>
    onToggle: (fullId: string) => void
}

function ModelColumn({ col, allModels, selected, onToggle }: ModelColumnProps) {
    const [search, setSearch] = useState("")
    const Icon = col.icon

    // Group by provider
    const grouped = useMemo(() => {
        const q = search.toLowerCase()
        const map = new Map<string, { displayName: string; models: ModelEntry[] }>()
        for (const m of allModels) {
            if (q && !m.modelId.toLowerCase().includes(q) && !m.providerDisplayName.toLowerCase().includes(q)) continue
            if (!map.has(m.providerName)) {
                map.set(m.providerName, { displayName: m.providerDisplayName, models: [] })
            }
            map.get(m.providerName)!.models.push(m)
        }
        return Array.from(map.values())
    }, [allModels, search])

    return (
        <Card className={`${col.borderClass} shadow-sm flex flex-col min-w-0`}>
            <CardHeader className={`${col.headerClass} py-3 px-4`}>
                <CardTitle className={`text-sm font-semibold ${col.titleClass} flex items-center gap-2`}>
                    <Icon className="h-4 w-4 flex-shrink-0" />
                    <span className="leading-tight">{col.label}</span>
                </CardTitle>
                <CardDescription className="text-xs mt-1">{col.description}</CardDescription>
            </CardHeader>

            {/* Search */}
            <div className="px-3 pt-3 pb-2 border-b">
                <div className="relative">
                    <Search className="absolute left-2 top-2 h-3.5 w-3.5 text-muted-foreground" />
                    <Input
                        placeholder="Search models..."
                        className="h-7 pl-7 text-xs"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                    />
                </div>
            </div>

            <CardContent className="pt-3 flex-1 overflow-y-auto max-h-96 space-y-4 px-3">
                {grouped.length === 0 ? (
                    <p className="text-xs text-muted-foreground text-center py-4">No models found</p>
                ) : (
                    grouped.map(group => (
                        <div key={group.displayName} className="space-y-1.5">
                            <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                                {group.displayName}
                            </h4>
                            <div className="space-y-1 pl-1">
                                {group.models.map(m => (
                                    <label
                                        key={m.fullId}
                                        className="flex items-start gap-2 cursor-pointer group"
                                    >
                                        <Checkbox
                                            className="mt-0.5 flex-shrink-0"
                                            checked={selected.has(m.fullId)}
                                            onCheckedChange={() => onToggle(m.fullId)}
                                        />
                                        <span className="text-xs font-mono break-all leading-tight group-hover:text-foreground text-muted-foreground transition-colors">
                                            {m.modelId}
                                        </span>
                                    </label>
                                ))}
                            </div>
                        </div>
                    ))
                )}
            </CardContent>

            <CardFooter className="bg-slate-50/50 dark:bg-slate-900/30 border-t py-2.5 px-3 flex justify-between items-center">
                <span className="text-xs text-muted-foreground">
                    Selected: <strong className="text-foreground">{selected.size}</strong>
                </span>
                {selected.size === 0 && (
                    <span className="text-xs text-amber-500 font-medium">None selected</span>
                )}
            </CardFooter>
        </Card>
    )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export function RoutingStrategy() {
    const { routingConfig, isLoading: configLoading, mutate } = useRoutingConfig()
    const { providers: allProviders } = useProviders()
    const { models: allModels } = useModels()

    const [globalStrategy, setGlobalStrategy] = useState<"highest_quota" | "cheapest_available">("highest_quota")
    const [tierModels, setTierModels] = useState<Record<TierKey, Set<string>>>({
        auto: new Set(),
        lite: new Set(),
        base: new Set(),
        thinking: new Set(),
    })

    const [isSaving, setIsSaving] = useState(false)
    const [saveError, setSaveError] = useState("")
    const [saveSuccess, setSaveSuccess] = useState(false)
    const [originalConfigObj, setOriginalConfigObj] = useState<RoutingConfig>({})

    // Parse incoming YAML config and populate state
    useEffect(() => {
        if (routingConfig !== undefined && routingConfig !== null) {
            try {
                const parsed = yaml.load(routingConfig) as RoutingConfig
                setOriginalConfigObj(parsed || {})

                const getSet = (tier: RoutingTier | undefined): Set<string> => {
                    if (!tier?.models) return new Set()
                    return new Set(tier.models.map(m => buildFullId(m.provider, m.model)))
                }

                setTierModels({
                    auto: getSet(parsed?.tiers?.auto),
                    lite: getSet(parsed?.tiers?.lite),
                    base: getSet(parsed?.tiers?.base),
                    thinking: getSet(parsed?.tiers?.thinking),
                })

                const hasCostStrategy = ["lite", "base", "thinking", "auto"].some(t =>
                    (parsed?.tiers?.[t] as RoutingTier | undefined)?.strategy === "cheapest_available"
                )
                setGlobalStrategy(hasCostStrategy ? "cheapest_available" : "highest_quota")
            } catch (e) {
                console.error("Error parsing routing.yaml:", e)
                setSaveError("Failed to parse the existing configuration. Saving will overwrite it.")
            }
        }
    }, [routingConfig])

    // Build flat model list grouped by provider
    const availableModels = useMemo((): ModelEntry[] => {
        if (!allProviders || !allModels) return []

        const providersMap = new Map<string, { name: string; display_name: string }>()
        ;(allProviders as Array<{ id: string; name: string; display_name: string; enabled: boolean }>)
            .filter(p => p.enabled)
            .forEach(p => providersMap.set(p.id, p))

        const entries: ModelEntry[] = []
        ;(allModels as Array<{ id: string; model_id: string; provider_id: string; enabled: boolean; tier: string }>)
            .filter(m => m.enabled && m.tier && m.tier.trim() !== "")
            .forEach(m => {
                const provider = providersMap.get(m.provider_id)
                if (provider) {
                    entries.push({
                        fullId: buildFullId(provider.name, m.model_id),
                        modelId: m.model_id,
                        providerName: provider.name,
                        providerDisplayName: provider.display_name,
                    })
                }
            })

        return entries
    }, [allProviders, allModels])

    const handleSave = async () => {
        setIsSaving(true)
        setSaveError("")
        setSaveSuccess(false)

        try {
            const newConfig: RoutingConfig = {
                ...originalConfigObj,
                tiers: { ...(originalConfigObj.tiers || {}) },
            }

            const buildTier = (key: TierKey, existing?: RoutingTier): RoutingTier => ({
                ...existing,
                strategy: globalStrategy,
                fallback_on: existing?.fallback_on || [429, 503, "timeout"],
                models: Array.from(tierModels[key]).map(id => parseFullId(id)),
            })

            newConfig.tiers!.auto = buildTier("auto", newConfig.tiers?.auto)
            newConfig.tiers!.lite = buildTier("lite", newConfig.tiers?.lite)
            newConfig.tiers!.base = buildTier("base", newConfig.tiers?.base)
            newConfig.tiers!.thinking = buildTier("thinking", newConfig.tiers?.thinking)

            const yamlString = yaml.dump(newConfig, { indent: 2, skipInvalid: true })
            await saveRoutingConfig(yamlString)
            await mutate()
            setSaveSuccess(true)
            setTimeout(() => setSaveSuccess(false), 3000)
        } catch (e: unknown) {
            setSaveError(e instanceof Error ? e.message : "Failed to save configuration")
        } finally {
            setIsSaving(false)
        }
    }

    const toggleModel = (tier: TierKey, fullId: string) => {
        setTierModels(prev => {
            const next = new Set(prev[tier])
            if (next.has(fullId)) {
                next.delete(fullId)
            } else {
                next.add(fullId)
            }
            return { ...prev, [tier]: next }
        })
    }

    return (
        <div className="p-8 space-y-8">
            {/* Header */}
            <div className="flex justify-between items-end">
                <div>
                    <h2 className="text-3xl font-bold tracking-tight">Routing Strategy</h2>
                    <p className="text-muted-foreground pt-1">
                        Configure how the gateway decides which model to use when a request is received.
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    <Button variant="outline" size="sm" onClick={() => mutate()}>
                        <RefreshCw className="h-4 w-4" />
                    </Button>
                    <Button onClick={handleSave} disabled={isSaving || configLoading}>
                        {isSaving
                            ? <><RefreshCw className="mr-2 h-4 w-4 animate-spin" /> Saving…</>
                            : <><Save className="mr-2 h-4 w-4" /> Apply Changes</>
                        }
                    </Button>
                </div>
            </div>

            {/* Status messages */}
            {saveError && (
                <div className="flex items-center gap-2 text-sm text-destructive bg-destructive/10 border border-destructive/20 rounded-lg px-4 py-3">
                    <AlertCircle className="h-4 w-4 flex-shrink-0" />
                    {saveError}
                </div>
            )}
            {saveSuccess && (
                <div className="flex items-center gap-2 text-sm text-green-700 dark:text-green-400 bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800 rounded-lg px-4 py-3">
                    <CheckCircle2 className="h-4 w-4 flex-shrink-0" />
                    Configuration saved and applied successfully.
                </div>
            )}

            {configLoading ? (
                <div className="flex justify-center py-20">
                    <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
                </div>
            ) : (
                <>
                    {/* Global Strategy Selection */}
                    <Card className="border-slate-200 dark:border-slate-800 shadow-sm relative overflow-hidden">
                        <div className="absolute top-0 right-0 p-8 opacity-[0.03] pointer-events-none">
                            <Settings2 className="w-48 h-48" />
                        </div>
                        <CardHeader className="bg-slate-50/50 dark:bg-slate-900/50 border-b">
                            <CardTitle className="flex items-center gap-2">
                                <Activity className="h-5 w-5 text-blue-500" />
                                Global Strategy
                            </CardTitle>
                            <CardDescription>
                                Determine how the application behaves when deciding which assigned model to use.
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="pt-6">
                            <RadioGroup
                                value={globalStrategy}
                                onValueChange={(v: string) => setGlobalStrategy(v as "highest_quota" | "cheapest_available")}
                                className="grid grid-cols-1 md:grid-cols-2 gap-4"
                            >
                                <Label
                                    htmlFor="strategy-quota"
                                    className={`flex flex-col gap-3 p-4 rounded-xl border-2 cursor-pointer transition-all ${globalStrategy === 'highest_quota'
                                        ? 'border-blue-500 bg-blue-50/30 dark:bg-blue-950/20'
                                        : 'border-transparent hover:bg-slate-50 dark:hover:bg-slate-900 bg-slate-100/50 dark:bg-slate-800/30'
                                    }`}
                                >
                                    <div className="flex items-center gap-2">
                                        <RadioGroupItem value="highest_quota" id="strategy-quota" />
                                        <span className="font-semibold text-base">Optimize for Availability</span>
                                    </div>
                                    <p className="text-sm pl-6 text-muted-foreground leading-relaxed">
                                        Prioritize models from providers with the <strong className="text-foreground">highest remaining quota</strong>.
                                        This provides maximum resilience and ensures users rarely hit rate limits.
                                    </p>
                                </Label>

                                <Label
                                    htmlFor="strategy-cost"
                                    className={`flex flex-col gap-3 p-4 rounded-xl border-2 cursor-pointer transition-all ${globalStrategy === 'cheapest_available'
                                        ? 'border-emerald-500 bg-emerald-50/30 dark:bg-emerald-950/20'
                                        : 'border-transparent hover:bg-slate-50 dark:hover:bg-slate-900 bg-slate-100/50 dark:bg-slate-800/30'
                                    }`}
                                >
                                    <div className="flex items-center gap-2">
                                        <RadioGroupItem value="cheapest_available" id="strategy-cost" />
                                        <span className="font-semibold text-base">Optimize for Cost</span>
                                    </div>
                                    <p className="text-sm pl-6 text-muted-foreground leading-relaxed">
                                        Always attempt to route the request to the <strong className="text-foreground">cheapest available model</strong> among the selected options.
                                        It will fallback to more expensive models only if rate limited.
                                    </p>
                                </Label>
                            </RadioGroup>
                        </CardContent>
                    </Card>

                    {/* Model Assignment Section */}
                    <div className="space-y-4 pt-4">
                        <div>
                            <h3 className="text-lg font-semibold flex items-center gap-2">
                                <Cpu className="h-5 w-5 text-indigo-500" />
                                Model Assignment
                            </h3>
                            <p className="text-sm text-muted-foreground mt-1">
                                Assign models to task complexity tiers. The gateway automatically picks the right tier per request.
                                Models are shown with their provider name. Select or deselect as needed.
                            </p>
                        </div>

                        {availableModels.length === 0 ? (
                            <Card className="bg-amber-50 dark:bg-amber-950/20 border-amber-200 dark:border-amber-800">
                                <CardContent className="pt-6 text-center text-amber-800 dark:text-amber-400">
                                    <p>No models are currently enabled or properly configured.</p>
                                    <Button
                                        variant="link"
                                        className="text-amber-700 dark:text-amber-300 px-0"
                                        onClick={() => window.location.href = '/models'}
                                    >
                                        Go to Provider Models to enable and assign tiers.
                                    </Button>
                                </CardContent>
                            </Card>
                        ) : (
                            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
                                {TIER_COLUMNS.map(col => (
                                    <ModelColumn
                                        key={col.key}
                                        col={col}
                                        allModels={availableModels}
                                        selected={tierModels[col.key]}
                                        onToggle={(id) => toggleModel(col.key, id)}
                                    />
                                ))}
                            </div>
                        )}
                    </div>
                </>
            )}
        </div>
    )
}
