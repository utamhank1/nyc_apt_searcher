"use client";

import { useEffect, useState } from "react";
import { api, hasApiKey } from "@/lib/api";
import { SavedSearch, ALL_BOROUGHS, ALL_AMENITIES, NEIGHBORHOODS_BY_BOROUGH } from "@/lib/types";
import { NavBar } from "@/components/nav-bar";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Slider } from "@/components/ui/slider";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";

export default function SearchesPage() {
  const [searches, setSearches] = useState<SavedSearch[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingSearch, setEditingSearch] = useState<SavedSearch | null>(null);
  const [showNew, setShowNew] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    if (typeof window !== "undefined" && !hasApiKey()) { window.location.href = "/"; return; }
    fetchSearches();
  }, []);

  const fetchSearches = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.get<{ items: SavedSearch[] }>("/api/v1/searches");
      setSearches(data.items);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    }
    setLoading(false);
  };

  const activeCount = searches.filter((s) => s.is_active).length;

  const activate = async (id: number) => {
    const res = await api.post<{ ok?: boolean; error?: string }>(`/api/v1/searches/${id}/activate`);
    if (res.error) { alert(res.error); return; }
    fetchSearches();
  };

  const deactivate = async (id: number) => {
    await api.post(`/api/v1/searches/${id}/deactivate`);
    fetchSearches();
  };

  const deleteSearch = async (id: number) => {
    if (!confirm("Delete this search?")) return;
    const res = await api.get<{ ok?: boolean; error?: string }>(`/api/v1/searches/${id}`);
    await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/v1/searches/${id}`, {
      method: "DELETE",
      headers: { "X-API-Key": localStorage.getItem("apt_api_key") || "" },
    });
    fetchSearches();
  };

  const saveSearch = async (search: SavedSearch) => {
    if (search.id) {
      await api.put(`/api/v1/searches/${search.id}`, search);
    } else {
      await api.post("/api/v1/searches", search);
    }
    setEditingSearch(null);
    setShowNew(false);
    fetchSearches();
  };

  if (!mounted) return null;

  return (
    <>
      <NavBar />
      <main className="max-w-3xl mx-auto px-4 py-6">
        <div className="flex items-center justify-between mb-2">
          <h1 className="text-2xl font-bold">Saved Searches</h1>
          <Button onClick={() => { setShowNew(true); setEditingSearch(null); }}>New Search</Button>
        </div>
        <p className="text-sm text-gray-500 mb-6">{activeCount}/3 active searches</p>

        {error && (
          <Card className="p-6 mb-4 border-yellow-200 bg-yellow-50">
            <p className="text-yellow-800">{error}</p>
            <Button variant="outline" size="sm" className="mt-2" onClick={fetchSearches}>Retry</Button>
          </Card>
        )}

        <div className="space-y-3">
          {searches.map((s) => (
            <Card key={s.id} className="p-4">
              <div className="flex items-center gap-3">
                {/* Status indicator */}
                <div className={`w-3 h-3 rounded-full flex-shrink-0 ${
                  s.is_active
                    ? "bg-green-500 shadow-[0_0_8px_2px_rgba(34,197,94,0.5)]"
                    : "bg-gray-300"
                }`} />

                {/* Search info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h3 className="font-semibold">{s.name}</h3>
                    <Badge variant={s.is_active ? "default" : "secondary"} className="text-xs">
                      {s.is_active ? "Active" : "Inactive"}
                    </Badge>
                  </div>
                  <div className="text-sm text-gray-500 mt-1">
                    {s.boroughs?.join(", ")} · ${s.min_price}-${s.max_price}/mo · {s.min_beds}+ BR
                    {s.neighborhoods?.length ? ` · ${s.neighborhoods.length} neighborhoods` : ""}
                  </div>
                </div>

                {/* Actions */}
                <div className="flex gap-2 flex-shrink-0">
                  {s.is_active ? (
                    <Button variant="outline" size="sm" onClick={() => deactivate(s.id)}>Deactivate</Button>
                  ) : (
                    <>
                      <Button variant="outline" size="sm" onClick={() => setEditingSearch({ ...s })}>Edit</Button>
                      <Button
                        size="sm"
                        onClick={() => activate(s.id)}
                        disabled={activeCount >= 3}
                        title={activeCount >= 3 ? "Max 3 active searches" : ""}
                      >
                        Activate
                      </Button>
                      <Button variant="ghost" size="sm" className="text-red-500" onClick={() => deleteSearch(s.id)}>Delete</Button>
                    </>
                  )}
                </div>
              </div>
            </Card>
          ))}
          {!loading && searches.length === 0 && (
            <Card className="p-8 text-center text-gray-500">
              No saved searches yet. Click &quot;New Search&quot; to create one.
            </Card>
          )}
        </div>

        {/* Edit / New Search Dialog */}
        <SearchFormDialog
          search={editingSearch || (showNew ? makeBlank() : null)}
          open={!!editingSearch || showNew}
          onClose={() => { setEditingSearch(null); setShowNew(false); }}
          onSave={saveSearch}
        />
      </main>
    </>
  );
}

function makeBlank(): SavedSearch {
  return {
    id: 0,
    name: "",
    is_active: false,
    boroughs: ["Manhattan", "Brooklyn"],
    neighborhoods: [],
    max_price: 3500,
    min_price: 0,
    min_beds: 1,
    min_baths: 1,
    must_have_amenities: [],
    preferred_amenities: [],
    work_address: "",
    lead_score_threshold: 70,
    sources_enabled: { streeteasy: true, zillow: true },
    move_in_mode: "",
    move_in_date: "",
    move_in_range_start: "",
    move_in_range_end: "",
    move_in_only: false,
    created_at: null,
    updated_at: null,
  };
}

function SearchFormDialog({ search, open, onClose, onSave }: {
  search: SavedSearch | null;
  open: boolean;
  onClose: () => void;
  onSave: (s: SavedSearch) => void;
}) {
  const [form, setForm] = useState<SavedSearch>(search || makeBlank());

  useEffect(() => {
    if (search) setForm(search);
  }, [search]);

  if (!open || !search) return null;

  const isNew = !form.id;

  const availableNeighborhoods = form.boroughs.flatMap((b) => NEIGHBORHOODS_BY_BOROUGH[b] || []).filter((n) => !form.neighborhoods.includes(n));

  const toggleNeighborhood = (n: string) => {
    if (form.neighborhoods.includes(n)) {
      setForm({ ...form, neighborhoods: form.neighborhoods.filter((x) => x !== n) });
    } else {
      setForm({ ...form, neighborhoods: [...form.neighborhoods, n] });
    }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isNew ? "New Search" : `Edit: ${form.name}`}</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <div>
            <Label>Search Name</Label>
            <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="e.g. Brooklyn - Williamsburg" />
          </div>

          <div>
            <Label>Boroughs</Label>
            <div className="flex gap-2 mt-1 flex-wrap">
              {ALL_BOROUGHS.map((b) => (
                <button key={b} onClick={() => setForm({ ...form, boroughs: form.boroughs.includes(b) ? form.boroughs.filter((x) => x !== b) : [...form.boroughs, b] })}
                  className={`px-2 py-1 rounded text-xs border ${form.boroughs.includes(b) ? "bg-gray-900 text-white border-gray-900" : "bg-white text-gray-600 border-gray-200"}`}>
                  {form.boroughs.includes(b) ? "✓ " : ""}{b}
                </button>
              ))}
            </div>
          </div>

          <div>
            <Label>Neighborhoods</Label>
            {form.boroughs.length === 0 && <p className="text-xs text-gray-400 mt-1">Select boroughs first</p>}
            <div className="flex gap-1 mt-1 flex-wrap max-h-40 overflow-y-auto">
              {form.boroughs.flatMap((b) => (NEIGHBORHOODS_BY_BOROUGH[b] || []).map((n) => {
                const selected = form.neighborhoods.includes(n);
                return (
                  <button key={n} onClick={() => toggleNeighborhood(n)}
                    className={`px-2 py-1 rounded text-xs border ${selected ? "bg-gray-900 text-white border-gray-900" : "bg-white text-gray-600 border-gray-200 hover:border-gray-400"}`}>
                    {selected ? "✓ " : ""}{n}
                  </button>
                );
              }))}
            </div>
          </div>

          <Separator />

          <div className="grid grid-cols-2 gap-3">
            <div><Label className="text-sm">Min Price ($)</Label><Input type="number" value={form.min_price} onChange={(e) => setForm({ ...form, min_price: parseInt(e.target.value) || 0 })} /></div>
            <div><Label className="text-sm">Max Price ($)</Label><Input type="number" value={form.max_price} onChange={(e) => setForm({ ...form, max_price: parseInt(e.target.value) || 0 })} /></div>
            <div><Label className="text-sm">Min Beds</Label><Input type="number" min={0} value={form.min_beds} onChange={(e) => setForm({ ...form, min_beds: parseInt(e.target.value) || 0 })} /></div>
            <div><Label className="text-sm">Min Baths</Label><Input type="number" min={0} step={0.5} value={form.min_baths} onChange={(e) => setForm({ ...form, min_baths: parseFloat(e.target.value) || 0 })} /></div>
          </div>

          <Separator />

          <div>
            <Label>Amenities</Label>
            <p className="text-xs text-gray-500 mb-1">Click: none → nice-to-have → must-have → none</p>
            <div className="grid grid-cols-2 gap-1">
              {ALL_AMENITIES.map((a) => {
                const isMust = form.must_have_amenities.includes(a);
                const isPref = form.preferred_amenities.includes(a);
                return (
                  <button key={a} onClick={() => {
                    if (!isPref && !isMust) setForm({ ...form, preferred_amenities: [...form.preferred_amenities, a] });
                    else if (isPref) setForm({ ...form, preferred_amenities: form.preferred_amenities.filter((x) => x !== a), must_have_amenities: [...form.must_have_amenities, a] });
                    else setForm({ ...form, must_have_amenities: form.must_have_amenities.filter((x) => x !== a) });
                  }}
                    className={`px-2 py-1 rounded text-xs text-left border ${isMust ? "bg-red-50 text-red-700 border-red-300" : isPref ? "bg-blue-50 text-blue-700 border-blue-300" : "bg-white text-gray-600 border-gray-200"}`}>
                    {isMust ? "MUST: " : isPref ? "✓ " : ""}{a}
                  </button>
                );
              })}
            </div>
          </div>

          <Separator />

          <div>
            <Label>Sources</Label>
            <div className="space-y-2 mt-1">
              {["streeteasy", "zillow"].map((src) => (
                <div key={src} className="flex items-center justify-between">
                  <span className="text-sm">{src === "streeteasy" ? "StreetEasy" : "Zillow"}</span>
                  <Switch checked={form.sources_enabled[src] ?? true} onCheckedChange={(c) => setForm({ ...form, sources_enabled: { ...form.sources_enabled, [src]: c } })} />
                </div>
              ))}
            </div>
          </div>

          <div>
            <Label>Score Threshold: {form.lead_score_threshold}</Label>
            <Slider value={[form.lead_score_threshold]} onValueChange={(v) => setForm({ ...form, lead_score_threshold: Array.isArray(v) ? v[0] : v })} min={0} max={100} step={5} />
          </div>

          <div>
            <Label>Work Address</Label>
            <Input value={form.work_address} onChange={(e) => setForm({ ...form, work_address: e.target.value })} placeholder="e.g. 123 Broadway, New York, NY" className="text-sm" />
          </div>

          <Separator />

          <div>
            <Label>Move-In Date</Label>
            <div className="flex gap-2 mt-1 flex-wrap">
              {[
                { value: "", label: "Any" },
                { value: "immediately", label: "Immediately" },
                { value: "date", label: "By Date" },
                { value: "range", label: "Date Range" },
              ].map((opt) => (
                <button key={opt.value} onClick={() => setForm({ ...form, move_in_mode: opt.value })}
                  className={`px-2 py-1 rounded text-xs border ${form.move_in_mode === opt.value ? "bg-gray-900 text-white border-gray-900" : "bg-white text-gray-600 border-gray-200"}`}>
                  {form.move_in_mode === opt.value ? "✓ " : ""}{opt.label}
                </button>
              ))}
            </div>
            {form.move_in_mode === "date" && (
              <div className="mt-2">
                <Label className="text-xs">Available by</Label>
                <Input type="date" value={form.move_in_date} onChange={(e) => setForm({ ...form, move_in_date: e.target.value })} className="w-48 text-sm" />
              </div>
            )}
            {form.move_in_mode === "range" && (
              <div className="grid grid-cols-2 gap-3 mt-2">
                <div><Label className="text-xs">From</Label><Input type="date" value={form.move_in_range_start} onChange={(e) => setForm({ ...form, move_in_range_start: e.target.value })} className="text-sm" /></div>
                <div><Label className="text-xs">To</Label><Input type="date" value={form.move_in_range_end} onChange={(e) => setForm({ ...form, move_in_range_end: e.target.value })} className="text-sm" /></div>
              </div>
            )}
            {form.move_in_mode && (
              <div className="flex items-center gap-2 mt-2">
                <Switch checked={form.move_in_only} onCheckedChange={(c) => setForm({ ...form, move_in_only: c })} />
                <span className="text-xs">Only show matching dates</span>
                {form.move_in_only && <span className="text-xs text-yellow-600">⚠️ May limit results</span>}
              </div>
            )}
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={() => onSave(form)} disabled={!form.name.trim()}>
            {isNew ? "Create Search" : "Save Changes"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
