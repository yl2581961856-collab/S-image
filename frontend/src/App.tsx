import { useEffect, useMemo, useRef, useState } from "react";

import { ImageUploader } from "./components/ImageUploader";
import { ProgressCard } from "./components/ProgressCard";
import { ResultViewer } from "./components/ResultViewer";
import {
  cancelJob,
  createClientReference,
  createIdempotencyKey,
  createJob,
  getJobStatus,
  uploadImage,
} from "./lib/apiClient";
import type { AspectRatio, GenerationParams, GenerationResult, JobStatus, ProcessStatus } from "./types/api";
import "./styles.css";

const TERMINAL_STATUSES = new Set<JobStatus>(["succeeded", "failed", "timeout", "cancelled"]);
const POLL_INTERVAL_MS = 2000;

const STYLE_OPTIONS = [
  { id: "french_street", label: "法式街头" },
  { id: "korean_minimal", label: "韩系极简" },
  { id: "city_commute", label: "都市通勤" },
];

const FACE_OPTIONS = [
  { id: "asian_sweet", label: "亚洲甜美" },
  { id: "asian_sharp", label: "亚洲高冷" },
  { id: "european_modern", label: "欧美现代" },
];

function buildWorkflowType(styleId: string, modelFace: string): string {
  return `model_photo_generation_${styleId}_${modelFace}`;
}

function statusToMessage(status: JobStatus, fallback?: string | null): string {
  if (fallback && fallback.trim().length > 0) {
    return fallback;
  }
  const map: Record<JobStatus, string> = {
    queued: "任务仍在排队。",
    running: "任务正在生成中。",
    postprocessing: "任务在做后处理，请稍候。",
    succeeded: "生成完成。",
    failed: "生成失败，请调整参数后重试。",
    timeout: "任务超时，请稍后重试。",
    cancelled: "任务已取消。",
  };
  return map[status];
}

export default function App(): JSX.Element {
  const [params, setParams] = useState<GenerationParams>({
    originalImage: null,
    styleId: STYLE_OPTIONS[0].id,
    modelFace: FACE_OPTIONS[0].id,
    aspectRatio: "3:4",
  });

  const [sourcePreviewUrl, setSourcePreviewUrl] = useState<string | null>(null);

  const [processStatus, setProcessStatus] = useState<ProcessStatus>({
    isGenerating: false,
    progress: 0,
    jobId: null,
    status: null,
  });

  const [result, setResult] = useState<GenerationResult>({
    resultImageUrl: null,
    error: null,
  });

  const pollingRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (pollingRef.current) {
        window.clearInterval(pollingRef.current);
      }
      if (sourcePreviewUrl?.startsWith("blob:")) {
        URL.revokeObjectURL(sourcePreviewUrl);
      }
    };
  }, [sourcePreviewUrl]);

  const canSubmit = useMemo(() => {
    return !!params.originalImage && !processStatus.isGenerating;
  }, [params.originalImage, processStatus.isGenerating]);

  function clearPolling(): void {
    if (pollingRef.current) {
      window.clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  }

  function handleFileSelected(file: File): void {
    setParams((prev) => ({ ...prev, originalImage: file }));
    setResult((prev) => ({ ...prev, error: null }));
    setProcessStatus((prev) => ({ ...prev, progress: 0 }));

    if (sourcePreviewUrl?.startsWith("blob:")) {
      URL.revokeObjectURL(sourcePreviewUrl);
    }
    setSourcePreviewUrl(URL.createObjectURL(file));
  }

  async function syncJob(jobId: string): Promise<JobStatus | null> {
    try {
      const job = await getJobStatus(jobId);

      const terminal = TERMINAL_STATUSES.has(job.status);
      const imageUrl = job.output_urls[0] ?? null;

      setProcessStatus({
        isGenerating: !terminal,
        progress: job.progress,
        jobId,
        status: job.status,
      });

      if (job.status === "succeeded") {
        setResult({
          resultImageUrl: imageUrl,
          error: imageUrl ? null : "任务完成但未返回成图地址。",
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
      const message = error instanceof Error ? error.message : "查询任务状态失败";
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
      setResult((prev) => ({ ...prev, error: "请先上传源图。" }));
      return;
    }

    clearPolling();
    setResult({ resultImageUrl: null, error: null });
    setProcessStatus({ isGenerating: true, progress: 0, jobId: null, status: "queued" });

    try {
      const uploaded = await uploadImage(params.originalImage);

      const created = await createJob(
        {
          workflow_type: buildWorkflowType(params.styleId, params.modelFace),
          workflow_version: "v1",
          workflow_params: {
            source_image_url: uploaded.image_url,
            style_id: params.styleId,
            model_face: params.modelFace,
            aspect_ratio: params.aspectRatio,
            original_file_name: params.originalImage.name,
          },
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
      const message = error instanceof Error ? error.message : "任务提交失败";
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
      const message = error instanceof Error ? error.message : "取消任务失败";
      setResult((prev) => ({ ...prev, error: message }));
    }
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <h1>Image Workflow Studio</h1>
        <p>上传源图，创建生成任务，实时追踪 JobId 状态并展示结果。</p>
      </header>

      <main className="workspace">
        <section className="left-panel">
          <ImageUploader
            file={params.originalImage}
            previewUrl={sourcePreviewUrl}
            disabled={processStatus.isGenerating}
            onFileSelected={handleFileSelected}
            onValidationError={(message) => setResult((prev) => ({ ...prev, error: message }))}
          />

          <section className="panel-block">
            <header className="block-head">
              <h3>风格参数</h3>
              <span>会写入 workflow_params</span>
            </header>
            <label>
              风格
              <select
                value={params.styleId}
                disabled={processStatus.isGenerating}
                onChange={(event) =>
                  setParams((prev) => ({ ...prev, styleId: event.target.value }))
                }
              >
                {STYLE_OPTIONS.map((option) => (
                  <option key={option.id} value={option.id}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>

            <label>
              模特脸型
              <select
                value={params.modelFace}
                disabled={processStatus.isGenerating}
                onChange={(event) =>
                  setParams((prev) => ({ ...prev, modelFace: event.target.value }))
                }
              >
                {FACE_OPTIONS.map((option) => (
                  <option key={option.id} value={option.id}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>

            <div className="ratio-group">
              <span>比例</span>
              <div>
                {(["1:1", "3:4"] as AspectRatio[]).map((ratio) => (
                  <button
                    key={ratio}
                    type="button"
                    className={params.aspectRatio === ratio ? "active" : ""}
                    disabled={processStatus.isGenerating}
                    onClick={() => setParams((prev) => ({ ...prev, aspectRatio: ratio }))}
                  >
                    {ratio}
                  </button>
                ))}
              </div>
            </div>
          </section>

          <div className="action-row">
            <button type="button" disabled={!canSubmit} onClick={() => void handleGenerate()}>
              {processStatus.isGenerating ? "生成中..." : "一键生成"}
            </button>
            <button
              type="button"
              className="secondary"
              disabled={!processStatus.isGenerating}
              onClick={() => void handleCancel()}
            >
              取消任务
            </button>
          </div>
        </section>

        <section className="right-panel">
          <ProgressCard
            status={processStatus.status}
            progress={processStatus.progress}
            jobId={processStatus.jobId}
          />

          {result.error ? <div className="error-box">{result.error}</div> : null}

          <ResultViewer imageUrl={result.resultImageUrl} isGenerating={processStatus.isGenerating} />
        </section>
      </main>
    </div>
  );
}
