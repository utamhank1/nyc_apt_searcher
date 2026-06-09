"use client";

import { useEffect, useState } from "react";
import { api, hasApiKey } from "@/lib/api";
import { Stats } from "@/lib/types";
import { NavBar } from "@/components/nav-bar";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export default function OverviewPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!hasApiKey()) { window.location.href = "/"; return; }
    fetchStats();
  }, []);

  const fetchStats = async () => {
    setLoading(true);
    try {
      const data = await api.get<Stats>("/api/v1/stats");
      setStats(data);
    } catch (e) {
      console.error("Failed to fetch stats", e);
    }
    setLoading(false);
  };

  const formatTimeAgo = (iso: string | null) => {
    if (!iso) return "Never";
    const diff = Date.now() - new Date(iso).getTime();
    const hours = Math.floor(diff / 3600000);
    const minutes = Math.floor((diff % 3600000) / 60000);
    if (hours > 24) return `${Math.floor(hours / 24)} days ago`;
    if (hours > 0) return `${hours}h ${minutes}m ago`;
    return `${minutes}m ago`;
  };

  return (
    <>
      <NavBar />
      <main className="max-w-3xl mx-auto px-4 py-6">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold">Overview</h1>
          <Button variant="outline" onClick={fetchStats} disabled={loading}>
            Refresh
          </Button>
        </div>

        {stats ? (
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
            <StatCard label="Total Listings" value={stats.total_listings} />
            <StatCard label="Active Listings" value={stats.active_listings} />
            <StatCard label="Hot Leads" value={stats.hot_leads} color="text-orange-600" />
            <StatCard label="Tours Scheduled" value={stats.tours_scheduled} color="text-green-600" />
            <StatCard label="Broker Emails Sent" value={stats.broker_emails_sent} color="text-blue-600" />
            <StatCard label="Passed" value={stats.passed} color="text-gray-400" />
            <div className="col-span-2 sm:col-span-3">
              <Card className="p-4">
                <div className="text-sm text-gray-500">Last Scrape</div>
                <div className="text-lg font-semibold">{formatTimeAgo(stats.last_scrape)}</div>
              </Card>
            </div>
          </div>
        ) : (
          <Card className="p-8 text-center text-gray-500">Loading stats...</Card>
        )}
      </main>
    </>
  );
}

function StatCard({ label, value, color }: { label: string; value: number; color?: string }) {
  return (
    <Card className="p-4">
      <div className="text-sm text-gray-500">{label}</div>
      <div className={`text-3xl font-bold ${color || "text-gray-900"}`}>{value}</div>
    </Card>
  );
}
