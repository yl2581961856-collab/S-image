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

const CATEGORY_OPTIONS: Array<{
  id: GarmentCategory;
  label: string;
  icon: string;
  promptHint: string;
}> = [
  {
    id: "tops",
    label: "上衣",
    icon: "TOP",
    promptHint: "upper-body clothing, top wear, keep garment on torso and shoulders",
  },
  {
    id: "bottoms",
    label: "下装",
    icon: "BTM",
    promptHint: "lower-body clothing, pants or skirt, keep garment on waist and legs",
  },
  {
    id: "dress_set",
    label: "连衣裙/套装",
    icon: "SET",
    promptHint: "full-body dress or matching set, keep coherent upper-lower garment structure",
  },
];

const STYLE_OPTIONS = [
  { id: "french_street", label: "法式街头", preview: "FS" },
  { id: "korean_minimal", label: "韩系极简", preview: "KM" },
  { id: "city_commute", label: "都市通勤", preview: "CC" },
  { id: "editorial_clean", label: "杂志感", preview: "ED" },
];

const FACE_OPTIONS = [
  { id: "asian_sweet", label: "亚洲甜美", preview: "AS" },
  { id: "asian_sharp", label: "亚洲高冷", preview: "AH" },
  { id: "european_modern", label: "欧美辣妹", preview: "EM" },
  { id: "neutral_clean", label: "中性高级", preview: "NC" },
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
    queued: "任务正在排队。",
    running: "任务正在生成中。",
    postprocessing: "任务正在做后处理，请稍候。",
    succeeded: "生成完成。",
    failed: "生成失败，请调整参数后重试。",
    timeout: "任务超时，请稍后重试。",
    cancelled: "任务已取消。",
  };

  return map[status];
}

function statusToInstantLine(status: JobStatus | null): string {
  if (!status) {
    return "AI 正在读取你的输入。";
  }

  const map: Record<JobStatus, string> = {
    queued: "正在搭建场景与光线",
    running: "正在进行高定级别的换装渲染",
    postprocessing: "正在打磨材质、皮肤与细节",
    succeeded: "渲染完成",
    failed: "本次渲染失败，请重试",
    timeout: "渲染超时，请重试",
    cancelled: "任务已取消",
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
    styleId: STYLE_OPTIONS[0].id,
    modelFace: FACE_OPTIONS[0].id,
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
  const [comparePosition, setComparePosition] = useState(52);

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
    () => ({ "--hero-image": 'url("/images/luxury-bg.jpg")' } as CSSProperties),
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
        setComparePosition(52);
        setResult({
          resultImageUrl: primaryImageUrl,
          resultImageUrls: imageUrls,
          error: primaryImageUrl ? null : "任务完成但未返回成图地址。",
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
      setResult((prev) => ({ ...prev, error: "请先上传服装图。" }));
      return;
    }

    if (!params.garmentCategory) {
      setResult((prev) => ({ ...prev, error: "请选择衣服品类（上衣/下装/连衣裙套装）。" }));
      return;
    }

    clearPolling();
    setActiveResultIndex(0);
    setComparePosition(52);
    setResult({ resultImageUrl: null, resultImageUrls: [], error: null });
    setProcessStatus({ isGenerating: true, progress: 3, jobId: null, status: "queued" });

    try {
      const uploaded = await uploadImage(params.originalImage);
      let modelReferenceUrl: string | null = null;

      if (params.modelImage) {
        const uploadedModel = await uploadImage(params.modelImage);
        modelReferenceUrl = uploadedModel.image_url;
      }

      const categoryConfig = CATEGORY_OPTIONS.find((item) => item.id === params.garmentCategory);

      const workflowParams: Record<string, unknown> = {
        source_image_url: uploaded.image_url,
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
    <div className={`stage-shell phase-${uiPhase}`} style={stageStyle}>
      <header className="brand-bar">
        <p className="brand-kicker">THIS JUST IN. AI STUDIO</p>
        <div className="brand-row">
          <div className="brand-left">
            <span>SHOP</span>
            <span>LOOKBOOK</span>
            <span>HOW TO STYLE</span>
          </div>
          <div className="brand-center">S-IMAGE</div>
          <div className="brand-right">
            <span>JOURNAL</span>
            <span>ABOUT</span>
            <span>ACCOUNT</span>
          </div>
        </div>
      </header>

      <main className="machine-grid">
        <section className="input-stage">
          <p className="phase-chip">INPUT</p>
          <h1>YOUR VISION</h1>
          <p className="stage-copy">上传服装平铺/人台图，定义风格与品类，触发专属 AI 商拍演化。</p>

          <div className="upload-dual">
            <ImageUploader
              title="服装图"
              hint="必传"
              placeholder="上传平铺图或人台图"
              emptyNote="JPG / PNG / WEBP"
              file={params.originalImage}
              previewUrl={sourcePreviewUrl}
              disabled={processStatus.isGenerating}
              onFileSelected={handleSourceSelected}
              onValidationError={(message) => setResult((prev) => ({ ...prev, error: message }))}
            />

            <ImageUploader
              title="模特参考图"
              hint="可选"
              placeholder="上传模特参考图（可留空）"
              emptyNote="用于视觉参考与对比滑块"
              file={params.modelImage}
              previewUrl={modelPreviewUrl}
              disabled={processStatus.isGenerating}
              onFileSelected={handleModelSelected}
              onValidationError={(message) => setResult((prev) => ({ ...prev, error: message }))}
            />
          </div>

          <section className="control-block">
            <header>
              <h3>品类</h3>
              <span>必须选择</span>
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
                  <strong>{option.icon}</strong>
                  <span>{option.label}</span>
                </button>
              ))}
            </div>
          </section>

          <section className="control-block">
            <header>
              <h3>风格图腾</h3>
              <span>点击即选中</span>
            </header>

            <div className="totem-row">
              {STYLE_OPTIONS.map((option) => (
                <button
                  key={option.id}
                  type="button"
                  className={`totem-btn ${params.styleId === option.id ? "active" : ""}`}
                  disabled={processStatus.isGenerating}
                  onClick={() => setParams((prev) => ({ ...prev, styleId: option.id }))}
                >
                  <span>{option.preview}</span>
                  <small>{option.label}</small>
                </button>
              ))}
            </div>

            <div className="totem-row">
              {FACE_OPTIONS.map((option) => (
                <button
                  key={option.id}
                  type="button"
                  className={`totem-btn ${params.modelFace === option.id ? "active" : ""}`}
                  disabled={processStatus.isGenerating}
                  onClick={() => setParams((prev) => ({ ...prev, modelFace: option.id }))}
                >
                  <span>{option.preview}</span>
                  <small>{option.label}</small>
                </button>
              ))}
            </div>
          </section>

          <section className="control-block ratio-block">
            <header>
              <h3>比例</h3>
              <span>全场景覆盖</span>
            </header>
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
          </section>

          <div className="action-row">
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

        <section className="after-stage">
          <div className="state-title">{uiPhase === "instant" ? "INSTANT" : "AFTER"}</div>

          <div className={`visual-canvas ${uiPhase}`}>
            {uiPhase === "input" ? (
              <div className="input-placeholder">
                <div className="ghost-silhouette" />
                <p>等待你的输入，右侧将展示成片冲击力。</p>
              </div>
            ) : null}

            {uiPhase === "instant" ? (
              <div className="instant-layer">
                {activeResultUrl ? <img src={activeResultUrl} alt="last result" className="blur-preview" /> : null}
                <div className="instant-overlay">
                  <h2>INSTANT FITTING</h2>
                  <p>{statusToInstantLine(processStatus.status)}</p>
                  <div className="shimmer-track">
                    <span style={{ width: `${Math.max(8, processStatus.progress)}%` }} />
                  </div>
                </div>
              </div>
            ) : null}

            {uiPhase === "after" && activeResultUrl ? (
              <div className="after-layer">
                <div className="compare-frame">
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
                    <div className="compare-handle" style={{ left: `${comparePosition}%` }}>
                      <span />
                    </div>
                  ) : null}

                  <div className="after-badge">AFTER</div>
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

                <a href={activeResultUrl} target="_blank" rel="noreferrer" className="open-link">
                  查看高清原图
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
                  className={`pose-dot ${index === activeResultIndex ? "active" : ""}`}
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