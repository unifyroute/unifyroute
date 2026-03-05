import { BrowserRouter, Routes, Route, Link, useLocation, Navigate, useNavigate } from "react-router-dom";
import { LayoutDashboard, Database, Key, Box, Gauge, ScrollText, Settings as SettingsIcon, GitBranch, LogOut, MessageSquare, Brain, Wand2, PackageCheck } from "lucide-react";

import { Dashboard } from "@/pages/Dashboard";
import { Providers } from "@/pages/Providers";
import { Credentials } from "@/pages/Credentials";
import { Models } from "@/pages/Models";
import { RoutingStrategy } from "@/pages/RoutingStrategy";
import { Quota } from "@/pages/Quota";
import { Logs } from "@/pages/Logs";
import { Settings } from "@/pages/Settings";
import { Login } from "@/pages/Login";
import { Chat } from "@/pages/Chat";
import { BrainPage } from "@/pages/Brain";
import { SetupWizard } from "@/pages/SetupWizard";
import { ModelManagement } from "@/pages/ModelManagement";
import { ThemeProvider } from "@/components/theme-provider";
import { ModeToggle } from "@/components/mode-toggle";
import { SWRConfig } from "swr";
import { getAuthToken, setAuthToken } from "@/lib/api";

const SidebarSection = ({ title, children }: { title: string, children: React.ReactNode }) => (
  <div className="mb-6">
    <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider px-4 mb-2 flex items-center justify-between">
      <span>{title}</span>
      <span className="text-slate-200 dark:text-slate-800">-</span>
    </div>
    <div className="flex flex-col gap-1">{children}</div>
  </div>
);

const NavItem = ({ to, icon: Icon, label, active = false }: { to: string, icon: any, label: string, active?: boolean }) => (
  <Link
    to={to}
    className={`flex items-center gap-3 px-4 py-2.5 rounded-md transition-colors ${active ? 'bg-orange-50 dark:bg-orange-500/10 text-orange-600 dark:text-orange-500 font-medium' : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800/50 hover:text-slate-900 dark:hover:text-slate-100'
      }`}
  >
    <Icon size={18} className={active ? 'text-orange-500' : 'text-slate-400'} />
    <span className="text-sm">{label}</span>
  </Link>
);

const Sidebar = () => {
  const location = useLocation();
  const path = location.pathname;
  const navigate = useNavigate();

  function handleLogout() {
    setAuthToken("");
    fetch("/api/admin/logout", { method: "POST", credentials: "include" }).catch(() => { });
    navigate("/login");
  }

  return (
    <aside className="w-64 bg-white dark:bg-slate-950 border-r border-slate-200 dark:border-slate-800 min-h-[calc(100vh-64px)] py-6 flex flex-col justify-between">
      <div>
        <SidebarSection title="Control">
          <NavItem to="/" icon={LayoutDashboard} label="Overview" active={path === "/"} />
          <NavItem to="/chat" icon={MessageSquare} label="Chat Playground" active={path === "/chat"} />
          <NavItem to="/providers" icon={Database} label="Providers" active={path === "/providers"} />
          <NavItem to="/credentials" icon={Key} label="Credentials" active={path === "/credentials"} />
          <NavItem to="/models" icon={Box} label="Provider Models" active={path === "/models"} />
          <NavItem to="/model-management" icon={PackageCheck} label="Model Management" active={path === "/model-management"} />
          <NavItem to="/routing" icon={GitBranch} label="Routing Strategy" active={path === "/routing"} />
          <NavItem to="/quota" icon={Gauge} label="Usage & Quota" active={path === "/quota"} />
          <NavItem to="/logs" icon={ScrollText} label="Sessions & Logs" active={path === "/logs"} />
          <NavItem to="/brain" icon={Brain} label="Brain" active={path === "/brain"} />
        </SidebarSection>

        <SidebarSection title="Setup">
          <NavItem to="/wizard" icon={Wand2} label="Setup Wizard" active={path === "/wizard"} />
        </SidebarSection>

        <SidebarSection title="Settings">
          <NavItem to="/settings" icon={SettingsIcon} label="Config" active={path === "/settings"} />
          <button
            onClick={handleLogout}
            className="flex items-center gap-3 w-full text-left px-4 py-2.5 rounded-md transition-colors text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800/50 hover:text-slate-900 dark:hover:text-slate-100"
          >
            <LogOut size={18} className="text-slate-400" />
            <span className="text-sm">Sign Out</span>
          </button>
        </SidebarSection>
      </div>
    </aside>
  );
};

const Header = () => (
  <header className="h-16 bg-white dark:bg-slate-950 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between px-6 z-10 sticky top-0">
    <div className="flex items-center gap-3">
      <img src="/images/favicon.png" alt="UnifyRoute" className="w-8 h-8 object-contain" />
      <div>
        <h1 className="font-bold text-slate-900 dark:text-slate-100 text-lg leading-tight tracking-tight uppercase">UnifyRouter</h1>
        <p className="text-[10px] text-slate-500 dark:text-slate-400 font-medium tracking-widest uppercase">Router Gateway Dashboard</p>
      </div>
    </div>
    <div className="flex items-center gap-4">
      <div className="flex items-center gap-2 bg-slate-50 dark:bg-slate-900 px-3 py-1.5 rounded-full border border-slate-200 dark:border-slate-800">
        <div className="w-2 h-2 rounded-full bg-emerald-500"></div>
        <span className="text-xs font-medium text-slate-600 dark:text-slate-400">Health <span className="text-slate-400 dark:text-slate-500">Online</span></span>
      </div>
      <ModeToggle />
    </div>
  </header>
);

/** Redirects to /login if no auth token is stored */
function RequireAuth({ children }: { children: React.ReactNode }) {
  const token = getAuthToken();
  if (!token) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}

function AppContent() {
  return (
    <div className="flex flex-col min-h-screen bg-slate-50 dark:bg-slate-900 font-sans text-slate-900 dark:text-slate-100">
      <Header />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main className="flex-1 w-full overflow-y-auto p-8">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/chat" element={<Chat />} />
            <Route path="/providers" element={<Providers />} />
            <Route path="/credentials" element={<Credentials />} />
            <Route path="/models" element={<Models />} />
            <Route path="/routing" element={<RoutingStrategy />} />
            <Route path="/quota" element={<Quota />} />
            <Route path="/logs" element={<Logs />} />
            <Route path="/brain" element={<BrainPage />} />
            <Route path="/wizard" element={<SetupWizard />} />
            <Route path="/model-management" element={<ModelManagement />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}

function App() {
  return (
    <ThemeProvider defaultTheme="system" storageKey="vite-ui-theme">
      <SWRConfig
        value={{
          shouldRetryOnError: false,
          revalidateOnFocus: false
        }}
      >
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route
              path="/*"
              element={
                <RequireAuth>
                  <AppContent />
                </RequireAuth>
              }
            />
          </Routes>
        </BrowserRouter>
      </SWRConfig>
    </ThemeProvider>
  );
}

export default App;
