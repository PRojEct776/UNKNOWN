import React, { useState, useRef, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  LogOut,
  User as UserIcon,
  ChevronDown,
} from 'lucide-react';
import { InfoModal, type ModalTab } from './InfoModal';

export const Navbar: React.FC = () => {
  const { user, logout } = useAuth();
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

  return (
    <>
      <header className="sticky top-0 z-50 w-full border-b border-[#4d728e]/25 bg-[#0b1219]/90 backdrop-blur-xl">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-14 flex items-center justify-between">
          {/* Brand Logo - Links directly to Chat */}
          <Link to="/search" className="flex items-center gap-2.5 group" title="UNKNOWN Research">
            <div className="w-7 h-7 rounded-lg overflow-hidden border border-[#d2434e]/50 group-hover:border-[#d2434e] group-hover:shadow-[0_0_12px_rgba(210,67,78,0.4)] transition-all shadow-sm shrink-0 bg-[#0d1117]">
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

          {/* Right Side: User Profile Dropdown */}
          <div className="flex items-center gap-2 sm:gap-3">
            {user && (
              <div className="relative" ref={dropdownRef}>
                <button
                  type="button"
                  onClick={() => setProfileDropdownOpen(!profileDropdownOpen)}
                  className="flex items-center gap-2 pl-2 pr-2.5 py-1 rounded-full bg-[#141d26] hover:bg-[#1b2734] border border-[#4d728e]/40 hover:border-[#d2434e]/60 transition-all cursor-pointer shadow-sm group"
                  title="Researcher Profile"
                >
                  <div className="relative">
                    <img
                      src={user.avatarUrl || `https://api.dicebear.com/7.x/bottts/svg?seed=${user.email}`}
                      alt={user.name}
                      className="w-7 h-7 rounded-full border border-[#d2434e] bg-[#0b1219] p-0.5 object-cover group-hover:scale-105 transition-transform"
                    />
                    <span className="absolute bottom-0 right-0 w-2 h-2 rounded-full bg-emerald-400 border border-[#141d26]" />
                  </div>

                  <span className="text-xs font-semibold text-white tracking-wide max-w-[120px] truncate hidden sm:inline-block">
                    {user.name}
                  </span>

                  <ChevronDown
                    className={`w-3.5 h-3.5 text-[#f3faf0]/60 group-hover:text-white transition-transform ${
                      profileDropdownOpen ? 'rotate-180 text-white' : ''
                    }`}
                  />
                </button>

                {profileDropdownOpen && (
                  <div className="absolute right-0 mt-2 w-56 rounded-xl border border-[#4d728e]/35 bg-[#141d26] p-1.5 shadow-2xl backdrop-blur-xl z-50 animate-in fade-in slide-in-from-top-2 duration-150">
                    <div className="px-3 py-2 border-b border-white/5">
                      <p className="text-xs font-semibold text-white truncate">{user.name}</p>
                      <p className="text-[11px] text-[#f3faf0]/50 truncate">{user.email}</p>
                    </div>

                    <div className="py-1 space-y-0.5">
                      <Link
                        to="/profile"
                        onClick={() => setProfileDropdownOpen(false)}
                        className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs text-[#f3faf0]/80 hover:bg-white/5 hover:text-white transition-colors"
                      >
                        <UserIcon className="w-3.5 h-3.5 text-[#a7d0d2]" />
                        <span>Profile settings</span>
                      </Link>

                      <button
                        type="button"
                        onClick={handleLogout}
                        className="w-full flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs text-rose-300 hover:bg-rose-500/10 transition-colors text-left cursor-pointer"
                      >
                        <LogOut className="w-3.5 h-3.5" />
                        <span>Sign out</span>
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Architecture / Info Modal */}
      {modalTab && (
        <InfoModal
          isOpen={modalTab !== null}
          activeTab={modalTab}
          onTabChange={(t) => setModalTab(t)}
          onClose={() => setModalTab(null)}
        />
      )}
    </>
  );
};
