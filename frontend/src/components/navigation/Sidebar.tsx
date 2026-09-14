import { NavLink } from 'react-router-dom';
import { 
  LayoutDashboard, 
  MonitorPlay, 
  Activity, 
  ShieldAlert, 
  FolderLock, 
  History, 
  BarChart2, 
  Server, 
  Settings 
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface SidebarProps {
  className?: string;
  onNavigate?: () => void;
}

const mainNavItems = [
  { name: 'Overview', path: '/', icon: LayoutDashboard },
  { name: 'Live Monitoring', path: '/monitoring', icon: MonitorPlay },
  { name: 'Events', path: '/events', icon: Activity },
  { name: 'Alerts & Risk', path: '/alerts', icon: ShieldAlert },
  { name: 'Evidence', path: '/evidence', icon: FolderLock },
  { name: 'History', path: '/history', icon: History },
  { name: 'Analytics', path: '/analytics', icon: BarChart2 },
];

const bottomNavItems = [
  { name: 'System Status', path: '/status', icon: Server },
  { name: 'Settings', path: '/settings', icon: Settings },
];

export function Sidebar({ className, onNavigate }: SidebarProps) {
  return (
    <div className={cn("flex flex-col h-full bg-card border-r border-border", className)}>
      <div className="p-4 flex items-center gap-3 border-b border-border">
        <div className="bg-primary/20 p-2 rounded-lg border border-primary/30">
          <ShieldAlert className="w-6 h-6 text-primary" />
        </div>
        <div>
          <h1 className="text-xl font-bold tracking-tight leading-none">HAWKEYE V2</h1>
          <p className="text-[10px] text-muted-foreground uppercase tracking-widest mt-1">Command Center</p>
        </div>
      </div>
      
      <div className="flex-1 overflow-y-auto py-4">
        <nav className="space-y-1 px-2">
          {mainNavItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              onClick={onNavigate}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors",
                  isActive 
                    ? "bg-primary/10 text-primary font-medium" 
                    : "text-muted-foreground hover:bg-secondary hover:text-foreground"
                )
              }
            >
              <item.icon className="w-4 h-4" />
              {item.name}
            </NavLink>
          ))}
        </nav>
      </div>

      <div className="p-4 border-t border-border">
        <nav className="space-y-1">
          {bottomNavItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              onClick={onNavigate}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors",
                  isActive 
                    ? "bg-primary/10 text-primary font-medium" 
                    : "text-muted-foreground hover:bg-secondary hover:text-foreground"
                )
              }
            >
              <item.icon className="w-4 h-4" />
              {item.name}
            </NavLink>
          ))}
        </nav>
      </div>
    </div>
  );
}
