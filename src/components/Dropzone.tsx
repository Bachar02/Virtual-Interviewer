import { useCallback } from "react";
import { useDropzone } from "react-dropzone";

export default function Dropzone({ onFile }: { onFile: (f: File) => void }) {
  const onDrop = useCallback(
    (files: File[]) => files.length && onFile(files[0]),
    [onFile]
  );
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "application/pdf": [] },
    maxFiles: 1,
  });

  return (
    <div
      {...getRootProps()}
      className={`p-6 border-2 border-dashed rounded cursor-pointer transition
        ${isDragActive ? "border-sky-400 bg-slate-700" : "border-slate-600"}`}
    >
      <input {...getInputProps()} />
      {isDragActive ? "Drop the PDF here…" : "Drag & drop or click to select PDF"}
    </div>
  );
}