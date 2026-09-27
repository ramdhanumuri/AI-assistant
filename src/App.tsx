import { AnimatePresence, motion } from 'framer-motion';
import { useEffect, useState, type ReactNode } from 'react';
import { AppProvider, useApp } from '@/state/AppContext';
import { AuthProvider, useAuth } from '@/state/AuthContext';
import { RouterProvider, useRouter } from '@/lib/router';
import { MODE_BY_ID } from '@/data/mock';
import { cx, rgba } from '@/lib/utils';
import { AmbientBackground } from '@/components/AmbientBackground';
import { BootSequence } from '@/components/BootSequence';
import { CommandCenter } from '@/components/CommandCenter';
import { SettingsPanel } from '@/components/SettingsPanel';
import { Sidebar } from '@/components/Sidebar';
import { TopNavigation } from '@/components/TopNavigation';
import { LandingHero } from '@/features/LandingHero';
import { ChatInterface } from '@/features/ChatInterface';
import { VoiceInterface } from '@/features/VoiceInterface';
import { IntelligenceDashboard } from '@/features/IntelligenceDashboard';
import {
  KnowledgeSurface,
  MemorySurface,
  ProjectsSurface,
  ToolsSurface,
} from '@/features/SystemSurfaces';
import { LoginScreen } from '@/features/auth/LoginScreen';
import { RegisterScreen } from '@/features/auth/RegisterScreen';
import { ForgotPasswordScreen, ResetPasswordScreen } from '@/features/auth/PasswordScreens';
import { ProfileScreen } from '@/features/auth/ProfileScreen';
import {
  AuthLoadingScreen,
  NotFoundScreen,
  RequireAdmin,
  RequireAuth,
  RequireGuest,
} from '@/features/auth/Guards';
import { AdminDashboard } from '@/features/admin/AdminDashboard';
import { PublicHome } from '@/features/PublicHome';

const VARIANT_BY_VIEW = {
  home: 'home',
  conversation: 'conversation',
  voice: 'voice',
  dashboard: 'dashboard',
  knowledge: 'system',
  tools: 'system',
  memory: 'system',
  projects: 'system',
} as const;

function AppShell({
  children,
  meta,
}: {
  /** Replaces the view switch. Used by /profile and /admin, which are real
   *  routes rather than entries in the in-app `view` state. */
  children?: ReactNode;
  meta?: { title: string; caption: string };
}) {
  const { view, mode, aiState, settings, sidebarOpen, toasts } = useApp();
  const active = MODE_BY_ID[mode];
  const [booted, setBooted] = useState(false);

  /* Honour the in-app motion preference alongside the OS setting */
  useEffect(() => {
    const root = document.documentElement;
    if (settings.reduceMotion) root.style.setProperty('--motion-scale', '0');
    else root.style.removeProperty('--motion-scale');
  }, [settings.reduceMotion]);

  return (
    <div className="relative flex h-full w-full overflow-hidden bg-obsidian-950">
      {settings.ambientLight && (
        <AmbientBackground
          aura={active.aura}
          variant={VARIANT_BY_VIEW[view]}
          intense={aiState !== 'idle' || view === 'voice'}
        />
      )}

      <AnimatePresence>
        {!booted && <BootSequence onComplete={() => setBooted(true)} />}
      </AnimatePresence>

      <motion.div
        initial={false}
        animate={{
          opacity: booted ? 1 : 0,
          filter: booted ? 'blur(0px)' : 'blur(16px)',
          scale: booted ? 1 : 1.015,
        }}
        transition={{ duration: 0.9, ease: [0.16, 1, 0.3, 1] }}
        className="relative z-10 flex h-full w-full min-w-0"
      >
        <Sidebar />

        <div className="relative flex h-full min-w-0 flex-1 flex-col">
          <TopNavigation meta={meta} />

          <main className="relative flex min-h-0 flex-1 flex-col overflow-hidden">
            <AnimatePresence mode="wait" initial={false}>
              <motion.div
                key={children ? (meta?.title ?? 'custom') : view}
                initial={{ opacity: 0, y: 14, filter: 'blur(10px)' }}
                animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
                exit={{ opacity: 0, y: -10, filter: 'blur(10px)' }}
                transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
                className={cx('flex min-h-0 flex-1 flex-col', children ? 'overflow-y-auto' : undefined)}
              >
                {children ?? (
                  <>
                    {view === 'home' && <LandingHero />}
                    {view === 'conversation' && <ChatInterface />}
                    {view === 'voice' && <VoiceInterface />}
                    {view === 'dashboard' && <IntelligenceDashboard />}
                    {view === 'knowledge' && <KnowledgeSurface />}
                    {view === 'tools' && <ToolsSurface />}
                    {view === 'memory' && <MemorySurface />}
                    {view === 'projects' && <ProjectsSurface />}
                  </>
                )}
              </motion.div>
            </AnimatePresence>
          </main>
        </div>
      </motion.div>

      <CommandCenter />
      <SettingsPanel />

      <ToastStack toasts={toasts} aura={active.aura} />

      {/* Keyboard-only skip link */}
      <a
        href="#command-input"
        className={cx(
          'sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-[120]',
          'focus:rounded-lg focus:border focus:border-white/20 focus:bg-obsidian-900 focus:px-4 focus:py-2',
          'focus:font-mono focus:text-xs focus:text-platinum',
        )}
      >
        Skip to message input
      </a>

      {/* Ambient edge frame — reinforces the "contained system" feel */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 z-[60]"
        style={{
          boxShadow: `inset 0 0 120px -60px ${rgba(active.aura, 0.35)}, inset 0 0 0 1px rgba(255,255,255,0.02)`,
        }}
      />

      {!sidebarOpen && (
        <div
          aria-hidden
          className="pointer-events-none absolute inset-y-0 left-0 z-[55] w-[76px] lg:hidden"
        />
      )}
    </div>
  );
}

/** `/settings` is a route over the existing settings overlay: land on the chat
 *  surface and open the panel, so there is one implementation, not two. */
function SettingsRoute() {
  const { setSettingsOpen, setView } = useApp();

  useEffect(() => {
    setView('conversation');
    setSettingsOpen(true);
  }, [setSettingsOpen, setView]);

  return <ChatInterface />;
}

/** Signed-in users landing on `/` belong in the workspace, not on the pitch. */
function HomeRoute() {
  const { status } = useAuth();
  const { navigate } = useRouter();

  useEffect(() => {
    if (status === 'authenticated') navigate('/chat', { replace: true });
  }, [status, navigate]);

  if (status === 'loading' || status === 'authenticated') return <AuthLoadingScreen />;
  return <PublicHome />;
}

function Routes() {
  const { path } = useRouter();

  switch (path) {
    case '/':
      return <HomeRoute />;

    case '/login':
      return (
        <RequireGuest>
          <LoginScreen />
        </RequireGuest>
      );

    case '/register':
      return (
        <RequireGuest>
          <RegisterScreen />
        </RequireGuest>
      );

    /* Signed-out pages by nature; RequireGuest keeps a signed-in visitor from
       sitting on a reset form that would revoke their own sessions. */
    case '/forgot-password':
      return (
        <RequireGuest>
          <ForgotPasswordScreen />
        </RequireGuest>
      );

    case '/reset-password':
      return <ResetPasswordScreen />;

    case '/chat':
      return (
        <RequireAuth>
          <AppShell />
        </RequireAuth>
      );

    case '/profile':
      return (
        <RequireAuth>
          <AppShell meta={{ title: 'Profile', caption: 'Account & security' }}>
            <ProfileScreen />
          </AppShell>
        </RequireAuth>
      );

    case '/settings':
      return (
        <RequireAuth>
          <AppShell meta={{ title: 'Preferences', caption: 'Interface & behaviour' }}>
            <SettingsRoute />
          </AppShell>
        </RequireAuth>
      );

    case '/admin':
      return (
        <RequireAdmin>
          <AppShell meta={{ title: 'Administration', caption: 'Platform control' }}>
            <AdminDashboard />
          </AppShell>
        </RequireAdmin>
      );

    default:
      return <NotFoundScreen />;
  }
}

function ToastStack({
  toasts,
  aura,
}: {
  toasts: { id: string; text: string }[];
  aura: string;
}) {
  return (
    <div
      className="pointer-events-none fixed bottom-6 left-1/2 z-[90] flex -translate-x-1/2 flex-col items-center gap-2"
      aria-live="polite"
    >
      <AnimatePresence>
        {toasts.map((t) => (
          <motion.div
            key={t.id}
            initial={{ opacity: 0, y: 16, scale: 0.96, filter: 'blur(8px)' }}
            animate={{ opacity: 1, y: 0, scale: 1, filter: 'blur(0px)' }}
            exit={{ opacity: 0, y: 10, scale: 0.97, filter: 'blur(8px)' }}
            transition={{ duration: 0.42, ease: [0.16, 1, 0.3, 1] }}
            className="glass-deep flex items-center gap-3 rounded-full px-4 py-2.5 shadow-glass"
          >
            <span
              className="h-1.5 w-1.5 rounded-full"
              style={{
                background: rgba(aura, 0.95),
                boxShadow: `0 0 10px ${rgba(aura, 0.85)}`,
              }}
            />
            <span className="font-mono text-3xs uppercase tracking-widest2 text-platinum-soft">
              {t.text}
            </span>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}

export default function App() {
  return (
    <RouterProvider>
      <AuthProvider>
        <AppProvider>
          <Routes />
        </AppProvider>
      </AuthProvider>
    </RouterProvider>
  );
}
