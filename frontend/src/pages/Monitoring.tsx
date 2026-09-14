import { useState, useEffect, useRef } from 'react';
import { AlertCircle, ShieldAlert, Activity, WifiOff, Play, Square } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import VideoUpload from '@/components/common/VideoUpload';
import VideoViewer from '@/components/common/VideoViewer';
import IncidentDetailPanel from '@/components/history/IncidentDetailPanel';
import { sessionsApi } from '@/api/sessions';
import type { VideoViewerRef } from '@/components/common/VideoViewer';
import type { ProcessingSession, Event, RiskAssessment, Evidence, TrackObservation } from '@/types/sessions';

export default function Monitoring() {
  const videoViewerRef = useRef<VideoViewerRef>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [demoSessionId, setDemoSessionId] = useState<string | null>(null);
  const [session, setSession] = useState<ProcessingSession | null>(null);
  const [events, setEvents] = useState<Event[]>([]);
  const [risks, setRisks] = useState<RiskAssessment[]>([]);
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [observations, setObservations] = useState<TrackObservation[]>([]);
  
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);

  // Poll session data if a demo session is active
  useEffect(() => {
    if (!demoSessionId) return;

    const interval = setInterval(async () => {
      try {
        const history = await sessionsApi.getSessionHistory(demoSessionId);
        setSession(history.session);
        setEvents(history.events);
        setRisks(history.risk_assessments);
        setEvidence(history.evidence);
        
        // Also fetch observations for VideoViewer
        const obs = await sessionsApi.getSessionObservations(demoSessionId);
        setObservations(obs);
      } catch (err) {
        console.error('Failed to poll session:', err);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [demoSessionId]);

  const handleStartDemo = async () => {
    setErrorMsg(null);
    try {
      const res = await sessionsApi.startDemoCamera();
      setDemoSessionId(res.session_id);
      setSelectedEventId(null);
      setEvents([]);
      setRisks([]);
      setEvidence([]);
      setObservations([]);
    } catch (err) {
      console.error("Failed to start demo camera", err);
      setErrorMsg("Unable to start Demo Camera.");
    }
  };

  const handleStopDemo = () => {
    setDemoSessionId(null);
    setSession(null);
    setSelectedEventId(null);
  };

  const handleEventClick = (eventId: string) => {
    setSelectedEventId(eventId);
    const event = events.find(e => e.event_id === eventId);
    if (event && videoViewerRef.current) {
      videoViewerRef.current.seekTo(event.timestamp_seconds - 1.5);
    }
  };

  const selectedEvent = events.find(e => e.event_id === selectedEventId) || null;
  const isAnalyzing = session?.status === 'STARTED';
  const isLive = demoSessionId && isAnalyzing;

  return (
    <div className="space-y-6 flex flex-col h-[calc(100vh-8rem)]">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 shrink-0">
        <div>
          <h3 className="text-2xl font-bold tracking-tight">Live Monitoring & Analysis</h3>
          <p className="text-muted-foreground text-sm mt-1">
            Real-time surveillance and recorded video intelligence dashboard.
          </p>
        </div>
        <div className="flex flex-col items-end gap-2">
          <div className="flex items-center gap-3">
            {!demoSessionId ? (
              <Button onClick={handleStartDemo} variant="outline" className="gap-2">
                <Play className="w-4 h-4" /> Start Demo Camera
              </Button>
            ) : (
              <Button onClick={handleStopDemo} variant="destructive" className="gap-2">
                <Square className="w-4 h-4" /> Stop Demo
              </Button>
            )}
            <Badge 
              variant="outline" 
              className={`px-3 uppercase tracking-wider text-[10px] ${
                isLive 
                  ? 'bg-green-500/10 text-green-500 border-green-500/20' 
                  : 'bg-gray-500/10 text-gray-500 border-gray-500/20'
              }`}
            >
              Live Status: {isLive ? 'LIVE' : 'Offline'}
            </Badge>
          </div>
          {errorMsg && <div className="text-red-500 text-sm font-semibold">{errorMsg}</div>}
        </div>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 flex-1 min-h-0">
        
        {/* Left Column (Video & Primary Context) */}
        <div className="lg:col-span-3 flex flex-col gap-6 min-h-0 overflow-y-auto pr-2">
          
          {/* Upload Workflow */}
          {!demoSessionId && <VideoUpload />}

          {/* Main Viewport */}
          <Card className="flex-1 shrink-0 bg-black border-border relative overflow-hidden min-h-[400px]">
            {demoSessionId ? (
              <VideoViewer
                ref={videoViewerRef}
                sessionId={demoSessionId}
                sourceId={session?.source_id || 'Demo Camera'}
                status={session?.status || 'UPLOADED'}
                events={events}
                observations={observations}
              />
            ) : (
              <div className="absolute inset-0 flex flex-col items-center justify-center text-center p-6 bg-secondary/10">
                <div className="w-16 h-16 bg-card/50 rounded-full flex items-center justify-center mb-4 border border-border/50">
                  <WifiOff className="w-8 h-8 text-muted-foreground" />
                </div>
                <h3 className="text-xl font-semibold tracking-tight text-foreground/80 mb-2">
                  Monitoring Source Unavailable
                </h3>
                <p className="text-sm text-muted-foreground max-w-md">
                  The monitoring UI is ready. Click "Start Demo Camera" above to launch a simulated CCTV feed.
                </p>
              </div>
            )}
          </Card>

          {/* Real-time Metadata / Processing State */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 shrink-0">
            <Card className="bg-card/40 border-border/50">
              <CardContent className="p-4 flex flex-col items-center justify-center text-center">
                <p className="text-xs text-muted-foreground uppercase font-semibold tracking-wider mb-1">Source</p>
                <p className="font-mono text-sm">{demoSessionId ? 'Simulated CCTV' : 'Unavailable'}</p>
              </CardContent>
            </Card>
            <Card className="bg-card/40 border-border/50">
              <CardContent className="p-4 flex flex-col items-center justify-center text-center">
                <p className="text-xs text-muted-foreground uppercase font-semibold tracking-wider mb-1">Status</p>
                <p className="font-mono text-sm">{demoSessionId ? (isAnalyzing ? 'Analyzing...' : session?.status) : '--'}</p>
              </CardContent>
            </Card>
            <Card className="bg-card/40 border-border/50">
              <CardContent className="p-4 flex flex-col items-center justify-center text-center">
                <p className="text-xs text-muted-foreground uppercase font-semibold tracking-wider mb-1">Detections</p>
                <p className="font-mono text-sm">{observations.length}</p>
              </CardContent>
            </Card>
            <Card className="bg-card/40 border-border/50">
              <CardContent className="p-4 flex flex-col items-center justify-center text-center">
                <p className="text-xs text-muted-foreground uppercase font-semibold tracking-wider mb-1">Events</p>
                <p className="font-mono text-sm">{events.length}</p>
              </CardContent>
            </Card>
          </div>
        </div>

        {/* Right Column (Intelligence Panels) */}
        <div className="flex flex-col gap-6 min-h-0 overflow-y-auto pr-2">
          
          {selectedEventId ? (
            <div className="flex flex-col gap-4">
              <Button variant="outline" size="sm" onClick={() => setSelectedEventId(null)} className="w-fit">
                ← Back to Live Stream
              </Button>
              <IncidentDetailPanel
                selectedEvent={selectedEvent}
                risks={risks.filter(r => r.event_id === selectedEventId)}
                evidence={evidence.filter(ev => 
                  ev.event_id === selectedEventId || 
                  risks.some(r => r.event_id === selectedEventId && ev.assessment_id === r.event_id)
                )}
              />
            </div>
          ) : (
            <>
              {/* Risk Panel */}
              <Card className="flex-1 bg-card/50 border-border flex flex-col min-h-[250px]">
                <CardHeader className="pb-3 pt-4 px-4 bg-card shrink-0 border-b border-border/50">
                  <CardTitle className="text-sm font-semibold flex items-center gap-2">
                    <ShieldAlert className="w-4 h-4 text-red-500" />
                    Live Risks
                  </CardTitle>
                </CardHeader>
                <CardContent className="flex-1 overflow-y-auto p-4 flex flex-col gap-2">
                  {risks.length === 0 ? (
                    <div className="flex-1 flex flex-col items-center justify-center text-center text-muted-foreground">
                      <AlertCircle className="w-8 h-8 mb-3 opacity-20" />
                      <p className="text-sm">No risks detected</p>
                    </div>
                  ) : (
                    risks.map(risk => {
                      const isHighRisk = risk.risk_level === 'HIGH' || risk.risk_level === 'CRITICAL';
                      const assocEvent = events.find(e => e.event_id === risk.event_id);
                      return (
                        <div 
                          key={risk.event_id}
                          className={`p-3 rounded-md border text-sm cursor-pointer transition-colors ${
                            isHighRisk ? 'bg-red-500/10 border-red-500/30 hover:bg-red-500/20' : 'bg-card border-border hover:bg-secondary'
                          }`}
                          onClick={() => risk.event_id && handleEventClick(risk.event_id)}
                        >
                          <div className="flex justify-between items-start mb-1">
                            <span className="font-semibold">{risk.risk_level}</span>
                            <span className="text-xs opacity-70">Track {assocEvent?.track_id ?? 'N/A'}</span>
                          </div>
                          <p className="text-xs text-muted-foreground">{risk.reason}</p>
                        </div>
                      )
                    })
                  )}
                </CardContent>
              </Card>

              {/* Event Panel */}
              <Card className="flex-1 bg-card/50 border-border flex flex-col min-h-[250px]">
                <CardHeader className="pb-3 pt-4 px-4 bg-card shrink-0 border-b border-border/50">
                  <CardTitle className="text-sm font-semibold flex items-center gap-2">
                    <Activity className="w-4 h-4 text-amber-500" />
                    Live Events
                  </CardTitle>
                </CardHeader>
                <CardContent className="flex-1 overflow-y-auto p-4 flex flex-col gap-2">
                  {events.length === 0 ? (
                    <div className="flex-1 flex flex-col items-center justify-center text-center text-muted-foreground">
                      <Activity className="w-8 h-8 mb-3 opacity-20" />
                      <p className="text-sm">No events detected</p>
                    </div>
                  ) : (
                    events.map(event => (
                      <div 
                        key={event.event_id}
                        className="p-3 rounded-md bg-card border border-border text-sm hover:bg-secondary cursor-pointer transition-colors"
                        onClick={() => handleEventClick(event.event_id)}
                      >
                        <div className="flex justify-between items-start mb-1">
                          <span className="font-semibold">{event.event_type}</span>
                          <span className="text-xs text-muted-foreground">{event.timestamp_seconds.toFixed(2)}s</span>
                        </div>
                        <p className="text-xs text-muted-foreground">{event.description}</p>
                      </div>
                    ))
                  )}
                </CardContent>
              </Card>
            </>
          )}

        </div>
      </div>
    </div>
  );
}
