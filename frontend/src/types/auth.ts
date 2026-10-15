export interface UserStats {
  queriesRun: number;
  savedConcepts: number;
  lastActive: string;
}

export interface User {
  id: string;
  name: string;
  email: string;
  username: string;
  avatarUrl?: string;
  role: string;
  department?: string;
  institution?: string;
  bio?: string;
  joinedDate?: string;
  apiToken?: string;
  stats?: UserStats;
}

export interface StoredAccount extends User {
  passwordHash: string;
}

export interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}

export interface LoginCredentials {
  identifier: string; // Supports both email or username
  password: string;
}

export interface SignupCredentials {
  name: string;
  username?: string;
  email: string;
  password: string;
  confirmPassword: string;
  role?: string;
  department?: string;
  institution?: string;
}
