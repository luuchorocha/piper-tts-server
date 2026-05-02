from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse

from src.api.docs.openapi import build_openapi_schema

_DOCS_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Piper TTS API Docs</title>
  <style>
    :root {
      color-scheme: light;
      font-family: "Iosevka Aile", "IBM Plex Sans", sans-serif;
      --bg: #f6f1e8;
      --panel: #fffdf9;
      --ink: #1d1a16;
      --muted: #6f665b;
      --line: #d9cdbd;
      --accent: #0e7c66;
      --accent-soft: #d9f1ea;
      --error: #9b2226;
      --error-soft: #f9d7d9;
      --shadow: 0 10px 30px rgba(29, 26, 22, 0.08);
      --radius: 16px;
    }

    * {
      box-sizing: border-box;
    }

    html, body {
      margin: 0;
      padding: 0;
      background: radial-gradient(circle at top left, #fff8ef 0, var(--bg) 55%);
      color: var(--ink);
    }

    body {
      min-height: 100vh;
    }

    .page {
      width: min(1240px, calc(100vw - 32px));
      margin: 0 auto;
      padding: 32px 0 56px;
    }

    .hero {
      display: grid;
      gap: 10px;
      margin-bottom: 28px;
    }

    .eyebrow {
      display: inline-flex;
      width: fit-content;
      padding: 6px 10px;
      border-radius: 999px;
      background: var(--accent-soft);
      color: var(--accent);
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }

    h1 {
      margin: 0;
      font-size: clamp(32px, 4vw, 52px);
      line-height: 0.95;
      letter-spacing: -0.04em;
    }

    .lede {
      margin: 0;
      max-width: 760px;
      color: var(--muted);
      font-size: 16px;
      line-height: 1.5;
    }

    .meta {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 6px;
      color: var(--muted);
      font-size: 13px;
    }

    .layout {
      display: grid;
      grid-template-columns: minmax(220px, 280px) minmax(0, 1fr);
      gap: 18px;
      align-items: start;
    }

    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
    }

    .sidebar {
      position: sticky;
      top: 18px;
      padding: 18px;
    }

    .sidebar h2,
    .content h2 {
      margin: 0 0 12px;
      font-size: 14px;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      color: var(--muted);
    }

    .nav {
      display: grid;
      gap: 8px;
    }

    .nav a {
      text-decoration: none;
      color: var(--ink);
      border: 1px solid transparent;
      border-radius: 12px;
      padding: 10px 12px;
      background: transparent;
      transition: background 120ms ease, border-color 120ms ease, transform 120ms ease;
    }

    .nav a:hover {
      background: #fbf6ef;
      border-color: var(--line);
      transform: translateX(2px);
    }

    .nav small {
      display: block;
      color: var(--muted);
      margin-top: 3px;
      font-size: 12px;
    }

    .content {
      display: grid;
      gap: 18px;
    }

    .endpoint {
      padding: 18px;
      display: grid;
      gap: 16px;
    }

    .endpoint-header {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      align-items: center;
    }

    .method {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 68px;
      padding: 7px 10px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 800;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }

    .method.get {
      background: #dff3ff;
      color: #005f8f;
    }

    .method.post {
      background: #e6f7df;
      color: #186b1d;
    }

    .path {
      font-family: "Iosevka", monospace;
      font-size: 18px;
      font-weight: 700;
    }

    .summary {
      color: var(--muted);
      font-size: 14px;
    }

    .grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
    }

    .card {
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 14px;
      background: #fff;
    }

    .card h3 {
      margin: 0 0 10px;
      font-size: 13px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--muted);
    }

    .field-list {
      display: grid;
      gap: 10px;
    }

    label {
      display: grid;
      gap: 6px;
      font-size: 13px;
      font-weight: 600;
    }

    input,
    textarea,
    button {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 10px 12px;
      font: inherit;
      color: var(--ink);
      background: #fff;
    }

    textarea {
      min-height: 220px;
      resize: vertical;
      font-family: "Iosevka", monospace;
      font-size: 13px;
      line-height: 1.45;
    }

    .hint {
      color: var(--muted);
      font-size: 12px;
      line-height: 1.45;
    }

    .actions {
      display: flex;
      gap: 10px;
      align-items: center;
      flex-wrap: wrap;
    }

    button {
      cursor: pointer;
      font-weight: 700;
      background: linear-gradient(135deg, #111 0, #2d2a26 100%);
      color: #fff;
      border-color: #111;
      width: auto;
      min-width: 144px;
    }

    button:disabled {
      opacity: 0.65;
      cursor: wait;
    }

    .status {
      font-size: 13px;
      color: var(--muted);
    }

    .response-meta {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      font-size: 12px;
      color: var(--muted);
      margin-bottom: 10px;
    }

    pre {
      margin: 0;
      overflow: auto;
      padding: 14px;
      border-radius: 14px;
      background: #171411;
      color: #f8f4ee;
      font-family: "Iosevka", monospace;
      font-size: 13px;
      line-height: 1.45;
      white-space: pre-wrap;
      word-break: break-word;
    }

    audio {
      width: 100%;
      margin-top: 10px;
    }

    .response-block.error pre {
      background: var(--error-soft);
      color: var(--error);
    }

    .empty {
      color: var(--muted);
      font-style: italic;
    }

    @media (max-width: 980px) {
      .layout {
        grid-template-columns: 1fr;
      }

      .sidebar {
        position: static;
      }
    }

    @media (max-width: 720px) {
      .page {
        width: min(100vw - 20px, 1240px);
        padding-top: 20px;
      }

      .grid {
        grid-template-columns: 1fr;
      }
    }
  </style>
</head>
<body>
  <main class="page">
    <section class="hero">
      <span class="eyebrow">Contained API Docs</span>
      <h1>Piper TTS HTTP API</h1>
      <p class="lede">Interactive docs and request testing with no external assets. The page reads the local OpenAPI schema and lets you exercise the endpoints directly from this server.</p>
      <div class="meta">
        <span id="meta-version">Loading schema…</span>
        <span>OpenAPI-backed</span>
        <span>Browser testing enabled</span>
      </div>
    </section>

    <section class="layout">
      <aside class="panel sidebar">
        <h2>Endpoints</h2>
        <nav id="nav" class="nav"></nav>
      </aside>

      <section id="content" class="content"></section>
    </section>
  </main>

  <script>
    (() => {
      const nav = document.getElementById("nav");
      const content = document.getElementById("content");
      const metaVersion = document.getElementById("meta-version");

      function escapeHtml(value) {
        return String(value)
          .replaceAll("&", "&amp;")
          .replaceAll("<", "&lt;")
          .replaceAll(">", "&gt;")
          .replaceAll('"', "&quot;");
      }

      function slugFor(method, path) {
        return `${method}-${path}`.replace(/[^a-zA-Z0-9]+/g, "-").replace(/^-|-$/g, "").toLowerCase();
      }

      function deref(schema, doc) {
        if (!schema) {
          return null;
        }
        if (schema.$ref) {
          const parts = schema.$ref.replace(/^#\//, "").split("/");
          return parts.reduce((acc, key) => acc && acc[key], doc);
        }
        return schema;
      }

      function buildExampleFromSchema(schema, doc) {
        const resolved = deref(schema, doc);
        if (!resolved) {
          return {};
        }

        if (Object.prototype.hasOwnProperty.call(resolved, "example")) {
          return resolved.example;
        }

        switch (resolved.type) {
          case "object": {
            const result = {};
            const properties = resolved.properties || {};
            const required = new Set(resolved.required || []);

            for (const [key, value] of Object.entries(properties)) {
              if (!required.has(key) && key === "include_alignments") {
                continue;
              }
              result[key] = buildExampleFromSchema(value, doc);
            }

            return result;
          }
          case "array":
            return [];
          case "integer":
            return resolved.minimum ?? 0;
          case "number":
            return resolved.minimum ?? 0;
          case "boolean":
            return false;
          default:
            return "";
        }
      }

      function formatResponseBody(text, contentType) {
        if (contentType && contentType.includes("application/json")) {
          try {
            return JSON.stringify(JSON.parse(text), null, 2);
          } catch (error) {
            return text;
          }
        }
        return text;
      }

      function renderNav(entries) {
        nav.innerHTML = "";
        entries.forEach((entry) => {
          const link = document.createElement("a");
          link.href = `#${entry.slug}`;
          link.innerHTML = `<strong>${escapeHtml(entry.method.toUpperCase())} ${escapeHtml(entry.path)}</strong><small>${escapeHtml(entry.summary || entry.description || "Endpoint")}</small>`;
          nav.appendChild(link);
        });
      }

      function createParameterFields(parameters) {
        const container = document.createElement("div");
        container.className = "field-list";

        if (!parameters.length) {
          const empty = document.createElement("div");
          empty.className = "empty";
          empty.textContent = "No query parameters.";
          container.appendChild(empty);
          return { container, readers: [] };
        }

        const readers = parameters.map((parameter) => {
          const label = document.createElement("label");
          const input = document.createElement("input");
          const hint = document.createElement("div");

          label.textContent = `${parameter.name}${parameter.required ? " *" : ""}`;
          input.name = parameter.name;
          input.placeholder = parameter.schema && parameter.schema.type ? parameter.schema.type : "value";
          hint.className = "hint";
          hint.textContent = parameter.description || "";

          label.appendChild(input);
          label.appendChild(hint);
          container.appendChild(label);

          return () => {
            const value = input.value.trim();
            if (!value) {
              return null;
            }
            return [parameter.name, value];
          };
        });

        return { container, readers };
      }

      function createRequestBodyEditor(operation, doc) {
        const wrapper = document.createElement("div");
        wrapper.className = "field-list";
        const requestBody = operation.requestBody;

        if (!requestBody || !requestBody.content || !requestBody.content["application/json"]) {
          const empty = document.createElement("div");
          empty.className = "empty";
          empty.textContent = "No JSON request body.";
          wrapper.appendChild(empty);
          return { container: wrapper, read: () => null };
        }

        const mediaType = requestBody.content["application/json"];
        const schema = mediaType.schema;
        const example = mediaType.examples && mediaType.examples.basic && mediaType.examples.basic.value
          ? mediaType.examples.basic.value
          : buildExampleFromSchema(schema, doc);

        const label = document.createElement("label");
        label.textContent = "JSON body";

        const textarea = document.createElement("textarea");
        textarea.value = JSON.stringify(example, null, 2);

        const hint = document.createElement("div");
        hint.className = "hint";
        hint.textContent = "Edit the JSON payload sent for POST requests.";

        label.appendChild(textarea);
        label.appendChild(hint);
        wrapper.appendChild(label);

        return {
          container: wrapper,
          read: () => textarea.value,
        };
      }

      function renderEndpoint(path, method, operation, doc) {
        const slug = slugFor(method, path);
        const endpoint = document.createElement("article");
        endpoint.className = "panel endpoint";
        endpoint.id = slug;

        const parameters = (operation.parameters || []).filter((parameter) => parameter.in === "query");
        const parameterFields = createParameterFields(parameters);
        const bodyEditor = createRequestBodyEditor(operation, doc);

        endpoint.innerHTML = `
          <header class="endpoint-header">
            <span class="method ${escapeHtml(method)}">${escapeHtml(method.toUpperCase())}</span>
            <span class="path">${escapeHtml(path)}</span>
          </header>
          <div>
            <div><strong>${escapeHtml(operation.summary || "Endpoint")}</strong></div>
            <div class="summary">${escapeHtml(operation.description || "")}</div>
          </div>
        `;

        const grid = document.createElement("div");
        grid.className = "grid";

        const requestCard = document.createElement("section");
        requestCard.className = "card";
        requestCard.innerHTML = `<h3>Request</h3>`;
        requestCard.appendChild(parameterFields.container);

        if (method === "post") {
          requestCard.appendChild(bodyEditor.container);
        }

        const actions = document.createElement("div");
        actions.className = "actions";
        const runButton = document.createElement("button");
        runButton.type = "button";
        runButton.textContent = "Send Request";
        const status = document.createElement("div");
        status.className = "status";
        actions.appendChild(runButton);
        actions.appendChild(status);
        requestCard.appendChild(actions);

        const responseCard = document.createElement("section");
        responseCard.className = "card response-block";
        responseCard.innerHTML = `<h3>Response</h3><div class="response-meta"><span>Waiting for a request…</span></div><pre>{}</pre>`;

        const responseMeta = responseCard.querySelector(".response-meta");
        const responsePre = responseCard.querySelector("pre");

        grid.appendChild(requestCard);
        grid.appendChild(responseCard);
        endpoint.appendChild(grid);

        runButton.addEventListener("click", async () => {
          runButton.disabled = true;
          status.textContent = "Sending…";
          responseCard.classList.remove("error");

          try {
            const query = new URLSearchParams();
            for (const read of parameterFields.readers) {
              const entry = read();
              if (entry) {
                query.set(entry[0], entry[1]);
              }
            }

            const url = query.toString() ? `${path}?${query.toString()}` : path;
            const init = { method: method.toUpperCase(), headers: {} };

            if (method === "post") {
              const rawBody = bodyEditor.read();
              if (rawBody && rawBody.trim()) {
                JSON.parse(rawBody);
                init.headers["Content-Type"] = "application/json";
                init.body = rawBody;
              }
            }

            const response = await fetch(url, init);
            const contentType = response.headers.get("content-type") || "";

            responseMeta.innerHTML = `
              <span>Status: <strong>${response.status}</strong></span>
              <span>Content-Type: <strong>${escapeHtml(contentType || "unknown")}</strong></span>
            `;

            if (contentType.includes("audio/wav")) {
              const blob = await response.blob();
              const objectUrl = URL.createObjectURL(blob);
              responsePre.textContent = "Binary WAV response received.";

              let audio = responseCard.querySelector("audio");
              if (!audio) {
                audio = document.createElement("audio");
                audio.controls = true;
                responseCard.appendChild(audio);
              }
              audio.src = objectUrl;
            } else {
              const text = await response.text();
              responsePre.textContent = formatResponseBody(text, contentType);
              const audio = responseCard.querySelector("audio");
              if (audio) {
                audio.remove();
              }
            }

            if (!response.ok) {
              responseCard.classList.add("error");
            }

            status.textContent = "Done.";
          } catch (error) {
            responseCard.classList.add("error");
            responseMeta.innerHTML = `<span>Request failed before the server responded.</span>`;
            responsePre.textContent = error && error.message ? error.message : String(error);
            status.textContent = "Request failed.";
          } finally {
            runButton.disabled = false;
          }
        });

        return {
          slug,
          path,
          method,
          summary: operation.summary,
          element: endpoint,
        };
      }

      async function init() {
        const response = await fetch("/openapi.json");
        if (!response.ok) {
          throw new Error(`Failed to load /openapi.json (${response.status})`);
        }

        const doc = await response.json();
        metaVersion.textContent = `${doc.info.title} v${doc.info.version}`;

        const entries = [];
        Object.entries(doc.paths || {}).forEach(([path, pathItem]) => {
          Object.entries(pathItem).forEach(([method, operation]) => {
            if (!["get", "post"].includes(method)) {
              return;
            }
            const rendered = renderEndpoint(path, method, operation, doc);
            entries.push(rendered);
            content.appendChild(rendered.element);
          });
        });

        renderNav(entries);
      }

      init().catch((error) => {
        content.innerHTML = `<section class="panel endpoint"><div class="response-block error"><pre>${escapeHtml(error.message || String(error))}</pre></div></section>`;
      });
    })();
  </script>
</body>
</html>
"""


def openapi_json(request: Request) -> JSONResponse:
    schema = build_openapi_schema()
    return JSONResponse(schema)


def swagger_ui(request: Request) -> HTMLResponse:
  return HTMLResponse(_DOCS_HTML)


__all__ = ["openapi_json", "swagger_ui"]