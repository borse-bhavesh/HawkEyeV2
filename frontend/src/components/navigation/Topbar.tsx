import { Menu, User, Bell } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useLocation } from 'react-router-dom';

interface TopbarProps {
  onMenuClick: () => void;
}

const routeTitles: Record<string, string> = {
  '/': 'Overview',
  '/monitoring': 'Live Monitoring',
  '/events': 'Events',
  '/alerts': 'Alerts & Risk',
  '/evidence': 'Evidence',
  '/history': 'History',
  '/analytics': 'Analytics',
  '/status': 'System Status',
  '/settings': 'Settings',
};

export function Topbar({ onMenuClick }: TopbarProps) {
  const location = useLocation();
  const title = routeTitles[location.pathname] || 'HAWKEYE';

  return (
    <header className="h-16 border-b border-border bg-card flex items-center justify-between px-4 lg:px-6 sticky top-0 z-10">
      <div className="flex items-center gap-4">
        <Button 
          variant="ghost" 
          size="icon" 
          className="lg:hidden" 
          onClick={onMenuClick}
          aria-label="Toggle Navigation"
        >
          <Menu className="w-5 h-5" />
        </Button>
        <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
      </div>

      <div className="flex items-center gap-4">
        <Badge variant="outline" className="hidden sm:flex gap-2 bg-primary/10 text-primary border-primary/20">
          <div className="w-2 h-2 rounded-full bg-primary" />
          Operational UI
        </Badge>
        
        <div className="flex items-center gap-2 border-l border-border pl-4 ml-2">
          <Button variant="ghost" size="icon" aria-label="Notifications">
            <Bell className="w-5 h-5 text-muted-foreground" />
          </Button>
          <Button variant="ghost" size="icon" className="rounded-full bg-secondary" aria-label="User Profile">
            <User className="w-5 h-5 text-muted-foreground" />
          </Button>
        </div>
      </div>
    </header>
  );
}
