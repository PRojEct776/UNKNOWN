/**
 * DEMO AUTHENTICATION — NOT PRODUCTION AUTH
 *
 * This module provides browser-local demo authentication for the UNKNOWN
 * prototype. Credentials are hard-coded for evaluator access; no real server
 * is involved. Passwords are stored in plain-text in localStorage.
 *
 * DO NOT use real passwords here. Replace with server-side auth before any
 * production deployment.
 */

import type {
  LoginCredentials,
  SignupCredentials,
  StoredAccount,
  User,
} from '../types/auth';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const STORAGE_KEY = 'unknown_demo_user';
const ACCOUNTS_KEY = 'unknown_demo_accounts';

/** Simulated network latency (ms) to make the demo feel realistic. */
const MOCK_LATENCY_MS = 320;

// ---------------------------------------------------------------------------
// Pre-seeded demo accounts
// ---------------------------------------------------------------------------

const SEED_ACCOUNTS: StoredAccount[] = [
  {
    id: 'usr_niddhyy_001',
    name: 'Niddhyy',
    email: 'niddhyy@sepm.edu',
    username: 'niddhyy',
    role: 'Lead Researcher',
    department: 'Department of Computer Science & Engineering',
    institution: 'Autonomous College of Engineering',
    bio: 'Lead researcher on adaptive semantic routing, 3D conceptual space projections, and hybrid dense-sparse IR architecture.',
    joinedDate: 'October 2026',
    apiToken: 'unk_demo_niddhyy_not_connected',
    avatarUrl: undefined,
    stats: { queriesRun: 24, savedConcepts: 7, lastActive: 'Today' },
    passwordHash: 'niddhyy123',
  },
  {
    id: 'usr_alex_002',
    name: 'Alex Rivera',
    email: 'researcher@sepm.edu',
    username: 'alex_rivera',
    role: 'AI Researcher',
    department: 'Department of Artificial Intelligence',
    institution: 'Autonomous College of Engineering',
    bio: 'Researcher investigating hybrid semantic retrieval, multi-modal knowledge graph representations, and dense-sparse query routing algorithms.',
    joinedDate: 'September 2026',
    apiToken: 'unk_demo_alex_not_connected',
    avatarUrl: undefined,
    stats: { queriesRun: 18, savedConcepts: 5, lastActive: 'Yesterday' },
    passwordHash: 'semantic123',
  },
  {
    id: 'usr_elena_003',
    name: 'Dr. Elena Vance',
    email: 'faculty@sepm.edu',
    username: 'dr_elena',
    role: 'SEPM Faculty',
    department: 'Faculty of Engineering',
    institution: 'Autonomous College of Engineering',
    bio: 'Faculty evaluator for the SEPM 2026 capstone project. Interests: knowledge engineering, ontology design, and evaluation methodology.',
    joinedDate: 'October 2026',
    apiToken: 'unk_demo_elena_not_connected',
    avatarUrl: undefined,
    stats: { queriesRun: 6, savedConcepts: 2, lastActive: 'Today' },
    passwordHash: 'evaluator2026',
  },
];

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

function simulateLatency(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, MOCK_LATENCY_MS));
}

/** Return all stored accounts, seeding defaults on first call. */
function getStoredAccounts(): StoredAccount[] {
  try {
    const raw = localStorage.getItem(ACCOUNTS_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as StoredAccount[];
      if (Array.isArray(parsed) && parsed.length > 0) return parsed;
    }
  } catch {
    // Fall through to seed
  }

  // Seed defaults on first run
  localStorage.setItem(ACCOUNTS_KEY, JSON.stringify(SEED_ACCOUNTS));
  return SEED_ACCOUNTS;
}

function saveAccounts(accounts: StoredAccount[]): void {
  localStorage.setItem(ACCOUNTS_KEY, JSON.stringify(accounts));
}

function stripPassword(account: StoredAccount): User {
  const { passwordHash: _pw, ...user } = account;
  return user;
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/** Read the currently persisted User session, or null if none. */
export function getStoredUser(): User | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as User;
  } catch {
    return null;
  }
}

/** Persist the current User session. */
export function updateStoredUser(user: User): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(user));
}

/**
 * [DEMO] Authenticate with email/username + password.
 * Throws an Error with a human-readable message on failure.
 */
export async function mockLogin(credentials: LoginCredentials): Promise<User> {
  await simulateLatency();

  const accounts = getStoredAccounts();
  const normalizedIdentifier = credentials.identifier.trim().toLowerCase();

  const account = accounts.find(
    (a) =>
      a.email.toLowerCase() === normalizedIdentifier ||
      a.username.toLowerCase() === normalizedIdentifier,
  );

  if (!account || account.passwordHash !== credentials.password) {
    throw new Error(
      'Invalid credentials. Please check your email/username and password.',
    );
  }

  const user = stripPassword(account);
  updateStoredUser(user);
  return user;
}

/**
 * [DEMO] Register a new account.
 * Throws an Error if the email is already taken or passwords do not match.
 */
export async function mockSignup(credentials: SignupCredentials): Promise<User> {
  await simulateLatency();

  if (credentials.password !== credentials.confirmPassword) {
    throw new Error('Passwords do not match.');
  }

  const accounts = getStoredAccounts();

  const emailTaken = accounts.some(
    (a) => a.email.toLowerCase() === credentials.email.trim().toLowerCase(),
  );
  if (emailTaken) {
    throw new Error('An account with this email address already exists.');
  }

  const newAccount: StoredAccount = {
    id: `usr_${Date.now()}`,
    name: credentials.name.trim(),
    email: credentials.email.trim().toLowerCase(),
    username:
      credentials.username?.trim() ||
      credentials.email.split('@')[0].toLowerCase(),
    role: credentials.role || 'Researcher',
    department: credentials.department?.trim() || undefined,
    institution: undefined,
    bio: undefined,
    joinedDate: new Date().toLocaleDateString('en-US', {
      month: 'long',
      year: 'numeric',
    }),
    apiToken: `unk_demo_${Date.now()}_not_connected`,
    avatarUrl: undefined,
    stats: { queriesRun: 0, savedConcepts: 0, lastActive: 'Just now' },
    passwordHash: credentials.password,
  };

  saveAccounts([...accounts, newAccount]);

  const user = stripPassword(newAccount);
  updateStoredUser(user);
  return user;
}

/**
 * [DEMO] Sign out and clear the local session.
 */
export async function mockLogout(): Promise<void> {
  await simulateLatency();
  localStorage.removeItem(STORAGE_KEY);
}

/**
 * [DEMO] Update mutable profile fields for the current user.
 * Returns the updated User object.
 */
export async function updateStoredProfile(updates: Partial<User>): Promise<User> {
  await simulateLatency();

  const current = getStoredUser();
  if (!current) throw new Error('No active session found.');

  const updated: User = { ...current, ...updates };
  updateStoredUser(updated);

  // Also persist into the accounts list so the change survives re-login
  const accounts = getStoredAccounts();
  const updatedAccounts = accounts.map((a) =>
    a.id === updated.id ? { ...a, ...updates } : a,
  );
  saveAccounts(updatedAccounts);

  return updated;
}
