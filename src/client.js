export const BASE = "https://api.exa.ai";
export const TIMEOUT = 15000;
export const RETRIES = 3;

function exitFor(status) {
  if (status === 401 || status === 403 || status === 404) return 3;
  if (status === 429) return 4;
  if (status >= 500 && status < 600) return 6;
  return 2;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function doRequest(method, endpoint, payload, apiKey, queryParams = null) {
  let url = BASE + endpoint;
  if (queryParams) {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(queryParams)) {
      if (v !== undefined && v !== null) {
        qs.append(k, String(v));
      }
    }
    const qstr = qs.toString();
    if (qstr) {
      url += (url.includes("?") ? "&" : "?") + qstr;
    }
  }

  for (let attempt = 1; attempt <= RETRIES; attempt++) {
    try {
      const headers = {
        "x-api-key": apiKey,
        "Content-Type": "application/json",
        "User-Agent": "exa-cli/0.1.0",
      };

      const options = {
        method,
        headers,
        signal: AbortSignal.timeout(TIMEOUT),
      };

      if (payload !== null && payload !== undefined && method !== "GET") {
        options.body = JSON.stringify(payload);
      }

      const res = await fetch(url, options);

      if (res.ok) {
        const text = await res.text();
        const trimmed = text.trim();
        if (trimmed.startsWith("{") || trimmed.startsWith("[")) {
          try {
            return JSON.parse(text);
          } catch {
            return { raw: text };
          }
        }
        return { raw: text };
      }

      const code = res.status;
      const text = (await res.text()).slice(0, 2000);

      if (code === 429 || code >= 500) {
        if (attempt < RETRIES) {
          const retryHeader = res.headers.get("retry-after") || "1";
          let wait = parseInt(retryHeader, 10);
          if (isNaN(wait) || wait <= 0) wait = attempt;
          wait = Math.min(wait, 30);
          console.error(`attempt ${attempt}/${RETRIES} HTTP ${code}, retrying in ${wait}s`);
          await sleep(wait * 1000);
          continue;
        }
        console.error(`attempts exhausted: ${RETRIES}/${RETRIES}`);
        process.exit(exitFor(code));
      }

      console.error(`error: HTTP ${code}: ${text}`);
      process.exit(exitFor(code));
    } catch (err) {
      console.error(`attempt ${attempt}/${RETRIES} network error: ${err.message}, retrying`);
      if (attempt >= RETRIES) {
        console.error(`error: network error: ${err.message}`);
        process.exit(5);
      }
      await sleep(attempt * 1000);
    }
  }
  process.exit(5);
}

export async function post(path, payload, apiKey) {
  return doRequest("POST", path, payload, apiKey);
}

export async function get(path, apiKey, params = null) {
  return doRequest("GET", path, null, apiKey, params);
}

export async function patch(path, payload, apiKey) {
  return doRequest("PATCH", path, payload, apiKey);
}

export async function del(path, apiKey) {
  return doRequest("DELETE", path, null, apiKey);
}
