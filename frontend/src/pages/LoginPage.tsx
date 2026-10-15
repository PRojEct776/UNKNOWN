import React, { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { User, Lock, ArrowRight, AlertCircle, Sparkles, Loader2, CheckCircle2 } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

export const LoginPage: React.FC = () => {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState<{ identifier?: string; password?: string; general?: string }>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [activeTab, setActiveTab] = useState<'signin' | 'credentials'>('signin');

  // Validate form inputs
  const validate = (): boolean => {
    const nextErrors: { identifier?: string; password?: string } = {};

    if (!identifier.trim()) {
      nextErrors.identifier = 'Please enter your registered email address or username.';
    }

    if (!password) {
      nextErrors.password = 'Password is required.';
    }

    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;

    setIsSubmitting(true);
    setErrors({});

    try {
      await login({ identifier, password });
      const destination = (location.state as { from?: { pathname: string } })?.from?.pathname;
      const target = !destination || destination === '/dashboard' ? '/search' : destination;
      navigate(target, { replace: true });
    } catch (err: unknown) {
      const message =
        err instanceof Error
          ? err.message
          : 'Invalid credentials. Access denied. Please check your username and password.';
      setErrors({ general: message });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSelectAccount = (demoIdentifier: string, demoPw: string) => {
    setIdentifier(demoIdentifier);
    setPassword(demoPw);
    setErrors({});
    setActiveTab('signin');
  };

  return (
    <div className="relative min-h-screen flex items-center justify-center p-4 bg-[#0b1219] overflow-hidden">
      {/* Ambient background glow matching palette */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[520px] h-[520px] bg-[#d2434e]/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-10 right-10 w-[380px] h-[380px] bg-[#a7d0d2]/5 rounded-full blur-3xl pointer-events-none" />

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, ease: 'easeOut' }}
        className="relative w-full max-w-md z-10"
      >
        {/* Auth Card Container */}
        <div className="refire-card p-6 sm:p-8 shadow-2xl border border-[#4d728e]/35 bg-[#141d26]/95 backdrop-blur-xl rounded-2xl">
          {/* Header with Project Logo */}
          <div className="text-center mb-6">
            <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl overflow-hidden border border-[#d2434e]/50 mb-3.5 shadow-lg bg-[#0d1117] ring-4 ring-[#d2434e]/10">
              <img src="/unknown-logo.jpg" alt="UNKNOWN Logo" className="w-full h-full object-cover" />
            </div>
            <h1 className="text-2xl font-black tracking-tight text-white mb-1">UNKNOWN</h1>
            <div className="inline-flex items-center gap-1.5 px-3 py-0.5 rounded-full bg-[#0b1219] border border-[#d2434e]/30 text-[11px] text-[#d2434e] font-mono mb-2">
              <span className="w-1.5 h-1.5 rounded-full bg-[#d2434e] animate-pulse" />
              <span>Adaptive Semantic Retrieval Engine</span>
            </div>
            <p className="text-xs text-[#f3faf0]/75">
              Sign in with your researcher credentials to access the engine
            </p>
          </div>

          {/* Tab Selector: Sign In vs Official Demo Accounts */}
          <div className="grid grid-cols-2 gap-1.5 p-1 mb-5 rounded-xl bg-[#0b1219] border border-[#4d728e]/30 text-xs">
            <button
              type="button"
              onClick={() => setActiveTab('signin')}
              className={`py-1.5 rounded-lg font-medium transition-all ${
                activeTab === 'signin'
                  ? 'bg-[#1b2734] text-white shadow-sm border border-[#4d728e]/40'
                  : 'text-[#f3faf0]/60 hover:text-white'
              }`}
            >
              Sign In
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('credentials')}
              className={`py-1.5 rounded-lg font-medium transition-all flex items-center justify-center gap-1.5 ${
                activeTab === 'credentials'
                  ? 'bg-[#1b2734] text-[#a7d0d2] shadow-sm border border-[#4d728e]/40'
                  : 'text-[#f3faf0]/60 hover:text-[#a7d0d2]'
              }`}
            >
              <Sparkles className="w-3.5 h-3.5 text-[#d2434e]" />
              <span>Demo Accounts</span>
            </button>
          </div>

          {/* Quick Demo Credentials Panel */}
          {activeTab === 'credentials' ? (
            <motion.div
              initial={{ opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: 0 }}
              className="space-y-2.5 mb-5"
            >
              <div className="p-3 rounded-xl bg-[#0b1219]/90 border border-[#a7d0d2]/25 text-xs text-[#f3faf0]/80">
                <p className="font-semibold text-white mb-1 flex items-center gap-1.5">
                  <CheckCircle2 className="w-3.5 h-3.5 text-[#a7d0d2]" />
                  Pre-configured Evaluator Profiles:
                </p>
                <p className="text-[11px] text-[#f3faf0]/65 mb-3">
                  Click any profile below to immediately fill the credentials and sign in.
                </p>

                <div className="space-y-2">
                  {/* Account 1: Niddhyy */}
                  <div
                    onClick={() => handleSelectAccount('niddhyy@sepm.edu', 'niddhyy123')}
                    className="p-2.5 rounded-lg bg-[#141d26] hover:bg-[#1b2734] border border-[#d2434e]/30 hover:border-[#d2434e] cursor-pointer transition-all flex items-center justify-between group"
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-white text-xs">Niddhyy</span>
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#d2434e]/20 text-[#d2434e] border border-[#d2434e]/30 font-mono">
                          Lead Researcher
                        </span>
                      </div>
                      <p className="text-[11px] text-[#f3faf0]/60 mt-0.5">
                        <span className="text-[#a7d0d2]">niddhyy@sepm.edu</span> &bull; pw: <span className="font-mono text-white">niddhyy123</span>
                      </p>
                    </div>
                    <span className="text-[11px] text-[#d2434e] font-semibold opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1">
                      Use &rarr;
                    </span>
                  </div>

                  {/* Account 2: Alex Rivera */}
                  <div
                    onClick={() => handleSelectAccount('researcher@sepm.edu', 'semantic123')}
                    className="p-2.5 rounded-lg bg-[#141d26] hover:bg-[#1b2734] border border-[#4d728e]/35 hover:border-[#a7d0d2] cursor-pointer transition-all flex items-center justify-between group"
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-white text-xs">Alex Rivera</span>
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#a7d0d2]/15 text-[#a7d0d2] border border-[#a7d0d2]/30 font-mono">
                          AI Researcher
                        </span>
                      </div>
                      <p className="text-[11px] text-[#f3faf0]/60 mt-0.5">
                        <span className="text-[#a7d0d2]">researcher@sepm.edu</span> &bull; pw: <span className="font-mono text-white">semantic123</span>
                      </p>
                    </div>
                    <span className="text-[11px] text-[#a7d0d2] font-semibold opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1">
                      Use &rarr;
                    </span>
                  </div>

                  {/* Account 3: Dr. Elena Vance */}
                  <div
                    onClick={() => handleSelectAccount('faculty@sepm.edu', 'evaluator2026')}
                    className="p-2.5 rounded-lg bg-[#141d26] hover:bg-[#1b2734] border border-[#4d728e]/35 hover:border-[#a7d0d2] cursor-pointer transition-all flex items-center justify-between group"
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-white text-xs">Dr. Elena Vance</span>
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-300 border border-amber-500/30 font-mono">
                          SEPM Faculty
                        </span>
                      </div>
                      <p className="text-[11px] text-[#f3faf0]/60 mt-0.5">
                        <span className="text-[#a7d0d2]">faculty@sepm.edu</span> &bull; pw: <span className="font-mono text-white">evaluator2026</span>
                      </p>
                    </div>
                    <span className="text-[11px] text-amber-300 font-semibold opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1">
                      Use &rarr;
                    </span>
                  </div>
                </div>
              </div>

              <button
                type="button"
                onClick={() => setActiveTab('signin')}
                className="w-full py-2 rounded-xl bg-[#0b1219] hover:bg-[#1b2734] border border-[#4d728e]/35 text-xs text-white font-medium transition-colors"
              >
                Back to Sign In Form
              </button>
            </motion.div>
          ) : (
            <>
              {/* General Error Banner */}
              <AnimatePresence>
                {errors.general && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    className="mb-4 p-3 rounded-xl bg-rose-500/15 border border-rose-500/40 flex items-start gap-2.5 text-rose-300 text-xs shadow-inner"
                  >
                    <AlertCircle className="w-4 h-4 shrink-0 text-rose-400 mt-0.5" />
                    <div>
                      <p className="font-bold text-rose-200">Authentication Failed</p>
                      <p className="mt-0.5 text-rose-300/90 leading-relaxed">{errors.general}</p>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Sign In Form */}
              <form onSubmit={handleSubmit} className="space-y-4">
                {/* Email / Username field */}
                <div>
                  <label className="block text-xs font-medium text-[#f3faf0]/80 mb-1.5">
                    Email Address or Username
                  </label>
                  <div className="relative">
                    <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-[#f3faf0]/50">
                      <User className="w-4 h-4" />
                    </div>
                    <input
                      type="text"
                      value={identifier}
                      onChange={(e) => {
                        setIdentifier(e.target.value);
                        if (errors.identifier || errors.general) {
                          setErrors((prev) => ({ ...prev, identifier: undefined, general: undefined }));
                        }
                      }}
                      placeholder="niddhyy@sepm.edu or niddhyy"
                      autoComplete="username"
                      className={`w-full pl-10 pr-3.5 py-2.5 bg-[#0b1219] border rounded-xl text-sm text-white placeholder-[#f3faf0]/40 focus:outline-none transition-all ${
                        errors.identifier || errors.general
                          ? 'border-rose-500/80 focus:border-rose-500 ring-1 ring-rose-500/20'
                          : 'border-[#4d728e]/40 focus:border-[#d2434e] focus:ring-1 focus:ring-[#d2434e]/30'
                      }`}
                    />
                  </div>
                  {errors.identifier && (
                    <p className="mt-1.5 text-xs text-rose-400 flex items-center gap-1">
                      <AlertCircle className="w-3.5 h-3.5" />
                      {errors.identifier}
                    </p>
                  )}
                </div>

                {/* Password field */}
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <label className="block text-xs font-medium text-[#f3faf0]/80">Password</label>
                    <button
                      type="button"
                      onClick={() => setActiveTab('credentials')}
                      className="text-xs text-[#a7d0d2] hover:text-[#d2434e] transition-colors"
                    >
                      View valid demo logins
                    </button>
                  </div>
                  <div className="relative">
                    <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-[#f3faf0]/50">
                      <Lock className="w-4 h-4" />
                    </div>
                    <input
                      type="password"
                      value={password}
                      onChange={(e) => {
                        setPassword(e.target.value);
                        if (errors.password || errors.general) {
                          setErrors((prev) => ({ ...prev, password: undefined, general: undefined }));
                        }
                      }}
                      placeholder="Enter account password"
                      autoComplete="current-password"
                      className={`w-full pl-10 pr-3.5 py-2.5 bg-[#0b1219] border rounded-xl text-sm text-white placeholder-[#f3faf0]/40 focus:outline-none transition-all ${
                        errors.password || errors.general
                          ? 'border-rose-500/80 focus:border-rose-500 ring-1 ring-rose-500/20'
                          : 'border-[#4d728e]/40 focus:border-[#d2434e] focus:ring-1 focus:ring-[#d2434e]/30'
                      }`}
                    />
                  </div>
                  {errors.password && (
                    <p className="mt-1.5 text-xs text-rose-400 flex items-center gap-1">
                      <AlertCircle className="w-3.5 h-3.5" />
                      {errors.password}
                    </p>
                  )}
                </div>

                {/* Submit Button */}
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="w-full mt-2 py-2.5 px-4 bg-[#d2434e] hover:bg-[#b83842] text-white font-bold rounded-xl text-sm shadow-[0_0_20px_rgba(210,67,78,0.35)] transition-all flex items-center justify-center gap-2 cursor-pointer disabled:opacity-60"
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin text-white" />
                      <span>Verifying Credentials...</span>
                    </>
                  ) : (
                    <>
                      <span>Sign In to Engine</span>
                      <ArrowRight className="w-4 h-4 stroke-[2.5]" />
                    </>
                  )}
                </button>
              </form>
            </>
          )}

          {/* Footer Navigation */}
          <div className="mt-6 pt-5 border-t border-white/8 text-center flex items-center justify-between text-xs text-[#f3faf0]/75">
            <span>Don't have an account?</span>
            <Link
              to="/signup"
              className="text-[#d2434e] font-semibold hover:underline underline-offset-2 transition-colors flex items-center gap-1"
            >
              <span>Create Account</span>
              <ArrowRight className="w-3 h-3" />
            </Link>
          </div>
        </div>
      </motion.div>
    </div>
  );
};

export default LoginPage;