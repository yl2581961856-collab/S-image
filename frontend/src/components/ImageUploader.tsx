import { useMemo } from "react";
import { useDropzone } from "react-dropzone";

interface ImageUploaderProps {
  label: string;
  requiredTag?: string;
  prompt: string;
  file: File | null;
  previewUrl: string | null;
  disabled?: boolean;
  onFileSelected: (file: File) => void;
  onValidationError: (message: string) => void;
}

export function ImageUploader({
  label,
  requiredTag,
  prompt,
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
        onValidationError("Upload failed. Please retry.");
        return;
      }

      const reason = first.errors[0]?.code;
      if (reason === "file-invalid-type") {
        onValidationError("Only JPG / PNG / WEBP are supported.");
        return;
      }
      onValidationError("File does not meet upload requirements. Please check and retry.");
    },
  });

  return (
    <section className="upload-minimal">
      <header>
        <h3>{requiredTag ? `${label} (${requiredTag})` : label}</h3>
      </header>

      <div
        {...getRootProps()}
        className={`upload-zone ${isDragActive ? "drag-active" : ""} ${disabled ? "disabled" : ""}`}
      >
        <input {...getInputProps()} />
        {previewUrl ? (
          <img src={previewUrl} alt={`${label} preview`} className="upload-thumb" />
        ) : (
          <div className="upload-empty">
            <p>{prompt}</p>
            <small>{file ? file.name : "NO FILE SELECTED"}</small>
          </div>
        )}
      </div>
    </section>
  );
}
