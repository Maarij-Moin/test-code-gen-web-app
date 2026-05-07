import { useState } from "react";
import {
  Bell,
  Bot,
  CheckCircle2,
  Globe,
  Key,
  Moon,
  Palette,
  Save,
  ShieldCheck,
  Sun,
  Zap,
} from "lucide-react";
import { Card, CardContent, CardHeader } from "@/components/ui/Card";
import { useAuthStore } from "@/stores/authStore";
import { useUiStore } from "@/stores/uiStore";

type SectionProps = { title: string; description: string; icon: React.ReactNode; children: React.ReactNode };

function Section({ title, description, icon, children }: SectionProps) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <span className="text-brand">{icon}</span>
          <div>
            <h2 className="text-base font-semibold text-text">{title}</h2>
            <p className="text-xs text-muted">{description}</p>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-5">{children}</CardContent>
    </Card>
  );
}

function Toggle({ checked, onChange, id }: { checked: boolean; onChange: () => void; id: string }) {
  return (
    <button
      id={id}
      role="switch"
      aria-checked={checked}
      onClick={onChange}
      className={`relative h-6 w-11 rounded-full transition-colors ${checked ? "bg-brand" : "bg-panel2"}`}
    >
      <span
        className={`absolute left-0.5 top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform ${checked ? "translate-x-5" : "translate-x-0"}`}
      />
    </button>
  );
}

function Field({ label, description, children }: { label: string; description?: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <div>
        <p className="text-sm font-medium text-text">{label}</p>
        {description && <p className="text-xs text-muted">{description}</p>}
      </div>
      {children}
    </div>
  );
}

export function Settings() {
  const user = useAuthStore((s) => s.user);
  const { theme, toggleTheme } = useUiStore();
  const [saved, setSaved] = useState(false);
  const [llmProvider, setLlmProvider] = useState("openai");
  const [model, setModel] = useState("gpt-4o-mini");
  const [apiBaseUrl, setApiBaseUrl] = useState(import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000");
  const [webhookNotif, setWebhookNotif] = useState(true);
  const [jobNotif, setJobNotif] = useState(true);
  const [repairLoops, setRepairLoops] = useState(true);

  function handleSave() {
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  return (
    <main className="space-y-6 px-4 py-6 md:px-8">
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-text">Settings</h1>
          <p className="mt-1 text-sm text-muted">Configure your workspace, LLM provider, and notifications.</p>
        </div>
        <button
          id="settings-save"
          onClick={handleSave}
          className="flex items-center gap-2 rounded-lg bg-gradient-to-r from-brand to-brand2 px-5 py-2.5 text-sm font-semibold text-white shadow-md transition hover:opacity-90"
        >
          {saved ? <CheckCircle2 size={16} /> : <Save size={16} />}
          {saved ? "Saved!" : "Save changes"}
        </button>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        {/* Profile */}
        <Section title="Profile" description="Your workspace account" icon={<ShieldCheck size={16} />}>
          <div className="flex items-center gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-gradient-to-br from-brand to-brand2 text-lg font-bold text-white">
              {(user?.full_name ?? user?.email ?? "?")[0].toUpperCase()}
            </div>
            <div>
              <p className="font-semibold text-text">{user?.full_name ?? "—"}</p>
              <p className="text-sm text-muted">{user?.email}</p>
            </div>
          </div>
          <Field label="Account status" description="Authentication state">
            <span className="flex items-center gap-1.5 rounded-md bg-success/10 px-3 py-1 text-xs font-semibold text-success">
              <CheckCircle2 size={12} /> Active
            </span>
          </Field>
        </Section>

        {/* Appearance */}
        <Section title="Appearance" description="Theme and display preferences" icon={<Palette size={16} />}>
          <Field label="Dark mode" description="Toggle between light and dark UI">
            <div className="flex items-center gap-2">
              <Sun size={14} className="text-muted" />
              <Toggle id="toggle-dark-mode" checked={theme === "dark"} onChange={toggleTheme} />
              <Moon size={14} className="text-muted" />
            </div>
          </Field>
          <Field label="Current theme">
            <span className="rounded-md bg-panel2 px-3 py-1 text-xs font-medium text-text capitalize">{theme}</span>
          </Field>
        </Section>

        {/* LLM Provider */}
        <Section title="LLM Provider" description="Test generation AI backend" icon={<Bot size={16} />}>
          <Field label="Provider" description="LLM_PROVIDER env variable">
            <select
              id="llm-provider-select"
              value={llmProvider}
              onChange={(e) => setLlmProvider(e.target.value)}
              className="rounded-lg border border-border bg-panel2 px-3 py-1.5 text-sm text-text focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand"
            >
              <option value="mock">Mock (CI / dev)</option>
              <option value="openai">OpenAI</option>
              <option value="azure">Azure OpenAI</option>
              <option value="ollama">Ollama (local)</option>
            </select>
          </Field>
          <Field label="Model" description="OPENAI_MODEL env variable">
            <select
              id="llm-model-select"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="rounded-lg border border-border bg-panel2 px-3 py-1.5 text-sm text-text focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand"
            >
              <option value="gpt-4o-mini">gpt-4o-mini</option>
              <option value="gpt-4o">gpt-4o</option>
              <option value="gpt-4-turbo">gpt-4-turbo</option>
              <option value="llama3">llama3 (Ollama)</option>
            </select>
          </Field>
          <Field label="Self-healing repair loops" description="Retry failed tests with LLM">
            <Toggle id="toggle-repair" checked={repairLoops} onChange={() => setRepairLoops((v) => !v)} />
          </Field>
        </Section>

        {/* API */}
        <Section title="API Connection" description="Backend endpoint configuration" icon={<Globe size={16} />}>
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-muted" htmlFor="api-base-url">
              API Base URL
            </label>
            <input
              id="api-base-url"
              type="url"
              value={apiBaseUrl}
              onChange={(e) => setApiBaseUrl(e.target.value)}
              className="w-full rounded-lg border border-border bg-panel2 px-3 py-2 text-sm text-text focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand"
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-muted" htmlFor="api-key-field">
              API Key (optional)
            </label>
            <div className="relative">
              <Key size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
              <input
                id="api-key-field"
                type="password"
                placeholder="sk-… or leave blank"
                className="w-full rounded-lg border border-border bg-panel2 py-2 pl-9 pr-4 text-sm text-text placeholder:text-muted focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand"
              />
            </div>
          </div>
        </Section>

        {/* Notifications */}
        <Section title="Notifications" description="In-app event notifications" icon={<Bell size={16} />}>
          <Field label="Webhook events" description="Alert on incoming GitHub webhooks">
            <Toggle id="toggle-webhook-notif" checked={webhookNotif} onChange={() => setWebhookNotif((v) => !v)} />
          </Field>
          <Field label="Job completion" description="Alert when generation jobs finish">
            <Toggle id="toggle-job-notif" checked={jobNotif} onChange={() => setJobNotif((v) => !v)} />
          </Field>
        </Section>

        {/* Pipeline */}
        <Section title="Pipeline" description="Generation and validation configuration" icon={<Zap size={16} />}>
          {[
            { label: "Max repair attempts", value: "3" },
            { label: "Validation timeout", value: "120s" },
            { label: "Embedding model", value: "BAAI/bge-base-en-v1.5" },
            { label: "Test output dir", value: "auto_tests/" },
          ].map(({ label, value }) => (
            <div key={label} className="flex justify-between text-sm">
              <span className="text-muted">{label}</span>
              <span className="font-mono text-xs font-medium text-text">{value}</span>
            </div>
          ))}
        </Section>
      </div>
    </main>
  );
}
