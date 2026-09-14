import { useQuery, useQueries } from '@tanstack/react-query';
import { BarChart3, Database, Target, ShieldAlert, FileText, AlertCircle, RefreshCw, Activity } from 'lucide-react';
import { sessionsApi } from '@/api/sessions';
import { calculateAnalytics, type AnalyticsResult, type Distribution } from '@/lib/analytics';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import type { ProcessingSession } from '@/types/sessions';

function DistributionBar({ item, max, colorClass }: { item: Distribution; max: number; colorClass: string }) {
  const width = Math.max(0, (item.count / max) * 100);
  return (
    <div className="flex flex-col space-y-1">
      <div className="flex justify-between items-end">
        <span className="text-xs font-semibold text-muted-foreground uppercase">{item.label}</span>
        <span className="text-xs font-mono">{item.count} ({item.percentage}%)</span>
      </div>
      <div className="h-2 w-full bg-secondary/50 rounded overflow-hidden">
        <div 
          className={`h-full rounded ${colorClass}`} 
          style={{ width: `${width}%` }} 
        />
      </div>
    </div>
  );
}

export default function Analytics() {
  // 1. Fetch base sessions to know what histories to fetch
  const { 
    data: sessions, 
    isLoading: isSessionsLoading,
    isError: isSessionsError,
    refetch: refetchSessions
  } = useQuery({
    queryKey: ['sessions'],
    queryFn: sessionsApi.getSessions
  });

  // 2. Fetch history for all available sessions
  const sessionQueries = useQueries({
    queries: (sessions || []).map((session: ProcessingSession) => ({
      queryKey: ['session', session.session_id, 'history'],
      queryFn: () => sessionsApi.getSessionHistory(session.session_id),
      staleTime: 60000 // Cache for 1 min
    }))
  });

  const isHistoriesLoading = sessionQueries.some(q => q.isLoading);
  const isHistoriesError = sessionQueries.some(q => q.isError);
  const isLoading = isSessionsLoading || isHistoriesLoading;
  const isError = isSessionsError || isHistoriesError;

  // 3. Aggregate
  let analytics: AnalyticsResult | null = null;
  if (!isLoading && !isError && sessions) {
    const runs = sessionQueries
      .map(q => q.data)
      .filter(data => data !== undefined) as NonNullable<typeof sessionQueries[0]['data']>[];
    analytics = calculateAnalytics(runs);
  }

  const getRiskColor = (label: string) => {
    switch (label) {
      case 'CRITICAL': return 'bg-red-500';
      case 'HIGH': return 'bg-orange-500';
      case 'MEDIUM': return 'bg-yellow-500';
      case 'LOW': return 'bg-emerald-500';
      default: return 'bg-primary';
    }
  };

  const getStatusColor = (label: string) => {
    switch (label) {
      case 'OPEN': return 'bg-red-500';
      case 'ACKNOWLEDGED': return 'bg-yellow-500';
      case 'RESOLVED': return 'bg-emerald-500';
      default: return 'bg-primary';
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h3 className="text-2xl font-bold tracking-tight">Historical Analytics</h3>
          <p className="text-muted-foreground text-sm mt-1">
            Aggregate intelligence patterns and system activity.
          </p>
        </div>
        <Badge variant="outline" className="bg-primary/5 text-primary border-primary/20 px-3 uppercase tracking-wider text-[10px]">
          Historical Mode
        </Badge>
      </div>

      {isLoading && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {[1, 2, 3, 4].map((i) => (
              <Card key={i} className="animate-pulse bg-card/50 border-border/50 h-24" />
            ))}
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {[1, 2].map((i) => (
              <Card key={i} className="animate-pulse bg-card/50 border-border/50 h-64" />
            ))}
          </div>
        </div>
      )}

      {isError && (
        <Card className="border-red-500/20 bg-red-500/5">
          <CardContent className="pt-6 flex flex-col items-center justify-center text-center space-y-4">
            <AlertCircle className="w-12 h-12 text-red-500/80" />
            <div>
              <h3 className="text-lg font-semibold text-red-500">Failed to load analytics</h3>
              <p className="text-sm text-muted-foreground mt-1">
                Unable to retrieve or aggregate session history.
              </p>
            </div>
            <Button variant="outline" onClick={() => {
              refetchSessions();
              sessionQueries.forEach(q => q.refetch());
            }}>
              <RefreshCw className="w-4 h-4 mr-2" />
              Retry
            </Button>
          </CardContent>
        </Card>
      )}

      {!isLoading && !isError && analytics && analytics.summary.totalSessions === 0 && (
        <Card className="border-dashed bg-transparent mt-8">
          <CardContent className="pt-10 pb-10 flex flex-col items-center justify-center text-center">
            <div className="w-16 h-16 bg-secondary/50 rounded-full flex items-center justify-center mb-4">
              <BarChart3 className="w-8 h-8 text-muted-foreground" />
            </div>
            <h3 className="text-xl font-semibold tracking-tight">No Historical Data Available</h3>
            <p className="text-muted-foreground max-w-sm mt-2">
              There are no processing sessions recorded in the database to analyze.
            </p>
          </CardContent>
        </Card>
      )}

      {!isLoading && !isError && analytics && analytics.summary.totalSessions > 0 && (
        <>
          {/* Summary KPIs */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <Card className="bg-card border-border/50 flex flex-col justify-center">
              <CardContent className="p-4 flex items-center gap-4">
                <div className="p-2 bg-blue-500/10 rounded border border-blue-500/20">
                  <Database className="w-5 h-5 text-blue-500" />
                </div>
                <div>
                  <p className="text-[10px] text-muted-foreground uppercase font-semibold tracking-wider">Sessions</p>
                  <p className="font-mono text-xl font-bold">{analytics.summary.totalSessions}</p>
                </div>
              </CardContent>
            </Card>
            <Card className="bg-card border-border/50 flex flex-col justify-center">
              <CardContent className="p-4 flex items-center gap-4">
                <div className="p-2 bg-purple-500/10 rounded border border-purple-500/20">
                  <Target className="w-5 h-5 text-purple-500" />
                </div>
                <div>
                  <p className="text-[10px] text-muted-foreground uppercase font-semibold tracking-wider">Tracks</p>
                  <p className="font-mono text-xl font-bold">{analytics.summary.totalTracks}</p>
                </div>
              </CardContent>
            </Card>
            <Card className="bg-card border-border/50 flex flex-col justify-center">
              <CardContent className="p-4 flex items-center gap-4">
                <div className="p-2 bg-amber-500/10 rounded border border-amber-500/20">
                  <Activity className="w-5 h-5 text-amber-500" />
                </div>
                <div>
                  <p className="text-[10px] text-muted-foreground uppercase font-semibold tracking-wider">Events</p>
                  <p className="font-mono text-xl font-bold">{analytics.summary.totalEvents}</p>
                </div>
              </CardContent>
            </Card>
            <Card className="bg-card border-border/50 flex flex-col justify-center">
              <CardContent className="p-4 flex items-center gap-4">
                <div className="p-2 bg-red-500/10 rounded border border-red-500/20">
                  <ShieldAlert className="w-5 h-5 text-red-500" />
                </div>
                <div>
                  <p className="text-[10px] text-muted-foreground uppercase font-semibold tracking-wider">Risks</p>
                  <p className="font-mono text-xl font-bold">{analytics.summary.totalRisks}</p>
                </div>
              </CardContent>
            </Card>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Event Distribution */}
            <Card className="bg-card border-border/50">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-semibold flex items-center gap-2">
                  <Activity className="w-4 h-4 text-amber-500" />
                  Event Distribution
                </CardTitle>
              </CardHeader>
              <CardContent>
                {analytics.eventDistribution.length > 0 ? (
                  <div className="space-y-4 mt-2">
                    {analytics.eventDistribution.map((item, idx) => (
                      <DistributionBar 
                        key={item.label} 
                        item={item} 
                        max={analytics!.eventDistribution[0].count}
                        colorClass={idx % 2 === 0 ? "bg-amber-500/80" : "bg-amber-600/80"} 
                      />
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground italic">No historical event data available.</p>
                )}
              </CardContent>
            </Card>

            {/* Risk Distributions (Stacked) */}
            <div className="space-y-6 flex flex-col">
              {/* Risk Level */}
              <Card className="bg-card border-border/50 flex-1">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-semibold flex items-center gap-2">
                    <ShieldAlert className="w-4 h-4 text-red-500" />
                    Risk Levels
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {analytics.riskLevelDistribution.length > 0 ? (
                    <div className="space-y-4 mt-2">
                      {analytics.riskLevelDistribution.map(item => (
                        <DistributionBar 
                          key={item.label} 
                          item={item} 
                          max={analytics!.riskLevelDistribution[0].count}
                          colorClass={getRiskColor(item.label)} 
                        />
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground italic">No risk assessment data available.</p>
                  )}
                </CardContent>
              </Card>

              {/* Status */}
              <Card className="bg-card border-border/50 flex-1">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-semibold flex items-center gap-2">
                    <FileText className="w-4 h-4 text-emerald-500" />
                    Assessment Status
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {analytics.statusDistribution.length > 0 ? (
                    <div className="space-y-4 mt-2">
                      {analytics.statusDistribution.map(item => (
                        <DistributionBar 
                          key={item.label} 
                          item={item} 
                          max={analytics!.statusDistribution[0].count}
                          colorClass={getStatusColor(item.label)} 
                        />
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground italic">No status data available.</p>
                  )}
                </CardContent>
              </Card>
            </div>
          </div>
        </>
      )}
    </div>
  );
}


