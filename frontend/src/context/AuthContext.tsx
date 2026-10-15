import React, { createContext, useContext, useState, useEffect } from 'react';
import type { User, LoginCredentials, SignupCredentials } from '../types/auth';
import {
  getStoredUser,
  mockLogin,
  mockSignup,
  mockLogout,
  updateStoredProfile,
  updateStoredUser,
} from '../lib/mockAuth';

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (credentials: LoginCredentials) => Promise<void>;
  signup: (credentials: SignupCredentials) => Promise<void>;
  logout: () => Promise<void>;
  updateProfile: (updates: Partial<User>) => Promise<void>;
  updateProfilePicture: (avatarUrl: string) => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // Load existing session on initial load
  useEffect(() => {
    try {
      const stored = getStoredUser();
      if (stored) {
        setUser(stored);
      }
    } catch (e) {
      console.error('Failed to load user session', e);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const login = async (credentials: LoginCredentials) => {
    const loggedInUser = await mockLogin(credentials);
    setUser(loggedInUser);
  };

  const signup = async (credentials: SignupCredentials) => {
    const newUser = await mockSignup(credentials);
    setUser(newUser);
  };

  const logout = async () => {
    await mockLogout();
    setUser(null);
  };

  const updateProfile = async (updates: Partial<User>) => {
    const updated = await updateStoredProfile(updates);
    setUser(updated);
  };

  const updateProfilePicture = (avatarUrl: string) => {
    if (!user) throw new Error('You must be signed in to update your profile.');
    const updatedUser = { ...user, avatarUrl };
    updateStoredUser(updatedUser);
    setUser(updatedUser);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isLoading,
        login,
        signup,
        logout,
        updateProfile,
        updateProfilePicture,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
