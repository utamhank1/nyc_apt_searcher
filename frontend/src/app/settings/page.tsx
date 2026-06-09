"use client";

import { useEffect, useState } from "react";
import { api, hasApiKey } from "@/lib/api";
import { SearchConfig, ALL_BOROUGHS, ALL_AMENITIES } from "@/lib/types";
import { NavBar } from "@/components/nav-bar";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Slider } from "@/components/ui/slider";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";

const DEFAULT_CONFIG: SearchConfig = {
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
  search_partner_emails: [],
  user_name: "",
  user_email: "",
  user_phone: "",
  use_custom_email_template: false,
  custom_email_subject: "Inquiry about {{address}} - {{source}}",
  custom_email_body: "Hi {{broker_name}},\n\nI came across your listing at {{address}} ({{beds}}BR/{{baths}}BA, {{price}}/mo) and I'm very interested in scheduling a viewing.\n\nCould you share available times this week?\n\nBest regards,\n{{your_name}}\n{{your_phone}}",
};

export default function SettingsPage() {
  const [config, setConfig] = useState<SearchConfig>(DEFAULT_CONFIG);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [neighborhoodInput, setNeighborhoodInput] = useState("");
  const [partnerInput, setPartnerInput] = useState("");

  useEffect(() => {
    setMounted(true);
    if (typeof window !== "undefined" && !hasApiKey()) {
      window.location.href = "/";
      return;
    }
    fetchConfig();
  }, []);

  const fetchConfig = async () => {
    setError(null);
    try {
      const data = await api.get<SearchConfig>("/api/v1/config");
      setConfig(data);
      setLoaded(true);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to connect";
      setError(msg);
      setLoaded(true);
    }
  };

  const save = async () => {
    setSaving(true);
    try {
      await api.put("/api/v1/config", config);
      setSaved(true);
      setError(null);
      setTimeout(() => setSaved(false), 3000);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to save";
      setError(msg);
    }
    setSaving(false);
  };

  if (!mounted) return null;

  const toggleBorough = (b: string) => {
    setConfig({
      ...config,
      boroughs: config.boroughs.includes(b)
        ? config.boroughs.filter((x) => x !== b)
        : [...config.boroughs, b],
    });
  };

  const toggleAmenity = (a: string, type: "must" | "preferred") => {
    if (type === "must") {
      const has = config.must_have_amenities.includes(a);
      setConfig({
        ...config,
        must_have_amenities: has
          ? config.must_have_amenities.filter((x) => x !== a)
          : [...config.must_have_amenities, a],
        preferred_amenities: config.preferred_amenities.filter((x) => x !== a),
      });
    } else {
      const has = config.preferred_amenities.includes(a);
      setConfig({
        ...config,
        preferred_amenities: has
          ? config.preferred_amenities.filter((x) => x !== a)
          : [...config.preferred_amenities, a],
        must_have_amenities: config.must_have_amenities.filter((x) => x !== a),
      });
    }
  };

  const addNeighborhood = () => {
    const n = neighborhoodInput.trim();
    if (n && !config.neighborhoods.includes(n)) {
      setConfig({ ...config, neighborhoods: [...config.neighborhoods, n] });
      setNeighborhoodInput("");
    }
  };

  const removeNeighborhood = (n: string) => {
    setConfig({ ...config, neighborhoods: config.neighborhoods.filter((x) => x !== n) });
  };

  const addPartner = () => {
    const e = partnerInput.trim();
    if (e && !config.search_partner_emails.includes(e) && config.search_partner_emails.length < 3) {
      setConfig({ ...config, search_partner_emails: [...config.search_partner_emails, e] });
      setPartnerInput("");
    }
  };

  const removePartner = (e: string) => {
    setConfig({ ...config, search_partner_emails: config.search_partner_emails.filter((x) => x !== e) });
  };

  return (
    <>
      <NavBar />
      <main className="max-w-3xl mx-auto px-4 py-6">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold">Settings</h1>
          <Button onClick={save} disabled={saving}>
            {saving ? "Saving..." : saved ? "Saved!" : "Save Changes"}
          </Button>
        </div>

        {error && (
          <Card className="p-6 mb-4 border-yellow-200 bg-yellow-50">
            <p className="font-medium text-yellow-800">Backend not connected</p>
            <p className="text-sm text-yellow-600 mt-1">{error}</p>
            <p className="text-sm text-yellow-600 mt-1">Showing default settings — changes won&apos;t save until the backend is running.</p>
            <Button variant="outline" size="sm" className="mt-3" onClick={fetchConfig}>
              Retry Connection
            </Button>
          </Card>
        )}

        <Tabs defaultValue="filters">
          <TabsList className="mb-4">
            <TabsTrigger value="filters">Search Filters</TabsTrigger>
            <TabsTrigger value="connections">Connections & Partners</TabsTrigger>
            <TabsTrigger value="template">Email Template</TabsTrigger>
          </TabsList>

          <TabsContent value="filters">
            <Card className="p-6 space-y-6">
              <div>
                <Label className="text-base font-semibold">Boroughs</Label>
                <div className="flex gap-2 mt-2 flex-wrap">
                  {ALL_BOROUGHS.map((b) => (
                    <button
                      key={b}
                      onClick={() => toggleBorough(b)}
                      className={`px-3 py-1.5 rounded-md text-sm border transition-colors ${
                        config.boroughs.includes(b)
                          ? "bg-gray-900 text-white border-gray-900"
                          : "bg-white text-gray-600 border-gray-200 hover:border-gray-400"
                      }`}
                    >
                      {config.boroughs.includes(b) ? "✓ " : ""}{b}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <Label className="text-base font-semibold">Neighborhoods</Label>
                <div className="flex gap-2 mt-2 flex-wrap">
                  {config.neighborhoods.map((n) => (
                    <Badge key={n} variant="secondary" className="cursor-pointer" onClick={() => removeNeighborhood(n)}>
                      {n} ✕
                    </Badge>
                  ))}
                </div>
                <div className="flex gap-2 mt-2">
                  <Input
                    placeholder="Add neighborhood..."
                    value={neighborhoodInput}
                    onChange={(e) => setNeighborhoodInput(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addNeighborhood())}
                  />
                  <Button variant="outline" onClick={addNeighborhood}>Add</Button>
                </div>
              </div>

              <Separator />

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>Min Price ($)</Label>
                  <Input type="number" value={config.min_price} onChange={(e) => setConfig({ ...config, min_price: parseInt(e.target.value) || 0 })} />
                </div>
                <div>
                  <Label>Max Price ($)</Label>
                  <Input type="number" value={config.max_price} onChange={(e) => setConfig({ ...config, max_price: parseInt(e.target.value) || 0 })} />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>Min Bedrooms</Label>
                  <Input type="number" min={0} value={config.min_beds} onChange={(e) => setConfig({ ...config, min_beds: parseInt(e.target.value) || 0 })} />
                </div>
                <div>
                  <Label>Min Bathrooms</Label>
                  <Input type="number" min={0} step={0.5} value={config.min_baths} onChange={(e) => setConfig({ ...config, min_baths: parseFloat(e.target.value) || 0 })} />
                </div>
              </div>

              <Separator />

              <div>
                <Label className="text-base font-semibold">Amenities</Label>
                <p className="text-sm text-gray-500 mb-2">Click once for &quot;nice to have&quot;, click again for &quot;must have&quot; (required)</p>
                <div className="grid grid-cols-2 gap-2">
                  {ALL_AMENITIES.map((a) => {
                    const isMust = config.must_have_amenities.includes(a);
                    const isPref = config.preferred_amenities.includes(a);
                    return (
                      <button
                        key={a}
                        onClick={() => {
                          if (!isPref && !isMust) toggleAmenity(a, "preferred");
                          else if (isPref) toggleAmenity(a, "must");
                          else setConfig({ ...config, must_have_amenities: config.must_have_amenities.filter(x => x !== a) });
                        }}
                        className={`px-3 py-2 rounded-md text-sm text-left border transition-colors ${
                          isMust ? "bg-red-50 text-red-700 border-red-300 font-medium"
                          : isPref ? "bg-blue-50 text-blue-700 border-blue-300"
                          : "bg-white text-gray-600 border-gray-200 hover:border-gray-400"
                        }`}
                      >
                        {isMust ? "MUST: " : isPref ? "✓ " : ""}{a}
                      </button>
                    );
                  })}
                </div>
              </div>

              <Separator />

              <div>
                <Label className="text-base font-semibold">Listing Sources</Label>
                <div className="space-y-3 mt-2">
                  {["streeteasy", "zillow"].map((source) => (
                    <div key={source} className="flex items-center justify-between">
                      <span className="font-medium">{source === "streeteasy" ? "StreetEasy" : "Zillow"}</span>
                      <Switch
                        checked={config.sources_enabled[source] ?? true}
                        onCheckedChange={(checked) => setConfig({ ...config, sources_enabled: { ...config.sources_enabled, [source]: checked } })}
                      />
                    </div>
                  ))}
                </div>
              </div>

              <Separator />

              <div>
                <Label className="text-base font-semibold">Lead Score Threshold: {config.lead_score_threshold}</Label>
                <p className="text-sm text-gray-500 mb-2">Only alert for listings scoring at or above this value</p>
                <Slider
                  value={[config.lead_score_threshold]}
                  onValueChange={(val) => setConfig({ ...config, lead_score_threshold: Array.isArray(val) ? val[0] : val })}
                  min={0} max={100} step={5}
                />
              </div>

              <div>
                <Label className="text-base font-semibold">Work Address (for commute calculation)</Label>
                <Input placeholder="e.g. 123 Broadway, New York, NY" value={config.work_address} onChange={(e) => setConfig({ ...config, work_address: e.target.value })} className="mt-2" />
              </div>
            </Card>
          </TabsContent>

          <TabsContent value="connections">
            <Card className="p-6 space-y-6">
              <div>
                <Label className="text-base font-semibold">Your Info</Label>
                <div className="grid grid-cols-1 gap-3 mt-2">
                  <div><Label className="text-sm">Name</Label><Input value={config.user_name} onChange={(e) => setConfig({ ...config, user_name: e.target.value })} placeholder="Your full name" /></div>
                  <div><Label className="text-sm">Email</Label><Input type="email" value={config.user_email} onChange={(e) => setConfig({ ...config, user_email: e.target.value })} placeholder="you@email.com" /></div>
                  <div><Label className="text-sm">Phone</Label><Input value={config.user_phone} onChange={(e) => setConfig({ ...config, user_phone: e.target.value })} placeholder="(555) 123-4567" /></div>
                </div>
              </div>

              <Separator />

              <div>
                <Label className="text-base font-semibold">Search Partners (up to 3)</Label>
                <p className="text-sm text-gray-500 mb-2">These people are CC&apos;d on all broker emails</p>
                <div className="space-y-2">
                  {config.search_partner_emails.map((e) => (
                    <div key={e} className="flex items-center gap-2">
                      <Input value={e} disabled className="flex-1" />
                      <Button variant="ghost" size="sm" onClick={() => removePartner(e)}>✕</Button>
                    </div>
                  ))}
                  {config.search_partner_emails.length < 3 && (
                    <div className="flex gap-2">
                      <Input type="email" placeholder="partner@email.com" value={partnerInput} onChange={(e) => setPartnerInput(e.target.value)} onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addPartner())} />
                      <Button variant="outline" onClick={addPartner}>Add</Button>
                    </div>
                  )}
                </div>
              </div>

              <Separator />

              <div>
                <Label className="text-base font-semibold">Telegram</Label>
                <p className="text-sm text-gray-500 mb-2">Click to connect, then send /start to the bot to get your chat ID</p>
                <a href="https://t.me/your_bot" target="_blank" rel="noopener noreferrer"><Button variant="outline">Connect Telegram Bot</Button></a>
              </div>

              <Separator />

              <div>
                <Label className="text-base font-semibold">Google Calendar</Label>
                <p className="text-sm text-gray-500 mb-2">Coming soon — auto-schedule open house visits</p>
                <Button variant="outline" disabled>Connect Google Calendar (Coming Soon)</Button>
              </div>
            </Card>
          </TabsContent>

          <TabsContent value="template">
            <Card className="p-6 space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <Label className="text-base font-semibold">Custom Broker Email Template</Label>
                  <p className="text-sm text-gray-500">Customize the email sent to brokers when you reply &quot;Y&quot;</p>
                </div>
                <Switch checked={config.use_custom_email_template} onCheckedChange={(checked) => setConfig({ ...config, use_custom_email_template: checked })} />
              </div>

              {config.use_custom_email_template && (
                <>
                  <div className="bg-gray-50 rounded-md p-4">
                    <p className="text-sm font-semibold mb-2">Available Placeholders:</p>
                    <div className="grid grid-cols-2 gap-1 text-xs font-mono">
                      {[["{{address}}", "Full listing address"], ["{{price}}", "Monthly rent"], ["{{beds}}", "Bedrooms"], ["{{baths}}", "Bathrooms"], ["{{sqft}}", "Square footage"], ["{{neighborhood}}", "Neighborhood"], ["{{source}}", "StreetEasy / Zillow"], ["{{listing_url}}", "Listing link"], ["{{broker_name}}", "Broker name"], ["{{your_name}}", "Your name"], ["{{your_phone}}", "Your phone"], ["{{your_email}}", "Your email"]].map(([key, desc]) => (
                        <div key={key} className="flex gap-2"><code className="text-blue-600">{key}</code><span className="text-gray-500">→ {desc}</span></div>
                      ))}
                    </div>
                  </div>
                  <div><Label>Subject Line</Label><Input value={config.custom_email_subject} onChange={(e) => setConfig({ ...config, custom_email_subject: e.target.value })} className="font-mono text-sm" /></div>
                  <div><Label>Email Body</Label><Textarea value={config.custom_email_body} onChange={(e) => setConfig({ ...config, custom_email_body: e.target.value })} rows={12} className="font-mono text-sm" /></div>
                  <Button variant="outline" onClick={() => setConfig({ ...config, custom_email_subject: DEFAULT_CONFIG.custom_email_subject, custom_email_body: DEFAULT_CONFIG.custom_email_body })}>Reset to Default</Button>
                </>
              )}
            </Card>
          </TabsContent>
        </Tabs>
      </main>
    </>
  );
}
