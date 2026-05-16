"use client";
import { useState, useRef } from "react";
import { FileText, Upload, GitCompare, Loader2 } from "lucide-react";
import { summarizeDocument, compareDocuments } from "@/lib/api";

type Mode = "summarize" | "compare";

function DropZone({
  label,
  file,
  onFile,
}: {
  label: string;
  file: File | null;
  onFile: (f: File) => void;
}) {
  const ref = useRef<HTMLInputElement>(null);
  return (
    <div
      onClick={() => ref.current?.click()}
      className="border-2 border-dashed border-gray-200 rounded-xl p-8 text-center cursor-pointer hover:border-blue-400 hover:bg-blue-50 transition-colors"
    >
      <input
        ref={ref}
        type="file"
        accept=".pdf"
        className="hidden"
        onChange={(e) => e.target.files?.[0] && onFile(e.target.files[0])}
      />
      <Upload size={24} className="mx-auto text-gray-400 mb-2" />
      <p className="text-sm font-medium text-gray-600">{label}</p>
      {file ? (
        <p className="text-xs text-blue-600 mt-1 font-medium">{file.name}</p>
      ) : (
        <p className="text-xs text-gray-400 mt-1">Click to browse or drop a PDF</p>
      )}
    </div>
  );
}

function ResultBox({ title, text }: { title: string; text: string }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-2">
      <p className="text-sm font-semibold text-gray-700">{title}</p>
      <div className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed max-h-[600px] overflow-y-auto">
        {text}
      </div>
    </div>
  );
}

export default function DocumentsPage() {
  const [mode, setMode] = useState<Mode>("summarize");
  const [fileA, setFileA] = useState<File | null>(null);
  const [fileB, setFileB] = useState<File | null>(null);
  const [result, setResult] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reset = () => {
    setFileA(null);
    setFileB(null);
    setResult(null);
    setError(null);
  };

  const handleModeChange = (m: Mode) => {
    setMode(m);
    reset();
  };

  const handleSubmit = async () => {
    setError(null);
    setResult(null);
    if (mode === "summarize" && !fileA) return;
    if (mode === "compare" && (!fileA || !fileB)) return;
    setLoading(true);
    try {
      if (mode === "summarize") {
        const data = await summarizeDocument(fileA!);
        setResult(data.summary);
      } else {
        const data = await compareDocuments(fileA!, fileB!);
        setResult(data.comparison);
      }
    } catch {
      setError("Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const canSubmit =
    !loading &&
    (mode === "summarize" ? !!fileA : !!(fileA && fileB));

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="text-xl font-semibold text-gray-800">Document Assistant</h1>
        <p className="text-sm text-gray-500 mt-0.5">
          Upload a policy PDF to get a plain-language summary, or compare two policies side by side.
        </p>
      </div>

      <div className="flex gap-2">
        <button
          onClick={() => handleModeChange("summarize")}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            mode === "summarize"
              ? "bg-blue-600 text-white"
              : "bg-white border border-gray-200 text-gray-600 hover:bg-gray-50"
          }`}
        >
          <FileText size={15} />
          Summarize
        </button>
        <button
          onClick={() => handleModeChange("compare")}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            mode === "compare"
              ? "bg-blue-600 text-white"
              : "bg-white border border-gray-200 text-gray-600 hover:bg-gray-50"
          }`}
        >
          <GitCompare size={15} />
          Compare Two Policies
        </button>
      </div>

      {mode === "summarize" ? (
        <DropZone label="Upload Policy PDF" file={fileA} onFile={setFileA} />
      ) : (
        <div className="grid grid-cols-2 gap-4">
          <DropZone label="Policy A" file={fileA} onFile={setFileA} />
          <DropZone label="Policy B" file={fileB} onFile={setFileB} />
        </div>
      )}

      <button
        onClick={handleSubmit}
        disabled={!canSubmit}
        className="flex items-center gap-2 px-5 py-2.5 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {loading ? (
          <>
            <Loader2 size={15} className="animate-spin" />
            Analyzing...
          </>
        ) : (
          <>
            <FileText size={15} />
            {mode === "summarize" ? "Summarize Document" : "Compare Policies"}
          </>
        )}
      </button>

      {error && <p className="text-sm text-red-500">{error}</p>}

      {result && (
        <ResultBox
          title={mode === "summarize" ? `Summary — ${fileA?.name}` : `Comparison — ${fileA?.name} vs ${fileB?.name}`}
          text={result}
        />
      )}
    </div>
  );
}
