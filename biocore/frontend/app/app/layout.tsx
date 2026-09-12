"use client";
// Person-app shell (mobile-first): phone-width frame + gradient app bar.
import "./app.css";
import { usePathname, useRouter } from "next/navigation";
import { api } from "../../lib/api";

export default function PersonLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();

  // login renders its own full-screen hero (no app bar)
  if (pathname === "/app/login") return <>{children}</>;

  async function logout() {
    try { await api("/person/auth/logout", { method: "POST" }); } catch {}
    router.push("/app/login");
  }

  return (
    <div className="app-shell">
      <header className="app-top">
        <div className="wrap">
          <a href="/app" className="brand"><span className="mark">B</span> BioCore</a>
          <button onClick={logout}>Sign out</button>
        </div>
      </header>
      <div className="app-body"><div className="wrap">{children}</div></div>
    </div>
  );
}
