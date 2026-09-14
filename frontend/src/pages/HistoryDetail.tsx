import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowLeft, ShieldAlert, FolderLock, Focus, Play, Loader2, Activity, ArrowRight } from 'lucide-react';
import { sessionsApi } from '@/api/sessions';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import VideoViewer from '@/components/common/VideoViewer';
import type { VideoViewerRef } from '@/components/common/VideoViewer';
import IncidentDetailPanel from '@/components/history/IncidentDetailPanel';
import { filterActionableEvents, getHighRiskEventCount, getHighRiskEvidenceCount } from '@/utils/eventFilters';
import type { Event, TrackObservation } from '@/types/sessions';
import { useState, useEffect, useRef } from 'react';

export default function HistoryDetail() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();

  const videoViewerRef = useRef<VideoViewerRef>(null);
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);

  const [observations, setObservations] = useState<TrackObservation[]>([]);
  const [events, setEvents] = useState<Event[]>([]);
  const [risks, setRisks] = useState<any[]>([]);
  const lastObsFrame = useRef<number>(-1);
  const lastEventFrame = useRef<number>(-1);
  
  const [isStarting, setIsStarting] = useState(false);

  // Poll for the session object
  const { 
    data: session, 
    isLoading: sessionLoading, 
    isError: sessionError,
    refetch: refetchSession
  } = useQuery({
    queryKey: ['session_obj', sessionId],
    queryFn: () => sessionsApi.getSessionHistory(sessionId as string).then(res => res.session).catch(async () => {
        // Fallback to get session directly if history fails (e.g. UPLOADED state has no history)
        const res = await sessionsApi.getSessions();
        const found = res.find((s: any) => s.session_id === sessionId);
        if (!found) throw new Error("Session not found");
        return found;
    }),
    enabled: !!sessionId,
    refetchInterval: (query) => query.state.data?.status.toUpperCase() === 'STARTED' ? 2000 : false
  });

  // Fetch full history only if COMPLETED
  const { data: historyRun } = useQuery({
    queryKey: ['session_history', sessionId],
    queryFn: () => sessionsApi.getSessionHistory(sessionId as string),
    enabled: !!sessionId && session?.status.toUpperCase() === 'COMPLETED',
  });

  // Polling for incremental data when STARTED
  useEffect(() => {
    let interval: any;
    if (session?.status.toUpperCase() === 'STARTED') {
      interval = setInterval(async () => {
        try {
          const newObs = await sessionsApi.getSessionObservations(session.session_id, lastObsFrame.current);
          if (newObs.length > 0) {
            lastObsFrame.current = Math.max(...newObs.map((o: any) => o.frame_number));
            setObservations(prev => [...prev, ...newObs]);
          }
          
          const newEvents = await sessionsApi.getSessionEvents(session.session_id, lastEventFrame.current);
          if (newEvents.length > 0) {
            lastEventFrame.current = Math.max(...newEvents.map((e: any) => e.frame_number));
            setEvents(prev => [...prev, ...newEvents]);
          }

          const currentRisks = await sessionsApi.getSessionRisks(session.session_id);
          setRisks(currentRisks);

        } catch (err) {
          console.error("Polling error", err);
        }
      }, 2000);
    }
    return () => {
      if (interval) clearInterval(interval);
    }
  }, [session?.status, session?.session_id]);

  const handleStartAnalysis = async () => {
    if (!session || !session.restricted_zone) return;
    setIsStarting(true);
    try {
      await sessionsApi.startAnalysis(session.session_id);
      refetchSession();
    } catch (err) {
      console.error(err);
      alert("Failed to start analysis. Make sure you saved a zone.");
    } finally {
      setIsStarting(false);
    }
  };

  const handleEventClick = (event: Event) => {
    setSelectedEventId(event.event_id);
    if (videoViewerRef.current) {
      videoViewerRef.current.seekTo(event.timestamp_seconds);
    }
  };

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    const ms = Math.floor((seconds % 1) * 100);
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}.${ms.toString().padStart(2, '0')}`;
  };

  if (sessionLoading) {
    return <div className="p-8"><Loader2 className="animate-spin text-blue-500 w-8 h-8 mx-auto" /></div>;
  }

  if (sessionError || !session) {
    return <div className="p-8 text-red-500">Failed to load session details.</div>;
  }

  const isCompleted = session.status.toUpperCase() === 'COMPLETED';
  const isUploaded = session.status.toUpperCase() === 'UPLOADED';
  const isStarted = session.status.toUpperCase() === 'STARTED';

  // Use history data if completed, else incremental
  const displayEvents = isCompleted && historyRun ? historyRun.events : events;
  const displayTracks = isCompleted && historyRun ? historyRun.tracks : [];
  const displayRisks = isCompleted && historyRun ? historyRun.risk_assessments : risks;
  const displayEvidence = isCompleted && historyRun ? historyRun.evidence : [];

  const sortedEvents = filterActionableEvents(displayEvents, displayRisks);
  const highRiskEventCount = getHighRiskEventCount(displayEvents, displayRisks);
  const highRiskEvidenceCount = getHighRiskEvidenceCount(displayEvidence, displayRisks, displayEvents);

  // highCriticalRisks also maps to unique tracks for restricted zone intrusions
  const highCriticalRisks = highRiskEventCount;

  return (
    <div className="space-y-8 pb-10">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <Button variant="outline" size="icon" onClick={() => navigate('/history')}>
            <ArrowLeft className="w-4 h-4" />
          </Button>
          <div>
            <div className="flex items-center gap-3">
              <h3 className="text-2xl font-bold tracking-tight uppercase">
                {isUploaded ? 'Workspace' : isStarted ? 'Analysis Running' : 'Session Results'}
              </h3>
              <Badge variant={isCompleted ? "default" : isStarted ? "secondary" : "outline"} className="uppercase">
                {session.status}
              </Badge>
            </div>
            <p className="text-sm text-muted-foreground mt-1 font-mono">{session.session_id}</p>
          </div>
        </div>
        
        {isUploaded && (
          <Button 
            onClick={handleStartAnalysis} 
            disabled={isStarting || !session.restricted_zone}
            className="bg-blue-600 hover:bg-blue-700"
          >
            {isStarting ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Play className="w-4 h-4 mr-2" />}
            Start Analysis
          </Button>
        )}
      </div>

      <VideoViewer 
        ref={videoViewerRef}
        sessionId={session.session_id} 
        sourceId={session.source_id || ''} 
        status={session.status}
        events={displayEvents}
        observations={isCompleted ? undefined : observations}
        processedUntilTimestamp={session.processed_until_timestamp}
        onZoneChanged={() => refetchSession()}
      />

      {/* Show summaries and detailed tables only if completed */}
      {isCompleted && historyRun && (
        <div className="space-y-8">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <Card className="bg-card/40 border-border/50">
                    <CardContent className="p-4 flex items-center gap-4">
                        <div className="p-3 bg-blue-500/10 rounded-lg border border-blue-500/20">
                            <Focus className="w-5 h-5 text-blue-500" />
                        </div>
                        <div>
                            <p className="text-xs text-muted-foreground uppercase font-semibold tracking-wider">Total Tracks</p>
                            <h4 className="text-2xl font-bold">{displayTracks.length}</h4>
                        </div>
                    </CardContent>
                </Card>
                <Card className="bg-card/40 border-border/50">
                    <CardContent className="p-4 flex items-center gap-4">
                        <div className="p-3 bg-amber-500/10 rounded-lg border border-amber-500/20">
                            <Activity className="w-5 h-5 text-amber-500" />
                        </div>
                        <div>
                            <p className="text-xs text-muted-foreground uppercase font-semibold tracking-wider">High-Risk Events</p>
                            <h4 className="text-2xl font-bold">{highRiskEventCount}</h4>
                        </div>
                    </CardContent>
                </Card>
                <Card className="bg-card/40 border-border/50">
                    <CardContent className="p-4 flex items-center gap-4">
                        <div className="p-3 bg-red-500/10 rounded-lg border border-red-500/20">
                            <ShieldAlert className="w-5 h-5 text-red-500" />
                        </div>
                        <div>
                            <p className="text-xs text-muted-foreground uppercase font-semibold tracking-wider">High / Crit.</p>
                            <h4 className="text-2xl font-bold">{highCriticalRisks}</h4>
                        </div>
                    </CardContent>
                </Card>
                <Card className="bg-card/40 border-border/50">
                    <CardContent className="p-4 flex items-center gap-4">
                        <div className="p-3 bg-emerald-500/10 rounded-lg border border-emerald-500/20">
                            <FolderLock className="w-5 h-5 text-emerald-500" />
                        </div>
                        <div>
                            <p className="text-xs text-muted-foreground uppercase font-semibold tracking-wider">High-Risk Evidence</p>
                            <h4 className="text-2xl font-bold">{highRiskEvidenceCount}</h4>
                        </div>
                    </CardContent>
                </Card>
            </div>
        </div>
      )}

      {(isCompleted || isStarted) && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mt-8">
          <Card className="bg-card border-border lg:col-span-1">
              <CardHeader className="pb-3 border-b border-border/50 bg-muted/10 shrink-0">
                  <CardTitle className="text-lg flex items-center gap-2">
                      Results Summary
                      {isStarted && <Loader2 className="w-4 h-4 animate-spin text-muted-foreground ml-2" />}
                  </CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                  <div className="max-h-[600px] overflow-y-auto p-4">
                      {sortedEvents.length === 0 ? (
                          <p className="text-sm text-muted-foreground">
                              {isStarted ? "Analysis running... waiting for events." : "No high-risk events detected during analysis."}
                          </p>
                      ) : (
                          <div className="space-y-4">
                        {sortedEvents.map((event: any) => {
                            const isZoneEntry = event.event_type === 'ZONE_ENTRY';
                            const isSelected = selectedEventId === event.event_id;
                            
                            return (
                                <div 
                                    key={event.event_id}
                                    className={`p-4 rounded-lg border transition-all ${
                                        isSelected 
                                            ? 'bg-accent border-accent-foreground/50' 
                                            : 'bg-card hover:bg-accent/50 border-border'
                                    }`}
                                >
                                    <div className="flex items-start justify-between">
                                        <div>
                                            <div className="flex items-center gap-2 mb-1">
                                                {isZoneEntry ? (
                                                    <Badge variant="destructive" className="flex items-center gap-1">
                                                        <ShieldAlert className="w-3 h-3" />
                                                        INTRUSION
                                                    </Badge>
                                                ) : (
                                                    <Badge variant="secondary" className="uppercase">
                                                        {event.event_type.replace('_', ' ')}
                                                    </Badge>
                                                )}
                                                {isZoneEntry && <span className="text-sm font-semibold text-destructive">Restricted Zone Entry</span>}
                                            </div>
                                            <div className="text-sm text-muted-foreground mt-2">
                                                {event.description || (isZoneEntry ? 'Person entered restricted zone' : 'Event detected')}
                                            </div>
                                            {event.track_id && (
                                                <div className="text-xs text-muted-foreground mt-1">
                                                    Track ID: {event.track_id}
                                                </div>
                                            )}
                                            <div className="text-xl font-mono mt-2 text-foreground">
                                                {formatTime(event.timestamp_seconds)}
                                            </div>
                                        </div>
                                        <Button 
                                            variant={isSelected ? "default" : "outline"}
                                            size="sm"
                                            onClick={() => handleEventClick(event)}
                                        >
                                            VIEW EVENT <ArrowRight className="w-4 h-4 ml-1" />
                                        </Button>
                                    </div>
                                </div>
                            );
                        })}
                          </div>
                      )}
                  </div>
              </CardContent>
          </Card>

          <div className="lg:col-span-2">
            <IncidentDetailPanel 
              selectedEvent={sortedEvents.find((e: any) => e.event_id === selectedEventId) || null}
              risks={displayRisks}
              evidence={displayEvidence}
            />
          </div>
        </div>
      )}
    </div>
  );
}
