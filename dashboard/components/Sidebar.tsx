"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Users, Bell, Mail, LayoutDashboard, Shield } from "lucide-react";

const nav = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/leads", label: "Leads", icon: Users },
  { href: "/renewals", label: "Renewals", icon: Bell },
  { href: "/email-logs", label: "Email Logs", icon: Mail },
];

export default function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="w-60 bg-white border-r border-gray-200 flex flex-col">
      <div className="flex items-center gap-2 px-6 py-5 border-b border-gray-200">
        <Shield className="text-blue-600" size={22} />
        <span className="font-semibold text-gray-800 text-sm">Insurance Advisor AI</span>
      </div>
      <nav className="flex-1 px-3 py-4 space-y-1">
        {nav.map(({ href, label, icon: Icon }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                active
                  ? "bg-blue-50 text-blue-700 font-medium"
                  : "text-gray-600 hover:bg-gray-100"
              }`}
            >
              <Icon size={17} />
              {label}
            </Link>
          );
        })}
      </nav>
      <div className="px-6 py-4 border-t border-gray-200 text-xs text-gray-400">
        Phase 1 — v1.0.0
      </div>
    </aside>
  );
}
