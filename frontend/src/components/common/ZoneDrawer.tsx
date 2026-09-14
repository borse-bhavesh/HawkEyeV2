import { useState, useRef, useEffect } from 'react';
import type { MouseEvent } from 'react';
import type { Point2D, ZoneCreateRequest } from '@/types/sessions';

interface ZoneDrawerProps {
  videoWidth: number;
  videoHeight: number;
  savedZone: ZoneCreateRequest | null;
  onSaveZone: (zone: ZoneCreateRequest) => void;
  onClearZone: () => void;
  isDrawingMode: boolean;
  setIsDrawingMode: (mode: boolean) => void;
}

export default function ZoneDrawer({
  videoWidth,
  videoHeight,
  savedZone,
  onSaveZone,
  onClearZone,
  isDrawingMode,
  setIsDrawingMode
}: ZoneDrawerProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [points, setPoints] = useState<Point2D[]>([]);

  useEffect(() => {
    if (!videoWidth || !videoHeight) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const drawPolygon = (pts: Point2D[], color: string, fillColor: string) => {
      if (pts.length === 0) return;
      ctx.beginPath();
      ctx.moveTo(pts[0].x, pts[0].y);
      for (let i = 1; i < pts.length; i++) {
        ctx.lineTo(pts[i].x, pts[i].y);
      }
      if (pts.length >= 3) ctx.closePath();
      ctx.fillStyle = fillColor;
      ctx.fill();
      ctx.lineWidth = Math.max(3, videoWidth / 300);
      ctx.strokeStyle = color;
      ctx.stroke();
      pts.forEach(pt => {
        ctx.beginPath();
        ctx.arc(pt.x, pt.y, Math.max(4, videoWidth / 250), 0, Math.PI * 2);
        ctx.fillStyle = '#ffffff';
        ctx.fill();
        ctx.stroke();
      });
      if (pts === savedZone?.polygon && pts.length >= 3) {
        const minX = Math.min(...pts.map(p => p.x));
        const minY = Math.min(...pts.map(p => p.y));
        const fontSize = Math.max(16, videoWidth / 80);
        ctx.font = `bold ${fontSize}px sans-serif`;
        const label = "RESTRICTED ZONE";
        const textWidth = ctx.measureText(label).width;
        ctx.fillStyle = 'rgba(255, 0, 0, 0.7)';
        ctx.fillRect(minX, minY - fontSize - 10, textWidth + 10, fontSize + 10);
        ctx.fillStyle = '#ffffff';
        ctx.fillText(label, minX + 5, minY - 8);
      }
    };

    if (savedZone && savedZone.polygon && savedZone.polygon.length > 0 && (!isDrawingMode || points.length === 0)) {
      drawPolygon(savedZone.polygon, '#ef4444', 'rgba(239, 68, 68, 0.2)');
    }
    if (isDrawingMode && points.length > 0) {
      drawPolygon(points, '#3b82f6', 'rgba(59, 130, 246, 0.2)');
    }
  }, [points, savedZone, videoWidth, videoHeight, isDrawingMode]);

  const handleCanvasClick = (e: MouseEvent<HTMLCanvasElement>) => {
    if (!isDrawingMode) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const elementAspect = rect.width / rect.height;
    const videoAspect = videoWidth / videoHeight;
    let renderWidth = rect.width, renderHeight = rect.height, renderX = 0, renderY = 0;
    if (elementAspect > videoAspect) {
      renderWidth = rect.height * videoAspect;
      renderX = (rect.width - renderWidth) / 2;
    } else {
      renderHeight = rect.width / videoAspect;
      renderY = (rect.height - renderHeight) / 2;
    }
    const clickX = e.clientX - rect.left - renderX;
    const clickY = e.clientY - rect.top - renderY;
    if (clickX < 0 || clickX > renderWidth || clickY < 0 || clickY > renderHeight) return;
    const x = clickX * (videoWidth / renderWidth);
    const y = clickY * (videoHeight / renderHeight);
    setPoints(prev => [...prev, { x, y }]);
  };

  const handleSave = () => {
    if (points.length >= 3) {
      onSaveZone({ zone_id: 'zone_1', name: 'Restricted Zone', polygon: points });
      setPoints([]);
      setIsDrawingMode(false);
    }
  };

  const handleCancel = () => {
    setPoints([]);
    setIsDrawingMode(false);
  };

  if (!videoWidth || !videoHeight) return null;

  return (
    <>
      <canvas ref={canvasRef} width={videoWidth} height={videoHeight} onClick={handleCanvasClick} className={`absolute inset-0 w-full h-full object-contain ${isDrawingMode ? 'cursor-crosshair z-20' : 'pointer-events-none z-10'}`} />
      <div className="absolute top-4 right-4 z-30 flex flex-col gap-2">
        {isDrawingMode ? (
          <>
            <div className="bg-background/90 p-2 rounded-md border border-border text-sm mb-2 shadow-lg max-w-[200px]">Click on the video to draw a polygon. At least 3 points required.</div>
            <button onClick={handleSave} disabled={points.length < 3} className="px-4 py-2 bg-primary text-primary-foreground text-sm font-medium rounded-md shadow-md disabled:opacity-50 transition-colors hover:bg-primary/90">Save Zone</button>
            <button onClick={handleCancel} className="px-4 py-2 bg-secondary text-secondary-foreground text-sm font-medium rounded-md shadow-md hover:bg-secondary/80 transition-colors">Cancel</button>
          </>
        ) : (
          <>
            <button onClick={() => { setPoints([]); setIsDrawingMode(true); }} className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-md shadow-md transition-colors">{savedZone ? 'Redraw Zone' : 'Draw Restricted Zone'}</button>
            {savedZone && savedZone.polygon && Object.keys(savedZone).length > 0 && (
              <button onClick={onClearZone} className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white text-sm font-medium rounded-md shadow-md transition-colors">Clear Zone</button>
            )}
          </>
        )}
      </div>
    </>
  );
}
