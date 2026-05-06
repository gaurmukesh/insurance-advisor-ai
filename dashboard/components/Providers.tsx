"use client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { AdvisorProvider } from "@/lib/AdvisorContext";

export default function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => new QueryClient());
  return (
    <QueryClientProvider client={queryClient}>
      <AdvisorProvider>{children}</AdvisorProvider>
    </QueryClientProvider>
  );
}
