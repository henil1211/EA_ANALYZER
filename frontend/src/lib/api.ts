const API_BASE = process.env.NEXT_PUBLIC_API_URL || "/api";

export async function analyzeReport(file: File) {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_BASE}/analyze`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Analysis failed" }));
    throw new Error(err.detail || "Analysis failed");
  }

  return res.json();
}

export async function analyzeQuick(file: File) {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_BASE}/analyze-quick`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Quick analysis failed" }));
    throw new Error(err.detail || "Quick analysis failed");
  }

  return res.json();
}
