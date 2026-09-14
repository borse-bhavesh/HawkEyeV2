export interface ProcessingSession {
  session_id: string;
  source_id: string;
  source_type: string;
  status: string;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  restricted_zone?: any;
  processed_until_timestamp?: number;
}

export interface Track {
  id: string;
  processing_session_id: string;
  session_track_id: number;
  class_id: number | null;
  class_name: string | null;
  confidence: number | null;
  latest_bbox: Record<string, any> | null;
}

export interface TrackObservation {
  processing_session_id: string;
  track_id: string;
  frame_number: number;
  timestamp_seconds: number;
  class_name: string | null;
  confidence: number | null;
  bbox_x1: number;
  bbox_y1: number;
  bbox_x2: number;
  bbox_y2: number;
}

export interface Event {
  event_id: string;
  event_type: string;
  frame_number: number;
  timestamp_seconds: number;
  description: string;
  track_id: number | null;
  evidence: Record<string, any>;
}

export interface RiskAssessmentEvidence {
  source_type: string;
  policy_identifier: string;
  contributing_event_ids: string[];
  contributing_event_types: string[];
  explanation: string;
  details: Record<string, any>;
}

export interface RiskAssessment {
  event_id: string;
  contributing_event_ids: string[];
  contributing_event_types: string[];
  risk_level: string;
  priority: string;
  reason: string;
  status: string;
  evidence: RiskAssessmentEvidence | null;
}

export interface EvidenceSource {
  source_id: string;
  source_type: string;
}

export interface FrameEvidence {
  frame_number: number;
  timestamp_seconds: number;
}

export interface Point2D {
  x: number;
  y: number;
}

export interface ZoneCreateRequest {
  zone_id?: string;
  name?: string;
  polygon: Point2D[];
}

export interface VideoSegmentEvidence {
  start_frame_number: number;
  end_frame_number: number;
  start_timestamp_seconds: number;
  end_timestamp_seconds: number;
}

export interface Evidence {
  evidence_id: string;
  evidence_type: string;
  source: EvidenceSource;
  frame: FrameEvidence | null;
  video_segment: VideoSegmentEvidence | null;
  event_id: string | null;
  assessment_id: string | null;
}

export interface HistoricalProcessingRunResponse {
  session: ProcessingSession;
  tracks: Track[];
  events: Event[];
  risk_assessments: RiskAssessment[];
  evidence: Evidence[];
}
