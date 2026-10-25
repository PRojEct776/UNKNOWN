import React from 'react';
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
} from 'react-router-dom';

import { AuthProvider, useAuth } from './context/AuthContext';
import { ProtectedRoute } from './components/ProtectedRoute';
import { Navbar } from './components/Navbar';

import { LoginPage } from './pages/LoginPage';
import { SignupPage } from './pages/SignupPage';
import { SearchPage } from './pages/SearchPage';
import { ProfilePage } from './pages/ProfilePage';
import { SharedConversationPage } from './pages/SharedConversationPage';

const RootRedirect: React.FC = () => {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return null;
  }

  return (
    <Navigate
      to={isAuthenticated ? '/search' : '/login'}
      replace
    />
  );
};

const PublicAuthRoute: React.FC<{
  children: React.ReactNode;
}> = ({ children }) => {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return null;
  }

  if (isAuthenticated) {
    return <Navigate to="/search" replace />;
  }

  return <>{children}</>;
};

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* PUBLIC */}
          <Route
            path="/login"
            element={
              <PublicAuthRoute>
                <LoginPage />
              </PublicAuthRoute>
            }
          />

          <Route
            path="/signup"
            element={
              <PublicAuthRoute>
                <SignupPage />
              </PublicAuthRoute>
            }
          />

          <Route
            path="/shared/:token"
            element={<SharedConversationPage />}
          />

          {/* PROTECTED */}
          <Route
            path="/dashboard"
            element={<Navigate to="/search" replace />}
          />

          <Route
            path="/workspace"
            element={<Navigate to="/search" replace />}
          />

          <Route
            path="/search"
            element={
              <ProtectedRoute>
                <SearchPage />
              </ProtectedRoute>
            }
          />

          <Route
            path="/profile"
            element={
              <ProtectedRoute>
                <div className="min-h-screen flex flex-col bg-[#0c1217] text-[#e6ebef]">
                  <Navbar />
                  <main className="flex-1">
                    <ProfilePage />
                  </main>
                </div>
              </ProtectedRoute>
            }
          />

          {/* ROOT */}
          <Route
            path="/"
            element={<RootRedirect />}
          />

          {/* FALLBACK */}
          <Route
            path="*"
            element={<Navigate to="/" replace />}
          />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
};

export default App;
