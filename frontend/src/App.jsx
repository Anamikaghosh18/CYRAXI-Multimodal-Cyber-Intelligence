import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Layout } from './components/Layout.jsx';
import { Dashboard } from './pages/Dashboard.jsx';
import { NewInvestigation } from './pages/NewInvestigation.jsx';
import { InvestigationReport } from './pages/InvestigationReport.jsx';
import { InvestigationHistory } from './pages/InvestigationHistory.jsx';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Layout>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/investigate" element={<NewInvestigation />} />
            <Route path="/report/:id" element={<InvestigationReport />} />
            <Route path="/history" element={<InvestigationHistory />} />
          </Routes>
        </Layout>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
