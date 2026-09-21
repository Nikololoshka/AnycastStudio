import { AppShell } from './components/AppShell';
import { HistoryPanel } from './features/history';
import { ComposerScreen, SummaryPanel } from './features/composer';

function App() {
  return <AppShell left={<HistoryPanel />} center={<ComposerScreen />} right={<SummaryPanel />} />;
}

export default App;
