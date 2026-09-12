"use client";
// Admin shell: sectioned sidebar nav for all /admin/* pages except login.
import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { api } from "../../lib/api";

const SECTIONS: [string, [string, string][]][] = [
  ["Overview", [
    ["/admin/dashboard", "Dashboard"],
    ["/admin/attendance", "Attendance"],
    ["/admin/reports", "Reports"],
  ]],
  ["People", [
    ["/admin/users", "Users"],
    ["/admin/identity", "Verify identity"],
    ["/admin/enroll", "Enroll"],
    ["/admin/leave", "Leave"],
    ["/admin/hr", "HR / Payroll"],
  ]],
  ["Access", [
    ["/admin/zones", "Zones"],
    ["/admin/badges", "Badges"],
    ["/admin/devices", "Devices"],
    ["/admin/verified", "Face access"],
    ["/admin/visitors", "Visitors"],
    ["/admin/blacklist", "Blacklist"],
    ["/admin/geofences", "Geofences"],
  ]],
  ["Operations", [
    ["/admin/alerts", "Alerts"],
    ["/admin/emergency", "Emergency"],
    ["/admin/security", "Security"],
  ]],
  ["Modules", [
    ["/admin/timetable", "Timetable"],
    ["/admin/memberships", "Memberships"],
    ["/admin/donations", "Donations"],
    ["/admin/events", "Events"],
  ]],
  ["System", [
    ["/admin/roles", "Roles"],
    ["/admin/grievances", "Grievances"],
    ["/admin/retention", "Retention"],
    ["/admin/audit", "Audit"],
    ["/admin/settings", "Settings"],
  ]],
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [alertCount, setAlertCount] = useState(0);

  useEffect(() => {
    if (pathname === "/admin/login") return;
    api<{ items: unknown[] }>("/alerts").then((d) => setAlertCount(d.items.length)).catch(() => {});
  }, [pathname]);

  if (pathname === "/admin/login") return <>{children}</>;

  async function logout() {
    try { await api("/auth/logout", { method: "POST" }); } catch {}
    router.push("/admin/login");
  }

  return (
    <div className="shell">
      <aside className="sidebar">
        <div style={{ fontWeight: 700, fontSize: 18, marginBottom: 16 }}>BioCore</div>
        {SECTIONS.map(([section, links]) => (
          <div key={section} style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 11, textTransform: "uppercase", color: "#64748b", margin: "6px 12px" }}>{section}</div>
            {links.map(([href, label]) => (
              <a key={href} href={href} className={pathname === href ? "active" : ""}>
                {label}
                {label === "Alerts" && alertCount > 0 && (
                  <span className="badge red" style={{ marginLeft: 8 }}>{alertCount}</span>
                )}
              </a>
            ))}
          </div>
        ))}
        <button className="ghost" onClick={logout} style={{ color: "#94a3b8", paddingLeft: 12 }}>Sign out</button>
      </aside>
      <main className="main">{children}</main>
    </div>
  );
}
