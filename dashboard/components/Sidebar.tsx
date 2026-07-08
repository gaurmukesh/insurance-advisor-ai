"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Users, Bell, Mail, LayoutDashboard, Shield, MessageCircle, Clock, FileText, BarChart2, LogOut } from "lucide-react";
import { logout } from "@/lib/api";
import { useAdvisor } from "@/lib/AdvisorContext";

const nav = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/leads", label: "Leads", icon: Users },
  { href: "/renewals", label: "Renewals", icon: Bell },
  { href: "/email-drafts", label: "Pending Approvals", icon: Clock },
  { href: "/email-logs", label: "Email Logs", icon: Mail },
  { href: "/whatsapp-logs", label: "WhatsApp Logs", icon: MessageCircle },
  { href: "/documents", label: "Documents", icon: FileText },
  { href: "/metrics", label: "Metrics", icon: BarChart2 },
];

export default function Sidebar() {
  const pathname = usePathname();
  const { advisor } = useAdvisor();
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
      <div className="px-3 py-4 border-t border-gray-200">
        {advisor && (
          <p className="px-3 text-xs text-gray-500 truncate mb-2">{advisor.name}</p>
        )}
        <button
          onClick={logout}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-gray-600 hover:bg-gray-100 transition-colors"
        >
          <LogOut size={17} />
          Logout
        </button>
      </div>
    </aside>
  );
}
