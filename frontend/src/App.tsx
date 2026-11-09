import { useQuery } from "@tanstack/react-query";
import { api } from "./api/client";

export default function App() {
  const { data, error, isLoading } = useQuery({
    queryKey: ["health"],
    queryFn: () => api<{ status: string }>("/health"),
  });

  return (
    <main style={{ padding: 24 }}>
      <h1>PR-Review-Assistant</h1>
      {isLoading && <p>Checking backend...</p>}
      {error && <p>Backend error: {(error as Error).message}</p>}
      {data && <p>Backend status: {data.status}</p>}
    </main>
  );
}