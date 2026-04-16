import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";

import { ImageUploader } from "./components/ImageUploader";
import {
  cancelJob,
  createClientReference,
  createIdempotencyKey,
  createJob,
  getJobStatus,
  uploadImage,
} from "./lib/apiClient";
import type {
  AspectRatio,
  GarmentCategory,
  GenerationParams,
  GenerationResult,
  JobStatus,
  ProcessStatus,
} from "./types/api";
import "./styles.css";

const TERMINAL_STATUSES = new Set<JobStatus>(["succeeded", "failed", "timeout", "cancelled"]);
const POLL_INTERVAL_MS = 2000;

type UiPhase = "input" | "instant" | "after";

const DEFAULT_STYLE_ID = "french_street";
const DEFAULT_MODEL_FACE = "asian_sweet";

const CATEGORY_OPTIONS: Array<{
  id: GarmentCategory;
  label: string;
  promptHint: string;
}> = [
  {
    id: "tops",
    label: "TOP",
    promptHint: "upper-body clothing, top wear, keep garment on torso and shoulders",
  },
  {
    id: "bottoms",
    label: "BOTTOM",
    promptHint: "lower-body clothing, pants or skirt, keep garment on waist and legs",
  },
  {
    id: "dress_set",
    label: "SET",
    promptHint: "full-body dress or matching set, keep coherent upper-lower garment structure",
  },
];

const ASPECT_RATIO_OPTIONS: Array<{
  value: AspectRatio;
  label: string;
}> = [
  { value: "1:1", label: "Square" },
  { value: "4:5", label: "Ecom" },
  { value: "3:4", label: "Portrait" },
  { value: "2:3", label: "Poster" },
  { value: "9:16", label: "Reel" },
  { value: "4:3", label: "Landscape" },
  { value: "16:9", label: "Wide" },
];

function buildWorkflowType(styleId: string, modelFace: string, garmentCategory: GarmentCategory): string {
  return `model_photo_generation_${styleId}_${modelFace}_${garmentCategory}`;
}

function statusToMessage(status: JobStatus, fallback?: string | null): string {
  if (fallback && fallback.trim().length > 0) {
    return fallback;
  }
  const map: Record<JobStatus, string> = {
    queued: "Job is queued.",
    running: "Job is generating.",
    postprocessing: "Job is post-processing.",
    succeeded: "Generation completed.",
    failed: "Generation failed. Please adjust params and retry.",
    timeout: "Generation timed out. Please retry later.",
    cancelled: "Job was cancelled.",
  };
  return map[status];
}
function statusToInstantLine(status: JobStatus | null): string {
  if (!status) {
    return "AI is preparing your session";
  }

  const map: Record<JobStatus, string> = {
    queued: "Staging lights and pose space",
    running: "Tailoring texture, silhouette and drape",
    postprocessing: "Finishing skin and fabric details",
    succeeded: "Render finished",
    failed: "Render failed, please retry",
    timeout: "Render timeout, please retry",
    cancelled: "Task cancelled",
  };

  return map[status];
}

function pickBeforeImage(modelPreviewUrl: string | null, sourcePreviewUrl: string | null): string | null {
  return modelPreviewUrl ?? sourcePreviewUrl;
}

export default function App(): JSX.Element {
  const [params, setParams] = useState<GenerationParams>({
    originalImage: null,
    modelImage: null,
    garmentCategory: null,
    styleId: DEFAULT_STYLE_ID,
    modelFace: DEFAULT_MODEL_FACE,
    aspectRatio: "3:4",
  });

  const [sourcePreviewUrl, setSourcePreviewUrl] = useState<string | null>(null);
  const [modelPreviewUrl, setModelPreviewUrl] = useState<string | null>(null);

  const [processStatus, setProcessStatus] = useState<ProcessStatus>({
    isGenerating: false,
    progress: 0,
    jobId: null,
    status: null,
  });

  const [result, setResult] = useState<GenerationResult>({
    resultImageUrl: null,
    resultImageUrls: [],
    error: null,
  });

  const [activeResultIndex, setActiveResultIndex] = useState(0);
  const [comparePosition, setComparePosition] = useState(50);

  const pollingRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (pollingRef.current) {
        window.clearInterval(pollingRef.current);
      }

      if (sourcePreviewUrl?.startsWith("blob:")) {
        URL.revokeObjectURL(sourcePreviewUrl);
      }

      if (modelPreviewUrl?.startsWith("blob:")) {
        URL.revokeObjectURL(modelPreviewUrl);
      }
    };
  }, [sourcePreviewUrl, modelPreviewUrl]);

  const canSubmit = useMemo(() => {
    return !!params.originalImage && !!params.garmentCategory && !processStatus.isGenerating;
  }, [params.originalImage, params.garmentCategory, processStatus.isGenerating]);

  const uiPhase = useMemo<UiPhase>(() => {
    if (processStatus.isGenerating) {
      return "instant";
    }
    if (result.resultImageUrls.length > 0 || result.resultImageUrl) {
      return "after";
    }
    return "input";
  }, [processStatus.isGenerating, result.resultImageUrl, result.resultImageUrls.length]);

  const activeResultUrl = useMemo(() => {
    if (result.resultImageUrls.length > 0) {
      return result.resultImageUrls[Math.min(activeResultIndex, result.resultImageUrls.length - 1)] ?? null;
    }
    return result.resultImageUrl;
  }, [result.resultImageUrls, result.resultImageUrl, activeResultIndex]);

  const beforeCompareUrl = useMemo(
    () => pickBeforeImage(modelPreviewUrl, sourcePreviewUrl),
    [modelPreviewUrl, sourcePreviewUrl],
  );

  const stageStyle = useMemo(
    () => ({ "--hero-image": 'url("/images/luxury-bg.png")' } as CSSProperties),
    [],
  );

  function clearPolling(): void {
    if (pollingRef.current) {
      window.clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  }

  function updatePreview(currentUrl: string | null, setUrl: (url: string | null) => void, file: File): void {
    if (currentUrl?.startsWith("blob:")) {
      URL.revokeObjectURL(currentUrl);
    }
    setUrl(URL.createObjectURL(file));
  }

  function handleSourceSelected(file: File): void {
    setParams((prev) => ({ ...prev, originalImage: file }));
    setResult((prev) => ({ ...prev, error: null }));
    updatePreview(sourcePreviewUrl, setSourcePreviewUrl, file);
  }

  function handleModelSelected(file: File): void {
    setParams((prev) => ({ ...prev, modelImage: file }));
    setResult((prev) => ({ ...prev, error: null }));
    updatePreview(modelPreviewUrl, setModelPreviewUrl, file);
  }

  async function syncJob(jobId: string): Promise<JobStatus | null> {
    try {
      const job = await getJobStatus(jobId);
      const imageUrls = job.output_urls ?? [];
      const terminal = TERMINAL_STATUSES.has(job.status);
      const primaryImageUrl = imageUrls[0] ?? null;

      setProcessStatus({
        isGenerating: !terminal,
        progress: job.progress,
        jobId,
        status: job.status,
      });

      if (job.status === "succeeded") {
        setActiveResultIndex(0);
        setComparePosition(50);
        setResult({
          resultImageUrl: primaryImageUrl,
          resultImageUrls: imageUrls,
          error: primaryImageUrl ? null : "Job completed but no output image URL was returned.",
        });
      } else if (terminal) {
        setResult((prev) => ({
          ...prev,
          error: statusToMessage(job.status, job.error_message),
        }));
      }

      if (terminal) {
        clearPolling();
      }
      return job.status;
    } catch (error) {
      clearPolling();
      const message = error instanceof Error ? error.message : "Failed to query job status.";
      setProcessStatus((prev) => ({ ...prev, isGenerating: false }));
      setResult((prev) => ({ ...prev, error: message }));
      return null;
    }
  }

  function beginPolling(jobId: string): void {
    clearPolling();
    pollingRef.current = window.setInterval(() => {
      void syncJob(jobId);
    }, POLL_INTERVAL_MS);
  }

  async function handleGenerate(): Promise<void> {
    if (!params.originalImage) {
      setResult((prev) => ({ ...prev, error: "Please upload a garment image first." }));
      return;
    }

    if (!params.garmentCategory) {
      setResult((prev) => ({ ...prev, error: "Please select a garment category." }));
      return;
    }

    clearPolling();
    setActiveResultIndex(0);
    setComparePosition(50);
    setResult({ resultImageUrl: null, resultImageUrls: [], error: null });
    setProcessStatus({ isGenerating: true, progress: 3, jobId: null, status: "queued" });

    try {
      const uploadedGarment = await uploadImage(params.originalImage);
      let modelReferenceUrl: string | null = null;

      if (params.modelImage) {
        const uploadedModel = await uploadImage(params.modelImage);
        modelReferenceUrl = uploadedModel.image_url;
      }

      const categoryConfig = CATEGORY_OPTIONS.find((item) => item.id === params.garmentCategory);

      const workflowParams: Record<string, unknown> = {
        source_image_url: uploadedGarment.image_url,
        style_id: params.styleId,
        model_face: params.modelFace,
        garment_category: params.garmentCategory,
        garment_category_prompt: categoryConfig?.promptHint,
        aspect_ratio: params.aspectRatio,
        original_file_name: params.originalImage.name,
      };

      if (modelReferenceUrl) {
        workflowParams.model_reference_url = modelReferenceUrl;
      }

      const created = await createJob(
        {
          workflow_type: buildWorkflowType(params.styleId, params.modelFace, params.garmentCategory),
          workflow_version: "v1",
          workflow_params: workflowParams,
          client_reference: createClientReference(),
        },
        createIdempotencyKey(),
      );

      const isTerminal = TERMINAL_STATUSES.has(created.status);
      setProcessStatus({
        isGenerating: !isTerminal,
        progress: created.progress,
        jobId: created.job_id,
        status: created.status,
      });

      const latestStatus = await syncJob(created.job_id);
      if (!isTerminal && latestStatus && !TERMINAL_STATUSES.has(latestStatus)) {
        beginPolling(created.job_id);
      }
    } catch (error) {
      clearPolling();
      const message = error instanceof Error ? error.message : "Failed to submit generation job.";
      setProcessStatus((prev) => ({ ...prev, isGenerating: false }));
      setResult((prev) => ({ ...prev, error: message }));
    }
  }

  async function handleCancel(): Promise<void> {
    if (!processStatus.jobId || !processStatus.isGenerating) {
      return;
    }

    try {
      await cancelJob(processStatus.jobId);
      await syncJob(processStatus.jobId);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to cancel job.";
      setResult((prev) => ({ ...prev, error: message }));
    }
  }

  return (
    <div className={`stage-shell phase-${uiPhase}`} style={stageStyle}>
      <header className="top-nav">
        <div className="nav-left">
          <span>SHOP</span>
          <span>LOOKBOOK</span>
          <span>HOW TO STYLE</span>
        </div>
        <div className="nav-brand">S-IMAGE</div>
        <div className="nav-right">
          <span>JOURNAL</span>
          <span>ABOUT</span>
          <span>ACCOUNT</span>
        </div>
      </header>

      <main className="stage-grid">
        <section className="left-pane">
          <p className="input-mark">INPUT</p>
          <h1>YOUR VISION</h1>
          <p className="input-note">Upload, choose category, ignite.</p>

          <div className="upload-stack">
            <ImageUploader
              label="GARMENT"
              requiredTag="REQUIRED"
              prompt="+ UPLOAD GARMENT"
              file={params.originalImage}
              previewUrl={sourcePreviewUrl}
              disabled={processStatus.isGenerating}
              onFileSelected={handleSourceSelected}
              onValidationError={(message) => setResult((prev) => ({ ...prev, error: message }))}
            />
            <ImageUploader
              label="MODEL REFERENCE"
              requiredTag="OPTIONAL"
              prompt="+ UPLOAD MODEL"
              file={params.modelImage}
              previewUrl={modelPreviewUrl}
              disabled={processStatus.isGenerating}
              onFileSelected={handleModelSelected}
              onValidationError={(message) => setResult((prev) => ({ ...prev, error: message }))}
            />
          </div>

          <section className="segment-control" aria-label="garment category">
            {CATEGORY_OPTIONS.map((option) => (
              <button
                key={option.id}
                type="button"
                className={params.garmentCategory === option.id ? "active" : ""}
                disabled={processStatus.isGenerating}
                onClick={() => setParams((prev) => ({ ...prev, garmentCategory: option.id }))}
              >
                {option.label}
              </button>
            ))}
          </section>

          <section className="ratio-line">
            {ASPECT_RATIO_OPTIONS.map((ratio) => (
              <button
                key={ratio.value}
                type="button"
                className={params.aspectRatio === ratio.value ? "active" : ""}
                disabled={processStatus.isGenerating}
                onClick={() => setParams((prev) => ({ ...prev, aspectRatio: ratio.value }))}
              >
                <span>{ratio.value}</span>
                <small>{ratio.label}</small>
              </button>
            ))}
          </section>

          <div className="action-line">
            <button type="button" className="ignite" disabled={!canSubmit} onClick={() => void handleGenerate()}>
              {processStatus.isGenerating ? "CRAFTING..." : "IGNITE"}
            </button>
            <button
              type="button"
              className="cancel"
              disabled={!processStatus.isGenerating}
              onClick={() => void handleCancel()}
            >
              CANCEL
            </button>
          </div>
        </section>

        <section className="right-pane">
          <div className="phase-word">{uiPhase === "instant" ? "INSTANT" : "AFTER"}</div>

          <div className={`visual-stage ${uiPhase}`}>
            {uiPhase === "input" ? <div className="awaiting">AWAITING GENERATION</div> : null}

            {uiPhase === "instant" ? (
              <div className="instant-layer">
                {activeResultUrl ? <img src={activeResultUrl} alt="last result" className="blur-preview" /> : null}
                <div className="instant-copy">
                  <h2>INSTANT UPGRADE</h2>
                  <p>{statusToInstantLine(processStatus.status)}</p>
                  <div className="shimmer-track">
                    <span style={{ width: `${Math.max(8, processStatus.progress)}%` }} />
                  </div>
                </div>
              </div>
            ) : null}

            {uiPhase === "after" && activeResultUrl ? (
              <div className="after-layer">
                <div className="compare-wrap">
                  <img src={activeResultUrl} alt="Generated result" className="after-image" />

                  {beforeCompareUrl ? (
                    <div
                      className="before-mask"
                      style={{ clipPath: `inset(0 ${100 - comparePosition}% 0 0)` }}
                    >
                      <img src={beforeCompareUrl} alt="Before reference" className="before-image" />
                    </div>
                  ) : null}

                  {beforeCompareUrl ? (
                    <div className="compare-line" style={{ left: `${comparePosition}%` }}>
                      <span />
                    </div>
                  ) : null}

                  <div className="after-label">AFTER</div>
                </div>

                {beforeCompareUrl ? (
                  <input
                    className="compare-range"
                    type="range"
                    min={0}
                    max={100}
                    value={comparePosition}
                    onChange={(event) => setComparePosition(Number(event.target.value))}
                    aria-label="before after slider"
                  />
                ) : null}

                <a href={activeResultUrl} target="_blank" rel="noreferrer" className="open-image-link">
                  OPEN ORIGINAL
                </a>
              </div>
            ) : null}
          </div>

          {result.resultImageUrls.length > 1 ? (
            <div className="pose-strip">
              {result.resultImageUrls.map((url, index) => (
                <button
                  key={url}
                  type="button"
                  className={`pose-thumb ${index === activeResultIndex ? "active" : ""}`}
                  onMouseEnter={() => setActiveResultIndex(index)}
                  onFocus={() => setActiveResultIndex(index)}
                  onClick={() => setActiveResultIndex(index)}
                >
                  <img src={url} alt={`Pose ${index + 1}`} />
                </button>
              ))}
            </div>
          ) : null}

          {result.error ? <div className="stage-error">{result.error}</div> : null}
        </section>
      </main>
    </div>
  );
}


