def build_alignments_html() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Alignment tester</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 760px; margin: 2rem auto; padding: 0 1rem; }
    label { display: block; margin-top: 1rem; font-weight: 600; }
    textarea, input { box-sizing: border-box; width: 100%; margin-top: 0.25rem; }
    textarea { min-height: 7rem; }
    button { margin-top: 1rem; padding: 0.5rem 0.8rem; }
    pre { background: #f5f5f5; overflow: auto; padding: 1rem; white-space: pre-wrap; }
  </style>
</head>
<body>
  <h1>Alignment tester</h1>
  <p>Upload a 16-bit PCM WAV file and provide the transcript to test <code>POST /alignments</code>.</p>

  <form id="alignment-form">
    <label for="audio">WAV file</label>
    <input id="audio" name="audio" type="file" accept="audio/wav,.wav" required>

    <label for="text">Transcript</label>
    <textarea id="text" name="text" required placeholder="Hello world"></textarea>

    <label for="grammar">Grammar hints (optional, separated by |)</label>
    <input id="grammar" name="grammar" type="text" placeholder="Hello world|Hello there">

    <button type="submit">Align</button>
  </form>

  <h2>Result</h2>
  <pre id="result">Submit a WAV file to see the JSON response.</pre>

  <script>
    const form = document.getElementById("alignment-form");
    const result = document.getElementById("result");

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      result.textContent = "Aligning...";

      const data = new FormData(form);
      if (!data.get("grammar")) {
        data.delete("grammar");
      }

      try {
        const response = await fetch("/alignments", {
          method: "POST",
          body: data,
        });
        const contentType = response.headers.get("content-type") || "";
        const payload = contentType.includes("application/json")
          ? await response.json()
          : await response.text();
        result.textContent = JSON.stringify(payload, null, 2);
      } catch (error) {
        result.textContent = String(error);
      }
    });
  </script>
</body>
</html>
"""
