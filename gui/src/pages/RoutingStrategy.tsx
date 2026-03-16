import { useState, useEffect, useMemo } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Label } from "@/components/ui/label"
import { Save, RefreshCw, AlertCircle, CheckCircle2, Zap, Cpu, BookOpen, Settings2, Activity } from "lucide-react"
import { useRoutingConfig, saveRoutingConfig, useProviders, useCredentials, useModels } from "@/lib/api"
import { ErrorState } from "@/components/error-state"
import * as yaml from "js-yaml"

// ── Type Definitions ──────────────────────────────────────────────────────────

interface ProviderBrowserItem {
    provider: { id: string; name: string; display_name: string; enabled: boolean }
    credentials: Array<{ id: string; label: string; provider_id: string; enabled: boolean }>
    models: Array<{ id: string; model_id: string; provider_id: string; tier: string; enabled: boolean }>
    ranking: BrainRankedEntry | null
}

interface TierInfo {
    id: string
    label: string
    icon: React.ElementType
    color: string
    bgColor: string
    borderColor: string
    description: string
    examples: string
    sampleYaml: string
}

// ── Helper Functions ──────────────────────────────────────────────────────────

function combineProviderData(
    providers: any[],
    credentials: any[],
    models: any[],
    brainRanking: BrainRankedEntry[]
): ProviderBrowserItem[] {
    return providers
        .filter(p => p.enabled)
        .map(p => ({
            provider: p,
            credentials: credentials.filter(c => c.provider_id === p.id && c.enabled),
            models: models.filter(m => m.provider_id === p.id && m.enabled),
            ranking: brainRanking.find(r => r.provider === p.name) || null,
        }))
}

// ── Tier Definitions ──────────────────────────────────────────────────────────

const TIERS: TierInfo[] = [
    {
        id: "lite",
        label: "Lite",
        icon: Zap,
        color: "text-sky-600 dark:text-sky-400",
        bgColor: "bg-sky-50 dark:bg-sky-950/30",
        borderColor: "border-sky-200 dark:border-sky-800",
        description: "Fastest models at the lowest cost. Ideal for simple completions, chat, and high-throughput workloads. Users cannot manually create a lite strategy — use the Brain button to auto-generate one.",
        examples: "groq/llama-3.1-8b, openai/gpt-4o-mini, gemini/flash",
        sampleYaml:
            `# ── lite tier — sample (uncomment and edit to enable) ──
# tiers:
#   lite:
#     strategy: cheapest_available
#     min_quota_remaining: 500
#     models:
#       - provider: groq
#         model: llama-3.1-8b-instant
#       - provider: openai
#         model: gpt-4o-mini
#       - provider: google
#         model: gemini-2.0-flash`,
    },
    {
        id: "base",
        label: "Base",
        icon: Cpu,
        color: "text-violet-600 dark:text-violet-400",
        bgColor: "bg-violet-50 dark:bg-violet-950/30",
        borderColor: "border-violet-200 dark:border-violet-800",
        description: "Balanced speed and capability for everyday assistant tasks, summarisation, and moderate reasoning.",
        examples: "openai/gpt-4o, anthropic/claude-3-5-haiku, gemini/pro",
        sampleYaml:
            `# ── base tier — sample (uncomment and edit to enable) ──
# tiers:
#   base:
#     strategy: round_robin
#     models:
#       - provider: openai
#         model: gpt-4o
#       - provider: anthropic
#         model: claude-3-5-haiku-20241022
#       - provider: google
#         model: gemini-1.5-pro`,
    },
    {
        id: "thinking",
        label: "Thinking",
        icon: BookOpen,
        color: "text-amber-600 dark:text-amber-400",
        bgColor: "bg-amber-50 dark:bg-amber-950/30",
        borderColor: "border-amber-200 dark:border-amber-800",
        description: "Highest reasoning capability for complex coding, math, and multi-step problem solving. Slower and more expensive.",
        examples: "openai/o3-mini, anthropic/claude-3-7-sonnet, deepseek/r1",
        sampleYaml:
            `# ── thinking tier — sample (uncomment and edit to enable) ──
# tiers:
#   thinking:
#     strategy: highest_quota
#     models:
#       - provider: anthropic
#         model: claude-3-7-sonnet-20250219
#       - provider: openai
#         model: o3-mini
#       - provider: deepseek
#         model: deepseek-reasoner`,
    },
    {
        id: "auto",
        label: "Auto",
        icon: Sparkles,
        color: "text-emerald-600 dark:text-emerald-400",
        bgColor: "bg-emerald-50 dark:bg-emerald-950/30",
        borderColor: "border-emerald-200 dark:border-emerald-800",
        description: "Task-aware heuristics — automatically picks the best tier per request (simple → lite, code → thinking, etc.). No explicit model list needed.",
        examples: "Automatic tier selection based on prompt analysis",
        sampleYaml:
            `# ── auto tier — sample (uncomment and edit to enable) ──
# tiers:
#   auto:
#     strategy: cheapest_available
#     # The router automatically selects lite/base/thinking
#     # based on prompt complexity analysis.`,
    },
]

// ── Brain Dialog ──────────────────────────────────────────────────────────────

interface BrainDialogProps {
    tier: TierInfo | null
    onClose: () => void
    onInsert: (yaml: string, tierLabel: string) => void
}

function BrainDialog({ tier, onClose, onInsert }: BrainDialogProps) {
    const { providers: brainProviders, isLoading: brainLoading } = useBrainStatus()
    const [userPrompt, setUserPrompt] = useState("")
    const [selectedModel, setSelectedModel] = useState("")
    const [generating, setGenerating] = useState(false)
    const [generatedYaml, setGeneratedYaml] = useState("")
    const [error, setError] = useState<string | null>(null)
    const abortRef = useRef<(() => void) | null>(null)

    // Pre-select first brain provider model
    useEffect(() => {
        if (brainProviders.length > 0 && !selectedModel) {
            setSelectedModel(brainProviders[0].model_id)
        }
    }, [brainProviders, selectedModel])

    function handleClose() {
        if (abortRef.current) abortRef.current()
        onClose()
    }

    function handleGenerate() {
        if (!userPrompt.trim() || !selectedModel) return
        setGenerating(true)
        setError(null)
        setGeneratedYaml("")

        const systemPrompt = `You are an expert LLM routing configuration assistant for UnifyRoute gateway.
Generate a valid routing.yaml configuration block for the "${tier?.id}" tier based on the user's requirements.
The routing.yaml uses this structure:
tiers:
  <tier_name>:
    strategy: cheapest_available | highest_quota | round_robin
    min_quota_remaining: <optional number>
    models:
      - provider: <provider_name>
        model: <model_id>

Rules:
- Return ONLY the YAML block starting with "tiers:" — no markdown fences, no explanation.
- Use realistic, well-known model IDs.
- Tailor strategy and model choices to the tier's purpose (${tier?.label}: ${tier?.description}).
- Include 2-4 models for resilience.
- Add brief YAML comments explaining key choices.`

        const messages = [
            { role: "system" as const, content: systemPrompt },
            { role: "user" as const, content: userPrompt.trim() },
        ]

        let accumulated = ""
        abortRef.current = sendChatMessageStream(
            selectedModel,
            messages,
            (delta) => {
                accumulated += delta
                setGeneratedYaml(accumulated)
            },
            () => {
                setGenerating(false)
                abortRef.current = null
            },
            (err) => {
                setError(err.message || "Generation failed")
                setGenerating(false)
                abortRef.current = null
            },
        )
    }

    function handleInsert() {
        if (!generatedYaml.trim()) return
        const commented = generatedYaml
            .split("\n")
            .map((line) => `# ${line}`)
            .join("\n")
        const block = `\n# ── Brain-generated suggestion for ${tier?.label} tier ──\n${commented}\n# ─────────────────────────────────────────\n`
        onInsert(block, tier?.label ?? "")
        onClose()
    }

    return (
        <Dialog open={!!tier} onOpenChange={(v: boolean) => !v && handleClose()}>
            <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <Brain className="h-5 w-5 text-orange-500" />
                        Generate Routing Strategy
                        {tier && (
                            <Badge className={`${tier.bgColor} ${tier.color} border ${tier.borderColor} ml-1`}>
                                {tier.label}
                            </Badge>
                        )}
                    </DialogTitle>
                    <DialogDescription>
                        Describe your routing requirements. The Brain will generate a YAML strategy snippet
                        that gets inserted as commented sample code in the editor.
                    </DialogDescription>
                </DialogHeader>

                <div className="space-y-4 py-2">
                    {/* Model selector */}
                    <div className="space-y-1.5">
                        <Label>Brain Model</Label>
                        {brainLoading ? (
                            <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading…
                            </div>
                        ) : brainProviders.length === 0 ? (
                            <div className="text-sm text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-800 rounded-md px-3 py-2">
                                No Brain providers assigned. Go to the{" "}
                                <strong>Brain</strong> page to assign a provider first.
                            </div>
                        ) : (
                            <Select value={selectedModel} onValueChange={setSelectedModel}>
                                <SelectTrigger>
                                    <SelectValue placeholder="Select a model…" />
                                </SelectTrigger>
                                <SelectContent>
                                    {brainProviders.filter(p => p.enabled).map((p) => (
                                        <SelectItem key={p.id} value={p.model_id}>
                                            <span className="font-medium">{p.provider_display}</span>
                                            <span className="text-muted-foreground ml-2 text-xs font-mono">{p.model_id}</span>
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        )}
                    </div>

                    {/* User prompt */}
                    <div className="space-y-1.5">
                        <Label>What do you want?</Label>
                        <Textarea
                            className="min-h-[100px] resize-y text-sm"
                            placeholder={`e.g. "Use Groq for speed, fallback to OpenAI if quota is below 500. Prefer cheapest option."`}
                            value={userPrompt}
                            onChange={(e) => setUserPrompt(e.target.value)}
                            disabled={generating}
                        />
                    </div>

                    {/* Error */}
                    {error && (
                        <div className="flex items-center gap-2 text-sm text-destructive bg-destructive/10 border border-destructive/20 rounded-md px-3 py-2">
                            <AlertCircle className="h-4 w-4 shrink-0" />
                            {error}
                        </div>
                    )}

                    {/* Generated YAML preview */}
                    {(generating || generatedYaml) && (
                        <div className="space-y-1.5">
                            <div className="flex items-center justify-between">
                                <Label>Generated YAML</Label>
                                {generating && (
                                    <span className="text-xs text-muted-foreground flex items-center gap-1">
                                        <Loader2 className="h-3 w-3 animate-spin" /> Generating…
                                    </span>
                                )}
                            </div>
                            <pre className="w-full min-h-[120px] max-h-[300px] overflow-auto p-3 rounded-md font-mono text-xs bg-slate-950 text-slate-50 border border-slate-700 whitespace-pre-wrap">
                                {generatedYaml || " "}
                            </pre>
                            {!generating && generatedYaml && (
                                <p className="text-xs text-muted-foreground">
                                    ↑ This will be inserted as <strong>commented lines</strong> in your YAML editor so you can review and uncomment what you want.
                                </p>
                            )}
                        </div>
                    )}
                </div>

                <DialogFooter className="flex-wrap gap-2">
                    <Button variant="outline" onClick={handleClose} disabled={generating}>
                        <X className="h-4 w-4 mr-1.5" /> Cancel
                    </Button>
                    <Button
                        variant="outline"
                        onClick={handleGenerate}
                        disabled={generating || !userPrompt.trim() || !selectedModel || brainProviders.length === 0}
                    >
                        {generating
                            ? <><Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> Generating…</>
                            : <><Wand2 className="h-4 w-4 mr-1.5" /> Generate</>
                        }
                    </Button>
                    <Button
                        onClick={handleInsert}
                        disabled={!generatedYaml.trim() || generating}
                        className="bg-orange-500 hover:bg-orange-600 text-white"
                    >
                        <CheckCircle2 className="h-4 w-4 mr-1.5" />
                        Insert into Editor
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}

// ── Tier Cards ────────────────────────────────────────────────────────────────

interface TierCardProps {
    tier: TierInfo
    onBrainClick: (tier: TierInfo) => void
    onInsertSample: (sample: string) => void
}

function TierCard({ tier, onBrainClick, onInsertSample }: TierCardProps) {
    const [showSample, setShowSample] = useState(false)
    const Icon = tier.icon

    return (
        <Card className={`border ${tier.borderColor} overflow-hidden`}>
            <CardHeader className={`pb-2 pt-3 px-4 ${tier.bgColor}`}>
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <Icon className={`h-4 w-4 ${tier.color}`} />
                        <CardTitle className={`text-sm font-semibold ${tier.color}`}>
                            {tier.label}
                        </CardTitle>
                        <code className="text-xs bg-black/10 dark:bg-white/10 px-1.5 py-0.5 rounded font-mono">{tier.id}</code>
                    </div>
                    <Button
                        size="sm"
                        variant="outline"
                        className={`h-7 gap-1.5 text-xs border ${tier.borderColor} ${tier.color} hover:${tier.bgColor}`}
                        onClick={() => onBrainClick(tier)}
                    >
                        <Brain className="h-3.5 w-3.5" />
                        Brain
                    </Button>
                </div>
            </CardHeader>
            <CardContent className="px-4 py-3 space-y-2">
                <CardDescription className="text-xs leading-relaxed">{tier.description}</CardDescription>
                <p className="text-xs text-muted-foreground">
                    <span className="font-medium text-foreground/70">Examples: </span>
                    {tier.examples}
                </p>
                <button
                    className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors mt-1"
                    onClick={() => setShowSample(v => !v)}
                >
                    {showSample ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                    {showSample ? "Hide" : "Show"} sample config
                </button>
                {showSample && (
                    <div className="space-y-1.5">
                        <pre className="text-xs font-mono bg-slate-950 text-slate-300 rounded-md p-3 overflow-x-auto whitespace-pre leading-relaxed">
                            {tier.sampleYaml}
                        </pre>
                        <Button
                            size="sm"
                            variant="outline"
                            className="h-7 text-xs gap-1"
                            onClick={() => onInsertSample(tier.sampleYaml)}
                        >
                            <CheckCircle2 className="h-3 w-3" />
                            Insert sample into editor
                        </Button>
                    </div>
                )}
            </CardContent>
        </Card>
    )
}

// ── Provider Browser Section ──────────────────────────────────────────────────

interface ProviderBrowserProps {
    items: ProviderBrowserItem[]
    selectedProviders: Set<string>
    onToggleProvider: (providerId: string) => void
    showHealth: boolean
    onShowHealthToggle: () => void
    searchTerm: string
    onSearchChange: (term: string) => void
}

function ProviderBrowser({
    items,
    selectedProviders,
    onToggleProvider,
    showHealth,
    onShowHealthToggle,
    searchTerm,
    onSearchChange,
}: ProviderBrowserProps) {
    const filtered = items.filter(item =>
        item.provider.display_name.toLowerCase().includes(searchTerm.toLowerCase())
    )

    return (
        <div className="space-y-3">
            <div className="flex items-center gap-2">
                <Input
                    placeholder="Search providers..."
                    value={searchTerm}
                    onChange={(e) => onSearchChange(e.target.value)}
                    className="max-w-xs"
                />
                <label className="flex items-center gap-2 text-sm cursor-pointer">
                    <Checkbox checked={showHealth} onCheckedChange={onShowHealthToggle} />
                    <span>Show health status</span>
                </label>
            </div>

            {filtered.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                    <p>No providers found</p>
                </div>
            ) : (
                <div className="space-y-2">
                    {filtered.map((item) => (
                        <Card key={item.provider.id} className="overflow-hidden">
                            <CardContent className="p-4">
                                <div className="flex items-start gap-4">
                                    <Checkbox
                                        checked={selectedProviders.has(item.provider.id)}
                                        onCheckedChange={() => onToggleProvider(item.provider.id)}
                                    />
                                    <div className="flex-1">
                                        <div className="flex items-center gap-2 mb-2">
                                            <span className="font-medium">{item.provider.display_name}</span>
                                            {item.credentials.length > 0 && (
                                                <Badge variant="outline" className="text-xs">
                                                    {item.credentials.length} credential{item.credentials.length !== 1 ? 's' : ''}
                                                </Badge>
                                            )}
                                            {showHealth && item.ranking && (
                                                <>
                                                    {item.ranking.health_ok ? (
                                                        <Badge className="bg-emerald-500 text-xs">
                                                            {item.ranking.latency_ms}ms
                                                        </Badge>
                                                    ) : (
                                                        <Badge variant="destructive" className="text-xs">
                                                            Unhealthy
                                                        </Badge>
                                                    )}
                                                </>
                                            )}
                                        </div>
                                        {item.models.length > 0 ? (
                                            <div className="text-xs text-muted-foreground">
                                                <span>{item.models.length} model{item.models.length !== 1 ? 's' : ''} available:</span>
                                                <div className="mt-2 space-y-1">
                                                    {item.models.map(m => (
                                                        <div key={m.id} className="flex items-center gap-2 text-xs">
                                                            <code className="px-2 py-1 bg-muted rounded">{m.model_id}</code>
                                                            {m.tier && <Badge variant="outline" className="text-xs">{m.tier}</Badge>}
                                                        </div>
                                                    ))}
                                                </div>
                                            </div>
                                        ) : (
                                            <p className="text-xs text-muted-foreground">No models available</p>
                                        )}
                                    </div>
                                </div>
                            </CardContent>
                        </Card>
                    ))}
                </div>
            )}
        </div>
    )
}

// ── Strategy Builder Section ───────────────────────────────────────────────────

interface StrategyBuilderProps {
    activeTier: string
    strategyType: string
    selectedProviders: Map<string, ProviderBrowserItem>
    onTierChange: (tier: string) => void
    onStrategyChange: (strategy: string) => void
    onGenerateWithBrain: () => void
    brainLoading: boolean
    brainProviders: any[]
}

function StrategyBuilder({
    activeTier,
    strategyType,
    selectedProviders,
    onTierChange,
    onStrategyChange,
    onGenerateWithBrain,
    brainLoading,
    brainProviders,
}: StrategyBuilderProps) {
    const tier = TIERS.find(t => t.id === activeTier)
    const selectedForTier = Array.from(selectedProviders.values())

    return (
        <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                    <Label>Tier</Label>
                    <Select value={activeTier} onValueChange={onTierChange}>
                        <SelectTrigger>
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                            {TIERS.map(t => (
                                <SelectItem key={t.id} value={t.id}>{t.label}</SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </div>
                <div className="space-y-2">
                    <Label>Strategy</Label>
                    <Select value={strategyType} onValueChange={onStrategyChange}>
                        <SelectTrigger>
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="cheapest_available">Cheapest Available</SelectItem>
                            <SelectItem value="highest_quota">Highest Quota</SelectItem>
                            <SelectItem value="round_robin">Round Robin</SelectItem>
                            <SelectItem value="auto">Auto (Task-aware)</SelectItem>
                        </SelectContent>
                    </Select>
                </div>
            </div>

            {tier && (
                <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-950 border">
                    <p className="text-xs text-muted-foreground mb-1">{tier.label} Tier</p>
                    <p className="text-sm">{tier.description}</p>
                </div>
            )}

            {selectedForTier.length > 0 && (
                <div className="space-y-2">
                    <Label>Selected Providers & Models</Label>
                    <Card>
                        <CardContent className="p-3">
                            <div className="space-y-2">
                                {selectedForTier.map(item => (
                                    <div key={item.provider.id} className="space-y-1">
                                        <div className="font-medium text-sm">{item.provider.display_name}</div>
                                        <div className="text-xs space-y-1 ml-2">
                                            {item.models.map((m: any) => (
                                                <div key={m.id} className="flex items-center gap-2">
                                                    <code className="px-2 py-1 bg-muted rounded text-xs">{m.model_id}</code>
                                                    {m.tier && <Badge variant="outline" className="text-xs">{m.tier}</Badge>}
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </CardContent>
                    </Card>
                </div>
            )}

            <Button
                onClick={onGenerateWithBrain}
                disabled={selectedForTier.length === 0 || brainProviders.length === 0 || brainLoading}
                className="w-full bg-orange-500 hover:bg-orange-600"
            >
                <Lightbulb className="h-4 w-4 mr-2" />
                {brainLoading ? "Generating…" : "Generate Strategy with Brain AI"}
            </Button>

            {selectedForTier.length === 0 && (
                <p className="text-xs text-muted-foreground text-center">
                    Select providers from the "Available Providers" section above to generate a strategy
                </p>
            )}
        </div>
    )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export function RoutingStrategy() {
    const { routingConfig, isLoading: configLoading, isError: configError, mutate } = useRoutingConfig()
    const { providers: allProviders } = useProviders()
    const { credentials: allCredentials } = useCredentials()
    const { models: allModels } = useModels()

    const [globalStrategy, setGlobalStrategy] = useState<"highest_quota" | "cheapest_available">("highest_quota")
    const [tierModels, setTierModels] = useState<{ lite: Set<string>, base: Set<string>, thinking: Set<string> }>({
        lite: new Set(),
        base: new Set(),
        thinking: new Set()
    })

    const [isSaving, setIsSaving] = useState(false)
    const [saveError, setSaveError] = useState("")
    const [saveSuccess, setSaveSuccess] = useState(false)

    // Original config object to preserve other settings when saving
    const [originalConfigObj, setOriginalConfigObj] = useState<RoutingYamlConfig>({})

    // Parse incoming YAML config and populate state
    useEffect(() => {
        if (routingConfig !== undefined && routingConfig !== null) {
            try {
                const parsed = yaml.load(routingConfig) as RoutingYamlConfig;
                setOriginalConfigObj(parsed || {});

                const getTierModelsSet = (tierName: "lite" | "base" | "thinking") => {
                    const models = parsed?.tiers?.[tierName]?.models || [];
                    return new Set(models.map(m => `${m.provider}::${m.model}`));
                };

                setTierModels({
                    lite: getTierModelsSet("lite"),
                    base: getTierModelsSet("base"),
                    thinking: getTierModelsSet("thinking")
                });

                // Infer global strategy. If any tier has cheapest_available, set it to cost, otherwise quota.
                const hasCostStrategy = ["lite", "base", "thinking", "auto"].some(t =>
                    parsed?.tiers?.[t]?.strategy === "cheapest_available"
                );

                setGlobalStrategy(hasCostStrategy ? "cheapest_available" : "highest_quota");

            } catch (e) {
                console.error("Error parsing routing.yaml:", e);
                setSaveError("Failed to parse the existing configuration. Continuing will overwrite it.");
            }
        }
    }, [routingConfig]);

    // Gather available models mapped by provider
    const availableModels = useMemo(() => {
        if (!allProviders || !allCredentials || !allModels) return [];

        const enabledProvidersMap = new Map();
        allProviders.filter((p: any) => p.enabled).forEach((p: any) => {
            enabledProvidersMap.set(p.id, p);
        });

        const enabledModels: Array<{ id: string, providerId: string, providerName: string, providerDisplayName: string, modelId: string }> = [];

        allModels.filter((m: any) => m.enabled).forEach((m: any) => {
            const provider = enabledProvidersMap.get(m.provider_id);
            if (provider) {
                enabledModels.push({
                    id: m.id,
                    providerId: provider.id,
                    providerName: provider.name,
                    providerDisplayName: provider.display_name,
                    modelId: m.model_id
                });
            }
        });

        // Group by provider for cleaner UI display
        const grouped = new Map<string, { providerName: string, providerDisplayName: string, models: Array<{ modelId: string, fullId: string }> }>();
        enabledModels.forEach(m => {
            const key = m.providerId;
            if (!grouped.has(key)) {
                grouped.set(key, { providerName: m.providerName, providerDisplayName: m.providerDisplayName, models: [] });
            }
            grouped.get(key)!.models.push({ modelId: m.modelId, fullId: `${m.providerName}::${m.modelId}` });
        });

        return Array.from(grouped.values());
    }, [allProviders, allCredentials, allModels]);


    const handleSave = async () => {
        setIsSaving(true)
        setSaveError("")
        setSaveSuccess(false)

        try {
            // Build the new config object
            const newConfig: RoutingYamlConfig = { ...originalConfigObj };
            if (!newConfig.tiers) {
                newConfig.tiers = {};
            }

            // Helper to build a tier
            const buildTierConfig = (tierName: "lite" | "base" | "thinking", existingTier?: RoutingTierConfig) => {
                const modelList = Array.from(tierModels[tierName]).map(id => {
                    const [provider, model] = id.split("::");
                    return { provider, model };
                });

                return {
                    ...existingTier,
                    strategy: globalStrategy,
                    fallback_on: existingTier?.fallback_on || [429, 503, "timeout"],
                    models: modelList
                };
            };

            newConfig.tiers.lite = buildTierConfig("lite", newConfig.tiers.lite);
            newConfig.tiers.base = buildTierConfig("base", newConfig.tiers.base);
            newConfig.tiers.thinking = buildTierConfig("thinking", newConfig.tiers.thinking);

            // Also update 'auto' tier to match the strategy, but don't touch its models 
            if (newConfig.tiers.auto) {
                newConfig.tiers.auto.strategy = globalStrategy;
            } else {
                newConfig.tiers.auto = {
                    strategy: globalStrategy,
                    fallback_on: [429, 503, "timeout"]
                }
            }

            // Serialize to YAML
            const yamlString = yaml.dump(newConfig, { indent: 2, skipInvalid: true });

            await saveRoutingConfig(yamlString)
            await mutate()
            setSaveSuccess(true)
            setTimeout(() => setSaveSuccess(false), 3000)
        } catch (e: any) {
            setSaveError(e.message || "Failed to save configuration")
        } finally {
            setIsSaving(false)
        }
    }

    const toggleModel = (tier: "lite" | "base" | "thinking", modelFullId: string) => {
        setTierModels(prev => {
            const newSet = new Set(prev[tier]);
            if (newSet.has(modelFullId)) {
                newSet.delete(modelFullId);
            } else {
                newSet.add(providerId)
            }
            return newSet
        })
    }

    async function handleGenerateWithBrain() {
        if (selectedProvidersMap.size === 0 || brainProviders.length === 0) return

        setBrainGenerating(true)
        const selectedProvidersInfo = Array.from(selectedProvidersMap.values())

        const systemPrompt = `You are an expert LLM routing configuration assistant for UnifyRoute gateway.
Generate a valid routing.yaml configuration block for the "${activeTier}" tier based on these selected providers.
The routing.yaml uses this structure:
tiers:
  <tier_name>:
    strategy: cheapest_available | highest_quota | round_robin | auto
    models:
      - provider: <provider_name>
        model: <model_id>

Selected providers and models:
${selectedProvidersInfo.map(p => `- ${p.provider.display_name}: ${p.models.map((m: any) => m.model_id).join(', ')}`).join('\n')}

Routing strategy: ${strategyType}
Tier description: ${TIERS.find(t => t.id === activeTier)?.description}

Rules:
- Return ONLY the YAML block starting with "tiers:" — no markdown fences, no explanation.
- Use the exact provider and model IDs from the selected providers above.
- Tailor strategy and model order based on the strategy type.
- Add brief YAML comments explaining key choices.`

        const messages = [
            { role: "system" as const, content: systemPrompt },
            { role: "user" as const, content: "Generate the routing configuration." },
        ]

        let accumulated = ""
        abortRef.current = sendChatMessageStream(
            brainProviders[0].model_id,
            messages,
            (delta) => {
                accumulated += delta
            },
            () => {
                setBrainGenerating(false)
                // Insert as commented block
                const commented = accumulated
                    .split("\n")
                    .map((line) => `# ${line}`)
                    .join("\n")
                const block = `\n# ── AI-suggested routing for ${activeTier} tier ──\n${commented}\n# ─────────────────────────────────────────\n`
                handleBrainInsert(block)
                abortRef.current = null
            },
            (err) => {
                setSaveError(err.message || "Generation failed")
                setBrainGenerating(false)
                abortRef.current = null
            },
        )
    }

    if (isError) return <ErrorState />

    return (
        <div className="space-y-6 max-w-5xl">
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
                        {/* Decorative background element */}
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
                                onValueChange={(v) => setGlobalStrategy(v as any)}
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
                                        This provides maximum resilience and ensures users rarely hit rate limits, guaranteeing they get an available model.
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
                            <p className="text-sm text-muted-foreground">
                                Assign enabled models to task complexity tiers. The application automatically determines the complexity of a user's prompt and routes it to the models defined below.
                            </p>
                        </div>

                        {availableModels.length === 0 ? (
                            <Card className="bg-amber-50 dark:bg-amber-950/20 border-amber-200 dark:border-amber-800">
                                <CardContent className="pt-6 text-center text-amber-800 dark:text-amber-400">
                                    <p>No models are currently enabled or properly configured.</p>
                                    <Button variant="link" className="text-amber-700 dark:text-amber-300 px-0" onClick={() => window.location.href = '/models'}>
                                        Go to Model Management to enable some models.
                                    </Button>
                                </CardContent>
                            </Card>
                        ) : (
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">

                                {/* Simple Ask (Lite) */}
                                <Card className="border-sky-200 dark:border-sky-900 shadow-sm flex flex-col">
                                    <CardHeader className="bg-sky-50 dark:bg-sky-950/30 border-b border-sky-100 dark:border-sky-900/50">
                                        <CardTitle className="text-lg text-sky-700 dark:text-sky-300 flex items-center gap-2">
                                            <Zap className="h-4 w-4" />
                                            Simple Ask
                                        </CardTitle>
                                        <CardDescription className="text-xs">
                                            Fast and cheap models for quick questions and high-volume tasks.
                                        </CardDescription>
                                    </CardHeader>
                                    <CardContent className="pt-4 flex-1 space-y-4">
                                        {availableModels.map(group => (
                                            <div key={`lite-${group.providerName}`} className="space-y-2">
                                                <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                                                    {group.providerDisplayName}
                                                </h4>
                                                <div className="space-y-1.5 pl-1">
                                                    {group.models.map(m => (
                                                        <label key={`lite-${m.fullId}`} className="flex items-start gap-2 cursor-pointer group">
                                                            <Checkbox
                                                                className="mt-0.5"
                                                                checked={tierModels.lite.has(m.fullId)}
                                                                onCheckedChange={() => toggleModel("lite", m.fullId)}
                                                            />
                                                            <span className="text-sm font-mono break-all leading-tight group-hover:text-foreground text-muted-foreground transition-colors">
                                                                {m.modelId}
                                                            </span>
                                                        </label>
                                                    ))}
                                                </div>
                                            </div>
                                        ))}
                                    </CardContent>
                                    <CardFooter className="bg-slate-50/50 dark:bg-slate-900/30 border-t py-3 flex justify-between">
                                        <span className="text-xs text-muted-foreground">Selected: <strong className="text-foreground">{tierModels.lite.size}</strong></span>
                                        {tierModels.lite.size === 0 && <span className="text-xs text-amber-500 font-medium">None selected!</span>}
                                    </CardFooter>
                                </Card>

                                {/* Normal Ask (Base) */}
                                <Card className="border-violet-200 dark:border-violet-900 shadow-sm flex flex-col">
                                    <CardHeader className="bg-violet-50 dark:bg-violet-950/30 border-b border-violet-100 dark:border-violet-900/50">
                                        <CardTitle className="text-lg text-violet-700 dark:text-violet-300 flex items-center gap-2">
                                            <Cpu className="h-4 w-4" />
                                            Better Model
                                        </CardTitle>
                                        <CardDescription className="text-xs">
                                            Capable models for balanced, everyday intelligent tasks and light coding.
                                        </CardDescription>
                                    </CardHeader>
                                    <CardContent className="pt-4 flex-1 space-y-4">
                                        {availableModels.map(group => (
                                            <div key={`base-${group.providerName}`} className="space-y-2">
                                                <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                                                    {group.providerDisplayName}
                                                </h4>
                                                <div className="space-y-1.5 pl-1">
                                                    {group.models.map(m => (
                                                        <label key={`base-${m.fullId}`} className="flex items-start gap-2 cursor-pointer group">
                                                            <Checkbox
                                                                className="mt-0.5"
                                                                checked={tierModels.base.has(m.fullId)}
                                                                onCheckedChange={() => toggleModel("base", m.fullId)}
                                                            />
                                                            <span className="text-sm font-mono break-all leading-tight group-hover:text-foreground text-muted-foreground transition-colors">
                                                                {m.modelId}
                                                            </span>
                                                        </label>
                                                    ))}
                                                </div>
                                            </div>
                                        ))}
                                    </CardContent>
                                    <CardFooter className="bg-slate-50/50 dark:bg-slate-900/30 border-t py-3 flex justify-between">
                                        <span className="text-xs text-muted-foreground">Selected: <strong className="text-foreground">{tierModels.base.size}</strong></span>
                                        {tierModels.base.size === 0 && <span className="text-xs text-amber-500 font-medium">None selected!</span>}
                                    </CardFooter>
                                </Card>

                                {/* Complex (Thinking) */}
                                <Card className="border-amber-200 dark:border-amber-900 shadow-sm flex flex-col">
                                    <CardHeader className="bg-amber-50 dark:bg-amber-950/30 border-b border-amber-100 dark:border-amber-900/50">
                                        <CardTitle className="text-lg text-amber-700 dark:text-amber-300 flex items-center gap-2">
                                            <BookOpen className="h-4 w-4" />
                                            Reasoning Model
                                        </CardTitle>
                                        <CardDescription className="text-xs">
                                            Large, intelligent models for complex reasoning, planning, and advanced coding.
                                        </CardDescription>
                                    </CardHeader>
                                    <CardContent className="pt-4 flex-1 space-y-4">
                                        {availableModels.map(group => (
                                            <div key={`thinking-${group.providerName}`} className="space-y-2">
                                                <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                                                    {group.providerDisplayName}
                                                </h4>
                                                <div className="space-y-1.5 pl-1">
                                                    {group.models.map(m => (
                                                        <label key={`thinking-${m.fullId}`} className="flex items-start gap-2 cursor-pointer group">
                                                            <Checkbox
                                                                className="mt-0.5"
                                                                checked={tierModels.thinking.has(m.fullId)}
                                                                onCheckedChange={() => toggleModel("thinking", m.fullId)}
                                                            />
                                                            <span className="text-sm font-mono break-all leading-tight group-hover:text-foreground text-muted-foreground transition-colors">
                                                                {m.modelId}
                                                            </span>
                                                        </label>
                                                    ))}
                                                </div>
                                            </div>
                                        ))}
                                    </CardContent>
                                    <CardFooter className="bg-slate-50/50 dark:bg-slate-900/30 border-t py-3 flex justify-between">
                                        <span className="text-xs text-muted-foreground">Selected: <strong className="text-foreground">{tierModels.thinking.size}</strong></span>
                                        {tierModels.thinking.size === 0 && <span className="text-xs text-amber-500 font-medium">None selected!</span>}
                                    </CardFooter>
                                </Card>
                            </div>
                        )}
                    </div>
                </>
            )}
        </div>
    )
}
