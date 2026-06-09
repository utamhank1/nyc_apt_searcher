"use client";

import { useEffect, useState } from "react";
import { hasApiKey, setApiKey } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { NavBar } from "@/components/nav-bar";
import { LeadsPage } from "@/components/leads-page";

export default function Home() {
  const [authenticated, setAuthenticated] = useState(false);
  const [apiKey, setApiKeyInput] = useState("");

  useEffect(() => {
    setAuthenticated(hasApiKey());
  }, []);

  if (!authenticated) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Card className="p-8 w-full max-w-md">
          <h1 className="text-2xl font-bold mb-2">NYC Apt Searcher</h1>
          <p className="text-gray-500 mb-6">Enter your API key to access the dashboard</p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (apiKey.trim()) {
                setApiKey(apiKey.trim());
                setAuthenticated(true);
              }
            }}
          >
            <Input
              type="password"
              placeholder="API Key"
              value={apiKey}
              onChange={(e) => setApiKeyInput(e.target.value)}
              className="mb-4"
            />
            <Button type="submit" className="w-full">
              Connect
            </Button>
          </form>
        </Card>
      </div>
    );
  }

  return (
    <>
      <NavBar />
      <main className="max-w-7xl mx-auto px-4 py-6">
        <LeadsPage />
      </main>
    </>
  );
}
