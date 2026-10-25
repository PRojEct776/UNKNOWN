import React, { useState, useRef, useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  LayoutDashboard,
  LogOut,
  HelpCircle,
  User as UserIcon,
  ChevronDown,
} from 'lucide-react';
import { InfoModal, type ModalTab } from './InfoModal';

export const Navbar: React.FC = () => {
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [modalTab, setModalTab] = useState<ModalTab | null>(null);
  const [profileDropdownOpen, setProfileDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown on click outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setProfileDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Allow any component to open the info modal via custom event
  useEffect(() => {
    const handleOpenModal = (e: Event) => {
      const customEvent = e as CustomEvent<ModalTab>;
      if (customEvent.detail) {
        setModalTab(customEvent.detail);
      }
    };
    window.addEventListener('open-unknown-info', handleOpenModal);
    return () => window.removeEventListener('open-unknown-info', handleOpenModal);
  }, []);

  const handleLogout = async () => {
    setProfileDropdownOpen(false);
    await logout();
    navigate('/login');
  };

  const handleSectionNav = (e: React.MouseEvent, sectionId: ModalTab) => {
    e.preventDefault();
    setModalTab(sectionId);
  };

  return (
    <>
      <header className="sticky top-0 z-50 w-full border-b border-[#4d728e]/25 bg-[#0b1219]/90 backdrop-blur-xl">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          {/* Brand Logo with 3D Isometric U-Hexagon mark - Links directly to Research Workspace */}
          <Link to="/search" className="flex items-center gap-2.5 group" title="UNKNOWN Research Workspace">
            <div className="w-8 h-8 rounded-xl overflow-hidden border border-[#d2434e]/50 group-hover:border-[#d2434e] group-hover:shadow-[0_0_12px_rgba(210,67,78,0.4)] transition-all shadow-sm shrink-0 bg-[#0d1117]">
              <img
                src="/unknown-logo.jpg"
                alt="UNKNOWN Logo"
                className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
              />
            </div>
            <div className="flex items-center gap-2">
              <span className="font-extrabold tracking-wider text-white text-base">UNKNOWN</span>
            </div>
          </Link>

          {/* Center Nav Links - Scopuz Pill Bar Style */}
          <nav className="hidden md:flex items-center gap-1 px-3 py-1.5 rounded-full bg-[#141d26]/90 border border-[#4d728e]/35 shadow-inner">
            <Link
              to="/search"
              className={`flex items-center gap-1.5 px-3.5 py-1 rounded-full text-xs font-medium transition-all ${
                location.pathname === '/search'
                  ? 'bg-[#1b2734] text-white shadow-sm border border-[#4d728e]/40'
                  : 'text-[#f3faf0]/75 hover:text-white hover:bg-white/5'
              }`}
            >
              <LayoutDashboard className="w-3.5 h-3.5 text-[#d2434e]" />
              <span>Workspace</span>
            </Link>

            <button
              onClick={(e) => handleSectionNav(e, 'how-it-works')}
              className="px-3.5 py-1 rounded-full text-xs font-medium text-[#f3faf0]/75 hover:text-white hover:bg-white/5 transition-colors cursor-pointer flex items-center gap-1.5"
            >
              <span>How it works</span>
            </button>

            <button
              onClick={(e) => handleSectionNav(e, 'domains')}
              className="px-3.5 py-1 rounded-full text-xs font-medium text-[#f3faf0]/75 hover:text-white hover:bg-white/5 transition-colors cursor-pointer flex items-center gap-1.5"
            >
              <span>Domains</span>
            </button>
          </nav>

          {/* Right Side: Quick Guide + User Profile Dropdown */}
          <div className="flex items-center gap-2 sm:gap-3">
            <button
              onClick={() => setModalTab('how-it-works')}
              className="hidden sm:flex items-center gap-1 px-3 py-1.5 rounded-full bg-[#141d26] border border-[#a7d0d2]/30 hover:border-[#a7d0d2] text-[#a7d0d2] hover:text-white text-xs font-medium transition-all cursor-pointer"
              title="Open Architecture Guide"
            >
              <HelpCircle className="w-3.5 h-3.5" />
              <span>Guide</span>
            </button>

            {/* User Profile Logo Mark / Dropdown */}
            {user && (
              <div className="relative" ref={dropdownRef}>
                <button
                  type="button"
                  onClick={() => setProfileDropdownOpen(!profileDropdownOpen)}
                  className="flex items-center gap-2 pl-2 pr-2.5 py-1 rounded-full bg-[#141d26] hover:bg-[#1b2734] border border-[#4d728e]/40 hover:border-[#d2434e]/60 transition-all cursor-pointer shadow-sm group"
                  title="Click to open your Researcher Profile"
                >
                  {/* Profile Avatar / Logo */}
                  <div className="relative">
                    <img
                      src={user.avatarUrl || `https://api.dicebear.com/7.x/bottts/svg?seed=${user.email}`}
                      alt={user.name}
                      className="w-7 h-7 rounded-full border border-[#d2434e] bg-[#0b1219] p-0.5 object-cover group-hover:scale-105 transition-transform"
                    />
                    <span className="absolute bottom-0 right-0 w-2 h-2 rounded-full bg-emerald-400 border border-[#141d26]" />
                  </div>

                  {/* Name & Role Preview */}
                  <div className="hidden sm:flex flex-col text-left">
                    <span className="text-xs font-bold text-white group-hover:text-[#a7d0d2] transition-colors leading-tight">
                      {user.name}
                    </span>
                    <span className="text-[10px] text-[#f3faf0]/60 leading-tight">
                      {user.role ? user.role.split(' ')[0] : 'Researcher'}
                    </span>
                  </div>

                  <ChevronDown
                    className={`w-3.5 h-3.5 text-[#f3faf0]/60 group-hover:text-white transition-transform ${
                      profileDropdownOpen ? 'rotate-180' : ''
                    }`}
                  />
                </button>

                {/* Profile Interactive Flyout Dropdown */}
                {profileDropdownOpen && (
                  <div className="absolute right-0 mt-2 w-72 rounded-2xl bg-[#141d26] border border-[#4d728e]/45 shadow-2xl py-2 z-50 animate-in fade-in slide-in-from-top-2 duration-150">
                    {/* Header: Person's Details */}
                    <div className="px-4 py-3 border-b border-white/10 bg-[#0b1219]/60">
                      <div className="flex items-center gap-3">
                        <img
                          src={user.avatarUrl || `https://api.dicebear.com/7.x/bottts/svg?seed=${user.email}`}
                          alt={user.name}
                          className="w-10 h-10 rounded-full border border-[#d2434e] bg-[#141d26] p-0.5 object-cover"
                        />
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-bold text-white truncate">{user.name}</p>
                          <p className="text-xs text-[#a7d0d2] truncate">@{user.username || user.email.split('@')[0]}</p>
                          <p className="text-[11px] text-[#f3faf0]/60 truncate">{user.email}</p>
                        </div>
                      </div>
                      <div className="mt-2.5 flex items-center justify-between text-[10px] font-mono text-[#f3faf0]/70 pt-2 border-t border-white/5">
                        <span>Role:</span>
                        <span className="text-[#d2434e] font-semibold">{user.role || 'Lead Researcher'}</span>
                      </div>
                    </div>

                    {/* Navigation Items */}
                    <div className="py-1">
                      <Link
                        to="/profile"
                        onClick={() => setProfileDropdownOpen(false)}
                        className="flex items-center gap-2.5 px-4 py-2 text-xs text-[#f3faf0]/85 hover:text-white hover:bg-white/5 transition-colors font-medium"
                      >
                        <UserIcon className="w-4 h-4 text-[#d2434e]" />
                        <span>View Researcher Profile Details</span>
                      </Link>

                      <Link
                        to="/search"
                        onClick={() => setProfileDropdownOpen(false)}
                        className="flex items-center gap-2.5 px-4 py-2 text-xs text-[#f3faf0]/85 hover:text-white hover:bg-white/5 transition-colors font-medium"
                      >
                        <LayoutDashboard className="w-4 h-4 text-[#a7d0d2]" />
                        <span>Research Assistant Workspace</span>
                      </Link>

                      <button
                        onClick={() => {
                          setProfileDropdownOpen(false);
                          setModalTab('how-it-works');
                        }}
                        className="w-full flex items-center gap-2.5 px-4 py-2 text-xs text-[#f3faf0]/85 hover:text-white hover:bg-white/5 transition-colors cursor-pointer text-left"
                      >
                        <HelpCircle className="w-4 h-4 text-[#4d728e]" />
                        <span>Architecture & Domain Guide</span>
                      </button>
                    </div>

                    {/* Footer: Log out */}
                    <div className="pt-1 mt-1 border-t border-white/10 px-2">
                      <button
                        onClick={handleLogout}
                        className="w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-xs text-rose-400 hover:text-rose-300 hover:bg-rose-500/15 transition-all cursor-pointer font-medium"
                      >
                        <LogOut className="w-4 h-4" />
                        <span>Sign Out</span>
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Global Interactive Info Modal */}
      <InfoModal
        isOpen={!!modalTab}
        activeTab={modalTab || 'how-it-works'}
        onClose={() => setModalTab(null)}
        onTabChange={(tab) => setModalTab(tab)}
      />
    </>
  );
};

export default Navbar;