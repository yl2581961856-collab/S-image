import { useMemo } from "react";
import { useDropzone } from "react-dropzone";

interface ImageUploaderProps {
  file: File | null;
  previewUrl: string | null;
  disabled?: boolean;
  onFileSelected: (file: File) => void;
  onValidationError: (message: string) => void;
}

export function ImageUploader({
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
        onValidationError("文件上传失败，请重试。");
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
    <section className="panel-block">
      <header className="block-head">
        <h3>上传源图</h3>
        <span>支持拖拽与点击上传</span>
      </header>
      <div
        {...getRootProps()}
        className={`uploader ${isDragActive ? "drag-active" : ""} ${disabled ? "disabled" : ""}`}
      >
        <input {...getInputProps()} />
        {previewUrl ? (
          <div className="uploader-preview">
            <img src={previewUrl} alt="Source preview" />
          </div>
        ) : (
          <div className="uploader-empty">
            <p>将图片拖拽到此处，或点击选择文件</p>
            <small>JPG / PNG / WEBP</small>
          </div>
        )}
      </div>
      <footer className="uploader-footer">
        {file ? <span>{file.name}</span> : <span>尚未选择文件</span>}
      </footer>
    </section>
  );
}
