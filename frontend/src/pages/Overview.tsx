import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ShieldAlert } from 'lucide-react';

import { Link } from 'react-router-dom';

export default function Overview() {
  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h3 className="text-2xl font-bold tracking-tight">System Overview</h3>
          <p className="text-muted-foreground">
            HAWKEYE V2 Command Center operational UI.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <Card className="bg-card/50 border-border/50">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Module Status
            </CardTitle>
            <ShieldAlert className="h-4 w-4 text-primary" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-foreground">Initialized</div>
            <p className="text-xs text-muted-foreground mt-1">
              Dashboard shell initialized successfully.
            </p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-8">
        <Card className="bg-card border-border/50 hover:border-primary/30 transition-colors">
          <CardHeader>
            <CardTitle className="text-lg">Historical Sessions</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground mb-4">
              Browse previously recorded processing sessions, intelligence tracks, and detected events.
            </p>
            <Link to="/history">
              <Button variant="secondary" className="w-full sm:w-auto">
                View History
              </Button>
            </Link>
          </CardContent>
        </Card>

        <Card className="bg-card border-border/50 hover:border-primary/30 transition-colors">
          <CardHeader>
            <CardTitle className="text-lg">Aggregate Analytics</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground mb-4">
              Explore historical detection distributions, risk levels, and operational metrics.
            </p>
            <Link to="/analytics">
              <Button variant="secondary" className="w-full sm:w-auto">
                View Analytics
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
