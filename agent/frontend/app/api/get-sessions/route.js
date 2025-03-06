// app/api/get-sessions/route.js
export async function GET(request) {
    try {
      const res = await fetch("http://localhost:8000/api/get-sessions");
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
  