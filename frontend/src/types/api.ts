export type AspectRatio = "1:1" | "3:4";
export type GarmentCategory = "tops" | "bottoms" | "dress_set";

export type JobStatus =
  | "queued"
  | "running"
  | "postprocessing"
  | "succeeded"
  | "failed"
  | "timeout"
  | "cancelled";

export interface GenerationParams {
  originalImage: File | null;
  garmentCategory: GarmentCategory | null;
  styleId: string;
  modelFace: string;
  aspectRatio: AspectRatio;
}

export interface ProcessStatus {
  isGenerating: boolean;
  progress: number;
  jobId: string | null;
  status: JobStatus | null;
}

export interface GenerationResult {
  resultImageUrl: string | null;
  error: string | null;
}

export interface UploadImageResponse {
  upload_id: string;
  file_name: string;
  content_type: string;
  size_bytes: number;
  image_url: string;
  created_at: string;
}

export interface JobCreateRequest {
  workflow_type: string;
  workflow_version: string;
  workflow_params: Record<string, unknown>;
  priority?: number;
  callback_url?: string;
  client_reference?: string;
}

export interface JobCreateResponse {
  job_id: string;
  status: JobStatus;
  progress: number;
  created_at: string;
  idempotency_key?: string | null;
}

export interface JobStatusResponse {
  job_id: string;
  status: JobStatus;
  progress: number;
  workflow_type: string;
  workflow_version: string;
  created_at: string;
  updated_at: string;
  output_urls: string[];
  error_message?: string | null;
}

export interface JobCancelResponse {
  job_id: string;
  status: JobStatus;
  cancelled_at: string;
}

export interface ErrorResponse {
  error: {
    code: string;
    message: string;
    request_id?: string | null;
  };
}
