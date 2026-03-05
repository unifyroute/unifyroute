import { useState, useRef, useEffect, useCallback } from "react"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Send, RotateCcw, Loader2, Zap, Bot, User } from "lucide-react"
import { sendChatMessage, sendChatMessageStream, type ChatMessage } from "@/lib/api"

interface DisplayMessage {
    role: "user" | "assistant"
    content: string
    model?: string
    provider?: string
    tokens?: { prompt: number; completion: number }
    latency?: number
}

const MODEL_OPTIONS = [
    { value: "auto", label: "Auto (smart select)" },
    { value: "lite", label: "Lite tier" },
    { value: "base", label: "Base tier" },
    { value: "thinking", label: "Thinking tier" },
]

const STORAGE_KEY = "unifyroute_chat_history"
const SETTINGS_KEY = "unifyroute_chat_settings"

function loadHistory(): DisplayMessage[] {
    try {
        const raw = localStorage.getItem(STORAGE_KEY)
        return raw ? JSON.parse(raw) : []
    } catch { return [] }
}

function saveHistory(msgs: DisplayMessage[]) {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(msgs)) } catch { /* quota exceeded */ }
}

function loadSettings(): { model: string; streaming: boolean } {
    try {
        const raw = localStorage.getItem(SETTINGS_KEY)
        return raw ? JSON.parse(raw) : { model: "auto", streaming: true }
    } catch { return { model: "auto", streaming: true } }
}

function saveSettings(s: { model: string; streaming: boolean }) {
    try { localStorage.setItem(SETTINGS_KEY, JSON.stringify(s)) } catch { /* */ }
}

export function Chat() {
    const saved = loadSettings()
    const [messages, setMessages] = useState<DisplayMessage[]>(loadHistory)
    const [input, setInput] = useState("")
    const [model, setModel] = useState(saved.model)
    const [streaming, setStreaming] = useState(saved.streaming)
    const [loading, setLoading] = useState(false)
    const [streamingText, setStreamingText] = useState("")
    const abortRef = useRef<(() => void) | null>(null)
    const messagesEndRef = useRef<HTMLDivElement>(null)
    const textareaRef = useRef<HTMLTextAreaElement>(null)

    const scrollToBottom = useCallback(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
    }, [])

    useEffect(scrollToBottom, [messages, streamingText, scrollToBottom])

    // Persist messages whenever they change
    useEffect(() => { saveHistory(messages) }, [messages])

    // Persist settings when model or streaming changes
    useEffect(() => { saveSettings({ model, streaming }) }, [model, streaming])

    // Auto-resize textarea
    useEffect(() => {
        if (textareaRef.current) {
            textareaRef.current.style.height = "auto"
            textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 200) + "px"
        }
    }, [input])

    function reset() {
        if (abortRef.current) abortRef.current()
        setMessages([])
        setInput("")
        setStreamingText("")
        setLoading(false)
        localStorage.removeItem(STORAGE_KEY)
    }

    async function handleSend() {
        const text = input.trim()
        if (!text || loading) return

        const userMsg: DisplayMessage = { role: "user", content: text }
        const newMessages = [...messages, userMsg]
        setMessages(newMessages)
        setInput("")
        setLoading(true)
        setStreamingText("")

        // Build the messages array for the API (full conversation history)
        const apiMessages: ChatMessage[] = newMessages.map(m => ({
            role: m.role,
            content: m.content,
        }))

        if (streaming) {
            // Streaming mode
            let accumulated = ""
            const abort = sendChatMessageStream(
                model,
                apiMessages,
                (delta) => {
                    accumulated += delta
                    setStreamingText(accumulated)
                },
                (info) => {
                    setMessages(prev => [
                        ...prev,
                        {
                            role: "assistant",
                            content: accumulated,
                            model: info.model,
                            provider: info.provider,
                        },
                    ])
                    setStreamingText("")
                    setLoading(false)
                },
                (err) => {
                    setMessages(prev => [
                        ...prev,
                        { role: "assistant", content: `⚠️ Error: ${err.message}` },
                    ])
                    setStreamingText("")
                    setLoading(false)
                }
            )
            abortRef.current = abort
        } else {
            // Non-streaming mode
            try {
                const startTime = Date.now()
                const res = await sendChatMessage(model, apiMessages)
                const latency = Date.now() - startTime
                const choice = res.choices?.[0]
                setMessages(prev => [
                    ...prev,
                    {
                        role: "assistant",
                        content: choice?.message?.content || "(empty response)",
                        model: res.model,
                        tokens: res.usage
                            ? { prompt: res.usage.prompt_tokens, completion: res.usage.completion_tokens }
                            : undefined,
                        latency,
                    },
                ])
            } catch (err: any) {
                setMessages(prev => [
                    ...prev,
                    { role: "assistant", content: `⚠️ Error: ${err.message}` },
                ])
            } finally {
                setLoading(false)
            }
        }
    }

    function handleKeyDown(e: React.KeyboardEvent) {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault()
            handleSend()
        }
    }

    return (
        <div className="flex flex-col h-[calc(100vh-64px-4rem)]">
            {/* Header */}
            <div className="flex items-center justify-between pb-4 border-b border-slate-200 dark:border-slate-800">
                <div>
                    <h2 className="text-2xl font-bold tracking-tight">Chat Playground</h2>
                    <p className="text-sm text-muted-foreground">
                        Test the gateway like a real application would.
                    </p>
                </div>
                <div className="flex items-center gap-3">
                    {/* Model selector */}
                    <Select value={model} onValueChange={setModel}>
                        <SelectTrigger className="w-[180px]">
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                            {MODEL_OPTIONS.map(o => (
                                <SelectItem key={o.value} value={o.value}>
                                    {o.label}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>

                    {/* Stream toggle */}
                    <Button
                        variant={streaming ? "default" : "outline"}
                        size="sm"
                        onClick={() => setStreaming(s => !s)}
                        className="gap-1.5"
                    >
                        <Zap className="h-3.5 w-3.5" />
                        {streaming ? "Stream" : "Batch"}
                    </Button>

                    {/* Reset */}
                    <Button variant="outline" size="sm" onClick={reset} className="gap-1.5">
                        <RotateCcw className="h-3.5 w-3.5" />
                        Reset
                    </Button>
                </div>
            </div>

            {/* Message area */}
            <div className="flex-1 overflow-y-auto py-6 space-y-4">
                {messages.length === 0 && !loading && (
                    <div className="flex flex-col items-center justify-center h-full text-center text-muted-foreground space-y-3">
                        <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-orange-500/10 to-orange-500/10 flex items-center justify-center">
                            <Bot className="h-8 w-8 text-orange-500/50" />
                        </div>
                        <div>
                            <p className="font-medium text-slate-600 dark:text-slate-300">Start a conversation</p>
                            <p className="text-sm">Select a model and type your message below.</p>
                        </div>
                    </div>
                )}

                {messages.map((msg, i) => (
                    <div key={i} className={`flex gap-3 ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                        {msg.role === "assistant" && (
                            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-orange-500 to-orange-600 flex items-center justify-center flex-shrink-0 mt-0.5">
                                <Bot className="h-4 w-4 text-white" />
                            </div>
                        )}
                        <div className={`max-w-[70%] ${msg.role === "user" ? "order-first" : ""}`}>
                            <Card className={`px-4 py-3 ${msg.role === "user"
                                ? "bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900 border-0"
                                : "bg-white dark:bg-slate-950"
                                }`}>
                                <div className="text-sm whitespace-pre-wrap leading-relaxed">
                                    {msg.content}
                                </div>
                            </Card>
                            {/* Metadata for assistant messages */}
                            {msg.role === "assistant" && (msg.model || msg.tokens || msg.provider) && (
                                <div className="flex items-center gap-2 mt-1.5 text-[11px] text-muted-foreground px-1">
                                    {msg.model && <span className="font-mono">{msg.model}</span>}
                                    {msg.provider && <span>via {msg.provider}</span>}
                                    {msg.tokens && (
                                        <span>{msg.tokens.prompt}↑ {msg.tokens.completion}↓</span>
                                    )}
                                    {msg.latency != null && <span>{msg.latency}ms</span>}
                                </div>
                            )}
                        </div>
                        {msg.role === "user" && (
                            <div className="w-8 h-8 rounded-lg bg-slate-200 dark:bg-slate-800 flex items-center justify-center flex-shrink-0 mt-0.5">
                                <User className="h-4 w-4 text-slate-600 dark:text-slate-400" />
                            </div>
                        )}
                    </div>
                ))}

                {/* Streaming text (live output) */}
                {streamingText && (
                    <div className="flex gap-3 justify-start">
                        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-orange-500 to-orange-600 flex items-center justify-center flex-shrink-0 mt-0.5">
                            <Bot className="h-4 w-4 text-white" />
                        </div>
                        <Card className="max-w-[70%] px-4 py-3 bg-white dark:bg-slate-950">
                            <div className="text-sm whitespace-pre-wrap leading-relaxed">
                                {streamingText}
                                <span className="inline-block w-2 h-4 bg-orange-500 ml-0.5 animate-pulse rounded-sm" />
                            </div>
                        </Card>
                    </div>
                )}

                {/* Loading indicator (non-streaming) */}
                {loading && !streamingText && (
                    <div className="flex gap-3 justify-start">
                        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-orange-500 to-orange-600 flex items-center justify-center flex-shrink-0 mt-0.5">
                            <Bot className="h-4 w-4 text-white" />
                        </div>
                        <Card className="px-4 py-3 bg-white dark:bg-slate-950">
                            <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                <Loader2 className="h-4 w-4 animate-spin" />
                                Thinking…
                            </div>
                        </Card>
                    </div>
                )}

                <div ref={messagesEndRef} />
            </div>

            {/* Input area */}
            <div className="border-t border-slate-200 dark:border-slate-800 pt-4">
                <div className="flex items-end gap-3">
                    <div className="flex-1 relative">
                        <textarea
                            ref={textareaRef}
                            value={input}
                            onChange={e => setInput(e.target.value)}
                            onKeyDown={handleKeyDown}
                            placeholder="Type your message… (Enter to send, Shift+Enter for newline)"
                            rows={1}
                            disabled={loading}
                            className="w-full resize-none rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-red-500/50 disabled:opacity-50 transition-shadow"
                        />
                    </div>
                    <Button
                        onClick={handleSend}
                        disabled={!input.trim() || loading}
                        size="icon"
                        className="rounded-xl h-11 w-11 bg-orange-600 hover:bg-orange-700 text-white flex-shrink-0"
                    >
                        <Send className="h-4 w-4" />
                    </Button>
                </div>
                <p className="text-[11px] text-muted-foreground mt-2 text-center">
                    Model: <span className="font-mono font-medium">{model}</span>
                    {" · "}
                    Mode: {streaming ? "Streaming SSE" : "Non-streaming"}
                    {" · "}
                    Messages in context: {messages.length}
                </p>
            </div>
        </div>
    )
}
