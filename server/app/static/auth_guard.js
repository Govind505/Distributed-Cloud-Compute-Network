/**
 * DCCN Dynamic Role-Based Access Control (RBAC) Client Guard
 * Enforces role isolation, token verification, session management,
 * and universal Administrator Omnibar cross-profile switching.
 */

class AuthGuard {
  constructor() {
    this.token = localStorage.getItem('dccn_token') || '';
    this.currentUser = null;
  }

  async verifyAndEnforce(allowedRoles = [], portalName = 'Portal') {
    if (!this.token) {
      window.location.href = '/login';
      return null;
    }

    try {
      const resp = await fetch('/api/v1/auth/me', {
        headers: { 'Authorization': `Bearer ${this.token}` }
      });

      if (!resp.ok) {
        // Token invalid or expired
        this.clearSession();
        window.location.href = '/login';
        return null;
      }

      this.currentUser = await resp.json();
      localStorage.setItem('dccn_role', this.currentUser.role);
      localStorage.setItem('dccn_email', this.currentUser.email);

      // Check role authorization
      const userRole = this.currentUser.role;
      const isAdmin = userRole === 'admin';
      const isAllowed = allowedRoles.length === 0 || allowedRoles.includes(userRole) || isAdmin;

      if (!isAllowed) {
        this.renderAccessDeniedModal(userRole, allowedRoles, portalName);
        return null;
      }

      this.updateNavbarUserBadge();

      // If user is Admin, render the universal Admin Omnibar profile switcher
      if (isAdmin) {
        this.renderAdminOmnibar();
      }

      return this.currentUser;
    } catch (err) {
      console.error('[AuthGuard] Verification failed:', err);
      return null;
    }
  }

  renderAdminOmnibar() {
    if (document.getElementById('adminOmniBar')) return;

    const currentPath = window.location.pathname;
    const bar = document.createElement('div');
    bar.id = 'adminOmniBar';
    bar.className = 'bg-gradient-to-r from-purple-950 via-slate-900 to-indigo-950 border-b border-purple-800/60 px-4 py-2 text-xs flex flex-wrap items-center justify-between gap-2 shadow-md sticky top-0 z-50';

    const getLinkClass = (path) => {
      const active = currentPath === path || (path === '/admin' && (currentPath === '/admin' || currentPath === '/admin/'));
      return active
        ? 'px-2.5 py-1 rounded-lg text-xs font-semibold bg-purple-600 text-white shadow'
        : 'px-2.5 py-1 rounded-lg text-xs font-semibold bg-slate-800/90 text-slate-300 hover:bg-slate-700 hover:text-white transition';
    };

    bar.innerHTML = `
      <div class="flex items-center space-x-2 font-mono text-purple-300">
        <span class="w-2 h-2 rounded-full bg-purple-400 animate-pulse"></span>
        <span class="font-bold tracking-tight">ADMIN SUPERUSER PRIVILEGE</span>
        <span class="text-slate-600 hidden sm:inline">|</span>
        <span class="text-slate-400 hidden sm:inline text-[11px]">Universal Access to All Portals & Profiles</span>
      </div>
      <div class="flex items-center space-x-1.5 font-sans">
        <span class="text-slate-400 text-[11px] font-mono mr-1 hidden md:inline">Switch Workspace:</span>
        <a href="/admin" class="${getLinkClass('/admin')}">Admin Console</a>
        <a href="/client" class="${getLinkClass('/client')}">Client Workspace</a>
        <a href="/provider" class="${getLinkClass('/provider')}">Provider Node Manager</a>
        <a href="/dashboard" class="${getLinkClass('/dashboard')}">System Overview</a>
      </div>
    `;

    document.body.prepend(bar);
  }

  updateNavbarUserBadge() {
    if (!this.currentUser) return;
    const emailEl = document.getElementById('navUserEmail');
    const roleBadgeEl = document.getElementById('navRoleBadge');

    if (emailEl) {
      emailEl.textContent = this.currentUser.email;
    }

    if (roleBadgeEl) {
      const role = this.currentUser.role;
      if (role === 'admin') {
        roleBadgeEl.className = 'text-[11px] px-2.5 py-0.5 rounded-full bg-purple-950 text-purple-300 border border-purple-800 font-mono font-bold';
        roleBadgeEl.textContent = 'Administrator';
      } else if (role === 'compute_provider') {
        roleBadgeEl.className = 'text-[11px] px-2.5 py-0.5 rounded-full bg-emerald-950 text-emerald-300 border border-emerald-800 font-mono font-bold';
        roleBadgeEl.textContent = 'Compute Provider';
      } else {
        roleBadgeEl.className = 'text-[11px] px-2.5 py-0.5 rounded-full bg-blue-950 text-blue-300 border border-blue-800 font-mono font-bold';
        roleBadgeEl.textContent = 'Compute Client';
      }
    }
  }

  renderAccessDeniedModal(currentRole, allowedRoles, portalName) {
    const modal = document.createElement('div');
    modal.className = 'fixed inset-0 bg-slate-950/90 backdrop-blur-md flex items-center justify-center p-4 z-50';
    
    const targetUrl = this.currentUser.portal_url || '/login';
    const roleTitles = {
      'admin': 'Administrator',
      'compute_provider': 'Compute Provider',
      'compute_user': 'Compute Client'
    };

    modal.innerHTML = `
      <div class="max-w-md w-full bg-slate-900 border border-rose-500/50 rounded-2xl p-6 shadow-2xl space-y-5 text-center font-sans">
        <div class="w-14 h-14 bg-rose-950 text-rose-400 rounded-2xl flex items-center justify-center mx-auto border border-rose-800/80">
          <svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
          </svg>
        </div>
        
        <div>
          <h2 class="text-xl font-bold text-white tracking-tight">Access Restricted</h2>
          <p class="text-xs text-slate-400 mt-2">
            You are signed in as <span class="text-white font-mono font-bold">${this.currentUser.email}</span> with role 
            <span class="text-rose-400 font-mono font-bold uppercase">${roleTitles[currentRole] || currentRole}</span>.
          </p>
          <p class="text-xs text-slate-400 mt-1">
            The <span class="text-indigo-300 font-semibold">${portalName}</span> requires <span class="text-emerald-400 font-semibold">${allowedRoles.map(r => roleTitles[r] || r).join(' or ')}</span> authorization.
          </p>
        </div>

        <div class="flex flex-col sm:flex-row gap-3 pt-2">
          <a href="${targetUrl}" class="flex-1 py-2.5 px-4 bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold rounded-xl transition shadow">
            Go to My Designated Workspace
          </a>
          <button onclick="authGuard.logout()" class="py-2.5 px-4 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-bold rounded-xl transition border border-slate-700">
            Sign In with Different Account
          </button>
        </div>
      </div>
    `;

    document.body.appendChild(modal);
  }

  clearSession() {
    localStorage.removeItem('dccn_token');
    localStorage.removeItem('dccn_email');
    localStorage.removeItem('dccn_role');
  }

  logout() {
    this.clearSession();
    window.location.href = '/login';
  }
}

window.authGuard = new AuthGuard();
