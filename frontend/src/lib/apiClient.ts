import type {
  ErrorResponse,
  JobCancelResponse,
  JobCreateRequest,
  JobCreateResponse,
  JobStatusResponse,
  UploadImageResponse,
} from "../types/api";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "/api";

export class ApiError extends Error {
  status: number;
  code?: string;

  constructor(message: string, status: number, code?: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

function withBase(path: string): string {
  const normalizedBase = API_BASE_URL.endsWith("/")
    ? API_BASE_URL.slice(0, -1)
    : API_BASE_URL;
  return `${normalizedBase}${path}`;
}

function toAbsoluteUrl(input: string): string {
  if (input.startsWith("http://") || input.startsWith("https://")) {
    return input;
  }
  if (input.startsWith("/")) {
    return `${window.location.origin}${input}`;
  }
  return input;
}

async function requestJson<T>(url: string, init: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    let errorMessage = `Request failed with status ${response.status}`;
    let errorCode: string | undefined;
    try {
      const parsed = (await response.json()) as ErrorResponse;
      if (parsed?.error?.message) {
        errorMessage = parsed.error.message;
      }
      errorCode = parsed?.error?.code;
    } catch {
      // ignore parse error
    }
    throw new ApiError(errorMessage, response.status, errorCode);
  }
  return (await response.json()) as T;
}

export async function uploadImage(file: File): Promise<UploadImageResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const uploaded = await requestJson<UploadImageResponse>(withBase("/v1/uploads/images"), {
    method: "POST",
    body: formData,
  });

  return {
    ...uploaded,
    image_url: toAbsoluteUrl(uploaded.image_url),
  };
}

export async function createJob(
  payload: JobCreateRequest,
  idempotencyKey: string,
): Promise<JobCreateResponse> {
  return requestJson<JobCreateResponse>(withBase("/v1/jobs"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": idempotencyKey,
    },
    body: JSON.stringify(payload),
  });
}

export async function getJobStatus(jobId: string): Promise<JobStatusResponse> {
  const status = await requestJson<JobStatusResponse>(withBase(`/v1/jobs/${jobId}`), {
    method: "GET",
  });

  return {
    ...status,
    output_urls: status.output_urls.map(toAbsoluteUrl),
  };
}

export async function cancelJob(jobId: string): Promise<JobCancelResponse> {
  return requestJson<JobCancelResponse>(withBase(`/v1/jobs/${jobId}/cancel`), {
    method: "POST",
  });
}

export function createClientReference(): string {
  return `web-${Date.now()}`;
}

export function createIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `idem-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}
