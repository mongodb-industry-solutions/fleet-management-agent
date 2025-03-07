// THIS FUNCTION IS NOT USED
export async function GET(request) {
    const { searchParams } = new URL(request.url);
    const issue_report = searchParams.get("issue_report") || "My vehicle’s fuel consumption has increased significantly over the past week. What might be wrong with the engine or fuel system?";
    try {
      const res = await fetch(`http://localhost:8000/api/run-agent-sse?issue_report=${encodeURIComponent(issue_report)}`);
      const data = await res.text(); // Streaming response is text
      return new Response(data, {
        status: 200,
        headers: { "Content-Type": "text/event-stream" },
      });
    } catch (error) {
      return new Response(JSON.stringify({ error: error.message }), {
        status: 500,
        headers: { "Content-Type": "application/json" },
      });
    }
  }
  