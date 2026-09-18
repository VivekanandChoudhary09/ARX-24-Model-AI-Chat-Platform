"use client";

import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api } from "@/lib/api";
import type { DocumentRecord } from "@/lib/types";

export function DocumentAdminTable({
  documents,
  onChange,
}: {
  documents: DocumentRecord[];
  onChange: () => void;
}): React.ReactElement {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Filename</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Chunks</TableHead>
          <TableHead>Excluded</TableHead>
          <TableHead></TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {documents.map((doc) => (
          <TableRow key={doc.id}>
            <TableCell>{doc.filename}</TableCell>
            <TableCell>{doc.status}</TableCell>
            <TableCell>{doc.chunk_count}</TableCell>
            <TableCell>
              <Switch
                checked={doc.excluded}
                onCheckedChange={async (value) => {
                  await api.patchDocument(doc.id, { excluded: value });
                  onChange();
                }}
              />
            </TableCell>
            <TableCell>
              <Button
                variant="destructive"
                size="sm"
                onClick={async () => {
                  await api.deleteDocument(doc.id);
                  onChange();
                }}
              >
                Delete
              </Button>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
