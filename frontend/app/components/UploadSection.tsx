'use client';

import { useState } from 'react';

interface UploadFile {
  id: string;
  name: string;
  size: string;
  status: 'pending' | 'uploading' | 'completed' | 'error';
  progress: number;
}

export default function UploadSection() {
  const [files, setFiles] = useState<UploadFile[]>([]);
  const [isDragging, setIsDragging] = useState(false);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const droppedFiles = Array.from(e.dataTransfer.files);
    addFiles(droppedFiles);
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      addFiles(Array.from(e.target.files));
    }
  };

  const addFiles = (newFiles: File[]) => {
    const uploadedFiles: UploadFile[] = newFiles.map((file, index) => ({
      id: `${Date.now()}-${index}`,
      name: file.name,
      size: formatFileSize(file.size),
      status: 'pending',
      progress: 0,
    }));
    setFiles((prev) => [...prev, ...uploadedFiles]);
    // Simulate upload progress
    uploadedFiles.forEach((file) => {
      simulateUpload(file.id);
    });
  };

  const simulateUpload = (fileId: string) => {
    let progress = 0;
    const interval = setInterval(() => {
      progress += Math.random() * 30;
      if (progress >= 100) {
        progress = 100;
        clearInterval(interval);
        setFiles((prev) =>
          prev.map((f) =>
            f.id === fileId ? { ...f, status: 'completed', progress: 100 } : f
          )
        );
      } else {
        setFiles((prev) =>
          prev.map((f) =>
            f.id === fileId ? { ...f, status: 'uploading', progress } : f
          )
        );
      }
    }, 500);
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
  };

  const removeFile = (fileId: string) => {
    setFiles((prev) => prev.filter((f) => f.id !== fileId));
  };

  return (
    <div className="bg-white rounded-xl shadow-md p-8">
      <h2 className="text-2xl font-bold text-slate-900 mb-2">Upload Assessment Materials</h2>
      <p className="text-slate-600 mb-6">Upload student responses, datasets, or assessment files</p>

      {/* Upload Area */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`border-2 border-dashed rounded-lg p-12 text-center transition-all ${
          isDragging
            ? 'border-blue-500 bg-blue-50'
            : 'border-slate-300 hover:border-slate-400'
        }`}
      >
        <div className="flex flex-col items-center gap-4">
          <div className="text-5xl">📤</div>
          <div>
            <p className="text-lg font-semibold text-slate-900 mb-1">
              Drag and drop files here
            </p>
            <p className="text-sm text-slate-600 mb-4">or click to browse</p>
          </div>
          <label className="cursor-pointer">
            <input
              type="file"
              multiple
              onChange={handleFileInput}
              className="hidden"
              accept=".pdf,.doc,.docx,.xlsx,.csv,.txt"
            />
            <span className="px-6 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors font-medium">
              Select Files
            </span>
          </label>
          <p className="text-xs text-slate-500 mt-2">
            Supported: PDF, DOC, DOCX, XLSX, CSV, TXT
          </p>
        </div>
      </div>

      {/* File List */}
      {files.length > 0 && (
        <div className="mt-8">
          <h3 className="text-lg font-semibold text-slate-900 mb-4">
            Uploaded Files ({files.length})
          </h3>
          <div className="space-y-3">
            {files.map((file) => (
              <div
                key={file.id}
                className="flex items-center justify-between p-4 bg-slate-50 rounded-lg border border-slate-200 hover:border-slate-300 transition-colors"
              >
                <div className="flex items-center gap-4 flex-1">
                  <div className="text-2xl">📄</div>
                  <div className="flex-1">
                    <p className="font-medium text-slate-900 truncate">{file.name}</p>
                    <p className="text-sm text-slate-600">{file.size}</p>
                  </div>
                </div>

                <div className="flex items-center gap-4">
                  {file.status === 'uploading' && (
                    <div className="w-32">
                      <div className="w-full bg-slate-200 rounded-full h-2">
                        <div
                          className="bg-blue-500 h-2 rounded-full transition-all"
                          style={{ width: `${file.progress}%` }}
                        />
                      </div>
                      <p className="text-xs text-slate-600 mt-1 text-right">
                        {Math.round(file.progress)}%
                      </p>
                    </div>
                  )}
                  {file.status === 'completed' && (
                    <span className="text-green-600 font-semibold">✓ Done</span>
                  )}
                  {file.status === 'pending' && (
                    <span className="text-slate-500 text-sm">Pending...</span>
                  )}
                  <button
                    onClick={() => removeFile(file.id)}
                    className="text-red-500 hover:text-red-700 font-bold text-lg transition-colors"
                  >
                    ✕
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
