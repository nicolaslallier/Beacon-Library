import {
  BookOpen,
  CheckCircle,
  FolderOpen,
  Loader2,
  Upload,
  XCircle,
  ExternalLink,
} from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { RequireAuth } from "../hooks/useAuth";
import {
  listLibraries,
  uploadFile,
  type Library,
  type UploadProgress,
} from "../services/files";

interface UploadStatus {
  file: File;
  status: "pending" | "uploading" | "success" | "error";
  progress: number;
  error?: string;
}

function CatalogContent() {
  const navigate = useNavigate();
  const [libraries, setLibraries] = useState<Library[]>([]);
  const [selectedLibraryId, setSelectedLibraryId] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [uploads, setUploads] = useState<Map<string, UploadStatus>>(new Map());
  const [isDragging, setIsDragging] = useState(false);

  useEffect(() => {
    loadLibraries();
  }, []);

  const loadLibraries = async () => {
    try {
      const response = await listLibraries();
      setLibraries(response.items);
      if (response.items.length > 0 && !selectedLibraryId) {
        setSelectedLibraryId(response.items[0].id);
      }
    } catch (error) {
      console.error("Failed to load libraries:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleFileSelect = async (files: FileList | null) => {
    if (!files || files.length === 0 || !selectedLibraryId) return;

    const fileArray = Array.from(files);

    // Initialize upload status for each file
    const newUploads = new Map(uploads);
    fileArray.forEach((file) => {
      newUploads.set(file.name, {
        file,
        status: "pending",
        progress: 0,
      });
    });
    setUploads(newUploads);

    // Upload files sequentially
    for (const file of fileArray) {
      await uploadSingleFile(file);
    }
  };

  const uploadSingleFile = async (file: File) => {
    const updateStatus = (status: Partial<UploadStatus>) => {
      setUploads((prev) => {
        const newMap = new Map(prev);
        const current = newMap.get(file.name);
        if (current) {
          newMap.set(file.name, { ...current, ...status });
        }
        return newMap;
      });
    };

    try {
      updateStatus({ status: "uploading", progress: 0 });

      await uploadFile(selectedLibraryId, file, {
        onProgress: (progress: UploadProgress) => {
          updateStatus({ progress: progress.percent });
        },
        onConflict: async () => {
          // Auto-rename on conflict for catalog uploads
          return "rename";
        },
        onDuplicate: "rename",
      });

      updateStatus({ status: "success", progress: 100 });
    } catch (error) {
      console.error("Upload failed:", error);
      updateStatus({
        status: "error",
        error: error instanceof Error ? error.message : "Upload failed",
      });
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    handleFileSelect(e.dataTransfer.files);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const clearUploads = () => {
    setUploads(new Map());
  };

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex items-center justify-center">
          <Loader2 className="w-8 h-8 animate-spin text-indigo-600" />
        </div>
      </div>
    );
  }

  if (libraries.length === 0) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="text-center max-w-md mx-auto">
          <div className="w-16 h-16 bg-indigo-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <FolderOpen className="w-8 h-8 text-indigo-600" />
          </div>
          <h1 className="text-2xl font-bold text-gray-900 mb-2">
            No Libraries
          </h1>
          <p className="text-gray-600 mb-6">
            Create a library first to upload files.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-12 h-12 bg-indigo-100 rounded-lg flex items-center justify-center">
            <BookOpen className="w-6 h-6 text-indigo-600" />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Catalog</h1>
            <p className="text-gray-600">Upload files to your libraries</p>
          </div>
        </div>
      </div>

      {/* Library Selection */}
      <div className="mb-6">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Select Library
        </label>
        <select
          value={selectedLibraryId}
          onChange={(e) => setSelectedLibraryId(e.target.value)}
          className="block w-full max-w-md rounded-lg border border-gray-300 px-4 py-2 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
        >
          {libraries.map((lib) => (
            <option key={lib.id} value={lib.id}>
              {lib.name} ({lib.file_count} files)
            </option>
          ))}
        </select>
      </div>

      {/* Upload Area */}
      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        className={`border-2 border-dashed rounded-lg p-12 text-center transition-colors ${
          isDragging
            ? "border-indigo-500 bg-indigo-50"
            : "border-gray-300 hover:border-gray-400"
        }`}
      >
        <Upload
          className={`w-12 h-12 mx-auto mb-4 ${
            isDragging ? "text-indigo-600" : "text-gray-400"
          }`}
        />
        <p className="text-lg font-medium text-gray-900 mb-2">
          Drop files here or click to browse
        </p>
        <p className="text-sm text-gray-600 mb-4">
          Upload files to{" "}
          {libraries.find((l) => l.id === selectedLibraryId)?.name}
        </p>
        <input
          type="file"
          multiple
          onChange={(e) => handleFileSelect(e.target.files)}
          className="hidden"
          id="file-input"
        />
        <label
          htmlFor="file-input"
          className="inline-flex items-center gap-2 px-6 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 cursor-pointer transition-colors"
        >
          <Upload className="w-5 h-5" />
          Select Files
        </label>
      </div>

      {/* Upload Progress */}
      {uploads.size > 0 && (
        <div className="mt-8">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900">
              Uploads ({uploads.size})
            </h2>
            <div className="flex items-center gap-3">
              {selectedLibraryId && Array.from(uploads.values()).some(u => u.status === 'success') && (
                <button
                  onClick={() => navigate(`/libraries/${selectedLibraryId}`)}
                  className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
                >
                  <ExternalLink className="w-4 h-4" />
                  View Files
                </button>
              )}
              <button
                onClick={clearUploads}
                className="text-sm text-gray-600 hover:text-gray-900"
              >
                Clear
              </button>
            </div>
          </div>
          <div className="space-y-3">
            {Array.from(uploads.values()).map((upload) => (
              <div
                key={upload.file.name}
                className="bg-white rounded-lg border border-gray-200 p-4"
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-3 flex-1 min-w-0">
                    {upload.status === "uploading" && (
                      <Loader2 className="w-5 h-5 animate-spin text-indigo-600 flex-shrink-0" />
                    )}
                    {upload.status === "success" && (
                      <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0" />
                    )}
                    {upload.status === "error" && (
                      <XCircle className="w-5 h-5 text-red-600 flex-shrink-0" />
                    )}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-900 truncate">
                        {upload.file.name}
                      </p>
                      <p className="text-xs text-gray-500">
                        {(upload.file.size / 1024 / 1024).toFixed(2)} MB
                      </p>
                    </div>
                  </div>
                  <div className="text-right ml-4">
                    {upload.status === "uploading" && (
                      <span className="text-sm font-medium text-indigo-600">
                        {upload.progress}%
                      </span>
                    )}
                    {upload.status === "success" && (
                      <span className="text-sm font-medium text-green-600">
                        Complete
                      </span>
                    )}
                    {upload.status === "error" && (
                      <span className="text-sm font-medium text-red-600">
                        Failed
                      </span>
                    )}
                  </div>
                </div>
                {upload.status === "uploading" && (
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div
                      className="bg-indigo-600 h-2 rounded-full transition-all duration-300"
                      style={{ width: `${upload.progress}%` }}
                    />
                  </div>
                )}
                {upload.status === "error" && upload.error && (
                  <p className="text-xs text-red-600 mt-1">{upload.error}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function Catalog() {
  // Check if auth is enabled
  const enableAuth = import.meta.env.VITE_ENABLE_AUTH === "true";

  if (enableAuth) {
    return (
      <RequireAuth>
        <CatalogContent />
      </RequireAuth>
    );
  }

  // Without auth, just render the content directly
  return <CatalogContent />;
}
