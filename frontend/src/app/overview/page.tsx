"use client";

import { useEffect, useState } from "react";
import { hasApiKey } from "@/lib/api";
import { NavBar } from "@/components/nav-bar";
import { OverviewContent } from "@/components/overview-content";

export default function OverviewPage() {
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
      <main className="max-w-3xl mx-auto px-4 py-6">
        <OverviewContent />
      </main>
    </>
  );
}
