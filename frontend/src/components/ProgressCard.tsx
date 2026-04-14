import type { JobStatus } from "../types/api";

interface ProgressCardProps {
  status: JobStatus | null;
  progress: number;
  jobId: string | null;
}

const statusText: Record<JobStatus, string> = {
  queued: "队列中",
  running: "生成中",
  postprocessing: "后处理",
  succeeded: "已完成",
  failed: "失败",
  timeout: "超时",
  cancelled: "已取消",
};

export function ProgressCard({ status, progress, jobId }: ProgressCardProps): JSX.Element {
  return (
    <div className="progress-card">
      <div className="progress-meta">
        <div>
          <strong>{status ? statusText[status] : "未开始"}</strong>
          <p>{jobId ? `JobId: ${jobId}` : "等待提交"}</p>
        </div>
        <span>{Math.round(progress)}%</span>
      </div>
      <div className="progress-track">
        <div className="progress-fill" style={{ width: `${Math.max(0, Math.min(progress, 100))}%` }} />
      </div>
    </div>
  );
}
