"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { Badge } from "@/components/ui/badge";

export function HealthBadge(): React.ReactElement {
  const [mongo, setMongo] = useState<boolean | null>(null);

  useEffect(() => {
    api
      .health()
      .then((status) => setMongo(status.mongo))
      .catch(() => setMongo(false));
  }, []);

  const label = mongo == null ? "checking" : mongo ? "mongo ok" : "mongo down";
  return (
    <Badge className={mongo ? "border-primary/40 text-primary" : "border-destructive text-destructive"}>
      {label}
    </Badge>
  );
}
