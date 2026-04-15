interface ResultViewerProps {
  imageUrl: string | null;
  isGenerating: boolean;
}

export function ResultViewer({ imageUrl, isGenerating }: ResultViewerProps): JSX.Element {
  if (imageUrl) {
    return (
      <div className="result-viewer has-result">
        <img src={imageUrl} alt="Generated result" />
        <a href={imageUrl} target="_blank" rel="noreferrer">
          打开原图
        </a>
      </div>
    );
  }

  return (
    <div className={`result-viewer ${isGenerating ? "is-busy" : ""}`}>
      <p>{isGenerating ? "正在生成，请稍候..." : "提交任务后，这里会展示最终商拍图"}</p>
    </div>
  );
}
