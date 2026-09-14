import { useQuery } from '@tanstack/react-query';
import { Loader2, CheckCircle2, AlertTriangle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { sessionsApi } from '@/api/sessions';
import { useNavigate } from 'react-router-dom';

interface ProcessingStatusProps {
  sessionId: string;
  onReset: () => void;
}

export default function ProcessingStatus({ sessionId, onReset }: ProcessingStatusProps) {
  const navigate = useNavigate();
  const { data: session, isError } = useQuery({
    queryKey: ['session', sessionId],
    queryFn: () => sessionsApi.getSession(sessionId),
    enabled: Boolean(sessionId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === 'COMPLETED' || status === 'FAILED') {
        return false;
      }
      return 2500;
    },
    retry: 3,
  });

  const displayStatus = session?.status?.toUpperCase() || 'PENDING';

  if (displayStatus === 'COMPLETED') {
    return (
      <div className="flex flex-col items-center justify-center text-center py-6 border border-border/50 rounded-lg bg-background/50">
        <CheckCircle2 className="w-12 h-12 text-green-500 mb-4" />
        <h3 className="text-xl font-bold tracking-tight text-foreground/90 mb-2 uppercase">
          Analysis Complete
        </h3>
        <p className="text-sm text-muted-foreground max-w-md mb-6">
          The recording has finished processing.
        </p>
        
        <div className="flex flex-col items-center gap-2 mb-8 bg-card px-6 py-4 rounded-lg border border-border">
          <div className="flex flex-row justify-between w-full max-w-xs gap-8">
            <span className="text-xs text-muted-foreground uppercase font-semibold">Session</span>
            <span className="font-mono text-sm">{sessionId.substring(0, 8)}...</span>
          </div>
          <div className="flex flex-row justify-between w-full max-w-xs gap-8 mt-1">
            <span className="text-xs text-muted-foreground uppercase font-semibold">Status</span>
            <span className="font-mono text-sm text-green-400 capitalize">Completed</span>
          </div>
        </div>

        <div className="flex gap-4">
          <Button variant="default" onClick={() => navigate(`/history/${sessionId}`)}>
            View Results
          </Button>
          <Button variant="outline" onClick={onReset}>
            Upload Another
          </Button>
        </div>
      </div>
    );
  }

  if (displayStatus === 'FAILED') {
    return (
      <div className="flex flex-col items-center justify-center text-center py-6 border border-red-500/20 rounded-lg bg-red-500/5">
        <AlertTriangle className="w-12 h-12 text-red-500 mb-4" />
        <h3 className="text-xl font-bold tracking-tight text-red-500 mb-2 uppercase">
          Processing Failed
        </h3>
        <p className="text-sm text-red-400/80 max-w-md mb-6">
          The video could not be processed.
        </p>
        
        <div className="flex flex-col items-center gap-2 mb-8 bg-card px-6 py-4 rounded-lg border border-border">
          <div className="flex flex-row justify-between w-full max-w-xs gap-8">
            <span className="text-xs text-muted-foreground uppercase font-semibold">Session</span>
            <span className="font-mono text-sm">{sessionId.substring(0, 8)}...</span>
          </div>
          <div className="flex flex-row justify-between w-full max-w-xs gap-8 mt-1">
            <span className="text-xs text-muted-foreground uppercase font-semibold">Status</span>
            <span className="font-mono text-sm text-red-400 capitalize">Failed</span>
          </div>
        </div>

        <Button variant="outline" onClick={onReset}>
          Try Again
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center text-center py-6 border border-border/50 rounded-lg bg-background/50">
      <Loader2 className="w-12 h-12 text-blue-500 mb-4 animate-spin" />
      <h3 className="text-xl font-bold tracking-tight text-foreground/90 mb-2 uppercase">
        {displayStatus === 'STARTED' ? 'Processing Video' : 'Processing Started'}
      </h3>
      <p className="text-sm text-muted-foreground max-w-md mb-6">
        {displayStatus === 'STARTED' 
          ? 'The uploaded CCTV recording is being analyzed.' 
          : 'Your recording was accepted successfully.'}
      </p>
      
      {isError && (
        <div className="mb-4 text-xs text-amber-500 bg-amber-500/10 px-3 py-1.5 rounded border border-amber-500/20">
          Experiencing network delays while fetching status...
        </div>
      )}

      <div className="flex flex-col items-center gap-2 mb-8 bg-card px-6 py-4 rounded-lg border border-border">
        <div className="flex flex-row justify-between w-full max-w-xs gap-8">
          <span className="text-xs text-muted-foreground uppercase font-semibold">Session</span>
          <span className="font-mono text-sm">{sessionId.substring(0, 8)}...</span>
        </div>
        <div className="flex flex-row justify-between w-full max-w-xs gap-8 mt-1">
          <span className="text-xs text-muted-foreground uppercase font-semibold">Status</span>
          <span className="font-mono text-sm text-blue-400 capitalize">
            {displayStatus === 'STARTED' ? 'Processing' : 'Pending'}
          </span>
        </div>
      </div>
    </div>
  );
}
