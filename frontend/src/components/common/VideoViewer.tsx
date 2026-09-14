import { useState, useRef, useEffect, forwardRef, useImperativeHandle } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Video, AlertCircle, Loader2, VolumeX, Volume2, ShieldAlert } from 'lucide-react';
import { sessionsApi } from '@/api/sessions';
import type { TrackObservation, Event, ZoneCreateRequest, RiskAssessment } from '@/types/sessions';
import DetectionOverlay from './DetectionOverlay';
import ZoneDrawer from './ZoneDrawer';

export interface VideoViewerRef {
  seekTo: (time: number) => void;
}

interface VideoViewerProps {
  sessionId: string;
  sourceId: string;
  status: string;
  events?: Event[];
  risks?: RiskAssessment[];
  observations?: TrackObservation[];
  processedUntilTimestamp?: number | null;
  onZoneChanged?: () => void;
}

const VideoViewer = forwardRef<VideoViewerRef, VideoViewerProps>(({ sessionId, sourceId, status, events = [], risks = [], observations: propObservations, onZoneChanged, processedUntilTimestamp }, ref) => {
  const [error, setError] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [videoDimensions, setVideoDimensions] = useState({ width: 0, height: 0 });
  const [internalObservations, setInternalObservations] = useState<TrackObservation[]>([]);
  
  const observations = status.toUpperCase() === 'COMPLETED' ? internalObservations : (propObservations || []);
  
  // Zone State
  const [savedZone, setSavedZone] = useState<ZoneCreateRequest | null>(null);
  const [isDrawingMode, setIsDrawingMode] = useState(false);

  // Audio / Alert State
  const [audioEnabled, setAudioEnabled] = useState(true);
  const [activeAlert, setActiveAlert] = useState<{ trackId: string, timestamp: number } | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const activeOscillatorRef = useRef<OscillatorNode | null>(null);
  const alertTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const highRiskTrackIdsRef = useRef<Set<string>>(new Set());
  
  const videoRef = useRef<HTMLVideoElement>(null);

  useImperativeHandle(ref, () => ({
    seekTo: (time: number) => {
      if (videoRef.current) {
        videoRef.current.currentTime = time;
        if (videoRef.current.paused && !isDrawingMode) {
          videoRef.current.play().catch(e => console.error("Autoplay failed:", e));
        }
        videoRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }
  }));

  const videoUrl = sessionsApi.getSessionVideoUrl(sessionId);

  useEffect(() => {
    if (status.toUpperCase() === 'COMPLETED') {
      sessionsApi.getSessionObservations(sessionId)
        .then(res => setInternalObservations(res))
        .catch(err => console.error("Failed to fetch observations:", err));
    }
    
    sessionsApi.getSessionZone(sessionId)
      .then(res => setSavedZone(res))
      .catch(err => console.error("Failed to fetch zone:", err));
  }, [sessionId, status]);

  // Audio Context initialization
  useEffect(() => {
    if (audioEnabled && !audioContextRef.current) {
      const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
      if (AudioContextClass) {
        audioContextRef.current = new AudioContextClass();
      }
    }
  }, [audioEnabled]);

  const stopBuzzer = () => {
    if (activeOscillatorRef.current) {
      try {
        activeOscillatorRef.current.stop();
        activeOscillatorRef.current.disconnect();
      } catch {
        // Ignore error
      }
      activeOscillatorRef.current = null;
    }
    if (alertTimeoutRef.current) {
      clearTimeout(alertTimeoutRef.current);
      alertTimeoutRef.current = null;
    }
  };

  useEffect(() => {
    return () => stopBuzzer();
  }, []);

  const playBuzzer = () => {
    if (!audioEnabled || !audioContextRef.current) return;
    
    if (audioContextRef.current.state === 'suspended') {
      audioContextRef.current.resume();
    }
    
    if (activeOscillatorRef.current) return;
    
    const ctx = audioContextRef.current;
    const osc = ctx.createOscillator();
    const gainNode = ctx.createGain();
    
    osc.type = 'square';
    osc.frequency.setValueAtTime(880, ctx.currentTime);
    
    gainNode.gain.setValueAtTime(0, ctx.currentTime);
    gainNode.gain.linearRampToValueAtTime(0.5, ctx.currentTime + 0.1);
    gainNode.gain.linearRampToValueAtTime(0, ctx.currentTime + 0.2);
    
    const interval = setInterval(() => {
      if (activeOscillatorRef.current === osc) {
        gainNode.gain.setValueAtTime(0, ctx.currentTime);
        gainNode.gain.linearRampToValueAtTime(0.5, ctx.currentTime + 0.1);
        gainNode.gain.linearRampToValueAtTime(0, ctx.currentTime + 0.2);
      } else {
        clearInterval(interval);
      }
    }, 400);

    osc.connect(gainNode);
    gainNode.connect(ctx.destination);
    
    osc.start();
    activeOscillatorRef.current = osc;
    
    if (alertTimeoutRef.current) clearTimeout(alertTimeoutRef.current);
    alertTimeoutRef.current = setTimeout(stopBuzzer, 3000);
  };

  const handleTimeUpdate = () => {
    if (!videoRef.current) return;
    const time = videoRef.current.currentTime;
    
    if (status.toUpperCase() === 'STARTED' && processedUntilTimestamp !== undefined && processedUntilTimestamp !== null) {
      if (time >= processedUntilTimestamp - 0.5) {
        videoRef.current.pause();
      } else if (videoRef.current.paused && !isDrawingMode) {
        videoRef.current.play().catch(e => console.error("Autoplay failed:", e));
      }
    }

    const activeHighRiskTrackIds = new Set<string>();
    const recentEvents = events.filter(e => 
      e.timestamp_seconds <= time && 
      e.timestamp_seconds >= time - 3.0 &&
      e.track_id !== undefined && e.track_id !== null
    );

    recentEvents.forEach(e => {
      if (e.event_type === 'ZONE_ENTRY') {
        const isHighRisk = risks.some(r => {
          const level = r.risk_level?.toUpperCase();
          if (level !== 'HIGH' && level !== 'CRITICAL') return false;
          return r.event_id === e.event_id || (r.contributing_event_ids && r.contributing_event_ids.includes(e.event_id));
        });
        if (isHighRisk) {
          activeHighRiskTrackIds.add(String(e.track_id));
        }
      }
    });

    if (highRiskTrackIdsRef.current) {
      highRiskTrackIdsRef.current.clear();
      activeHighRiskTrackIds.forEach(id => highRiskTrackIdsRef.current.add(id));
    }

    const recentEntry = events.find(e => 
      e.event_type === 'ZONE_ENTRY' && 
      e.timestamp_seconds <= time && 
      e.timestamp_seconds >= time - 0.5
    );

    const recentExit = events.find(e => 
      e.event_type === 'ZONE_EXIT' && 
      e.timestamp_seconds <= time && 
      e.timestamp_seconds >= time - 0.5
    );

    if (recentEntry && !activeAlert) {
      setActiveAlert({ trackId: String(recentEntry.track_id), timestamp: recentEntry.timestamp_seconds });
      playBuzzer();
    } else if (recentExit && activeAlert) {
      setActiveAlert(null);
      stopBuzzer();
    } else if (activeAlert && (time < activeAlert.timestamp || time > activeAlert.timestamp + 5)) {
      setActiveAlert(null);
      stopBuzzer();
    }
  };

  const handleSaveZone = async (zone: ZoneCreateRequest) => {
    try {
      const saved = await sessionsApi.saveSessionZone(sessionId, zone);
      setSavedZone(saved);
      if (onZoneChanged) onZoneChanged();
    } catch (err) {
      console.error("Failed to save zone", err);
    }
  };

  const handleClearZone = async () => {
    try {
      await sessionsApi.deleteSessionZone(sessionId);
      setSavedZone(null);
      if (onZoneChanged) onZoneChanged();
    } catch (err) {
      console.error("Failed to clear zone", err);
    }
  };

  const handleLoadedMetadata = (e: React.SyntheticEvent<HTMLVideoElement>) => {
    const target = e.target as HTMLVideoElement;
    setVideoDimensions({
      width: target.videoWidth,
      height: target.videoHeight
    });
  };

  if (status.toUpperCase() === 'FAILED') {
    return (
      <Card className="bg-card border-border overflow-hidden">
        <CardHeader className="pb-3 border-b border-border/50 bg-muted/20">
          <div className="flex justify-between items-center">
            <CardTitle className="text-lg flex items-center gap-2 uppercase tracking-wide">
              <Video className="w-5 h-5 text-primary" />
              Recorded CCTV
            </CardTitle>
            <Badge variant="outline" className="font-mono text-xs uppercase bg-red-500/10 text-red-500 border-red-500/30">
              {status}
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="p-10 flex flex-col items-center justify-center bg-background/50 text-center">
          <AlertCircle className="w-12 h-12 text-red-500/50 mb-4" />
          <h4 className="text-lg font-medium mb-1">Session Failed</h4>
          <p className="text-sm text-muted-foreground">Recorded video is not available for this session.</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="bg-card border-border overflow-hidden">
      <CardHeader className="pb-3 border-b border-border/50 bg-muted/20">
        <div className="flex justify-between items-start md:items-center flex-col md:flex-row gap-4">
          <div className="flex items-center gap-3">
            <CardTitle className="text-lg flex items-center gap-2 uppercase tracking-wide">
              <Video className="w-5 h-5 text-primary" />
              Recorded CCTV
            </CardTitle>
            <Badge variant="outline" className="font-mono text-xs uppercase">
              {status}
            </Badge>
          </div>
          <div className="flex flex-col md:items-end text-sm gap-2">
            <div className="flex items-center gap-2">
              <span className="text-muted-foreground text-xs uppercase tracking-wider mb-0.5">Source</span>
              <span className="font-mono truncate max-w-[200px] md:max-w-xs">{sourceId}</span>
            </div>
            
            <button
              onClick={() => setAudioEnabled(!audioEnabled)}
              className={`flex items-center gap-1.5 px-3 py-1 text-xs font-semibold uppercase tracking-wider rounded-md border transition-colors ${
                audioEnabled 
                  ? 'bg-red-500/10 text-red-500 border-red-500/30' 
                  : 'bg-muted text-muted-foreground border-border hover:bg-muted/80'
              }`}
            >
              {audioEnabled ? <Volume2 className="w-3.5 h-3.5" /> : <VolumeX className="w-3.5 h-3.5" />}
              Alert Sound: {audioEnabled ? 'ON' : 'OFF'}
            </button>
          </div>
        </div>
      </CardHeader>
      
      <CardContent className="p-0 bg-black relative aspect-video flex items-center justify-center overflow-hidden">
        {error ? (
          <div className="flex flex-col items-center justify-center p-8 text-center text-muted-foreground">
            <AlertCircle className="w-10 h-10 mb-3 text-red-500/50" />
            <p>Unable to load the recorded footage.</p>
          </div>
        ) : (
          <>
            {isLoading && (
              <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/80 z-10 text-muted-foreground">
                <Loader2 className="w-8 h-8 animate-spin mb-4 text-primary" />
                <span className="text-sm">Loading recorded footage...</span>
              </div>
            )}
            
            <video
              ref={videoRef}
              src={videoUrl}
              className="w-full h-full object-contain"
              controls
              controlsList="nodownload"
              playsInline
              onLoadedMetadata={handleLoadedMetadata}
              onCanPlay={() => setIsLoading(false)}
              onError={() => { setError(true); setIsLoading(false); }}
              onTimeUpdate={handleTimeUpdate}
            >
              Your browser does not support the video tag.
            </video>

            {/* Detection Overlay */}
            {observations.length > 0 && videoDimensions.width > 0 && !isDrawingMode && (
              <DetectionOverlay
                videoRef={videoRef}
                observations={observations}
                videoWidth={videoDimensions.width}
                videoHeight={videoDimensions.height}
                highRiskTrackIdsRef={highRiskTrackIdsRef}
              />
            )}

            {/* Zone Drawer */}
            {videoDimensions.width > 0 && (
              <ZoneDrawer
                videoWidth={videoDimensions.width}
                videoHeight={videoDimensions.height}
                savedZone={savedZone}
                onSaveZone={handleSaveZone}
                onClearZone={handleClearZone}
                isDrawingMode={isDrawingMode}
                setIsDrawingMode={setIsDrawingMode}
              />
            )}

            {/* Active Intrusion Alert Overlay */}
            {activeAlert && (
              <div className="absolute top-8 left-1/2 -translate-x-1/2 z-40 animate-in fade-in zoom-in duration-300">
                <div className="bg-red-600 text-white px-6 py-4 rounded-xl shadow-2xl border-2 border-red-400 flex items-center gap-4 animate-pulse">
                  <ShieldAlert className="w-8 h-8" />
                  <div>
                    <h2 className="text-xl font-black uppercase tracking-widest">Intrusion Detected</h2>
                    <p className="text-sm font-medium opacity-90">
                      Restricted Zone Entry • Track ID: {activeAlert.trackId} • Timestamp: {activeAlert.timestamp.toFixed(2)}s
                    </p>
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
});

VideoViewer.displayName = 'VideoViewer';
export default VideoViewer;
