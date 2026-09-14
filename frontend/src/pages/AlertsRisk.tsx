import { useSearchParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ShieldAlert, AlertCircle, ArrowLeft, Shield, AlertTriangle } from 'lucide-react';
import { sessionsApi } from '@/api/sessions';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import type { RiskAssessment } from '@/types/sessions';

export default function AlertsRisk() {
  const [searchParams] = useSearchParams();
  const sessionId = searchParams.get('sessionId');
  const navigate = useNavigate();

  const { 
    data: risks, 
    isLoading, 
    isError, 
    error,
    refetch 
  } = useQuery({
    queryKey: ['session', sessionId, 'risks'],
    queryFn: () => sessionsApi.getSessionRisks(sessionId as string),
    enabled: !!sessionId,
  });

  if (!sessionId) {
    return (
      <Card className="border-dashed bg-transparent mt-8">
        <CardContent className="pt-10 pb-10 flex flex-col items-center justify-center text-center">
          <div className="w-16 h-16 bg-secondary/50 rounded-full flex items-center justify-center mb-4">
            <ShieldAlert className="w-8 h-8 text-muted-foreground" />
          </div>
          <h3 className="text-xl font-semibold tracking-tight">No Session Selected</h3>
          <p className="text-muted-foreground max-w-sm mt-2 mb-6">
            Please select a historical session to view its risk assessments.
          </p>
          <Button onClick={() => navigate('/history')}>Browse Sessions</Button>
        </CardContent>
      </Card>
    );
  }

  const getRiskLevelBadge = (level: string) => {
    switch (level.toLowerCase()) {
      case 'low':
        return <Badge variant="outline" className="bg-blue-500/10 text-blue-500 border-blue-500/20 px-3 uppercase tracking-wider text-[10px]">Level: Low</Badge>;
      case 'medium':
        return <Badge variant="outline" className="bg-amber-500/10 text-amber-500 border-amber-500/20 px-3 uppercase tracking-wider text-[10px]">Level: Medium</Badge>;
      case 'high':
        return <Badge variant="outline" className="bg-orange-500/10 text-orange-500 border-orange-500/20 px-3 uppercase tracking-wider text-[10px]">Level: High</Badge>;
      case 'critical':
        return <Badge variant="outline" className="bg-red-500/10 text-red-500 border-red-500/20 px-3 uppercase tracking-wider text-[10px]">Level: Critical</Badge>;
      default:
        return <Badge variant="outline" className="px-3 uppercase tracking-wider text-[10px]">Level: {level}</Badge>;
    }
  };

  const getPriorityBadge = (priority: string) => {
    switch (priority.toLowerCase()) {
      case 'low':
        return <Badge variant="secondary" className="px-3 uppercase tracking-wider text-[10px]">Priority: Low</Badge>;
      case 'medium':
        return <Badge variant="secondary" className="px-3 uppercase tracking-wider text-[10px] bg-amber-500/20 text-amber-500 hover:bg-amber-500/30">Priority: Medium</Badge>;
      case 'high':
        return <Badge variant="secondary" className="px-3 uppercase tracking-wider text-[10px] bg-orange-500/20 text-orange-500 hover:bg-orange-500/30">Priority: High</Badge>;
      case 'critical':
        return <Badge variant="secondary" className="px-3 uppercase tracking-wider text-[10px] bg-red-500/20 text-red-500 hover:bg-red-500/30">Priority: Critical</Badge>;
      default:
        return <Badge variant="secondary" className="px-3 uppercase tracking-wider text-[10px]">Priority: {priority}</Badge>;
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status.toLowerCase()) {
      case 'open':
        return <Badge variant="outline" className="bg-blue-500/10 text-blue-500 border-blue-500/20 px-3 uppercase tracking-wider text-[10px]">Status: Open</Badge>;
      case 'acknowledged':
        return <Badge variant="outline" className="bg-purple-500/10 text-purple-500 border-purple-500/20 px-3 uppercase tracking-wider text-[10px]">Status: Acknowledged</Badge>;
      case 'resolved':
        return <Badge variant="outline" className="bg-emerald-500/10 text-emerald-500 border-emerald-500/20 px-3 uppercase tracking-wider text-[10px]">Status: Resolved</Badge>;
      default:
        return <Badge variant="outline" className="px-3 uppercase tracking-wider text-[10px]">Status: {status}</Badge>;
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
            <h3 className="text-2xl font-bold tracking-tight">Risk Assessments</h3>
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
              <h3 className="text-lg font-semibold text-red-500">Failed to load risk assessments</h3>
              <p className="text-sm text-muted-foreground mt-1">
                {error instanceof Error ? error.message : 'An unknown error occurred while communicating with the API.'}
              </p>
            </div>
            <Button variant="outline" onClick={() => refetch()}>Try Again</Button>
          </CardContent>
        </Card>
      )}

      {!isLoading && !isError && risks?.length === 0 && (
        <Card className="border-dashed bg-transparent">
          <CardContent className="pt-10 pb-10 flex flex-col items-center justify-center text-center">
            <div className="w-16 h-16 bg-secondary/50 rounded-full flex items-center justify-center mb-4">
              <Shield className="w-8 h-8 text-muted-foreground" />
            </div>
            <h3 className="text-xl font-semibold tracking-tight">No Risk Assessments</h3>
            <p className="text-muted-foreground max-w-sm mt-2 mb-6">
              There are no risk assessments recorded for this session.
            </p>
          </CardContent>
        </Card>
      )}

      {!isLoading && !isError && risks && risks.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {risks.map((risk: RiskAssessment) => (
            <Card key={risk.event_id} className="bg-card/50 border-border flex flex-col">
              <CardHeader className="pb-3 pt-5 px-5">
                <div className="flex flex-wrap gap-2 mb-3">
                  {getRiskLevelBadge(risk.risk_level)}
                  {getPriorityBadge(risk.priority)}
                  {getStatusBadge(risk.status)}
                </div>
                <CardTitle className="text-lg flex items-start gap-2">
                  <AlertTriangle className="w-5 h-5 mt-0.5 opacity-80" />
                  {risk.reason}
                </CardTitle>
              </CardHeader>
              <CardContent className="px-5 pb-5 flex-1 flex flex-col justify-between space-y-4">
                {risk.evidence && (
                  <div className="bg-secondary/30 p-4 rounded-md border border-border/50">
                    <p className="text-sm font-medium mb-1">Policy Explanation</p>
                    <p className="text-sm text-muted-foreground">{risk.evidence.explanation}</p>
                    <div className="flex items-center gap-2 mt-3 pt-3 border-t border-border/50 text-xs text-muted-foreground">
                      <span className="font-mono bg-background px-1.5 py-0.5 rounded">{risk.evidence.source_type}</span>
                      <span className="font-mono bg-background px-1.5 py-0.5 rounded">{risk.evidence.policy_identifier}</span>
                    </div>
                  </div>
                )}
                
                {risk.contributing_event_types.length > 0 && (
                  <div>
                    <p className="text-xs text-muted-foreground uppercase font-semibold tracking-wider mb-2">Contributing Events</p>
                    <div className="flex flex-wrap gap-2">
                      {risk.contributing_event_types.map((type, idx) => (
                        <Badge key={idx} variant="outline" className="text-xs bg-background">
                          {type.replace(/_/g, ' ')}
                        </Badge>
                      ))}
                    </div>
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
