import { useCallback, useRef, useState } from "react";
import { UploadCloud, FileVideo, X } from "lucide-react";

export default function Dropzone({ files, setFiles, disabled }) {
  const inputRef = useRef(null);
  const [drag, setDrag] = useState(false);

  const addFiles = useCallback(
    (list) => {
      const accepted = Array.from(list).filter((f) =>
        /\.(mp4|mov|m4v)$/i.test(f.name)
      );
      setFiles((prev) => [...prev, ...accepted]);
    },
    [setFiles]
  );

  const onDrop = (e) => {
    e.preventDefault();
    setDrag(false);
    if (disabled) return;
    addFiles(e.dataTransfer.files);
  };

  const onPick = (e) => {
    if (e.target.files) addFiles(e.target.files);
    e.target.value = "";
  };

  return (
    <div>
      <div
        data-testid="dropzone"
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabled) setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={onDrop}
        onClick={() => !disabled && inputRef.current?.click()}
        className={
          "group relative cursor-pointer rounded-2xl border-2 border-dashed p-10 transition-all " +
          (drag
            ? "border-[#e6bb77] bg-[#e6bb77]/10"
            : "border-[#c29d5f]/30 hover:border-[#c29d5f]/60 bg-[#1a140c]/40") +
          (disabled ? " opacity-50 pointer-events-none" : "")
        }
      >
        <input
          ref={inputRef}
          type="file"
          accept="video/mp4,video/quicktime,.mp4,.mov,.m4v"
          multiple
          className="hidden"
          onChange={onPick}
          data-testid="dropzone-input"
        />
        <div className="flex flex-col items-center text-center gap-3">
          <UploadCloud className="w-10 h-10 text-[#e6bb77]" />
          <div className="text-[#f4ede3]">
            <span className="text-lg">Drop MP4 files here</span>
            <span className="text-[#8a7f6d]"> or click to select</span>
          </div>
          <div
            className="text-xs text-[#8a7f6d]"
            style={{ fontFamily: "'JetBrains Mono', monospace" }}
          >
            mp4 · mov · up to 200 MB per file · unlimited clips
          </div>
        </div>
      </div>

      {files.length > 0 && (
        <ul className="mt-4 space-y-2" data-testid="dropzone-file-list">
          {files.map((f, i) => (
            <li
              key={i}
              className="flex items-center gap-3 p-3 rounded-lg bg-[#1a140c]/80 border border-[#c29d5f]/20"
            >
              <FileVideo className="w-4 h-4 text-[#e6bb77]" />
              <div className="flex-1 min-w-0">
                <div className="text-sm truncate text-[#f4ede3]">{f.name}</div>
                <div
                  className="text-xs text-[#8a7f6d]"
                  style={{ fontFamily: "'JetBrains Mono', monospace" }}
                >
                  {(f.size / (1024 * 1024)).toFixed(1)} MB
                </div>
              </div>
              <button
                type="button"
                data-testid={`dropzone-remove-${i}`}
                onClick={(e) => {
                  e.stopPropagation();
                  setFiles(files.filter((_, j) => j !== i));
                }}
                className="text-[#8a7f6d] hover:text-[#e6bb77] p-1"
              >
                <X className="w-4 h-4" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
