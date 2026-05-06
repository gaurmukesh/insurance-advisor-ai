"use client";
import { createContext, useContext, ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { getAdvisors, Advisor } from "@/lib/api";

interface AdvisorContextValue {
  advisor: Advisor | null;
  isLoading: boolean;
}

const AdvisorContext = createContext<AdvisorContextValue>({ advisor: null, isLoading: true });

export function AdvisorProvider({ children }: { children: ReactNode }) {
  const { data, isLoading } = useQuery({
    queryKey: ["advisors"],
    queryFn: getAdvisors,
    staleTime: Infinity,
  });

  const advisor = data?.[0] ?? null;

  return (
    <AdvisorContext.Provider value={{ advisor, isLoading }}>
      {children}
    </AdvisorContext.Provider>
  );
}

export function useAdvisor() {
  return useContext(AdvisorContext);
}
