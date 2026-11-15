import { useEffect, useState } from "react";

// When a Librarian Core runs this workspace for one library, it passes that
// library's name and its own loopback address. Standalone servers return nulls
// (or no route at all), and this renders nothing.
type Context = { library_name: string | null; librarian_url: string | null };

export function LibraryLink() {
  const [context, setContext] = useState<Context | null>(null);
  useEffect(() => {
    let live = true;
    fetch("/api/workspace/context")
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => live && setContext(data))
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, []);
  if (!context?.librarian_url) return null;
  const name = context.library_name ?? "library";
  return (
    <a
      className="library-link"
      href={context.librarian_url}
      title={`Return to the Librarian for ${name}`}
      aria-label={`Back to Librarian: ${name}`}
    >
      ← Librarian · {name}
    </a>
  );
}
