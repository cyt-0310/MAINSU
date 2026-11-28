import type { ApplicationTarget } from "./PortfolioManager";
import type { Session } from "./VoiceInterview";

export type Account = {
  id: string;
  email: string;
  name: string;
  targets: ApplicationTarget[] | null;
  pointBalance: number | null;
};

export async function workspaceRequest<T>(path: string, method = "GET", body?: unknown, accountId?: string): Promise<T> {
  const headers = new Headers();
  if (body !== undefined) headers.set("Content-Type", "application/json");
  if (accountId) headers.set("X-MAINSU-Account", accountId);
  const response = await fetch(path, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await response.json().catch(() => null);
  if (!response.ok || data === null) {
    throw new Error(data?.error || "暫時無法連線到 MAINSU，請稍後再試。");
  }
  return data as T;
}

export function workspaceStorage(accountId: string) {
  const key = (name: string) => `mainsu.account.${accountId}.${name}`;
  return {
    read<T>(name: string): T | null {
      try { return JSON.parse(localStorage.getItem(key(name)) ?? "null") as T | null; }
      catch { return null; }
    },
    write(name: string, value: unknown) {
      try { localStorage.setItem(key(name), JSON.stringify(value)); } catch {}
    },
    remove(name: string) {
      try { localStorage.removeItem(key(name)); } catch {}
    },
  };
}

export async function saveFreeReport(report: Session, accountId: string) {
  await workspaceRequest("/api/voice-interviews/free-report", "POST", report, accountId);
}
