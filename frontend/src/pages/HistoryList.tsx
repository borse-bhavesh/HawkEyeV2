import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { History, Search, ArrowRight, AlertCircle, Calendar, Trash2, Loader2 } from 'lucide-react';
import { sessionsApi } from '@/api/sessions';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import type { ProcessingSession } from '@/types/sessions';

export default function HistoryList() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [sessionToDelete, setSessionToDelete] = useState<ProcessingSession | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const deleteMutation = useMutation({
    mutationFn: (sessionId: string) => sessionsApi.deleteSession(sessionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sessions'] });
      setSessionToDelete(null);
      setDeleteError(null);
    },
    onError: (err: any) => {
      setDeleteError(err.message || 'Failed to delete session');
    }
  });
  
  const { 
    data: sessions, 
    isLoading, 
    isError, 
    error,
    refetch 
  } = useQuery({
    queryKey: ['sessions'],
    queryFn: sessionsApi.getSessions,
  });

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
  };

  const getStatusBadge = (status: string) => {
    switch (status.toUpperCase()) {
      case 'COMPLETED':
        return <Badge variant="outline" className="bg-emerald-500/10 text-emerald-500 border-emerald-500/20">Completed</Badge>;
      case 'FAILED':
        return <Badge variant="outline" className="bg-red-500/10 text-red-500 border-red-500/20">Failed</Badge>;
      case 'STARTED':
      case 'PROCESSING':
        return <Badge variant="outline" className="bg-blue-500/10 text-blue-500 border-blue-500/20">Processing</Badge>;
      default:
        return <Badge variant="outline" className="bg-gray-500/10 text-gray-500 border-gray-500/20">{status}</Badge>;
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h3 className="text-2xl font-bold tracking-tight">Historical Sessions</h3>
          <p className="text-muted-foreground">
            Browse and review previously processed surveillance sessions.
          </p>
        </div>
        <div className="relative w-full md:w-64">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search sessions..."
            className="flex h-9 w-full rounded-md border border-border bg-background px-3 py-1 text-sm shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 pl-9"
          />
        </div>
      </div>

      {isLoading && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <Card key={i} className="animate-pulse bg-card/50 border-border/50 h-48" />
          ))}
        </div>
      )}

      {isError && (
        <Card className="border-red-500/20 bg-red-500/5">
          <CardContent className="pt-6 flex flex-col items-center justify-center text-center space-y-4">
            <AlertCircle className="w-12 h-12 text-red-500/80" />
            <div>
              <h3 className="text-lg font-semibold text-red-500">Failed to load sessions</h3>
              <p className="text-sm text-muted-foreground mt-1">
                {error instanceof Error ? error.message : 'An unknown error occurred while communicating with the API.'}
              </p>
            </div>
            <Button variant="outline" onClick={() => refetch()}>Try Again</Button>
          </CardContent>
        </Card>
      )}

      {!isLoading && !isError && sessions?.length === 0 && (
        <Card className="border-dashed bg-transparent">
          <CardContent className="pt-10 pb-10 flex flex-col items-center justify-center text-center">
            <div className="w-16 h-16 bg-secondary/50 rounded-full flex items-center justify-center mb-4">
              <History className="w-8 h-8 text-muted-foreground" />
            </div>
            <h3 className="text-xl font-semibold tracking-tight">No Sessions Found</h3>
            <p className="text-muted-foreground max-w-sm mt-2 mb-6">
              There are no historical processing sessions available in the database.
            </p>
          </CardContent>
        </Card>
      )}

      {!isLoading && !isError && sessions && sessions.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {sessions.map((session: ProcessingSession) => (
            <Card 
              key={session.session_id} 
              className="group hover:border-primary/50 transition-all cursor-pointer bg-card/50"
              onClick={() => navigate(`/history/${session.session_id}`)}
            >
              <CardHeader className="pb-3">
                <div className="flex justify-between items-start">
                  <Badge variant="secondary" className="font-mono text-xs truncate max-w-[150px]">
                    {session.session_id.substring(0, 8)}...
                  </Badge>
                  {getStatusBadge(session.status)}
                </div>
                <CardTitle className="text-lg mt-2">{session.source_id}</CardTitle>
                <div className="text-sm text-muted-foreground">{session.source_type}</div>
              </CardHeader>
              <CardContent className="pb-3">
                <div className="flex flex-col gap-2 text-sm text-muted-foreground">
                  <div className="flex items-center gap-2">
                    <Calendar className="w-4 h-4 opacity-70" />
                    <span className="truncate">
                      Started: {session.started_at ? formatDate(session.started_at) : 'N/A'}
                    </span>
                  </div>
                </div>
              </CardContent>
              <div className="flex items-center p-6 pt-0 justify-end space-x-4">
                <div className="flex items-center text-sm font-medium text-primary opacity-0 group-hover:opacity-100 transition-opacity">
                  View Details <ArrowRight className="w-4 h-4 ml-1" />
                </div>
                <Button 
                  variant="ghost" 
                  size="icon"
                  className="h-8 w-8 text-muted-foreground hover:text-red-500 hover:bg-red-500/10 opacity-0 group-hover:opacity-100 transition-opacity"
                  onClick={(e) => {
                    e.stopPropagation();
                    setSessionToDelete(session);
                    setDeleteError(null);
                  }}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}
      {/* Delete Confirmation Modal */}
      {sessionToDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <div className="w-full max-w-md p-6 bg-background border rounded-lg shadow-lg" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-xl font-bold mb-4">Delete Session?</h3>
            <p className="text-muted-foreground mb-4">
              This will permanently remove:
            </p>
            <ul className="list-disc list-inside text-muted-foreground mb-6 space-y-1">
              <li>session</li>
              <li>video</li>
              <li>detections/tracks</li>
              <li>events</li>
              <li>risks</li>
              <li>evidence</li>
            </ul>
            
            {deleteError && (
              <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 rounded-md text-red-500 text-sm">
                {deleteError}
              </div>
            )}
            
            <div className="flex justify-end space-x-3">
              <Button 
                variant="outline" 
                onClick={() => setSessionToDelete(null)}
                disabled={deleteMutation.isPending}
              >
                Cancel
              </Button>
              <Button 
                variant="destructive"
                onClick={() => deleteMutation.mutate(sessionToDelete.session_id)}
                disabled={deleteMutation.isPending}
              >
                {deleteMutation.isPending ? (
                  <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Deleting...</>
                ) : (
                  'Delete Session'
                )}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
