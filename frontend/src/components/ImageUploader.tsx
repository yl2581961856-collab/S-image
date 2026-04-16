import { useMemo } from "react";
import { useDropzone } from "react-dropzone";

interface ImageUploaderProps {
  title: string;
  hint?: string;
  placeholder: string;
  emptyNote?: string;
  file: File | null;
  previewUrl: string | null;
  disabled?: boolean;
  onFileSelected: (file: File) => void;
  onValidationError: (message: string) => void;
}

export function ImageUploader({
  title,
  hint,
  placeholder,
  emptyNote,
  file,
  previewUrl,
  disabled = false,
  onFileSelected,
  onValidationError,
}: ImageUploaderProps): JSX.Element {
  const accept = useMemo(
    () => ({
      "image/jpeg": [".jpg", ".jpeg"],
      "image/png": [".png"],
      "image/webp": [".webp"],
    }),
    [],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept,
    maxFiles: 1,
    multiple: false,
    disabled,
    onDropAccepted(files) {
      onFileSelected(files[0]);
    },
    onDropRejected(rejections) {
      const first = rejections[0];
      if (!first) {
        onValidationError("上传失败，请重试。");
        return;
      }

      const reason = first.errors[0]?.code;
      if (reason === "file-invalid-type") {
        onValidationError("仅支持 JPG / PNG / WEBP 图片。");
        return;
      }
      onValidationError("文件不符合上传要求，请检查后重试。");
    },
  });

  return (
    <section className="upload-card">
      <header className="upload-head">
        <h3>{title}</h3>
        {hint ? <span>{hint}</span> : null}
      </header>

      <div
        {...getRootProps()}
        className={`upload-dropzone ${isDragActive ? "drag-active" : ""} ${disabled ? "disabled" : ""}`}
      >
        <input {...getInputProps()} />
        {previewUrl ? (
          <div className="upload-preview">
            <img src={previewUrl} alt={`${title} preview`} />
          </div>
        ) : (
          <div className="upload-empty">
            <p>{placeholder}</p>
            <small>{emptyNote ?? "拖拽或点击上传"}</small>
          </div>
        )}
      </div>

      <footer className="upload-meta">{file ? file.name : "未选择文件"}</footer>
    </section>
  );
}