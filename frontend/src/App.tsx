import { useEffect, useMemo, useRef, useState } from "react";

import { ImageUploader } from "./components/ImageUploader";
import { ResultViewer } from "./components/ResultViewer";
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

const CATEGORY_OPTIONS: Array<{
  id: GarmentCategory;
  label: string;
  icon: string;
  promptHint: string;
}> = [
  {
    id: "tops",
    label: "上衣",
    icon: "👕",
    promptHint: "upper-body clothing, top wear, keep garment on torso and shoulders",
  },
  {
    id: "bottoms",
    label: "下装",
    icon: "👖",
    promptHint: "lower-body clothing, pants or skirt, keep garment on waist and legs",
  },
  {
    id: "dress_set",
    label: "连衣裙/套装",
    icon: "👗",
    promptHint: "full-body dress or matching set, keep coherent upper-lower garment structure",
  },
];

const STYLE_OPTIONS = [
  { id: "french_street", label: "法式街头", preview: "🧥" },
  { id: "korean_minimal", label: "韩系高冷", preview: "🖤" },
  { id: "city_commute", label: "都市通勤", preview: "🏙️" },
  { id: "editorial_clean", label: "杂志感", preview: "📸" },
];

const FACE_OPTIONS = [
  { id: "asian_sweet", label: "亚洲甜美", preview: "😊" },
  { id: "asian_sharp", label: "亚洲高冷", preview: "😼" },
  { id: "european_modern", label: "欧美辣妹", preview: "💄" },
  { id: "neutral_clean", label: "中性高级", preview: "✨" },
];

const ASPECT_RATIO_OPTIONS: Array<{
  value: AspectRatio;
  label: string;
}> = [
  { value: "1:1", label: "方图" },
  { value: "4:5", label: "电商主图" },
  { value: "3:4", label: "模特竖版" },
  { value: "2:3", label: "海报竖版" },
  { value: "9:16", label: "短视频竖屏" },
  { value: "4:3", label: "图文横版" },
  { value: "16:9", label: "宽屏横版" },
];

function buildWorkflowType(styleId: string, modelFace: string, garmentCategory: GarmentCategory): string {
  return `model_photo_generation_${styleId}_${modelFace}_${garmentCategory}`;
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

function statusToFriendlyLine(status: JobStatus | null): string {
  if (!status) {
    return "";
  }
  const map: Record<JobStatus, string> = {
    queued: "AI 正在排队准备中，马上开始出片",
    running: "AI 正在布光、换装、构图中",
    postprocessing: "正在精修细节和材质纹理",
    succeeded: "成图已完成",
    failed: "本次生成未成功，请调整后重试",
    timeout: "本次生成超时，请重试",
    cancelled: "任务已取消",
  };
  return map[status];
}

export default function App(): JSX.Element {
  const [params, setParams] = useState<GenerationParams>({
    originalImage: null,
    garmentCategory: null,
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
    return !!params.originalImage && !!params.garmentCategory && !processStatus.isGenerating;
  }, [params.originalImage, params.garmentCategory, processStatus.isGenerating]);

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
    if (!params.garmentCategory) {
      setResult((prev) => ({ ...prev, error: "请先选择衣服品类（上衣/下装/连衣裙套装）。" }));
      return;
    }

    clearPolling();
    setResult({ resultImageUrl: null, error: null });
    setProcessStatus({ isGenerating: true, progress: 0, jobId: null, status: "queued" });

    try {
      const uploaded = await uploadImage(params.originalImage);
      const categoryConfig = CATEGORY_OPTIONS.find((item) => item.id === params.garmentCategory);

      const created = await createJob(
        {
          workflow_type: buildWorkflowType(params.styleId, params.modelFace, params.garmentCategory),
          workflow_version: "v1",
          workflow_params: {
            source_image_url: uploaded.image_url,
            style_id: params.styleId,
            model_face: params.modelFace,
            garment_category: params.garmentCategory,
            garment_category_prompt: categoryConfig?.promptHint,
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
        <h1>上传服装平铺/人台图，一键召唤专属 AI 模特</h1>
        <p>选好品类、风格和模特气质，自动生成可用于电商展示与种草投放的成图。</p>
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
              <h3>选择衣服品类</h3>
              <span>必选项</span>
            </header>
            <div className="category-grid">
              {CATEGORY_OPTIONS.map((option) => (
                <button
                  key={option.id}
                  type="button"
                  className={`category-btn ${params.garmentCategory === option.id ? "active" : ""}`}
                  disabled={processStatus.isGenerating}
                  onClick={() => setParams((prev) => ({ ...prev, garmentCategory: option.id }))}
                >
                  <span className="category-icon" aria-hidden>
                    {option.icon}
                  </span>
                  <span>{option.label}</span>
                </button>
              ))}
            </div>
          </section>

          <section className="panel-block">
            <header className="block-head">
              <h3>风格与模特气质</h3>
              <span>所见即所得</span>
            </header>

            <div className="selector-group">
              <p className="selector-title">风格氛围</p>
              <div className="visual-strip">
                {STYLE_OPTIONS.map((option) => (
                  <button
                    key={option.id}
                    type="button"
                    className={`visual-totem ${params.styleId === option.id ? "active" : ""}`}
                    disabled={processStatus.isGenerating}
                    onClick={() => setParams((prev) => ({ ...prev, styleId: option.id }))}
                  >
                    <span className="totem-avatar">{option.preview}</span>
                    <span className="totem-label">{option.label}</span>
                  </button>
                ))}
              </div>
            </div>

            <div className="selector-group">
              <p className="selector-title">模特脸型</p>
              <div className="visual-strip">
                {FACE_OPTIONS.map((option) => (
                  <button
                    key={option.id}
                    type="button"
                    className={`visual-totem ${params.modelFace === option.id ? "active" : ""}`}
                    disabled={processStatus.isGenerating}
                    onClick={() => setParams((prev) => ({ ...prev, modelFace: option.id }))}
                  >
                    <span className="totem-avatar">{option.preview}</span>
                    <span className="totem-label">{option.label}</span>
                  </button>
                ))}
              </div>
            </div>

            <div className="ratio-group">
              <span>成图比例</span>
              <div className="ratio-grid">
                {ASPECT_RATIO_OPTIONS.map((ratio) => (
                  <button
                    key={ratio.value}
                    type="button"
                    className={params.aspectRatio === ratio.value ? "active" : ""}
                    disabled={processStatus.isGenerating}
                    onClick={() => setParams((prev) => ({ ...prev, aspectRatio: ratio.value }))}
                  >
                    <strong>{ratio.value}</strong>
                    <small>{ratio.label}</small>
                  </button>
                ))}
              </div>
            </div>
          </section>

          <div className="action-row">
            <button type="button" disabled={!canSubmit} onClick={() => void handleGenerate()}>
              {processStatus.isGenerating ? "AI 出片中..." : "一键召唤 AI 模特"}
            </button>
            <button
              type="button"
              className="secondary"
              disabled={!processStatus.isGenerating}
              onClick={() => void handleCancel()}
            >
              取消本次生成
            </button>
          </div>
        </section>

        <section className="right-panel">
          {processStatus.isGenerating ? (
            <div className="generation-banner">
              <strong>{statusToFriendlyLine(processStatus.status)}</strong>
              <p>正在专注生成你的商拍图，不需要关注任务编号。</p>
            </div>
          ) : null}

          {result.error ? <div className="error-box">{result.error}</div> : null}

          <ResultViewer imageUrl={result.resultImageUrl} isGenerating={processStatus.isGenerating} />
        </section>
      </main>
    </div>
  );
}
