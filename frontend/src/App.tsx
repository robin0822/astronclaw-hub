import { BrowserRouter } from 'react-router-dom';
import { StoreProvider } from './store/store-provider';
import { ThemeProvider } from './theme/theme-provider';
import ScrollToTop from './components/ScrollToTop';
import AppRoutes from './routes/app-routes';

export default function App() {
  return (
    <ThemeProvider>
      <StoreProvider>
        <BrowserRouter>
          <ScrollToTop />
          <AppRoutes />
        </BrowserRouter>
      </StoreProvider>
    </ThemeProvider>
  );
}
