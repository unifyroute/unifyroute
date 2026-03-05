import { Moon, Sun, Monitor } from "lucide-react"
import { cn } from "@/lib/utils"
import { useTheme } from "@/components/theme-provider"

export function ModeToggle() {
    const { theme, setTheme } = useTheme()

    // Order: system, light, dark to match UnifyRouter precisely
    const themeIndex = theme === 'system' ? 0 : theme === 'light' ? 1 : 2;

    return (
        <div className="relative inline-flex items-center rounded-full border border-slate-200 dark:border-slate-800 bg-slate-100/50 dark:bg-slate-900 p-1 gap-0.5 translate-y-[1px]">
            <div
                className="absolute left-1 top-1 h-7 w-7 rounded-full bg-white dark:bg-slate-800 shadow-sm transition-transform duration-300 ease-out"
                style={{ transform: `translateX(${themeIndex * 30}px)` }}
            />

            <button
                onClick={() => setTheme("system")}
                className={cn(
                    "relative z-10 flex h-7 w-7 items-center justify-center rounded-full transition-colors",
                    theme === "system" ? "text-slate-900 dark:text-slate-100" : "text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100"
                )}
                title="System"
            >
                <Monitor className="h-[14px] w-[14px]" strokeWidth={1.5} />
            </button>
            <button
                onClick={() => setTheme("light")}
                className={cn(
                    "relative z-10 flex h-7 w-7 items-center justify-center rounded-full transition-colors",
                    theme === "light" ? "text-slate-900 dark:text-slate-100" : "text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100"
                )}
                title="Light"
            >
                <Sun className="h-[14px] w-[14px]" strokeWidth={1.5} />
            </button>
            <button
                onClick={() => setTheme("dark")}
                className={cn(
                    "relative z-10 flex h-7 w-7 items-center justify-center rounded-full transition-colors",
                    theme === "dark" ? "text-slate-900 dark:text-slate-100" : "text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100"
                )}
                title="Dark"
            >
                <Moon className="h-[14px] w-[14px]" strokeWidth={1.5} />
            </button>
        </div>
    )
}
