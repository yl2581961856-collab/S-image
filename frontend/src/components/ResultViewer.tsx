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
      <p>{isGenerating ? "AI 正在打磨你的专属商拍图，请稍候..." : "完成参数选择后，成图会展示在这里"}</p>
    </div>
  );
}
