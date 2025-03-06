
export async function GET(request) {
  const { searchParams } = new URL(request.url);
  const issue_report = searchParams.get("issue_report") || "I am hearing knocking sound while turning at low speeds";
  try {
    const res = await fetch(`http://localhost:8000/api/run-agent?issue_report=${encodeURIComponent(issue_report)}`);
    const data = await res.json();
    return new Response(JSON.stringify(data), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  } catch (error) {
    return new Response(JSON.stringify({ error: error.message }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }
}
