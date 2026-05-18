"use client";

import { useState, useRef } from "react";
import { motion } from "framer-motion";
import { Upload, File, X, CheckCircle2, AlertCircle, Loader2 } from "lucide-react";

interface FileUploadProps {
  onAnalyze: (file: File) => void;
  isLoading: boolean;
}

export default function FileUpload({ onAnalyze, isLoading }: FileUploadProps) {
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
    }
  };

  const onDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const onDragLeave = () => {
    setIsDragging(false);
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setFile(e.dataTransfer.files[0]);
    }
  };

  const clearFile = () => {
    setFile(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  return (
    <div className="w-full max-w-xl">
      {!file ? (
        <motion.div
          onClick={() => fileInputRef.current?.click()}
          onDragOver={onDragOver}
          onDragLeave={onDragLeave}
          onDrop={onDrop}
          whileHover={{ scale: 1.01 }}
          whileTap={{ scale: 0.99 }}
          className={`
            relative cursor-pointer rounded-3xl border-2 border-dashed p-12 transition-all duration-300
            ${isDragging 
              ? "border-primary bg-primary/5 shadow-2xl shadow-primary/10" 
              : "border-border hover:border-primary/50 hover:bg-muted/30"}
          `}
        >
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileChange}
            className="hidden"
            accept=".html,.htm,.csv,.xlsx"
          />
          <div className="flex flex-col items-center justify-center text-center">
            <div className="mb-4 rounded-2xl bg-primary/10 p-4 text-primary">
              <Upload className="h-8 w-8" />
            </div>
            <h3 className="mb-1 text-lg font-bold">Upload Backtest Report</h3>
            <p className="text-sm text-muted-foreground">
              Drag & drop MT4/MT5 HTML, CSV, or XLSX history
            </p>
          </div>
        </motion.div>
      ) : (
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="glass-strong rounded-3xl p-6 border border-white/5 shadow-2xl"
        >
          <div className="flex items-center gap-4">
            <div className="rounded-2xl bg-primary/10 p-4 text-primary">
              <File className="h-6 w-6" />
            </div>
            <div className="flex-1 overflow-hidden">
              <p className="truncate font-bold text-foreground">{file.name}</p>
              <p className="text-xs text-muted-foreground">
                {(file.size / 1024).toFixed(1)} KB
              </p>
            </div>
            <button
              onClick={clearFile}
              disabled={isLoading}
              className="rounded-xl p-2 text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          <motion.button
            onClick={() => onAnalyze(file)}
            disabled={isLoading}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            className={`
              mt-6 w-full rounded-2xl py-4 font-black uppercase tracking-widest text-sm transition-all
              ${isLoading 
                ? "bg-muted text-muted-foreground cursor-not-allowed" 
                : "gradient-primary text-white shadow-lg shadow-primary/30 hover:glow"}
            `}
          >
            {isLoading ? (
              <div className="flex items-center justify-center gap-3">
                <Loader2 className="h-4 w-4 animate-spin" />
                Auditing Data...
              </div>
            ) : (
              "Start Institutional Audit"
            )}
          </motion.button>
        </motion.div>
      )}
    </div>
  );
}
