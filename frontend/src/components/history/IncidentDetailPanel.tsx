import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ShieldAlert, Image as ImageIcon, Video as VideoIcon, FileText, Info } from 'lucide-react';
import type { Event, RiskAssessment, Evidence } from '@/types/sessions';

interface IncidentDetailPanelProps {
  selectedEvent: Event | null;
  risks: RiskAssessment[];
  evidence: Evidence[];
}

const formatTime = (seconds: number) => {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  const ms = Math.floor((seconds % 1) * 100);
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}.${ms.toString().padStart(2, '0')}`;
};

export default function IncidentDetailPanel({ selectedEvent, risks, evidence }: IncidentDetailPanelProps) {
  if (!selectedEvent) {
    return (
      <Card className="bg-card/40 border-border/50 h-full min-h-[400px] flex items-center justify-center">
        <div className="flex flex-col items-center text-muted-foreground gap-3">
          <Info className="w-8 h-8 opacity-50" />
          <p className="text-sm uppercase tracking-wider">Select an incident to view details.</p>
        </div>
      </Card>
    );
  }

  // Find associated risk assessment
  // Risk could be associated by event_id or contributing_event_ids
  const associatedRisk = risks.find(r => 
    r.event_id === selectedEvent.event_id || 
    (r.contributing_event_ids && r.contributing_event_ids.includes(selectedEvent.event_id))
  );

  const isHighRisk = associatedRisk && 
    (associatedRisk.risk_level?.toUpperCase() === 'HIGH' || associatedRisk.risk_level?.toUpperCase() === 'CRITICAL');

  // Find and deduplicate evidence
  const relevantEvidence = evidence.filter(item => {
    if (item.event_id === selectedEvent.event_id) return true;
    if (item.assessment_id && associatedRisk) {
      const riskAny = associatedRisk as any;
      if (riskAny.id === item.assessment_id || 
          riskAny.assessment_id === item.assessment_id || 
          riskAny.event_id === item.assessment_id) {
        return true;
      }
    }
    return false;
  });

  const uniqueEvidenceMap = new Map<string, Evidence>();
  relevantEvidence.forEach(item => uniqueEvidenceMap.set(item.evidence_id, item));
  const uniqueEvidence = Array.from(uniqueEvidenceMap.values());

  return (
    <Card className="bg-card border-border shadow-xl flex flex-col h-full max-h-[600px]">
      <CardHeader className="border-b border-border/50 bg-muted/10 pb-4 shrink-0">
        <CardTitle className="text-lg uppercase tracking-wide">Incident Details</CardTitle>
        {isHighRisk && selectedEvent.event_type === 'ZONE_ENTRY' && (
          <div className="mt-3 inline-flex items-center gap-2 px-3 py-1.5 bg-red-500/10 border border-red-500/30 rounded-md text-red-500">
            <ShieldAlert className="w-4 h-4 animate-pulse" />
            <span className="text-xs font-bold uppercase tracking-widest">High Risk - Restricted Zone Intrusion</span>
          </div>
        )}
      </CardHeader>

      <CardContent className="flex-1 overflow-y-auto p-0">
        <div className="p-6 space-y-6">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Track ID</p>
              <p className="font-mono text-sm">{selectedEvent.track_id ?? 'N/A'}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Time</p>
              <p className="font-mono text-sm">{formatTime(selectedEvent.timestamp_seconds)}</p>
            </div>
            <div className="col-span-2">
              <p className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Event</p>
              <Badge variant="secondary" className="uppercase font-mono text-xs">
                {selectedEvent.event_type}
              </Badge>
            </div>
            <div className="col-span-2">
              <p className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Description</p>
              <p className="text-sm">{selectedEvent.description || 'No description available.'}</p>
            </div>
            
            {isHighRisk && associatedRisk?.reason && (
              <div className="col-span-2 mt-2 p-3 bg-red-950/20 border border-red-900/30 rounded-md">
                <p className="text-xs text-red-400 uppercase tracking-wider mb-1 font-semibold">Risk Reason</p>
                <p className="text-sm text-red-200">{associatedRisk.reason}</p>
              </div>
            )}
          </div>

          <div className="pt-4 border-t border-border/50">
            <h4 className="text-sm font-semibold uppercase tracking-wider mb-4 flex items-center justify-between">
              Evidence
              <Badge variant="outline" className="font-mono text-xs">{uniqueEvidence.length} Item(s)</Badge>
            </h4>

            {uniqueEvidence.length === 0 ? (
              <p className="text-sm text-muted-foreground italic">No evidence available for this incident.</p>
            ) : (
              <div className="space-y-3">
                {uniqueEvidence.map(item => {
                  const type = item.evidence_type.toUpperCase();
                  const Icon = type.includes('VIDEO') ? VideoIcon : type.includes('FRAME') ? ImageIcon : FileText;
                  
                  return (
                    <div key={item.evidence_id} className="p-3 bg-muted/20 border border-border/50 rounded-lg">
                      <div className="flex items-center gap-3 mb-2">
                        <Icon className="w-4 h-4 text-blue-400" />
                        <span className="text-xs font-semibold uppercase tracking-wider text-blue-400">{type}</span>
                        {item.frame?.timestamp_seconds !== undefined && (
                          <span className="text-xs font-mono text-muted-foreground ml-auto">
                            {formatTime(item.frame.timestamp_seconds)}
                          </span>
                        )}
                        {item.video_segment?.start_timestamp_seconds !== undefined && (
                          <span className="text-xs font-mono text-muted-foreground ml-auto">
                            {formatTime(item.video_segment.start_timestamp_seconds)} - {formatTime(item.video_segment.end_timestamp_seconds)}
                          </span>
                        )}
                      </div>
                      
                      <div className="mt-2 space-y-1">
                        <div className="flex items-center justify-between text-xs">
                          <span className="text-muted-foreground">Source Type:</span>
                          <span className="font-mono">{item.source?.source_type || 'UNKNOWN'}</span>
                        </div>
                        {item.frame?.frame_number !== undefined && (
                          <div className="flex items-center justify-between text-xs">
                            <span className="text-muted-foreground">Frame:</span>
                            <span className="font-mono">{item.frame.frame_number}</span>
                          </div>
                        )}
                        {item.assessment_id && (
                          <div className="flex items-center justify-between text-xs">
                            <span className="text-muted-foreground">Assoc. Risk:</span>
                            <span className="font-mono text-emerald-400">Linked</span>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
