import { useSearchParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Activity, AlertCircle, ArrowLeft, Clock } from 'lucide-react';
import { sessionsApi } from '@/api/sessions';
import { Card, CardHeader, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import type { Event } from '@/types/sessions';

export default function Events() {
  const [searchParams] = useSearchParams();
  const sessionId = searchParams.get('sessionId');
  const navigate = useNavigate();

  const { 
    data: events, 
    isLoading, 
    isError, 
    error,
    refetch 
  } = useQuery({
    queryKey: ['session', sessionId, 'events'],
    queryFn: () => sessionsApi.getSessionEvents(sessionId as string),
    enabled: !!sessionId,
  });

  if (!sessionId) {
    return (
      <Card className="border-dashed bg-transparent mt-8">
        <CardContent className="pt-10 pb-10 flex flex-col items-center justify-center text-center">
          <div className="w-16 h-16 bg-secondary/50 rounded-full flex items-center justify-center mb-4">
            <Activity className="w-8 h-8 text-muted-foreground" />
          </div>
          <h3 className="text-xl font-semibold tracking-tight">No Session Selected</h3>
          <p className="text-muted-foreground max-w-sm mt-2 mb-6">
            Please select a historical session to view its events.
          </p>
          <Button onClick={() => navigate('/history')}>Browse Sessions</Button>
        </CardContent>
      </Card>
    );
  }

  const formatEventType = (type: string) => {
    return type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
  };

  const getEventBadge = (type: string) => {
    switch (type) {
      case 'TRACK_STARTED':
      case 'TRACK_ENDED':
        return <Badge variant="outline" className="bg-blue-500/10 text-blue-500 border-blue-500/20">{formatEventType(type)}</Badge>;
      case 'ZONE_ENTRY':
      case 'ZONE_EXIT':
        return <Badge variant="outline" className="bg-purple-500/10 text-purple-500 border-purple-500/20">{formatEventType(type)}</Badge>;
      case 'LOITERING':
        return <Badge variant="outline" className="bg-amber-500/10 text-amber-500 border-amber-500/20">{formatEventType(type)}</Badge>;
      case 'RAPID_MOVEMENT':
      case 'DIRECTION_CHANGE':
        return <Badge variant="outline" className="bg-orange-500/10 text-orange-500 border-orange-500/20">{formatEventType(type)}</Badge>;
      case 'MULTIPLE_OBJECT_PROXIMITY':
        return <Badge variant="outline" className="bg-red-500/10 text-red-500 border-red-500/20">{formatEventType(type)}</Badge>;
      default:
        return <Badge variant="outline" className="bg-gray-500/10 text-gray-500 border-gray-500/20">{formatEventType(type)}</Badge>;
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <Button variant="outline" size="icon" onClick={() => navigate(`/history/${sessionId}`)}>
            <ArrowLeft className="w-4 h-4" />
          </Button>
          <div>
            <h3 className="text-2xl font-bold tracking-tight">System Events</h3>
            <p className="text-muted-foreground text-sm font-mono mt-1">
              Session: {sessionId}
            </p>
          </div>
        </div>
      </div>

      {isLoading && (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <Card key={i} className="animate-pulse bg-card/50 border-border/50 h-24" />
          ))}
        </div>
      )}

      {isError && (
        <Card className="border-red-500/20 bg-red-500/5">
          <CardContent className="pt-6 flex flex-col items-center justify-center text-center space-y-4">
            <AlertCircle className="w-12 h-12 text-red-500/80" />
            <div>
              <h3 className="text-lg font-semibold text-red-500">Failed to load events</h3>
              <p className="text-sm text-muted-foreground mt-1">
                {error instanceof Error ? error.message : 'An unknown error occurred while communicating with the API.'}
              </p>
            </div>
            <Button variant="outline" onClick={() => refetch()}>Try Again</Button>
          </CardContent>
        </Card>
      )}

      {!isLoading && !isError && events?.length === 0 && (
        <Card className="border-dashed bg-transparent">
          <CardContent className="pt-10 pb-10 flex flex-col items-center justify-center text-center">
            <div className="w-16 h-16 bg-secondary/50 rounded-full flex items-center justify-center mb-4">
              <Activity className="w-8 h-8 text-muted-foreground" />
            </div>
            <h3 className="text-xl font-semibold tracking-tight">No Events Found</h3>
            <p className="text-muted-foreground max-w-sm mt-2 mb-6">
              There are no observable events recorded for this session.
            </p>
          </CardContent>
        </Card>
      )}

      {!isLoading && !isError && events && events.length > 0 && (
        <div className="grid grid-cols-1 gap-4">
          {events.map((event: Event) => (
            <Card key={event.event_id} className="bg-card/50 border-border">
              <CardHeader className="pb-2 pt-4 px-4 flex flex-row items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="flex items-center gap-1.5 text-sm text-muted-foreground bg-secondary/50 px-2 py-1 rounded-md border border-border/50">
                    <Clock className="w-3.5 h-3.5" />
                    <span>T+{event.timestamp_seconds.toFixed(2)}s</span>
                  </div>
                  {event.track_id !== null && (
                    <span className="text-sm text-muted-foreground font-mono">
                      Track: {event.track_id}
                    </span>
                  )}
                </div>
                {getEventBadge(event.event_type)}
              </CardHeader>
              <CardContent className="px-4 pb-4">
                <p className="text-sm">{event.description}</p>
                {event.evidence && Object.keys(event.evidence).length > 0 && (
                  <div className="mt-3 bg-background/50 p-3 rounded-md border border-border/50 text-xs font-mono text-muted-foreground">
                    <pre className="whitespace-pre-wrap">{JSON.stringify(event.evidence, null, 2)}</pre>
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
