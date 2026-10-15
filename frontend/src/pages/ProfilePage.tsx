import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  Building,
  Key,
  Calendar,
  Search,
  Check,
  Copy,
  Edit3,
  Save,
  X,
  LogOut,
  Sparkles,
  ShieldCheck,
  Activity,
  ArrowRight,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

export const ProfilePage: React.FC = () => {
  const { user, logout, updateProfile } = useAuth();
  const navigate = useNavigate();

  const [isEditing, setIsEditing] = useState(false);
  const [copiedToken, setCopiedToken] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Edit form state
  const [formData, setFormData] = useState({
    name: user?.name || '',
    department: user?.department || 'Department of Computer Science & Engineering',
    institution: user?.institution || 'Autonomous College of Engineering',
    bio:
      user?.bio ||
      'Lead researcher on adaptive semantic routing, 3D conceptual space projections, and hybrid dense-sparse IR architecture.',
  });

  if (!user) {
    return null;
  }

  const handleCopyToken = () => {
    if (user.apiToken) {
      navigator.clipboard.writeText(user.apiToken);
      setCopiedToken(true);
      setTimeout(() => setCopiedToken(false), 2000);
    }
  };

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    await updateProfile({
      name: formData.name.trim(),
      department: formData.department.trim(),
      institution: formData.institution.trim(),
      bio: formData.bio.trim(),
    });
    setIsEditing(false);
    setSaveSuccess(true);
    setTimeout(() => setSaveSuccess(false), 3000);
  };

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <div className="min-h-[calc(100vh-4rem)] bg-[#0b1219] text-[#f3faf0] pb-16">
      {/* Cover Banner with geometric glow */}
      <div className="relative h-48 sm:h-56 bg-gradient-to-r from-[#141d26] via-[#1b2734] to-[#141d26] border-b border-[#4d728e]/25 overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(#d2434e_1px,transparent_1px)] [background-size:24px_24px] opacity-15" />
        <div className="absolute -top-12 right-1/4 w-96 h-96 bg-[#d2434e]/15 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute top-1/2 left-10 w-72 h-72 bg-[#a7d0d2]/10 rounded-full blur-3xl pointer-events-none" />

        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 h-full flex flex-col justify-end pb-4 relative z-10">
          <div className="flex items-center gap-2 text-xs font-mono text-[#a7d0d2]">
            <Sparkles className="w-3.5 h-3.5 text-[#d2434e]" />
            <span>ACADEMIC RESEARCH PROFILE &bull; SEPM 2026</span>
          </div>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 -mt-16 sm:-mt-20 relative z-20">
        {/* Profile Header Block */}
        <div className="bg-[#141d26]/95 border border-[#4d728e]/35 backdrop-blur-xl rounded-2xl p-6 sm:p-8 shadow-2xl">
          <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-6 pb-6 border-b border-white/10">
            {/* Avatar & Identifiers */}
            <div className="flex flex-col sm:flex-row items-start sm:items-center gap-5">
              <div className="relative group">
                <div className="w-24 h-24 sm:w-28 sm:h-28 rounded-2xl overflow-hidden border-2 border-[#d2434e] bg-[#0b1219] shadow-xl p-1 shrink-0 ring-4 ring-[#d2434e]/15">
                  <img
                    src={user.avatarUrl || `https://api.dicebear.com/7.x/bottts/svg?seed=${user.email}`}
                    alt={user.name}
                    className="w-full h-full object-cover rounded-xl"
                  />
                </div>
                <span className="absolute bottom-1 right-1 w-4 h-4 rounded-full bg-emerald-500 border-2 border-[#141d26]" title="Active Session" />
              </div>

              <div>
                <div className="flex flex-wrap items-center gap-2.5 mb-1.5">
                  <h1 className="text-2xl sm:text-3xl font-black text-white tracking-tight">{user.name}</h1>
                  <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-[#d2434e]/20 border border-[#d2434e]/40 text-[#d2434e]">
                    {user.role || 'Lead Researcher'}
                  </span>
                </div>
                <p className="text-xs sm:text-sm text-[#a7d0d2] font-mono mb-2">
                  @{user.username || user.email.split('@')[0]} &bull; {user.email}
                </p>
                <p className="text-xs text-[#f3faf0]/75 flex items-center gap-2">
                  <Building className="w-3.5 h-3.5 text-[#4d728e]" />
                  <span>{user.department || 'Department of Computer Science & Engineering'}</span>
                </p>
              </div>
            </div>

            {/* Quick Action Buttons */}
            <div className="flex flex-wrap items-center gap-2.5">
              {!isEditing ? (
                <button
                  onClick={() => setIsEditing(true)}
                  className="px-4 py-2 rounded-xl bg-[#0b1219] hover:bg-[#1b2734] border border-[#4d728e]/40 text-xs font-medium text-white transition-all flex items-center gap-2 cursor-pointer shadow-sm"
                >
                  <Edit3 className="w-3.5 h-3.5 text-[#a7d0d2]" />
                  <span>Edit Profile</span>
                </button>
              ) : (
                <button
                  onClick={() => setIsEditing(false)}
                  className="px-4 py-2 rounded-xl bg-[#0b1219] hover:bg-[#1b2734] border border-[#4d728e]/40 text-xs font-medium text-[#f3faf0]/70 transition-all flex items-center gap-2 cursor-pointer"
                >
                  <X className="w-3.5 h-3.5" />
                  <span>Cancel</span>
                </button>
              )}

              <Link
                to="/search"
                className="px-4 py-2 rounded-xl bg-[#d2434e] hover:bg-[#b83842] text-xs font-bold text-white transition-all flex items-center gap-2 shadow-[0_0_15px_rgba(210,67,78,0.35)]"
              >
                <Search className="w-3.5 h-3.5 stroke-[2.5]" />
                <span>Concept Search</span>
              </Link>

              <button
                onClick={handleLogout}
                className="p-2 rounded-xl bg-[#0b1219] hover:bg-rose-500/20 border border-[#4d728e]/40 hover:border-rose-500/40 text-xs font-medium text-rose-400 transition-all flex items-center gap-1.5 cursor-pointer"
                title="Sign Out"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Success banner */}
          <AnimatePresence>
            {saveSuccess && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="mt-4 p-3 rounded-xl bg-emerald-500/15 border border-emerald-500/40 text-emerald-300 text-xs flex items-center gap-2"
              >
                <Check className="w-4 h-4 text-emerald-400" />
                <span>Profile details updated and saved successfully!</span>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Edit Profile Form OR View Details */}
          {isEditing ? (
            <form onSubmit={handleSaveProfile} className="mt-6 space-y-4 pt-2">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-[#f3faf0]/80 mb-1">
                    Display Name
                  </label>
                  <input
                    type="text"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    className="w-full px-3.5 py-2.5 bg-[#0b1219] border border-[#4d728e]/40 rounded-xl text-sm text-white focus:border-[#d2434e] focus:outline-none"
                    required
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-[#f3faf0]/80 mb-1">
                    Department
                  </label>
                  <input
                    type="text"
                    value={formData.department}
                    onChange={(e) => setFormData({ ...formData, department: e.target.value })}
                    className="w-full px-3.5 py-2.5 bg-[#0b1219] border border-[#4d728e]/40 rounded-xl text-sm text-white focus:border-[#d2434e] focus:outline-none"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-[#f3faf0]/80 mb-1">
                    Institution / University
                  </label>
                  <input
                    type="text"
                    value={formData.institution}
                    onChange={(e) => setFormData({ ...formData, institution: e.target.value })}
                    className="w-full px-3.5 py-2.5 bg-[#0b1219] border border-[#4d728e]/40 rounded-xl text-sm text-white focus:border-[#d2434e] focus:outline-none"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-[#f3faf0]/80 mb-1">
                    Email Address (Immutable)
                  </label>
                  <input
                    type="email"
                    value={user.email}
                    disabled
                    className="w-full px-3.5 py-2.5 bg-[#0b1219]/50 border border-white/10 rounded-xl text-sm text-[#f3faf0]/50 cursor-not-allowed"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-[#f3faf0]/80 mb-1">
                  Research Bio & Focus
                </label>
                <textarea
                  rows={3}
                  value={formData.bio}
                  onChange={(e) => setFormData({ ...formData, bio: e.target.value })}
                  className="w-full px-3.5 py-2 bg-[#0b1219] border border-[#4d728e]/40 rounded-xl text-sm text-white focus:border-[#d2434e] focus:outline-none resize-none"
                />
              </div>

              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setIsEditing(false)}
                  className="px-4 py-2 rounded-xl bg-[#0b1219] text-xs font-medium text-[#f3faf0]/70 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 rounded-xl bg-[#d2434e] hover:bg-[#b83842] text-xs font-bold text-white flex items-center gap-2 shadow-md cursor-pointer"
                >
                  <Save className="w-3.5 h-3.5" />
                  <span>Save Changes</span>
                </button>
              </div>
            </form>
          ) : (
            <div className="mt-6 pt-2">
              <p className="text-xs text-[#f3faf0]/60 uppercase tracking-wider font-mono mb-2">Research Focus & Bio</p>
              <p className="text-sm text-[#f3faf0]/90 leading-relaxed max-w-3xl bg-[#0b1219]/60 p-4 rounded-xl border border-white/5">
                {user.bio || 'Researcher investigating hybrid semantic retrieval, multi-modal knowledge graph representations, and dense-sparse query routing algorithms.'}
              </p>
            </div>
          )}
        </div>

        {/* 3-Column Profile Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-8">
          {/* Card 1: Account & Credentials Details */}
          <div className="p-6 rounded-2xl bg-[#141d26]/90 border border-[#4d728e]/35 shadow-xl flex flex-col justify-between">
            <div>
              <div className="flex items-center gap-2 mb-4 text-xs font-mono text-[#a7d0d2]">
                <ShieldCheck className="w-4 h-4 text-[#d2434e]" />
                <span>AUTHENTICATION & DETAILS</span>
              </div>

              <div className="space-y-3.5 text-xs">
                <div>
                  <span className="text-[#f3faf0]/50 block text-[11px]">Account ID</span>
                  <span className="font-mono text-white font-medium">{user.id}</span>
                </div>

                <div>
                  <span className="text-[#f3faf0]/50 block text-[11px]">Primary Email</span>
                  <span className="text-white font-medium">{user.email}</span>
                </div>

                <div>
                  <span className="text-[#f3faf0]/50 block text-[11px]">Institutional Role</span>
                  <span className="text-white font-medium">{user.role || 'Lead Researcher'}</span>
                </div>

                <div>
                  <span className="text-[#f3faf0]/50 block text-[11px]">Affiliation</span>
                  <span className="text-white font-medium">{user.institution || 'Autonomous College of Engineering'}</span>
                </div>

                <div>
                  <span className="text-[#f3faf0]/50 block text-[11px]">Member Since</span>
                  <span className="text-white font-medium flex items-center gap-1.5 mt-0.5">
                    <Calendar className="w-3.5 h-3.5 text-[#a7d0d2]" />
                    {user.joinedDate || 'October 2026'}
                  </span>
                </div>
              </div>
            </div>

            <div className="mt-6 pt-4 border-t border-white/10">
              <div className="flex items-center justify-between">
                <span className="text-[11px] text-[#f3faf0]/60">Status</span>
                <span className="inline-flex items-center gap-1 text-[11px] text-emerald-400 font-medium">
                  <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                  Authenticated Session
                </span>
              </div>
            </div>
          </div>

          {/* Card 2: Research Engine & API Access */}
          <div className="p-6 rounded-2xl bg-[#141d26]/90 border border-[#4d728e]/35 shadow-xl flex flex-col justify-between">
            <div>
              <div className="flex items-center gap-2 mb-4 text-xs font-mono text-[#a7d0d2]">
                <Key className="w-4 h-4 text-[#d2434e]" />
                <span>API & BACKEND INTEGRATION</span>
              </div>

              <div className="space-y-4 text-xs">
                <div>
                  <span className="text-[#f3faf0]/50 block text-[11px] mb-1">Retrieval Endpoint</span>
                  <span className="font-mono text-xs px-2.5 py-1.5 rounded-lg bg-[#0b1219] border border-[#4d728e]/35 text-[#a7d0d2] block truncate">
                    POST http://localhost:8000/api/v1/retrieve
                  </span>
                </div>

                <div>
                  <span className="text-[#f3faf0]/50 block text-[11px] mb-1">Demo API Token · Not connected to a backend</span>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs px-2.5 py-1.5 rounded-lg bg-[#0b1219] border border-[#4d728e]/35 text-white flex-1 truncate">
                      {user.apiToken || 'unk_demo_not_connected'}
                    </span>
                    <button
                      onClick={handleCopyToken}
                      className="p-1.5 rounded-lg bg-[#0b1219] hover:bg-[#1b2734] border border-[#4d728e]/40 text-[#a7d0d2] hover:text-white transition-all cursor-pointer"
                      title="Copy API Token"
                    >
                      {copiedToken ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                    </button>
                  </div>
                </div>

                <div>
                  <span className="text-[#f3faf0]/50 block text-[11px]">Offline Fallback Engine</span>
                  <p className="text-[11px] text-[#f3faf0]/75 mt-0.5">
                    Graceful mock dataset activates automatically if backend server is unreachable.
                  </p>
                </div>
              </div>
            </div>

            <div className="mt-6 pt-4 border-t border-white/10">
              <Link
                to="/search"
                className="w-full py-2 px-3 rounded-xl bg-[#0b1219] hover:bg-[#1b2734] border border-[#4d728e]/40 text-xs text-white font-medium flex items-center justify-between transition-colors"
              >
                <span>Launch Query Console</span>
                <ArrowRight className="w-3.5 h-3.5 text-[#a7d0d2]" />
              </Link>
            </div>
          </div>

          {/* Card 3: Research Engine Activity */}
          <div className="p-6 rounded-2xl bg-[#141d26]/90 border border-[#4d728e]/35 shadow-xl flex flex-col justify-between">
            <div>
              <div className="flex items-center gap-2 mb-4 text-xs font-mono text-[#a7d0d2]">
                <Activity className="w-4 h-4 text-[#d2434e]" />
                <span>ACTIVITY & METRICS</span>
              </div>

              <div className="grid grid-cols-2 gap-3 mb-4">
                <div className="p-3 rounded-xl bg-[#0b1219] border border-[#4d728e]/30">
                  <span className="text-[11px] text-[#f3faf0]/50 block">Queries Run</span>
                  <span className="text-2xl font-black text-white">{user.stats?.queriesRun ?? 24}</span>
                </div>

                <div className="p-3 rounded-xl bg-[#0b1219] border border-[#4d728e]/30">
                  <span className="text-[11px] text-[#f3faf0]/50 block">Saved Nodes</span>
                  <span className="text-2xl font-black text-[#a7d0d2]">{user.stats?.savedConcepts ?? 7}</span>
                </div>
              </div>

              <div className="space-y-2.5 text-xs text-[#f3faf0]/75">
                <div className="flex items-center justify-between">
                  <span>3D Orbit Visualizer</span>
                  <span className="text-emerald-400 font-mono text-[11px]">Enabled (WebGL)</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>Cross-Encoder Reranker</span>
                  <span className="text-[#a7d0d2] font-mono text-[11px]">Active</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>Benchmark Domains</span>
                  <span className="text-white font-mono text-[11px]">5 Active</span>
                </div>
              </div>
            </div>

            <div className="mt-6 pt-4 border-t border-white/10">
              <Link
                to="/search"
                className="w-full py-2 px-3 rounded-xl bg-[#0b1219] hover:bg-[#1b2734] border border-[#4d728e]/40 text-xs text-white font-medium flex items-center justify-between transition-colors"
              >
                <span>Return to Research Workspace</span>
                <ArrowRight className="w-3.5 h-3.5 text-[#d2434e]" />
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ProfilePage;