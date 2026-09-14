import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AppShell } from '@/layouts/AppShell';
import Overview from '@/pages/Overview';
import PlaceholderPage from '@/pages/PlaceholderPage';

import HistoryList from '@/pages/HistoryList';
import HistoryDetail from '@/pages/HistoryDetail';

import Events from '@/pages/Events';
import AlertsRisk from '@/pages/AlertsRisk';
import EvidencePage from '@/pages/Evidence';
import Monitoring from '@/pages/Monitoring';
import Analytics from '@/pages/Analytics';

const queryClient = new QueryClient();

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Router>
        <Routes>
          <Route element={<AppShell />}>
            <Route path="/" element={<Overview />} />
            <Route path="/monitoring" element={<Monitoring />} />
            
            <Route path="/events" element={<Events />} />
            <Route path="/alerts" element={<AlertsRisk />} />
            <Route path="/evidence" element={<EvidencePage />} />
            
            {/* History Routes */}
            <Route path="/history" element={<HistoryList />} />
            <Route path="/history/:sessionId" element={<HistoryDetail />} />
            
            {/* Analytics */}
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/status" element={<PlaceholderPage title="System Status" description="Module diagnostics and connection statuses." />} />
            <Route path="/settings" element={<PlaceholderPage title="Settings" description="Application and engine configuration." />} />
          </Route>
        </Routes>
      </Router>
    </QueryClientProvider>
  );
}

export default App;
