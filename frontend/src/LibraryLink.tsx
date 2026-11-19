import { useEffect, useState } from "react";
import { setLibraryName } from "./names";

// When a Librarian Core runs this workspace for one library, it passes that
// library's name and its own loopback address. Standalone servers return nulls
// (or no route at all), and this renders nothing.
type Context = {
  library_name: string | null;
  librarian_url: string | null;
  can_close?: boolean;
};

export function LibraryLink({ onContext }: { onContext?: (c: Context) => void }) {
  const [context, setContext] = useState<Context | null>(null);
  const [closed, setClosed] = useState<"" | "closing" | "closed" | string>("");
  useEffect(() => {
    let live = true;
    fetch("/api/workspace/context")
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!live || !data) return;
        setLibraryName(data.library_name);
        setContext(data);
        onContext?.(data);
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, []);
  if (!context?.librarian_url) return null;
  const name = context.library_name ?? "library";
  // Close (owner, 2026-11-17): this library's Geo-Grapher stops cleanly; its Librarian
  // keeps running and can open it again.
  async function close() {
    if (!window.confirm(`Close Geo-Grapher for ${name}? The library keeps running and can open it again.`)) return;
    setClosed("closing");
    try {
      const reply = await fetch("/api/workspace/close", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      });
      setClosed(reply.ok ? "closed" : `Not closed (HTTP ${reply.status})`);
    } catch {
      setClosed("closed"); // the server may stop before the reply is read
    }
  }
  return (
    <>
      <a
        className="library-link"
        href={context.librarian_url}
        title={`Return to the Librarian for ${name}`}
        aria-label={`Back to Librarian: ${name}`}
      >
        <span aria-hidden="true">← </span>Librarian
        <span className="library-link-name"> · {name}</span>
      </a>
      {context.can_close && (
        <button
          className="library-close"
          onClick={() => void close()}
          disabled={closed === "closing" || closed === "closed"}
          title={`Close Geo-Grapher for ${name}`}
        >
          {closed === "closing" ? "Closing…" : "Close"}
        </button>
      )}
      {closed === "closed" && (
        <div className="closed-overlay" role="alertdialog" aria-label="Geo-Grapher closed">
          <div>
            <h2>Geo-Grapher is closed</h2>
            <p>
              {name}'s graphs are no longer served. The library itself is still running; open
              Geo-Grapher again from the Librarian.
            </p>
            <a href={context.librarian_url}>Back to the Librarian</a>
          </div>
        </div>
      )}
      {closed && closed !== "closing" && closed !== "closed" && (
        <span role="status" className="library-close-error">{closed}</span>
      )}
    </>
  );
}
