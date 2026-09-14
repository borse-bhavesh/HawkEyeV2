import { useSearchParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { FolderLock, AlertCircle, ArrowLeft, Image as ImageIcon, Video, FileQuestion } from 'lucide-react';
import { sessionsApi } from '@/api/sessions';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import type { Evidence } from '@/types/sessions';

export default function EvidencePage() {
  const [searchParams] = useSearchParams();
  const sessionId = searchParams.get('sessionId');
  const navigate = useNavigate();

  const { 
    data: evidence, 
    isLoading, 
    isError, 
    error,
    refetch 
  } = useQuery({
    queryKey: ['session', sessionId, 'evidence'],
    queryFn: () => sessionsApi.getSessionEvidence(sessionId as string),
    enabled: !!sessionId,
  });

  if (!sessionId) {
    return (
      <Card className="border-dashed bg-transparent mt-8">
        <CardContent className="pt-10 pb-10 flex flex-col items-center justify-center text-center">
          <div className="w-16 h-16 bg-secondary/50 rounded-full flex items-center justify-center mb-4">
            <FolderLock className="w-8 h-8 text-muted-foreground" />
          </div>
          <h3 className="text-xl font-semibold tracking-tight">No Session Selected</h3>
          <p className="text-muted-foreground max-w-sm mt-2 mb-6">
            Please select a historical session to view its evidence records.
          </p>
          <Button onClick={() => navigate('/history')}>Browse Sessions</Button>
        </CardContent>
      </Card>
    );
  }

  const getEvidenceIcon = (type: string) => {
    switch (type) {
      case 'FRAME':
        return <ImageIcon className="w-5 h-5 text-blue-500" />;
      case 'VIDEO_SEGMENT':
        return <Video className="w-5 h-5 text-purple-500" />;
      default:
        return <FileQuestion className="w-5 h-5 text-muted-foreground" />;
    }
  };

  const formatDuration = (start: number, end: number) => {
    const diff = Math.max(0, end - start);
    return `${diff.toFixed(2)}s`;
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <Button variant="outline" size="icon" onClick={() => navigate(`/history/${sessionId}`)}>
            <ArrowLeft className="w-4 h-4" />
          </Button>
          <div>
            <h3 className="text-2xl font-bold tracking-tight">Evidence Records</h3>
            <p className="text-muted-foreground text-sm font-mono mt-1">
              Session: {sessionId}
            </p>
          </div>
        </div>
      </div>

      {isLoading && (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <Card key={i} className="animate-pulse bg-card/50 border-border/50 h-32" />
          ))}
        </div>
      )}

      {isError && (
        <Card className="border-red-500/20 bg-red-500/5">
          <CardContent className="pt-6 flex flex-col items-center justify-center text-center space-y-4">
            <AlertCircle className="w-12 h-12 text-red-500/80" />
            <div>
              <h3 className="text-lg font-semibold text-red-500">Failed to load evidence</h3>
              <p className="text-sm text-muted-foreground mt-1">
                {error instanceof Error ? error.message : 'An unknown error occurred while communicating with the API.'}
              </p>
            </div>
            <Button variant="outline" onClick={() => refetch()}>Try Again</Button>
          </CardContent>
        </Card>
      )}

      {!isLoading && !isError && evidence?.length === 0 && (
        <Card className="border-dashed bg-transparent">
          <CardContent className="pt-10 pb-10 flex flex-col items-center justify-center text-center">
            <div className="w-16 h-16 bg-secondary/50 rounded-full flex items-center justify-center mb-4">
              <FolderLock className="w-8 h-8 text-muted-foreground" />
            </div>
            <h3 className="text-xl font-semibold tracking-tight">No Evidence Found</h3>
            <p className="text-muted-foreground max-w-sm mt-2 mb-6">
              There are no evidence records associated with this session.
            </p>
          </CardContent>
        </Card>
      )}

      {!isLoading && !isError && evidence && evidence.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {evidence.map((record: Evidence) => (
            <Card key={record.evidence_id} className="bg-card/50 border-border flex flex-col">
              <CardHeader className="pb-3 flex flex-row items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-secondary/50 rounded-md border border-border/50">
                    {getEvidenceIcon(record.evidence_type)}
                  </div>
                  <div>
                    <CardTitle className="text-base font-semibold">
                      {record.evidence_type.replace('_', ' ')}
                    </CardTitle>
                    <p className="text-xs text-muted-foreground font-mono mt-0.5 max-w-[150px] truncate">
                      {record.evidence_id}
                    </p>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="flex-1 flex flex-col justify-between space-y-4">
                
                {/* Specific Metadata */}
                <div className="bg-background/50 rounded-md p-3 border border-border/50">
                  {record.evidence_type === 'FRAME' && record.frame && (
                    <div className="grid grid-cols-2 gap-2 text-sm">
                      <div>
                        <p className="text-xs text-muted-foreground mb-1">Frame Number</p>
                        <p className="font-mono">{record.frame.frame_number}</p>
                      </div>
                      <div>
                        <p className="text-xs text-muted-foreground mb-1">Timestamp</p>
                        <p className="font-mono">T+{record.frame.timestamp_seconds.toFixed(2)}s</p>
                      </div>
                    </div>
                  )}

                  {record.evidence_type === 'VIDEO_SEGMENT' && record.video_segment && (
                    <div className="space-y-3 text-sm">
                      <div className="grid grid-cols-2 gap-2">
                        <div>
                          <p className="text-xs text-muted-foreground mb-1">Start</p>
                          <p className="font-mono text-xs">F{record.video_segment.start_frame_number} (T+{record.video_segment.start_timestamp_seconds.toFixed(2)}s)</p>
                        </div>
                        <div>
                          <p className="text-xs text-muted-foreground mb-1">End</p>
                          <p className="font-mono text-xs">F{record.video_segment.end_frame_number} (T+{record.video_segment.end_timestamp_seconds.toFixed(2)}s)</p>
                        </div>
                      </div>
                      <div className="pt-2 border-t border-border/50 flex justify-between items-center">
                        <span className="text-xs text-muted-foreground">Duration</span>
                        <span className="font-mono text-xs font-semibold">
                          {formatDuration(record.video_segment.start_timestamp_seconds, record.video_segment.end_timestamp_seconds)}
                        </span>
                      </div>
                    </div>
                  )}

                  {!record.frame && !record.video_segment && (
                    <p className="text-sm text-muted-foreground italic">No detailed metadata available.</p>
                  )}
                </div>

                {/* Associations */}
                <div className="space-y-2">
                  {(record.event_id || record.assessment_id) && (
                    <p className="text-xs text-muted-foreground uppercase font-semibold tracking-wider">Associations</p>
                  )}
                  <div className="flex flex-wrap gap-2">
                    {record.event_id && (
                      <Badge variant="secondary" className="font-mono text-[10px] cursor-pointer hover:bg-secondary/80" onClick={() => navigate(`/events?sessionId=${sessionId}`)}>
                        Event: {record.event_id.substring(0, 8)}...
                      </Badge>
                    )}
                    {record.assessment_id && (
                      <Badge variant="secondary" className="font-mono text-[10px] cursor-pointer hover:bg-secondary/80" onClick={() => navigate(`/alerts?sessionId=${sessionId}`)}>
                        Risk: {record.assessment_id.substring(0, 8)}...
                      </Badge>
                    )}
                  </div>
                </div>

                {/* Media Disclaimer */}
                <div className="mt-4 pt-3 border-t border-border/50">
                  <p className="text-xs text-muted-foreground italic flex items-center justify-center">
                    Media preview unavailable — metadata only
                  </p>
                </div>

              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
