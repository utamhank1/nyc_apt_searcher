"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Stats } from "@/lib/types";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export function OverviewContent() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.get<Stats>("/api/v1/stats");
      setStats(data);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to connect";
      setError(msg);
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
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Overview</h1>
        <Button variant="outline" onClick={fetchStats} disabled={loading}>
          {loading ? "Loading..." : "Refresh"}
        </Button>
      </div>

      {error && (
        <Card className="p-6 mb-4 border-yellow-200 bg-yellow-50">
          <p className="font-medium text-yellow-800">Backend not connected</p>
          <p className="text-sm text-yellow-600 mt-1">{error}</p>
          <Button variant="outline" size="sm" className="mt-3" onClick={fetchStats}>
            Retry
          </Button>
        </Card>
      )}

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
        <StatCard label="Total Listings" value={stats?.total_listings ?? 0} />
        <StatCard label="Active Listings" value={stats?.active_listings ?? 0} />
        <StatCard label="Hot Leads" value={stats?.hot_leads ?? 0} color="text-orange-600" />
        <StatCard label="Tours Scheduled" value={stats?.tours_scheduled ?? 0} color="text-green-600" />
        <StatCard label="Broker Emails Sent" value={stats?.broker_emails_sent ?? 0} color="text-blue-600" />
        <StatCard label="Passed" value={stats?.passed ?? 0} color="text-gray-400" />
        <div className="col-span-2 sm:col-span-3">
          <Card className="p-4">
            <div className="text-sm text-gray-500">Last Scrape</div>
            <div className="text-lg font-semibold">{stats ? formatTimeAgo(stats.last_scrape) : "—"}</div>
          </Card>
        </div>
      </div>
    </div>
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
