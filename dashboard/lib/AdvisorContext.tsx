"use client";
import { createContext, useContext, ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { getMe, getToken, Advisor } from "@/lib/api";

interface AdvisorContextValue {
  advisor: Advisor | null;
  isLoading: boolean;
}

const AdvisorContext = createContext<AdvisorContextValue>({ advisor: null, isLoading: true });

export function AdvisorProvider({ children }: { children: ReactNode }) {
  const { data, isLoading } = useQuery({
    queryKey: ["me"],
    queryFn: getMe,
    enabled: !!getToken(),
    retry: false,
    staleTime: Infinity,
  });

  return (
    <AdvisorContext.Provider value={{ advisor: data ?? null, isLoading }}>
      {children}
    </AdvisorContext.Provider>
  );
}

export function useAdvisor() {
  return useContext(AdvisorContext);
}
