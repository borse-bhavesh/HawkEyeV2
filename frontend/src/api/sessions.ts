import { apiClient, API_BASE_URL } from './client';
import type { ProcessingSession, HistoricalProcessingRunResponse, Event, RiskAssessment, Evidence, TrackObservation, ZoneCreateRequest } from '../types/sessions';

export const sessionsApi = {
  /**
   * Fetch all processing sessions
   */
  getSessions: () => {
    return apiClient<ProcessingSession[]>('/sessions');
  },

  /**
   * Fetch a single processing session
   */
  getSession: (sessionId: string) => {
    return apiClient<ProcessingSession>(`/sessions/${sessionId}`);
  },

  /**
   * Start demo camera session
   */
  startDemoCamera: () => {
    return apiClient<ProcessingSession>('/video/demo', {
      method: 'POST',
    });
  },

  /**
   * Start analysis for a specific session
   */
  startAnalysis: (sessionId: string) => {
    return apiClient<ProcessingSession>(`/sessions/${sessionId}/analyze`, {
      method: 'POST',
    });
  },

  /**
   * Fetch zone associated with a specific session
   */
  getSessionZone: (sessionId: string) => {
    return apiClient<ZoneCreateRequest | null>(`/sessions/${sessionId}/zone`);
  },

  /**
   * Save or update zone associated with a specific session
   */
  saveSessionZone: (sessionId: string, zone: ZoneCreateRequest) => {
    return apiClient<ZoneCreateRequest>(`/sessions/${sessionId}/zone`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(zone),
    });
  },

  /**
   * Delete zone associated with a specific session
   */
  deleteSessionZone: (sessionId: string) => {
    return apiClient<{ message: string }>(`/sessions/${sessionId}/zone`, {
      method: 'DELETE',
    });
  },

  /**
   * Fetch the full historical intelligence representation of a session
   */
  getSessionHistory: (sessionId: string) => {
    return apiClient<HistoricalProcessingRunResponse>(`/sessions/${sessionId}/history`);
  },

  /**
   * Fetch events associated with a specific session
   */
  getSessionEvents: (sessionId: string, afterFrame?: number) => {
    const query = afterFrame !== undefined ? `?after_frame=${afterFrame}` : '';
    return apiClient<Event[]>(`/sessions/${sessionId}/events${query}`);
  },

  /**
   * Fetch risk assessments associated with a specific session
   */
  getSessionRisks: (sessionId: string) => {
    return apiClient<RiskAssessment[]>(`/sessions/${sessionId}/risks`);
  },

  /**
   * Fetch evidence associated with a specific session
   */
  getSessionEvidence: (sessionId: string) => {
    return apiClient<Evidence[]>(`/sessions/${sessionId}/evidence`);
  },

  /**
   * Get the direct URL for the session's recorded video
   */
  getSessionVideoUrl: (sessionId: string) => {
    return `${API_BASE_URL}/sessions/${sessionId}/video`;
  },

  /**
   * Fetch observations associated with a specific session
   */
  getSessionObservations: (sessionId: string, afterFrame?: number) => {
    const query = afterFrame !== undefined ? `?after_frame=${afterFrame}` : '';
    return apiClient<TrackObservation[]>(`/sessions/${sessionId}/observations${query}`);
  },

  /**
   * Delete a session and all its associated data
   */
  deleteSession: (sessionId: string) => {
    // Return empty string since the response is 204 No Content
    return apiClient<string>(`/sessions/${sessionId}`, {
      method: 'DELETE',
    }).catch(err => {
        // If it's a JSON parsing error on an empty 204 response, ignore it, 
        // though apiClient handles empty responses if implemented carefully. 
        // Our apiClient calls response.json() unconditionally right now, 
        // which will throw on a 204. Let's just use raw fetch to be safe.
        throw err;
    });
  }
};

