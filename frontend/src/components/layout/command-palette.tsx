"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Command } from "cmdk";
import { Search, Users, Building2, TrendingUp, User, Loader2 } from "lucide-react";
import {
  Dialog,
  DialogContent,
} from "@/components/ui/dialog";

type SearchResult = {
  id: string;
  type: "lead" | "contact" | "company" | "deal";
  title: string;
  subtitle: string;
  href: string;
};

const typeIcons = {
  lead: User,
  contact: Users,
  company: Building2,
  deal: TrendingUp,
};

const typeLabels = {
  lead: "Leads",
  contact: "Contatos",
  company: "Empresas",
  deal: "Negócios",
};

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function CommandPalette({ open, onOpenChange }: Props) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);

  const search = useCallback(async (q: string) => {
    if (!q || q.length < 2) {
      setResults([]);
      return;
    }
    setLoading(true);
    try {
      const res = await fetch(`/api/v1/search?q=${encodeURIComponent(q)}`);
      const data = await res.json();
      setResults(data.results ?? []);
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timeout = setTimeout(() => search(query), 300);
    return () => clearTimeout(timeout);
  }, [query, search]);

  const handleSelect = (result: SearchResult) => {
    router.push(result.href);
    onOpenChange(false);
    setQuery("");
    setResults([]);
  };

  // Group results by type
  const grouped = results.reduce<Record<string, SearchResult[]>>((acc, r) => {
    if (!acc[r.type]) acc[r.type] = [];
    acc[r.type].push(r);
    return acc;
  }, {});

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="p-0 overflow-hidden max-w-lg">
        <Command className="rounded-lg" shouldFilter={false}>
          <div className="flex items-center border-b px-3">
            {loading ? (
              <Loader2 className="h-4 w-4 text-muted-foreground animate-spin mr-2 shrink-0" />
            ) : (
              <Search className="h-4 w-4 text-muted-foreground mr-2 shrink-0" />
            )}
            <Command.Input
              value={query}
              onValueChange={setQuery}
              placeholder="Buscar leads, contatos, empresas, negócios..."
              className="flex h-12 w-full bg-transparent py-3 text-sm outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed disabled:opacity-50"
            />
          </div>

          <Command.List className="max-h-96 overflow-y-auto p-2">
            {!query && (
              <Command.Empty className="py-8 text-center text-sm text-muted-foreground">
                Digite para buscar...
              </Command.Empty>
            )}
            {query && !loading && results.length === 0 && (
              <Command.Empty className="py-8 text-center text-sm text-muted-foreground">
                Nenhum resultado para &ldquo;{query}&rdquo;
              </Command.Empty>
            )}

            {Object.entries(grouped).map(([type, items]) => {
              const Icon = typeIcons[type as keyof typeof typeIcons] ?? User;
              const label = typeLabels[type as keyof typeof typeLabels] ?? type;

              return (
                <Command.Group key={type} heading={label} className="[&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-xs [&_[cmdk-group-heading]]:font-medium [&_[cmdk-group-heading]]:text-muted-foreground">
                  {items.map((result) => (
                    <Command.Item
                      key={result.id}
                      value={result.id}
                      onSelect={() => handleSelect(result)}
                      className="flex items-center gap-3 rounded-md px-2 py-2 text-sm cursor-pointer hover:bg-accent aria-selected:bg-accent"
                    >
                      <div className="flex h-8 w-8 items-center justify-center rounded-md border bg-background shrink-0">
                        <Icon className="h-4 w-4 text-muted-foreground" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="font-medium truncate">{result.title}</p>
                        {result.subtitle && (
                          <p className="text-xs text-muted-foreground truncate">{result.subtitle}</p>
                        )}
                      </div>
                    </Command.Item>
                  ))}
                </Command.Group>
              );
            })}
          </Command.List>
        </Command>
      </DialogContent>
    </Dialog>
  );
}
