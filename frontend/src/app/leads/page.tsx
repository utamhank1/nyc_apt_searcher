"use client";

import { useEffect, useState } from "react";
import { hasApiKey } from "@/lib/api";
import { NavBar } from "@/components/nav-bar";
import { LeadsPage } from "@/components/leads-page";

export default function LeadsRoute() {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    if (typeof window !== "undefined" && !hasApiKey()) {
      window.location.href = "/";
    }
  }, []);

  if (!mounted) return null;

  return (
    <>
      <NavBar />
      <main className="max-w-7xl mx-auto px-4 py-6">
        <LeadsPage />
      </main>
    </>
  );
}
