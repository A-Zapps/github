/**
 * Standardized HTTP API client with envelope unwrapping and typed error handling.
 */

export class ApiError extends Error {
  constructor(code, message, details = {}, status = 400) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.details = details;
    this.status = status;
  }
}

async function request(path, options = {}) {
  const url = path.startsWith("http") ? path : `/api/v1${path.startsWith("/") ? path : `/${path}`}`;
  const headers = {
    "Accept": "application/json",
    ...(options.headers || {}),
  };

  if (options.body && typeof options.body === "object" && !(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(options.body);
  }

  const res = await fetch(url, { ...options, headers });
  let json;
  try {
    json = await res.json();
  } catch (err) {
    if (!res.ok) {
      throw new ApiError("INTERNAL", `HTTP ${res.status}: Failed to parse JSON response.`, {}, res.status);
    }
    return null;
  }

  if (!res.ok || json.error) {
    const err = json.error || {};
    throw new ApiError(
      err.code || "INTERNAL",
      err.message || "An unexpected error occurred.",
      err.details || {},
      res.status
    );
  }

  return {
    data: json.data,
    meta: json.meta || {},
  };
}

export const api = {
  postAnalysis: (repo) => request("/analyses", { method: "POST", body: { repo } }),
  getJob: (jobId) => request(`/jobs/${jobId}`),
  getRecentAnalyses: (limit = 10) => request(`/analyses?limit=${limit}`),
  getAnalysisSummary: (analysisId) => request(`/analyses/${analysisId}`),
  getRepositoryData: (analysisId) => request(`/analyses/${analysisId}/repository`),
  getQualityData: (analysisId) => request(`/analyses/${analysisId}/quality`),
  getSecurityData: (analysisId) => request(`/analyses/${analysisId}/security`),
  getRateLimit: () => request("/github/rate-limit"),
  getSettings: () => request("/settings"),
};
