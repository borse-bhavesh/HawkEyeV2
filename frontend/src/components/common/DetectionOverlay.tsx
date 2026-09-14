import { useEffect, useRef } from 'react';
import type { TrackObservation } from '@/types/sessions';

interface DetectionOverlayProps {
  videoRef: React.RefObject<HTMLVideoElement | null>;
  observations: TrackObservation[];
  videoWidth: number;
  videoHeight: number;
  highRiskTrackIdsRef?: React.RefObject<Set<string>>;
}

export default function DetectionOverlay({
  videoRef,
  observations,
  videoWidth,
  videoHeight,
  highRiskTrackIdsRef
}: DetectionOverlayProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    if (!videoWidth || !videoHeight) return;

    let animationFrameId: number;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const renderLoop = () => {
      const video = videoRef.current;
      if (!video) return;

      // Clear canvas
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      const currentTime = video.currentTime;
      
      // Find observations for current time (approximate within 100ms or closest frame)
      // Since video playback might fall exactly between frames, we find the closest observations.
      // Easiest is to filter observations within a small time window, e.g., +/- 0.05s
      const activeObs = observations.filter(obs => 
        Math.abs(obs.timestamp_seconds - currentTime) < 0.05
      );

      // Draw bounding boxes
      activeObs.forEach(obs => {
        const x = obs.bbox_x1;
        const y = obs.bbox_y1;
        const width = obs.bbox_x2 - obs.bbox_x1;
        const height = obs.bbox_y2 - obs.bbox_y1;

        const isHighRisk = highRiskTrackIdsRef?.current?.has(String(obs.track_id));

        // Use neutral color for normal tracks, red/pulsing for high risk
        let color = '#0ea5e9'; // standard blue
        let bgColor = 'rgba(14, 165, 233, 0.2)';

        if (isHighRisk) {
          color = '#ef4444'; // alert red
          bgColor = 'rgba(239, 68, 68, 0.3)';
        }

        ctx.strokeStyle = color;
        // Thicker lines if high risk
        ctx.lineWidth = Math.max(isHighRisk ? 4 : 2, videoWidth / (isHighRisk ? 300 : 500));
        
        ctx.fillStyle = bgColor;
        ctx.fillRect(x, y, width, height);
        ctx.strokeRect(x, y, width, height);

        // Extract clean ID
        const formatTrackId = (trackId: string | number) => {
          if (typeof trackId === 'string' && trackId.includes('-track-')) {
            const parts = trackId.split('-track-');
            return parts[1] || String(trackId);
          }
          return String(trackId);
        };

        // Draw label
        if (obs.class_name) {
          const fontSize = Math.max(10, Math.min(14, videoWidth / 120));
          ctx.font = `${fontSize}px sans-serif`;
          
          const displayClass = obs.class_name === 'class_0' ? 'PERSON' : obs.class_name.toUpperCase();
          const labelParts = [];
          if (obs.track_id !== undefined && obs.track_id !== null) {
            labelParts.push(`ID ${formatTrackId(obs.track_id)}`);
          }
          labelParts.push(displayClass);
          if (obs.confidence) {
            labelParts.push(`${(obs.confidence * 100).toFixed(0)}%`);
          }
          const label = labelParts.join(' • ');
          const textWidth = ctx.measureText(label).width;
          
          ctx.fillStyle = color;
          ctx.fillRect(x - ctx.lineWidth / 2, y - fontSize - 6, textWidth + 8, fontSize + 6);
          
          ctx.fillStyle = '#ffffff';
          ctx.fillText(label, x + 4, y - 4);
        }
      });

      animationFrameId = requestAnimationFrame(renderLoop);
    };

    // Start loop
    animationFrameId = requestAnimationFrame(renderLoop);

    return () => {
      cancelAnimationFrame(animationFrameId);
    };
  }, [videoRef, observations, videoWidth, videoHeight, highRiskTrackIdsRef]);

  if (!videoWidth || !videoHeight) return null;

  return (
    <canvas
      ref={canvasRef}
      width={videoWidth}
      height={videoHeight}
      className="absolute inset-0 w-full h-full object-contain pointer-events-none"
    />
  );
}
