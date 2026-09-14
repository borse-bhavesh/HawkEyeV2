import React, { useState, useRef, useEffect } from 'react';
import { Upload, X, FileVideo, AlertCircle, Loader2 } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { uploadVideo } from '@/api/video';
import type { AsyncVideoProcessingResponse } from '@/types/video';
import { useNavigate } from 'react-router-dom';

const ALLOWED_EXTENSIONS = [".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm"];

export default function VideoUpload() {
  const navigate = useNavigate();

  const [file, setFile] = useState<File | null>(null);
  const [uploadState, setUploadState] = useState<'IDLE' | 'FILE_SELECTED' | 'UPLOADING' | 'SUCCESS' | 'ERROR'>(
    'IDLE'
  );
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [result, setResult] = useState<AsyncVideoProcessingResponse | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (result?.session_id && uploadState === 'SUCCESS') {
      navigate(`/history/${result.session_id}`);
    }
  }, [result?.session_id, uploadState, navigate]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (!selected) return;

    setErrorMsg(null);
    setResult(null);

    // Validation
    if (selected.size === 0) {
      setErrorMsg('The selected file is empty.');
      setUploadState('ERROR');
      return;
    }

    const ext = selected.name.substring(selected.name.lastIndexOf('.')).toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      setErrorMsg(`Unsupported file extension. Allowed: ${ALLOWED_EXTENSIONS.join(', ')}`);
      setUploadState('ERROR');
      return;
    }

    setFile(selected);
    setUploadState('FILE_SELECTED');
  };

  const handleUpload = async () => {
    if (!file) return;

    setUploadState('UPLOADING');
    setErrorMsg(null);

    try {
      const response = await uploadVideo(file);
      setResult(response);
      setUploadState('SUCCESS');
    } catch (err: any) {
      const message = err.message || 'Unknown error';
      if (message.includes('413')) {
        setErrorMsg('Video exceeds the maximum upload size.');
      } else if (message.includes('422')) {
        setErrorMsg('The selected file could not be read as a valid video.');
      } else if (message.includes('400')) {
        setErrorMsg('Please select a supported video file or valid request.');
      } else if (message.includes('500')) {
        setErrorMsg('Video processing could not be started. Please try again.');
      } else {
        setErrorMsg('Upload failed. Please check your connection and try again.');
      }
      setUploadState('ERROR');
    }
  };

  const handleClear = () => {
    setFile(null);
    setErrorMsg(null);
    setResult(null);
    setUploadState('IDLE');
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const formatSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  return (
    <Card className="bg-card/50 border-border shrink-0">
      <CardHeader className="pb-3 border-b border-border/50">
        <CardTitle className="text-lg font-semibold flex items-center gap-2">
          <Upload className="w-5 h-5 text-blue-500" />
          Recorded Video Analysis
        </CardTitle>
        <p className="text-sm text-muted-foreground mt-1">
          Upload CCTV footage for offline analysis
        </p>
      </CardHeader>
      <CardContent className="p-6">
        {uploadState === 'SUCCESS' ? (
          <div className="flex flex-col items-center justify-center p-8 space-y-4">
            <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
            <p className="text-muted-foreground">Preparing workspace...</p>
          </div>
        ) : (
          <div className="space-y-6">
            {/* File Dropzone / Selector */}
            <div 
              className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
                uploadState === 'UPLOADING' ? 'border-border/50 opacity-50 cursor-not-allowed' : 'border-border hover:border-blue-500/50 cursor-pointer'
              }`}
              onClick={() => {
                if (uploadState !== 'UPLOADING') {
                  fileInputRef.current?.click();
                }
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  if (uploadState !== 'UPLOADING') {
                    fileInputRef.current?.click();
                  }
                }
              }}
              tabIndex={uploadState === 'UPLOADING' ? -1 : 0}
              role="button"
              aria-label="Select Video"
            >
              <input
                type="file"
                ref={fileInputRef}
                className="hidden"
                accept={ALLOWED_EXTENSIONS.join(',')}
                onChange={handleFileChange}
                disabled={uploadState === 'UPLOADING'}
                aria-label="Hidden File Input"
              />
              <div className="flex flex-col items-center justify-center gap-3">
                <div className="w-12 h-12 rounded-full bg-blue-500/10 flex items-center justify-center text-blue-500 mb-2">
                  <Upload className="w-6 h-6" />
                </div>
                <h4 className="text-sm font-semibold">Select recorded footage</h4>
                <p className="text-xs text-muted-foreground">
                  Supports MP4, AVI, MKV, MOV (up to system limits)
                </p>
              </div>
            </div>

            {/* Selected File / Error Info */}
            {(file || errorMsg) && (
              <div className="flex flex-col gap-4">
                {file && (
                  <div className="flex items-center justify-between p-3 bg-background/50 border border-border/50 rounded-md">
                    <div className="flex items-center gap-3 overflow-hidden">
                      <FileVideo className="w-5 h-5 text-blue-400 shrink-0" />
                      <div className="flex flex-col overflow-hidden">
                        <span className="text-sm font-medium truncate">{file.name}</span>
                        <span className="text-xs text-muted-foreground">{formatSize(file.size)}</span>
                      </div>
                    </div>
                    {uploadState !== 'UPLOADING' && (
                      <Button variant="ghost" size="icon" className="shrink-0 h-8 w-8 text-muted-foreground hover:text-red-400" onClick={(e) => { e.stopPropagation(); handleClear(); }} aria-label="Clear selection">
                        <X className="w-4 h-4" />
                      </Button>
                    )}
                  </div>
                )}
                
                {errorMsg && (
                  <div className="flex items-start gap-2 p-3 bg-red-500/10 border border-red-500/20 text-red-400 rounded-md text-sm">
                    <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
                    <p>{errorMsg}</p>
                  </div>
                )}

                <div className="flex justify-end pt-2">
                  <Button 
                    onClick={handleUpload} 
                    disabled={!file || uploadState === 'UPLOADING'}
                    className="min-w-[140px]"
                  >
                    {uploadState === 'UPLOADING' ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        Uploading...
                      </>
                    ) : (
                      'Analyze Recording'
                    )}
                  </Button>
                </div>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
