import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Mail, Lock, User as UserIcon, ArrowRight, AlertCircle, Loader2, CheckCircle2, Building, ShieldCheck } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

export const SignupPage: React.FC = () => {
  const { signup } = useAuth();
  const navigate = useNavigate();

  const [name, setName] = useState('');
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [department, setDepartment] = useState('Department of Computer Science & Engineering');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [errors, setErrors] = useState<{
    name?: string;
    username?: string;
    email?: string;
    password?: string;
    confirmPassword?: string;
    general?: string;
  }>({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Validate form
  const validate = (): boolean => {
    const nextErrors: typeof errors = {};

    if (!name.trim()) {
      nextErrors.name = 'Full name is required.';
    }

    if (!email.trim()) {
      nextErrors.email = 'Email address is required.';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      nextErrors.email = 'Please enter a valid email address.';
    }

    if (!password) {
      nextErrors.password = 'Password is required.';
    } else if (password.length < 6) {
      nextErrors.password = 'Password must be at least 6 characters.';
    }

    if (!confirmPassword) {
      nextErrors.confirmPassword = 'Confirm your password.';
    } else if (confirmPassword !== password) {
      nextErrors.confirmPassword = 'Passwords do not match.';
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
      await signup({
        name,
        username: username.trim() || undefined,
        email,
        department,
        password,
        confirmPassword,
      });
      navigate('/search', { replace: true });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Registration failed. Please try again.';
      setErrors({ general: message });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="relative min-h-screen flex items-center justify-center p-4 bg-[#0b1219] overflow-hidden py-10">
      {/* Background ambient glow */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[520px] h-[520px] bg-[#d2434e]/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-10 right-10 w-[380px] h-[380px] bg-[#a7d0d2]/5 rounded-full blur-3xl pointer-events-none" />

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, ease: 'easeOut' }}
        className="relative w-full max-w-md z-10"
      >
        <div className="refire-card p-6 sm:p-8 shadow-2xl border border-[#4d728e]/35 bg-[#141d26]/95 backdrop-blur-xl rounded-2xl">
          {/* Header */}
          <div className="text-center mb-6">
            <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl overflow-hidden border border-[#d2434e]/50 mb-3.5 shadow-lg bg-[#0d1117] ring-4 ring-[#d2434e]/10">
              <img src="/unknown-logo.jpg" alt="UNKNOWN Logo" className="w-full h-full object-cover" />
            </div>
            <h1 className="text-2xl font-black tracking-tight text-white mb-1">Create Account</h1>
            <div className="inline-flex items-center gap-1.5 px-3 py-0.5 rounded-full bg-[#0b1219] border border-[#d2434e]/30 text-[11px] text-[#d2434e] font-mono mb-2">
              <ShieldCheck className="w-3.5 h-3.5" />
              <span>Researcher Registration</span>
            </div>
            <p className="text-xs text-[#f3faf0]/75">
              Register your researcher profile to query the semantic knowledge engine
            </p>
          </div>

          {/* General Error */}
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
                  <p className="font-bold text-rose-200">Registration Error</p>
                  <p className="mt-0.5 text-rose-300/90 leading-relaxed">{errors.general}</p>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-3.5">
            {/* Full Name */}
            <div>
              <label className="block text-xs font-medium text-[#f3faf0]/80 mb-1">
                Full Name <span className="text-[#d2434e]">*</span>
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-[#f3faf0]/50">
                  <UserIcon className="w-4 h-4" />
                </div>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => {
                    setName(e.target.value);
                    if (errors.name) setErrors((prev) => ({ ...prev, name: undefined }));
                  }}
                  placeholder="e.g. Niddhyy or Alex Rivera"
                  className={`w-full pl-10 pr-3.5 py-2.5 bg-[#0b1219] border rounded-xl text-sm text-white placeholder-[#f3faf0]/40 focus:outline-none transition-all ${
                    errors.name
                      ? 'border-rose-500/80 focus:border-rose-500 ring-1 ring-rose-500/20'
                      : 'border-[#4d728e]/40 focus:border-[#d2434e] focus:ring-1 focus:ring-[#d2434e]/30'
                  }`}
                />
              </div>
              {errors.name && (
                <p className="mt-1 text-xs text-rose-400 flex items-center gap-1">
                  <AlertCircle className="w-3.5 h-3.5" />
                  {errors.name}
                </p>
              )}
            </div>

            {/* Username */}
            <div>
              <label className="block text-xs font-medium text-[#f3faf0]/80 mb-1">
                Username / Researcher ID (Optional)
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-[#f3faf0]/50">
                  <span className="text-xs font-mono font-bold text-[#a7d0d2]">@</span>
                </div>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="e.g. niddhyy"
                  className="w-full pl-10 pr-3.5 py-2.5 bg-[#0b1219] border border-[#4d728e]/40 rounded-xl text-sm text-white placeholder-[#f3faf0]/40 focus:border-[#d2434e] focus:outline-none transition-all"
                />
              </div>
            </div>

            {/* Email Address */}
            <div>
              <label className="block text-xs font-medium text-[#f3faf0]/80 mb-1">
                Email Address <span className="text-[#d2434e]">*</span>
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-[#f3faf0]/50">
                  <Mail className="w-4 h-4" />
                </div>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value);
                    if (errors.email) setErrors((prev) => ({ ...prev, email: undefined }));
                  }}
                  placeholder="researcher@university.edu"
                  className={`w-full pl-10 pr-3.5 py-2.5 bg-[#0b1219] border rounded-xl text-sm text-white placeholder-[#f3faf0]/40 focus:outline-none transition-all ${
                    errors.email
                      ? 'border-rose-500/80 focus:border-rose-500 ring-1 ring-rose-500/20'
                      : 'border-[#4d728e]/40 focus:border-[#d2434e] focus:ring-1 focus:ring-[#d2434e]/30'
                  }`}
                />
              </div>
              {errors.email && (
                <p className="mt-1 text-xs text-rose-400 flex items-center gap-1">
                  <AlertCircle className="w-3.5 h-3.5" />
                  {errors.email}
                </p>
              )}
            </div>

            {/* Department / Institution */}
            <div>
              <label className="block text-xs font-medium text-[#f3faf0]/80 mb-1">
                Department / Institution
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-[#f3faf0]/50">
                  <Building className="w-4 h-4" />
                </div>
                <input
                  type="text"
                  value={department}
                  onChange={(e) => setDepartment(e.target.value)}
                  placeholder="Department of Computer Science"
                  className="w-full pl-10 pr-3.5 py-2.5 bg-[#0b1219] border border-[#4d728e]/40 rounded-xl text-sm text-white placeholder-[#f3faf0]/40 focus:border-[#d2434e] focus:outline-none transition-all"
                />
              </div>
            </div>

            {/* Password */}
            <div>
              <label className="block text-xs font-medium text-[#f3faf0]/80 mb-1">
                Password <span className="text-[#d2434e]">*</span>
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-[#f3faf0]/50">
                  <Lock className="w-4 h-4" />
                </div>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value);
                    if (errors.password) setErrors((prev) => ({ ...prev, password: undefined }));
                  }}
                  placeholder="Min. 6 characters"
                  className={`w-full pl-10 pr-3.5 py-2.5 bg-[#0b1219] border rounded-xl text-sm text-white placeholder-[#f3faf0]/40 focus:outline-none transition-all ${
                    errors.password
                      ? 'border-rose-500/80 focus:border-rose-500 ring-1 ring-rose-500/20'
                      : 'border-[#4d728e]/40 focus:border-[#d2434e] focus:ring-1 focus:ring-[#d2434e]/30'
                  }`}
                />
              </div>
              {errors.password && (
                <p className="mt-1 text-xs text-rose-400 flex items-center gap-1">
                  <AlertCircle className="w-3.5 h-3.5" />
                  {errors.password}
                </p>
              )}
            </div>

            {/* Confirm Password */}
            <div>
              <label className="block text-xs font-medium text-[#f3faf0]/80 mb-1">
                Confirm Password <span className="text-[#d2434e]">*</span>
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-[#f3faf0]/50">
                  <CheckCircle2 className="w-4 h-4" />
                </div>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => {
                    setConfirmPassword(e.target.value);
                    if (errors.confirmPassword) setErrors((prev) => ({ ...prev, confirmPassword: undefined }));
                  }}
                  placeholder="Repeat your password"
                  className={`w-full pl-10 pr-3.5 py-2.5 bg-[#0b1219] border rounded-xl text-sm text-white placeholder-[#f3faf0]/40 focus:outline-none transition-all ${
                    errors.confirmPassword
                      ? 'border-rose-500/80 focus:border-rose-500 ring-1 ring-rose-500/20'
                      : 'border-[#4d728e]/40 focus:border-[#d2434e] focus:ring-1 focus:ring-[#d2434e]/30'
                  }`}
                />
              </div>
              {errors.confirmPassword && (
                <p className="mt-1 text-xs text-rose-400 flex items-center gap-1">
                  <AlertCircle className="w-3.5 h-3.5" />
                  {errors.confirmPassword}
                </p>
              )}
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full mt-3 py-2.5 px-4 bg-[#d2434e] hover:bg-[#b83842] text-white font-bold rounded-xl text-sm shadow-[0_0_20px_rgba(210,67,78,0.35)] transition-all flex items-center justify-center gap-2 cursor-pointer disabled:opacity-60"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin text-white" />
                  <span>Registering Account...</span>
                </>
              ) : (
                <>
                  <span>Create Account & Enter</span>
                  <ArrowRight className="w-4 h-4 stroke-[2.5]" />
                </>
              )}
            </button>
          </form>

          {/* Footer */}
          <div className="mt-5 pt-4 border-t border-white/8 text-center flex items-center justify-between text-xs text-[#f3faf0]/75">
            <span>Already registered?</span>
            <Link
              to="/login"
              className="text-[#d2434e] font-semibold hover:underline underline-offset-2 transition-colors flex items-center gap-1"
            >
              <span>Sign In</span>
              <ArrowRight className="w-3 h-3" />
            </Link>
          </div>
        </div>
      </motion.div>
    </div>
  );
};

export default SignupPage;
