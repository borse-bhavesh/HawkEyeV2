import { apiClient } from './client';
import type { AsyncVideoProcessingResponse } from '../types/video';

export async function uploadVideo(file: File): Promise<AsyncVideoProcessingResponse> {
  const formData = new FormData();
  formData.append('file', file);

  return apiClient<AsyncVideoProcessingResponse>('/video/upload', {
    method: 'POST',
    body: formData,
  });
}
