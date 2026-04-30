const SAFE_METHODS = ["GET", "HEAD", "OPTIONS", "TRACE"];

export class ApiError extends Error {
  constructor(message, status, payload = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

export function getCookie(name) {
  return document.cookie
    .split(";")
    .map((cookie) => cookie.trim())
    .find((cookie) => cookie.startsWith(`${name}=`))
    ?.slice(name.length + 1) || "";
}

async function readJson(response) {
  if (response.status === 204) {
    return {};
  }

  const text = await response.text();
  if (!text) {
    return {};
  }

  try {
    return JSON.parse(text);
  } catch {
    return {};
  }
}

export async function api(path, options = {}) {
  const { headers: optionHeaders, ...fetchOptions } = options;
  const method = (options.method || "GET").toUpperCase();
  const headers = {
    "Content-Type": "application/json",
    ...(optionHeaders || {})
  };

  if (!SAFE_METHODS.includes(method)) {
    headers["X-CSRFToken"] = decodeURIComponent(getCookie("csrftoken"));
  }

  const response = await fetch(`/api${path}`, {
    credentials: "include",
    headers,
    ...fetchOptions
  });
  const payload = await readJson(response);

  if (!response.ok) {
    throw new ApiError(payload.detail || `API request failed: ${response.status}`, response.status, payload);
  }

  return payload;
}
