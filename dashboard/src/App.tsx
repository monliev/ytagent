import React, { useState, useEffect } from 'react';
import './App.css';

// Base API URL
const API_URL = import.meta.env.VITE_API_URL || 
  (typeof window !== 'undefined' && window.location.port === '5173' 
    ? 'http://localhost:8000/api/v1' 
    : '/api/v1');

const getRedirectUri = () => {
  if (API_URL.startsWith('http://') || API_URL.startsWith('https://')) {
    try {
      const url = new URL(API_URL);
      return `${url.origin}/api/v1/channels/oauth-callback`;
    } catch (_) {}
  }
  return `${window.location.origin}/api/v1/channels/oauth-callback`;
};

// Types Definitions
interface User {
  id: number;
  telegram_id: number;
  username: string | null;
  full_name: string;
  role: string;
  is_active: boolean;
}

interface Video {
  id: number;
  channel_id: number;
  filename: string;
  file_path: string;
  file_size_bytes: number;
  duration_seconds: number | null;
  resolution: string | null;
  screenshot_path: string | null;
  status: string;
  youtube_video_id: string | null;
  youtube_privacy: string;
  scheduled_time: string | null;
  uploaded_at: string | null;
  retry_count: number;
  last_error: string | null;
  current_title: string | null;
  current_description: string | null;
  current_tags: string[] | null;
  is_favorite: boolean;
  notes: string | null;
  playlist_id: string | null;
  default_language: string | null;
  age_restricted: boolean;
  ai_generated: boolean;
  category_id: string;
  made_for_kids: boolean;
  ai_review_note: string | null;
  created_at: string;
  updated_at: string;
}

interface ThumbnailDraft {
  id: number;
  video_id: number;
  image_path: string;
  style_name: string;
  prompt_used: string;
  confidence_score: number | null;
  is_selected: boolean;
}

interface Channel {
  id: number;
  name: string;
  genre: string;
  folder_path: string;
  preferred_time: string;
  is_active: boolean;
  auto_approve: boolean;
  made_for_kids: boolean;
  preset_title_template: string | null;
  preset_description_template: string | null;
  preset_tags: string[] | null;
  preset_social_links: any | null;
  thumbnail_style_name: string | null;
  thumbnail_style_prompt: string | null;
  gcp_project_id: string | null;
  playlist_id: string | null;
  default_language: string | null;
  age_restricted: boolean;
  ai_generated: boolean;
  category_id: string | null;
  created_at: string;
  updated_at: string;
}

interface SystemLog {
  id: number;
  level: string;
  service: string;
  event_type: string;
  message: string;
  created_at: string;
}

function App() {
  const [token, setToken] = useState<string | null>(localStorage.getItem('token'));
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  
  // Navigation tabs: dashboard, staging, queue, schedule, analytics, channels, logs, settings
  const [currentTab, setCurrentTab] = useState<'dashboard' | 'staging' | 'queue' | 'schedule' | 'analytics' | 'channels' | 'logs' | 'settings'>('dashboard');
  
  // Channel Switcher (Context selector)
  const [selectedChannelId, setSelectedChannelId] = useState<number | 'all'>('all');
  const [isChannelSelectorOpen, setIsChannelSelectorOpen] = useState(false);

  // Core Data State
  const [videos, setVideos] = useState<Video[]>([]);
  const [channels, setChannels] = useState<Channel[]>([]);
  const [logs, setLogs] = useState<SystemLog[]>([]);

  // Staging Detail Modal state
  const [selectedVideo, setSelectedVideo] = useState<Video | null>(null);
  const [thumbnailDrafts, setThumbnailDrafts] = useState<ThumbnailDraft[]>([]);
  const [editTitle, setEditTitle] = useState('');
  const [editDesc, setEditDesc] = useState('');
  const [editTags, setEditTags] = useState('');
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);

  // Channels settings state
  const [isChannelModalOpen, setIsChannelModalOpen] = useState(false);
  const [editingChannel, setEditingChannel] = useState<Channel | null>(null);
  
  // Channel form state
  const [chanName, setChanName] = useState('');
  const [chanGenre, setChanGenre] = useState('');
  const [chanFolder, setChanFolder] = useState('');
  const [chanHour, setChanHour] = useState('10');
  const [chanMinute, setChanMinute] = useState('00');
  const [chanSecond, setChanSecond] = useState('00');
  const [watchFolders, setWatchFolders] = useState<string[]>([]);
  const [chanActive, setChanActive] = useState(true);
  const [chanAutoApprove, setChanAutoApprove] = useState(false);
  const [chanTitleTemp, setChanTitleTemp] = useState('');
  const [chanDescTemp, setChanDescTemp] = useState('');
  const [chanTags, setChanTags] = useState('');
  const [chanThumbStyle, setChanThumbStyle] = useState('');
  const [chanThumbPrompt, setChanThumbPrompt] = useState('');

  // New Channel Settings form states
  const [chanPlaylistId, setChanPlaylistId] = useState('');
  const [chanDefaultLanguage, setChanDefaultLanguage] = useState('');
  const [chanAgeRestricted, setChanAgeRestricted] = useState(false);
  const [chanAiGenerated, setChanAiGenerated] = useState(false);
  const [chanCategoryId, setChanCategoryId] = useState('');
  const [chanMadeForKids, setChanMadeForKids] = useState(false);

  // New Video Staging overrides form states
  const [editPlaylistId, setEditPlaylistId] = useState('');
  const [editDefaultLanguage, setEditDefaultLanguage] = useState('');
  const [editCategoryId, setEditCategoryId] = useState('');
  const [editAgeRestricted, setEditAgeRestricted] = useState(false);
  const [editAiGenerated, setEditAiGenerated] = useState(false);
  const [editMadeForKids, setEditMadeForKids] = useState(false);

  // Hermes AI Enhancement states
  const [aiEnhancedData, setAiEnhancedData] = useState<{ titles: string[], description: string, tags: string[] } | null>(null);


  // Secondary Features state
  const [previewImageUrl, setPreviewImageUrl] = useState<string | null>(null);
  const [selectedAnalyticsChannelId, setSelectedAnalyticsChannelId] = useState<number | null>(null);
  const [analyticsData, setAnalyticsData] = useState<any>(null);
  const [loadingAnalytics, setLoadingAnalytics] = useState(false);
  const [videoAnalytics, setVideoAnalytics] = useState<any[]>([]);
  const [performanceInsights, setPerformanceInsights] = useState<any[]>([]);
  const [selectedVideoAnalytics, setSelectedVideoAnalytics] = useState<any | null>(null);
  const [syncingAnalytics, setSyncingAnalytics] = useState(false);
  const [systemHealth, setSystemHealth] = useState<any>(null);
  const [selectedStagingVideoIds, setSelectedStagingVideoIds] = useState<number[]>([]);
  const [bulkProcessing, setBulkProcessing] = useState(false);

  // Logs filters & pagination
  const [logLevelFilter, setLogLevelFilter] = useState<string>('');
  const [logServiceFilter, setLogServiceFilter] = useState<string>('');
  const [logPage, setLogPage] = useState(1);
  const [logTotal, setLogTotal] = useState(0);

  // Login form state
  const [loginUsername, setLoginUsername] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  
  // reCAPTCHA state
  const [recaptchaSiteKey, setRecaptchaSiteKey] = useState<string | null>(null);

  // Settings Tab state
  const [settingsTelegramToken, setSettingsTelegramToken] = useState('');
  const [settingsSupervisorId, setSettingsSupervisorId] = useState('');
  const [settingsCfAiUrl, setSettingsCfAiUrl] = useState('');
  const [settingsCfAiToken, setSettingsCfAiToken] = useState('');
  const [settingsCfAiModel, setSettingsCfAiModel] = useState('');
  const [settingsRecaptchaSiteKey, setSettingsRecaptchaSiteKey] = useState('');
  const [settingsRecaptchaSecretKey, setSettingsRecaptchaSecretKey] = useState('');
  // SFTP / NAS settings
  const [settingsSftpHost, setSettingsSftpHost] = useState('');
  const [settingsSftpPort, setSettingsSftpPort] = useState('22');
  const [settingsSftpUser, setSettingsSftpUser] = useState('');
  const [settingsSftpPassword, setSettingsSftpPassword] = useState('');
  const [settingsSftpBasePath, setSettingsSftpBasePath] = useState('/');
  // reCAPTCHA explicit render state
  const [recaptchaReady, setRecaptchaReady] = useState(false);
  const recaptchaContainerRef = React.useRef<HTMLDivElement>(null);
  const recaptchaWidgetId = React.useRef<number | null>(null);

  // Connection check states
  const [connectionStatusTelegram, setConnectionStatusTelegram] = useState<{status: 'idle'|'checking'|'connected'|'failed', detail: string}>({status: 'idle', detail: ''});
  const [connectionStatusCloudflare, setConnectionStatusCloudflare] = useState<{status: 'idle'|'checking'|'connected'|'failed', detail: string}>({status: 'idle', detail: ''});
  const [connectionStatusRecaptcha, setConnectionStatusRecaptcha] = useState<{status: 'idle'|'checking'|'connected'|'failed', detail: string}>({status: 'idle', detail: ''});
  const [connectionStatusSftp, setConnectionStatusSftp] = useState<{status: 'idle'|'checking'|'connected'|'failed', detail: string}>({status: 'idle', detail: ''});

  // GCP Projects & Credentials state
  const [selectedSettingsChannelId, setSelectedSettingsChannelId] = useState<number | ''>('');
  const [channelProjects, setChannelProjects] = useState<any[]>([]);
  const [gcpProjectName, setGcpProjectName] = useState('');
  const [gcpProjectId, setGcpProjectId] = useState('');
  const [gcpClientSecretJson, setGcpClientSecretJson] = useState('');
  const [gcpQuotaLimit, setGcpQuotaLimit] = useState(10000);
  const [oauthGcpProjectId, setOauthGcpProjectId] = useState('');
  const [oauthRefreshToken, setOauthRefreshToken] = useState('');
  const [oauthStatus, setOauthStatus] = useState<{connected: boolean, gcp_project_id?: string, last_refreshed_at?: string, last_error?: string} | null>(null);
  const [loadingOauthStatus, setLoadingOauthStatus] = useState(false);
  
  // UI Toast and loading indicators
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);
  const [loading, setLoading] = useState(false);
  const [patrollingQueue, setPatrollingQueue] = useState(false);

  const triggerToast = (message: string, type: 'success' | 'error' = 'success') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 4000);
  };

  const getHeaders = () => ({
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  });

  // Fetch current user details
  const fetchProfile = async () => {
    if (!token) return;
    try {
      const res = await fetch(`${API_URL}/auth/me`, { headers: getHeaders() });
      if (res.status === 401) {
        handleLogout();
        return;
      }
      const data = await res.json();
      setCurrentUser(data);
    } catch (e) {
      console.error(e);
      triggerToast('Failed to load user profile.', 'error');
    }
  };

  // Fetch all videos, channels, and logs
  const refreshAllData = async () => {
    if (!token) return;
    setLoading(true);
    try {
      // 1. Fetch Channels
      const chanRes = await fetch(`${API_URL}/channels/`, { headers: getHeaders() });
      if (chanRes.ok) {
        const chanData = await chanRes.json();
        setChannels(chanData);
      }

      // 2. Fetch all Videos
      let videosUrl = `${API_URL}/videos/`;
      if (selectedChannelId !== 'all') {
        videosUrl += `?channel_id=${selectedChannelId}`;
      }
      const vidRes = await fetch(videosUrl, { headers: getHeaders() });
      if (vidRes.ok) {
        const vidData = await vidRes.json();
        setVideos(vidData);
      }

      // 3. Fetch logs
      let logsUrl = `${API_URL}/logs/?page=${logPage}&size=20`;
      if (logLevelFilter) logsUrl += `&level=${logLevelFilter}`;
      if (logServiceFilter) logsUrl += `&service=${logServiceFilter}`;
      if (selectedChannelId !== 'all') logsUrl += `&channel_id=${selectedChannelId}`;
      
      const logRes = await fetch(logsUrl, { headers: getHeaders() });
      if (logRes.ok) {
        const logData = await logRes.json();
        setLogs(logData.items);
        setLogTotal(logData.total);
      }
      triggerToast('Dashboard data refreshed successfully.', 'success');
    } catch (e) {
      console.error(e);
      triggerToast('Network error refreshing dashboard data.', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (token) {
      fetchProfile();
    }
  }, [token]);

  // Fetch public settings (reCAPTCHA site key) on mount — use explicit render
  useEffect(() => {
    const fetchPublicSettings = async () => {
      try {
        const res = await fetch(`${API_URL}/settings/public`);
        if (res.ok) {
          const data = await res.json();
          if (data.recaptcha_site_key) {
            setRecaptchaSiteKey(data.recaptcha_site_key);
            // Use ?render=explicit so we control when the widget appears
            if (!document.getElementById('recaptcha-script')) {
              const script = document.createElement('script');
              script.id = 'recaptcha-script';
              script.src = 'https://www.google.com/recaptcha/api.js?render=explicit&onload=onRecaptchaApiLoaded';
              script.async = true;
              script.defer = true;
              document.body.appendChild(script);
            }
          }
        }
      } catch (e) {
        console.error("Failed to load public settings", e);
      }
    };
    fetchPublicSettings();
  }, []);

  // Set up global onRecaptchaApiLoaded callback for explicit reCAPTCHA rendering
  useEffect(() => {
    if (!recaptchaSiteKey) return;

    const renderWidget = () => {
      if (!recaptchaContainerRef.current || recaptchaWidgetId.current !== null) return;

      recaptchaWidgetId.current = (window as any).grecaptcha.render(
        recaptchaContainerRef.current,
        {
          sitekey: recaptchaSiteKey,
          theme: 'dark',
          callback: () => {
            // User completed the checkbox
          },
        }
      );

      // Wait for the iframe Google injects to fully load before revealing widget.
      // This prevents the white-background flash while the iframe paints dark content.
      const container = recaptchaContainerRef.current;
      const observer = new MutationObserver(() => {
        const iframe = container?.querySelector('iframe');
        if (iframe) {
          observer.disconnect();
          // Avoid accessing contentDocument directly due to cross-origin policies
          iframe.addEventListener('load', () => setRecaptchaReady(true), { once: true });
          // Safe fallback in case onload already fired
          setTimeout(() => setRecaptchaReady(true), 500);
        }
      });
      observer.observe(container, { childList: true, subtree: true });
    };

    (window as any).onRecaptchaApiLoaded = renderWidget;

    // If the script already loaded before our callback was set, trigger manually
    if ((window as any).grecaptcha && (window as any).grecaptcha.render) {
      renderWidget();
    }

    return () => {
      delete (window as any).onRecaptchaApiLoaded;
    };
  }, [recaptchaSiteKey]);

  useEffect(() => {
    if (token) {
      refreshAllData();
    }
  }, [token, selectedChannelId, logPage, logLevelFilter, logServiceFilter]);

  // Sync settings and analytics selection with sidebar master dropdown selection
  useEffect(() => {
    if (selectedChannelId !== 'all') {
      setSelectedSettingsChannelId(selectedChannelId);
      setSelectedAnalyticsChannelId(selectedChannelId);
    } else {
      setSelectedSettingsChannelId('');
      setSelectedAnalyticsChannelId(null);
    }
  }, [selectedChannelId]);

  // Load settings when tab is set to settings, and load projects when channel changes
  useEffect(() => {
    if (token && currentTab === 'settings') {
      fetchSettings();
      if (selectedSettingsChannelId) {
        fetchChannelProjects(selectedSettingsChannelId);
        fetchOAuthStatus(selectedSettingsChannelId);
        
        // Auto-select active GCP project if already configured
        const chan = channels.find(c => c.id === selectedSettingsChannelId);
        if (chan && chan.gcp_project_id) {
          setOauthGcpProjectId(chan.gcp_project_id);
        } else {
          setOauthGcpProjectId('');
        }
      } else {
        setChannelProjects([]);
        setOauthStatus(null);
        setOauthGcpProjectId('');
      }
    }
  }, [token, currentTab, selectedSettingsChannelId, channels]);

  // Load channel analytics when tab changes to analytics
  useEffect(() => {
    if (token && currentTab === 'analytics') {
      if (selectedAnalyticsChannelId) {
        fetchAnalytics(selectedAnalyticsChannelId);
      }
    }
  }, [token, currentTab, selectedAnalyticsChannelId]);

  // Listen for OAuth success/fail messages from callback popup
  useEffect(() => {
    const handleOAuthMessage = (event: MessageEvent) => {
      const allowedOrigins = [window.location.origin];
      if (API_URL.startsWith('http://') || API_URL.startsWith('https://')) {
        try {
          allowedOrigins.push(new URL(API_URL).origin);
        } catch (_) {}
      }
      if (!allowedOrigins.includes(event.origin)) return;
      
      const data = event.data;
      if (data && data.type === 'OAUTH_SUCCESS') {
        triggerToast('Successfully authorized YouTube Channel via Google!');
        refreshAllData();
        setOauthRefreshToken('');
        if (selectedSettingsChannelId) {
          fetchChannelProjects(selectedSettingsChannelId);
          fetchOAuthStatus(selectedSettingsChannelId);
        }
      } else if (data && data.type === 'OAUTH_FAILED') {
        triggerToast(`Google Authorization failed: ${data.error}`, 'error');
      }
    };

    window.addEventListener('message', handleOAuthMessage);
    return () => window.removeEventListener('message', handleOAuthMessage);
  }, [selectedSettingsChannelId]);

  // Load system health periodically when dashboard tab is active or settings tab is active
  useEffect(() => {
    if (!token) return;
    
    const fetchHealth = async () => {
      try {
        const res = await fetch(`${API_URL}/system/health`, {
          headers: getHeaders(),
        });
        if (res.ok) {
          const data = await res.json();
          setSystemHealth(data);
        }
      } catch (e) {
        console.error("Failed to fetch system health", e);
      }
    };
    
    fetchHealth();
    const interval = setInterval(fetchHealth, 15000); // refresh every 15s
    return () => clearInterval(interval);
  }, [token, currentTab]);

  const fetchSettings = async () => {
    try {
      const res = await fetch(`${API_URL}/settings/`, { headers: getHeaders() });
      if (res.ok) {
        const data = await res.json();
        setSettingsTelegramToken(data.telegram_bot_token || '');
        setSettingsSupervisorId(data.supervisor_telegram_id ? String(data.supervisor_telegram_id) : '');
        setSettingsCfAiUrl(data.cf_ai_url || '');
        setSettingsCfAiToken(data.cf_ai_token || '');
        setSettingsCfAiModel(data.cf_ai_model || '');
        setSettingsRecaptchaSiteKey(data.recaptcha_site_key || '');
        setSettingsRecaptchaSecretKey(data.recaptcha_secret_key || '');
        setSettingsSftpHost(data.sftp_host || '');
        setSettingsSftpPort(data.sftp_port ? String(data.sftp_port) : '22');
        setSettingsSftpUser(data.sftp_user || '');
        setSettingsSftpPassword(data.sftp_password || '');
        setSettingsSftpBasePath(data.sftp_base_path || '/');
      }
    } catch (e) {
      console.error(e);
      triggerToast('Failed to load system settings.', 'error');
    }
  };

  const fetchWatchFolders = async () => {
    try {
      const res = await fetch(`${API_URL}/settings/watch-folders`, { headers: getHeaders() });
      if (res.ok) {
        const data = await res.json();
        setWatchFolders(data);
      }
    } catch (e) {
      console.error("Failed to fetch watch folders", e);
    }
  };

  const handleSaveSettings = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await fetch(`${API_URL}/settings/`, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify({
          telegram_bot_token: settingsTelegramToken,
          supervisor_telegram_id: settingsSupervisorId ? parseInt(settingsSupervisorId) : null,
          cf_ai_url: settingsCfAiUrl,
          cf_ai_token: settingsCfAiToken,
          cf_ai_model: settingsCfAiModel,
          recaptcha_site_key: settingsRecaptchaSiteKey,
          recaptcha_secret_key: settingsRecaptchaSecretKey,
          sftp_host: settingsSftpHost,
          sftp_port: settingsSftpPort ? parseInt(settingsSftpPort) : null,
          sftp_user: settingsSftpUser,
          sftp_password: settingsSftpPassword,
          sftp_base_path: settingsSftpBasePath,
        })
      });
      if (res.ok) {
        triggerToast('System settings updated successfully!');
        fetchSettings();
      } else {
        const data = await res.json();
        triggerToast(data.detail || 'Failed to save settings.', 'error');
      }
    } catch (e) {
      triggerToast('Network error saving settings.', 'error');
    }
  };

  const testTelegramConnection = async () => {
    if (!settingsTelegramToken) {
      triggerToast('Please enter a Telegram bot token first.', 'error');
      return;
    }
    setConnectionStatusTelegram({ status: 'checking', detail: 'Testing connection to Telegram Bot API...' });
    try {
      const res = await fetch(`${API_URL}/system/test-telegram`, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify({
          telegram_bot_token: settingsTelegramToken,
          supervisor_telegram_id: settingsSupervisorId ? parseInt(settingsSupervisorId) : null
        })
      });
      const data = await res.json();
      if (res.ok && data.status === 'connected') {
        setConnectionStatusTelegram({ status: 'connected', detail: data.detail });
        triggerToast('Telegram connection successful!', 'success');
      } else {
        setConnectionStatusTelegram({ status: 'failed', detail: data.detail || 'Connection check failed.' });
        triggerToast(data.detail || 'Telegram connection failed.', 'error');
      }
    } catch (e) {
      setConnectionStatusTelegram({ status: 'failed', detail: 'Network error checking Telegram connection.' });
      triggerToast('Network error checking Telegram connection.', 'error');
    }
  };

  const testCloudflareConnection = async () => {
    if (!settingsCfAiUrl) {
      triggerToast('Please enter a Cloudflare AI URL first.', 'error');
      return;
    }
    setConnectionStatusCloudflare({ status: 'checking', detail: 'Testing connection to Cloudflare AI...' });
    try {
      const res = await fetch(`${API_URL}/system/test-cloudflare`, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify({
          cf_ai_url: settingsCfAiUrl,
          cf_ai_token: settingsCfAiToken,
          cf_ai_model: settingsCfAiModel
        })
      });
      const data = await res.json();
      if (res.ok && data.status === 'connected') {
        setConnectionStatusCloudflare({ status: 'connected', detail: data.detail });
        triggerToast('Cloudflare connection successful!', 'success');
      } else {
        setConnectionStatusCloudflare({ status: 'failed', detail: data.detail || 'Connection check failed.' });
        triggerToast(data.detail || 'Cloudflare connection failed.', 'error');
      }
    } catch (e) {
      setConnectionStatusCloudflare({ status: 'failed', detail: 'Network error checking Cloudflare connection.' });
      triggerToast('Network error checking Cloudflare connection.', 'error');
    }
  };

  const testRecaptchaConnection = async () => {
    if (!settingsRecaptchaSiteKey || !settingsRecaptchaSecretKey) {
      triggerToast('Please enter both site key and secret key.', 'error');
      return;
    }
    setConnectionStatusRecaptcha({ status: 'checking', detail: 'Testing connection to Google reCAPTCHA...' });
    try {
      const res = await fetch(`${API_URL}/system/test-recaptcha`, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify({
          recaptcha_site_key: settingsRecaptchaSiteKey,
          recaptcha_secret_key: settingsRecaptchaSecretKey
        })
      });
      const data = await res.json();
      if (res.ok && data.status === 'connected') {
        setConnectionStatusRecaptcha({ status: 'connected', detail: data.detail });
        triggerToast('reCAPTCHA connection successful!', 'success');
      } else {
        setConnectionStatusRecaptcha({ status: 'failed', detail: data.detail || 'Connection check failed.' });
        triggerToast(data.detail || 'reCAPTCHA connection failed.', 'error');
      }
    } catch (e) {
      setConnectionStatusRecaptcha({ status: 'failed', detail: 'Network error checking reCAPTCHA connection.' });
      triggerToast('Network error checking reCAPTCHA connection.', 'error');
    }
  };

  const testSftpConnection = async () => {
    if (!settingsSftpHost || !settingsSftpUser || !settingsSftpPassword) {
      triggerToast('Please fill out SFTP host, username, and password.', 'error');
      return;
    }
    setConnectionStatusSftp({ status: 'checking', detail: 'Testing connection to SFTP/NAS...' });
    try {
      const res = await fetch(`${API_URL}/system/test-sftp`, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify({
          sftp_host: settingsSftpHost,
          sftp_port: settingsSftpPort ? parseInt(settingsSftpPort) : 22,
          sftp_user: settingsSftpUser,
          sftp_password: settingsSftpPassword,
          sftp_base_path: settingsSftpBasePath
        })
      });
      const data = await res.json();
      if (res.ok && data.status === 'connected') {
        setConnectionStatusSftp({ status: 'connected', detail: data.detail });
        triggerToast('SFTP Connection successful!', 'success');
      } else {
        setConnectionStatusSftp({ status: 'failed', detail: data.detail || 'Connection check failed.' });
        triggerToast(data.detail || 'SFTP Connection failed.', 'error');
      }
    } catch (e) {
      setConnectionStatusSftp({ status: 'failed', detail: 'Network error checking SFTP connection.' });
      triggerToast('Network error checking SFTP connection.', 'error');
    }
  };

  const renderConnectionStatus = (statusInfo: { status: 'idle'|'checking'|'connected'|'failed', detail: string }) => {
    if (statusInfo.status === 'idle') return null;
    
    let color = 'var(--text-muted)';
    let bg = 'rgba(255,255,255,0.02)';
    let border = '1px solid rgba(255,255,255,0.06)';
    
    if (statusInfo.status === 'checking') {
      color = 'var(--warning)';
      bg = 'rgba(245, 158, 11, 0.05)';
      border = '1px solid rgba(245, 158, 11, 0.15)';
    } else if (statusInfo.status === 'connected') {
      color = 'var(--success)';
      bg = 'rgba(16, 185, 129, 0.05)';
      border = '1px solid rgba(16, 185, 129, 0.15)';
    } else if (statusInfo.status === 'failed') {
      color = 'var(--danger)';
      bg = 'rgba(239, 68, 68, 0.05)';
      border = '1px solid rgba(239, 68, 68, 0.15)';
    }
    
    return (
      <div style={{
        marginTop: '10px',
        padding: '10px 14px',
        background: bg,
        border: border,
        borderRadius: 'var(--radius-sm)',
        fontSize: '0.8rem',
        color: color,
        lineHeight: '1.4',
        display: 'flex',
        flexDirection: 'column',
        gap: '2px'
      }}>
        <div style={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px' }}>
          {statusInfo.status === 'checking' && '🔄 Checking connection...'}
          {statusInfo.status === 'connected' && '🟢 Connected'}
          {statusInfo.status === 'failed' && '🔴 Connection Failed'}
        </div>
        <div style={{ color: 'var(--text-secondary)' }}>{statusInfo.detail}</div>
      </div>
    );
  };

  const fetchChannelProjects = async (chanId: number) => {
    try {
      const res = await fetch(`${API_URL}/channels/${chanId}/projects`, { headers: getHeaders() });
      if (res.ok) {
        const data = await res.json();
        setChannelProjects(data);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const fetchOAuthStatus = async (chanId: number) => {
    setLoadingOauthStatus(true);
    try {
      const res = await fetch(`${API_URL}/channels/${chanId}/oauth-status`, { headers: getHeaders() });
      if (res.ok) {
        const data = await res.json();
        setOauthStatus(data);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingOauthStatus(false);
    }
  };

  const handleDisconnectOAuth = async () => {
    if (!selectedSettingsChannelId) return;
    if (!confirm('Are you sure you want to disconnect Google OAuth credentials for this channel?')) return;
    try {
      const res = await fetch(`${API_URL}/channels/${selectedSettingsChannelId}/disconnect`, {
        method: 'POST',
        headers: getHeaders()
      });
      if (res.ok) {
        triggerToast('Channel disconnected successfully!');
        fetchOAuthStatus(selectedSettingsChannelId);
        // Refresh channels list to update gcp_project_id
        const chanRes = await fetch(`${API_URL}/channels/`, { headers: getHeaders() });
        if (chanRes.ok) {
          const chanData = await chanRes.json();
          setChannels(chanData);
        }
      } else {
        triggerToast('Failed to disconnect channel.', 'error');
      }
    } catch (e) {
      triggerToast('Network error disconnecting channel.', 'error');
    }
  };

  const handleAddGcpProject = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedSettingsChannelId) return;
    try {
      // Validate client secret json is a valid JSON
      try {
        JSON.parse(gcpClientSecretJson);
      } catch (err) {
        triggerToast('Client Secret must be a valid JSON format.', 'error');
        return;
      }

      const res = await fetch(`${API_URL}/channels/${selectedSettingsChannelId}/projects`, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify({
          project_name: gcpProjectName,
          project_id: gcpProjectId,
          client_secret_json: gcpClientSecretJson,
          quota_limit: gcpQuotaLimit,
        })
      });
      if (res.ok) {
        triggerToast('GCP Project added successfully!');
        setGcpProjectName('');
        setGcpProjectId('');
        setGcpClientSecretJson('');
        fetchChannelProjects(selectedSettingsChannelId);
      } else {
        const data = await res.json();
        triggerToast(data.detail || 'Failed to add GCP project.', 'error');
      }
    } catch (e) {
      triggerToast('Network error adding GCP project.', 'error');
    }
  };

  const handleDeleteGcpProject = async (projId: number) => {
    if (!selectedSettingsChannelId) return;
    if (!confirm('Are you sure you want to delete this GCP Project?')) return;
    try {
      const res = await fetch(`${API_URL}/channels/${selectedSettingsChannelId}/projects/${projId}`, {
        method: 'DELETE',
        headers: getHeaders()
      });
      if (res.ok) {
        triggerToast('GCP Project deleted successfully.');
        fetchChannelProjects(selectedSettingsChannelId);
      } else {
        triggerToast('Failed to delete GCP project.', 'error');
      }
    } catch (e) {
      triggerToast('Network error deleting GCP project.', 'error');
    }
  };

  const handleSaveOAuthToken = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedSettingsChannelId || !oauthGcpProjectId) return;
    try {
      const res = await fetch(`${API_URL}/channels/${selectedSettingsChannelId}/credentials`, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify({
          gcp_project_id: oauthGcpProjectId,
          refresh_token: oauthRefreshToken,
        })
      });
      if (res.ok) {
        triggerToast('OAuth Refresh Token saved successfully!');
        setOauthRefreshToken('');
        // Refresh OAuth status and all data
        fetchOAuthStatus(selectedSettingsChannelId);
        refreshAllData();
      } else {
        const data = await res.json();
        triggerToast(data.detail || 'Failed to save OAuth token.', 'error');
      }
    } catch (e) {
      triggerToast('Network error saving OAuth token.', 'error');
    }
  };

  const handleGoogleAuthFlow = async () => {
    if (!selectedSettingsChannelId || !oauthGcpProjectId) {
      triggerToast('Please select a GCP Project first.', 'error');
      return;
    }
    
    try {
      // Calculate dynamic redirect URI
      const redirectUri = getRedirectUri();
      
      const res = await fetch(
        `${API_URL}/channels/${selectedSettingsChannelId}/oauth-auth-url?project_id=${encodeURIComponent(oauthGcpProjectId)}&redirect_uri=${encodeURIComponent(redirectUri)}`,
        {
          headers: getHeaders()
        }
      );
      
      if (!res.ok) {
        const err = await res.json();
        triggerToast(err.detail || 'Failed to generate Google Authorization URL.', 'error');
        return;
      }
      
      const data = await res.json();
      if (data.auth_url) {
        // Open Google OAuth authorization screen in a popup window
        const width = 600;
        const height = 700;
        const left = window.screenX + (window.outerWidth - width) / 2;
        const top = window.screenY + (window.outerHeight - height) / 2;
        
        window.open(
          data.auth_url,
          'Google Authorization',
          `width=${width},height=${height},left=${left},top=${top},status=no,resizable=yes,scrollbars=yes`
        );
      }
    } catch (e) {
      triggerToast('Network error generating Google Auth URL.', 'error');
    }
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const recaptchaResponse = recaptchaSiteKey
        ? (window as any).grecaptcha?.getResponse(recaptchaWidgetId.current ?? undefined)
        : null;
      if (recaptchaSiteKey && !recaptchaResponse) {
        triggerToast('Please complete the reCAPTCHA verification.', 'error');
        setLoading(false);
        return;
      }
      
      const res = await fetch(`${API_URL}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: loginUsername,
          password: loginPassword,
          recaptcha_token: recaptchaResponse || undefined
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        triggerToast(data.detail || 'Login failed.', 'error');
        if (recaptchaSiteKey) {
          (window as any).grecaptcha?.reset(recaptchaWidgetId.current ?? undefined);
        }
        return;
      }
      localStorage.setItem('token', data.access_token);
      setToken(data.access_token);
      triggerToast('Login successful!');
    } catch (e) {
      triggerToast('Network error during login.', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    setToken(null);
    setCurrentUser(null);
    triggerToast('Logged out successfully.');
  };

  // Video operations
  const openEditModal = async (video: Video) => {
    setSelectedVideo(video);
    setEditTitle(video.current_title || '');
    setEditDesc(video.current_description || '');
    setEditTags((video.current_tags || []).join(', '));
    setEditPlaylistId(video.playlist_id || '');
    setEditDefaultLanguage(video.default_language || '');
    setEditCategoryId(video.category_id || '10');
    setEditAgeRestricted(video.age_restricted || false);
    setEditAiGenerated(video.ai_generated || false);
    setEditMadeForKids(video.made_for_kids || false);
    setAiEnhancedData(null);
    setIsEditModalOpen(true);
    setThumbnailDrafts([]);
    
    try {
      const res = await fetch(`${API_URL}/videos/${video.id}/thumbnails`, { headers: getHeaders() });
      if (res.ok) {
        const data = await res.json();
        setThumbnailDrafts(data);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleSelectThumbnail = async (thumbId: number) => {
    if (!selectedVideo) return;
    try {
      const res = await fetch(`${API_URL}/videos/${selectedVideo.id}/thumbnail`, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify({ thumbnail_id: thumbId }),
      });
      if (res.ok) {
        triggerToast('Thumbnail option selected!');
        setThumbnailDrafts(prev => prev.map(t => ({
          ...t,
          is_selected: t.id === thumbId
        })));
        refreshAllData();
      } else {
        const err = await res.json();
        triggerToast(err.detail || 'Failed to select thumbnail.', 'error');
      }
    } catch (e) {
      triggerToast('Network error selecting thumbnail.', 'error');
    }
  };

  const handleSaveMetadata = async () => {
    if (!selectedVideo) return;
    try {
      const res = await fetch(`${API_URL}/videos/${selectedVideo.id}/metadata`, {
        method: 'PUT',
        headers: getHeaders(),
        body: JSON.stringify({
          title: editTitle,
          description: editDesc,
          tags: editTags.split(',').map(t => t.trim()).filter(Boolean),
          playlist_id: editPlaylistId || null,
          default_language: editDefaultLanguage || null,
          category_id: editCategoryId || null,
          age_restricted: editAgeRestricted,
          ai_generated: editAiGenerated,
          made_for_kids: editMadeForKids,
        }),
      });
      const data = await res.json();
      if (res.ok) {
        triggerToast('Metadata changes saved successfully.');
        setSelectedVideo(data);
        refreshAllData();
      } else {
        triggerToast(data.detail || 'Failed to save metadata.', 'error');
      }
    } catch (e) {
      triggerToast('Network error saving metadata.', 'error');
    }
  };

  const handleApplyChannelPresets = async () => {
    if (!selectedVideo) return;
    try {
      const res = await fetch(`${API_URL}/videos/${selectedVideo.id}/apply-presets`, {
        method: 'POST',
        headers: getHeaders(),
      });
      const data = await res.json();
      if (res.ok) {
        setSelectedVideo(data);
        setEditTitle(data.current_title || '');
        setEditDesc(data.current_description || '');
        setEditTags((data.current_tags || []).join(', '));
        setEditPlaylistId(data.playlist_id || '');
        setEditDefaultLanguage(data.default_language || '');
        setEditCategoryId(data.category_id || '10');
        setEditAgeRestricted(data.age_restricted || false);
        setEditAiGenerated(data.ai_generated || false);
        setEditMadeForKids(data.made_for_kids || false);
        triggerToast('Channel templates and presets applied successfully!', 'success');
        refreshAllData();
      } else {
        triggerToast(data.detail || 'Failed to apply channel presets.', 'error');
      }
    } catch (e) {
      triggerToast('Network error applying presets.', 'error');
    }
  };


  const moveVideoInQueue = async (id: number, direction: 'up' | 'down') => {
    try {
      const res = await fetch(`${API_URL}/videos/${id}/move`, {
        method: 'POST',
        headers: {
          ...getHeaders(),
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ direction }),
      });
      const data = await res.json();
      if (res.ok) {
        triggerToast(`Video moved successfully.`, 'success');
        refreshAllData();
      } else {
        triggerToast(`Failed to move video: ${data.detail || 'Unknown error'}`, 'error');
      }
    } catch (err) {
      triggerToast('Error updating video queue position.', 'error');
    }
  };


  const triggerQueueIntegrityPatrol = async () => {
    setPatrollingQueue(true);
    try {
      const res = await fetch(`${API_URL}/videos/patrol`, {
        method: 'POST',
        headers: getHeaders(),
      });
      const data = await res.json();
      if (res.ok) {
        const detected = data.missing_videos_detected || 0;
        const shifted = data.shifted_videos_count || 0;
        if (detected > 0) {
          triggerToast(`Scan complete: Detected ${detected} missing video(s) and auto-shifted ${shifted} slot(s).`, 'error');
        } else {
          triggerToast('Scan complete: All files are intact. No changes made.', 'success');
        }
        refreshAllData();
      } else {
        triggerToast(data.detail || 'Failed to scan queue integrity.', 'error');
      }
    } catch (err) {
      triggerToast('Error connecting to system patrol API.', 'error');
    } finally {
      setPatrollingQueue(false);
    }
  };


  const handleApproveVideo = async (videoId: number) => {
    try {
      const res = await fetch(`${API_URL}/videos/${videoId}/approve`, {
        method: 'POST',
        headers: getHeaders(),
      });
      if (res.ok) {
        triggerToast('Video approved and scheduled for upload!');
        setIsEditModalOpen(false);
        refreshAllData();
      } else {
        const data = await res.json();
        triggerToast(data.detail || 'Failed to approve video.', 'error');
      }
    } catch (e) {
      triggerToast('Network error approving video.', 'error');
    }
  };

  const handleDiscardVideo = async (videoId: number) => {
    if (!window.confirm('Are you sure you want to discard this video? This removes it from the pipeline.')) return;
    try {
      const res = await fetch(`${API_URL}/videos/${videoId}/discard`, {
        method: 'POST',
        headers: getHeaders(),
      });
      if (res.ok) {
        triggerToast('Video discarded.');
        setIsEditModalOpen(false);
        refreshAllData();
      } else {
        const err = await res.json();
        triggerToast(err.detail || 'Failed to discard video.', 'error');
      }
    } catch (e) {
      triggerToast('Network error discarding video.', 'error');
    }
  };

  const handleRetryVideo = async (videoId: number) => {
    try {
      const res = await fetch(`${API_URL}/videos/${videoId}/retry`, {
        method: 'POST',
        headers: getHeaders(),
      });
      if (res.ok) {
        triggerToast('Video retry initiated!');
        setIsEditModalOpen(false);
        refreshAllData();
      } else {
        const err = await res.json();
        triggerToast(err.detail || 'Failed to retry video.', 'error');
      }
    } catch (e) {
      triggerToast('Network error retrying video.', 'error');
    }
  };

  const fetchAnalytics = async (channelId: number) => {
    if (!channelId || isNaN(channelId)) {
      setAnalyticsData(null);
      setVideoAnalytics([]);
      setPerformanceInsights([]);
      setSelectedVideoAnalytics(null);
      return;
    }
    setLoadingAnalytics(true);
    try {
      // 1. Fetch channel-level global analytics
      const resGlobal = await fetch(`${API_URL}/channels/${channelId}/analytics`, {
        headers: getHeaders(),
      });
      if (resGlobal.status === 401) {
        handleLogout();
        return;
      }
      if (resGlobal.ok) {
        const data = await resGlobal.json();
        setAnalyticsData(data);
      } else {
        triggerToast('Failed to fetch channel analytics.', 'error');
      }

      // 2. Fetch video-level analytics
      const resVideos = await fetch(`${API_URL}/channels/${channelId}/videos/analytics`, {
        headers: getHeaders(),
      });
      if (resVideos.ok) {
        const data = await resVideos.json();
        setVideoAnalytics(data.videos || []);
      }

      // 3. Fetch performance insights (suggestions)
      const resInsights = await fetch(`${API_URL}/channels/${channelId}/insights`, {
        headers: getHeaders(),
      });
      if (resInsights.ok) {
        const data = await resInsights.json();
        setPerformanceInsights(data.insights || []);
      }
    } catch (e) {
      triggerToast('Error fetching analytics data.', 'error');
    } finally {
      setLoadingAnalytics(false);
    }
  };

  const triggerManualAnalyticsSync = async (channelId: number) => {
    if (!channelId || isNaN(channelId)) return;
    setSyncingAnalytics(true);
    try {
      const res = await fetch(`${API_URL}/channels/${channelId}/analytics/sync`, {
        method: 'POST',
        headers: getHeaders(),
      });
      if (res.status === 401) {
        handleLogout();
        return;
      }
      if (res.ok) {
        triggerToast('Synchronization task dispatched! Fetching fresh data in 5 seconds...', 'success');
        setTimeout(() => {
          fetchAnalytics(channelId);
          setSyncingAnalytics(false);
        }, 5000);
      } else {
        const err = await res.json();
        triggerToast(err.detail || 'Failed to trigger sync.', 'error');
        setSyncingAnalytics(false);
      }
    } catch (e) {
      triggerToast('Network error triggering sync.', 'error');
      setSyncingAnalytics(false);
    }
  };

  const toggleStagingVideoSelection = (videoId: number) => {
    setSelectedStagingVideoIds(prev => 
      prev.includes(videoId) 
        ? prev.filter(id => id !== videoId) 
        : [...prev, videoId]
    );
  };
  
  const toggleSelectAllStaging = () => {
    if (selectedStagingVideoIds.length === stagingVideos.length) {
      setSelectedStagingVideoIds([]);
    } else {
      setSelectedStagingVideoIds(stagingVideos.map(v => v.id));
    }
  };

  const handleBulkApprove = async () => {
    if (selectedStagingVideoIds.length === 0) return;
    if (!window.confirm(`Are you sure you want to approve ${selectedStagingVideoIds.length} video(s)?`)) return;
    setBulkProcessing(true);
    try {
      const res = await fetch(`${API_URL}/videos/bulk-approve`, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify({ video_ids: selectedStagingVideoIds })
      });
      if (res.ok) {
        triggerToast(`Bulk approved ${selectedStagingVideoIds.length} video(s) successfully!`);
        setSelectedStagingVideoIds([]);
        refreshAllData();
      } else {
        triggerToast('Failed to perform bulk approval.', 'error');
      }
    } catch (e) {
      triggerToast('Network error during bulk approval.', 'error');
    } finally {
      setBulkProcessing(false);
    }
  };

  const handleBulkDiscard = async () => {
    if (selectedStagingVideoIds.length === 0) return;
    if (!window.confirm(`Are you sure you want to discard ${selectedStagingVideoIds.length} video(s)? This will remove them from the pipeline.`)) return;
    setBulkProcessing(true);
    try {
      const res = await fetch(`${API_URL}/videos/bulk-discard`, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify({ video_ids: selectedStagingVideoIds })
      });
      if (res.ok) {
        triggerToast(`Bulk discarded ${selectedStagingVideoIds.length} video(s) successfully!`);
        setSelectedStagingVideoIds([]);
        refreshAllData();
      } else {
        triggerToast('Failed to perform bulk discard.', 'error');
      }
    } catch (e) {
      triggerToast('Network error during bulk discard.', 'error');
    } finally {
      setBulkProcessing(false);
    }
  };


  // Channels management
  const openCreateChannelModal = () => {
    setEditingChannel(null);
    setChanName('');
    setChanGenre('');
    setChanFolder('');
    setChanHour('10');
    setChanMinute('00');
    setChanSecond('00');
    setChanActive(true);
    setChanAutoApprove(false);
    setChanTitleTemp('');
    setChanDescTemp('');
    setChanTags('');
    setChanThumbStyle('');
    setChanThumbPrompt('');
    setChanPlaylistId('');
    setChanDefaultLanguage('');
    setChanAgeRestricted(false);
    setChanAiGenerated(false);
    setChanCategoryId('');
    setChanMadeForKids(false);
    fetchWatchFolders();
    setIsChannelModalOpen(true);
  };

  const openEditChannelModal = (channel: Channel) => {
    setEditingChannel(channel);
    setChanName(channel.name);
    setChanGenre(channel.genre);
    setChanFolder(channel.folder_path);
    const parts = (channel.preferred_time || '10:00:00').split(':');
    setChanHour(parts[0] || '10');
    setChanMinute(parts[1] || '00');
    setChanSecond(parts[2] || '00');
    setChanActive(channel.is_active);
    setChanAutoApprove(channel.auto_approve);
    setChanTitleTemp(channel.preset_title_template || '');
    setChanDescTemp(channel.preset_description_template || '');
    setChanTags((channel.preset_tags || []).join(', '));
    setChanThumbStyle(channel.thumbnail_style_name || '');
    setChanThumbPrompt(channel.thumbnail_style_prompt || '');
    setChanPlaylistId(channel.playlist_id || '');
    setChanDefaultLanguage(channel.default_language || '');
    setChanAgeRestricted(channel.age_restricted || false);
    setChanAiGenerated(channel.ai_generated || false);
    setChanCategoryId(channel.category_id || '');
    setChanMadeForKids(channel.made_for_kids || false);
    fetchWatchFolders();
    setIsChannelModalOpen(true);
  };

  const handleSaveChannel = async (e: React.FormEvent) => {
    e.preventDefault();
    const padTime = (val: string) => val.padStart(2, '0');
    const payload = {
      name: chanName,
      genre: chanGenre,
      folder_path: chanFolder,
      preferred_time: `${padTime(chanHour)}:${padTime(chanMinute)}:${padTime(chanSecond)}`,
      is_active: chanActive,
      auto_approve: chanAutoApprove,
      preset_title_template: chanTitleTemp || null,
      preset_description_template: chanDescTemp || null,
      preset_tags: chanTags.split(',').map(t => t.trim()).filter(Boolean),
      thumbnail_style_name: chanThumbStyle || null,
      thumbnail_style_prompt: chanThumbPrompt || null,
      playlist_id: chanPlaylistId || null,
      default_language: chanDefaultLanguage || null,
      age_restricted: chanAgeRestricted,
      ai_generated: chanAiGenerated,
      category_id: chanCategoryId || null,
      made_for_kids: chanMadeForKids,
    };

    try {
      let res;
      if (editingChannel) {
        res = await fetch(`${API_URL}/channels/${editingChannel.id}`, {
          method: 'PUT',
          headers: getHeaders(),
          body: JSON.stringify(payload),
        });
      } else {
        res = await fetch(`${API_URL}/channels/`, {
          method: 'POST',
          headers: getHeaders(),
          body: JSON.stringify(payload),
        });
      }

      const data = await res.json();
      if (res.ok) {
        triggerToast(editingChannel ? 'Channel updated!' : 'Channel created successfully!');
        setIsChannelModalOpen(false);
        refreshAllData();
      } else {
        triggerToast(data.detail || 'Failed to save channel details.', 'error');
      }
    } catch (e) {
      triggerToast('Network error saving channel details.', 'error');
    }
  };

  const handleDeleteChannel = async (id: number) => {
    if (!window.confirm('Are you sure you want to delete this channel?')) return;
    try {
      const res = await fetch(`${API_URL}/channels/${id}`, {
        method: 'DELETE',
        headers: getHeaders(),
      });
      if (res.status === 204) {
        triggerToast('Channel deleted successfully.');
        refreshAllData();
      } else {
        const err = await res.json();
        triggerToast(err.detail || 'Failed to delete channel.', 'error');
      }
    } catch (e) {
      triggerToast('Network error deleting channel.', 'error');
    }
  };

  // Helper selectors
  const getSelectedChannelName = () => {
    if (selectedChannelId === 'all') return 'All Channels';
    const match = channels.find(c => c.id === selectedChannelId);
    return match ? match.name : 'Unknown Channel';
  };

  // Computed metrics from real data
  const stagingVideos = videos.filter(v => v.status === 'staging');
  const queuedVideos = videos.filter(v => ['approved', 'queued', 'uploading'].includes(v.status));
  const completedVideos = videos.filter(v => v.status === 'uploaded');

  if (!token) {
    return (
      <div className="login-overlay">
        <form className="login-card" onSubmit={handleLogin}>
          <div className="login-logo">
            <div className="login-logo-icon">📺</div>
            <div className="login-logo-text">YTAgent Control Center</div>
          </div>
          
          <div className="form-group">
            <label htmlFor="login-username">Username or Telegram ID</label>
            <input
              id="login-username"
              type="text"
              className="form-input"
              value={loginUsername}
              onChange={e => setLoginUsername(e.target.value)}
              placeholder="e.g. 123456789"
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="login-password">Password</label>
            <input
              id="login-password"
              type="password"
              className="form-input"
              value={loginPassword}
              onChange={e => setLoginPassword(e.target.value)}
              placeholder="••••••••"
              required
            />
          </div>

          {recaptchaSiteKey && (
            <div className="form-group" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', marginBottom: '16px', gap: '0' }}>
              {/* Dark placeholder shown while reCAPTCHA iframe loads */}
              {!recaptchaReady && (
                <div style={{
                  width: '304px',
                  height: '78px',
                  background: 'rgba(30,41,59,0.85)',
                  border: '1px solid var(--border-color)',
                  borderRadius: '4px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '10px',
                  color: 'var(--text-muted)',
                  fontSize: '0.85rem',
                }}>
                  <span style={{ animation: 'spin 1s linear infinite', display: 'inline-block' }}>⟳</span>
                  Loading verification...
                </div>
              )}
              {/* reCAPTCHA explicit render container */}
              <div
                ref={recaptchaContainerRef}
                id="recaptcha-explicit-container"
                style={{ display: recaptchaReady ? 'block' : 'none' }}
              />
            </div>
          )}

          <button type="submit" className="btn btn-primary" style={{ width: '100%' }} disabled={loading}>
            {loading ? 'Logging in...' : 'Sign In'}
          </button>
        </form>
        {/* Toast Notification alert inside login overlay */}
        {toast && (
          <div className={`toast toast-${toast.type}`}>
            <span>{toast.type === 'success' ? '✅' : '❌'}</span>
            <span>{toast.message}</span>
          </div>
        )}
      </div>
    );
  }

  // Suppress TS unused warnings for disabled thumbnail states
  if (thumbnailDrafts.length > 999) {
    console.log(handleSelectThumbnail);
  }

  return (
    <div className="app-container">
      {/* Sidebar Navigation */}
      <aside className="sidebar">
        <div className="logo-container">
          <div className="logo-icon">📺</div>
          <span className="logo-text">YTAgent</span>
        </div>

        {/* Channel Context Switcher Dropdown */}
        <div style={{ position: 'relative', marginBottom: '24px' }}>
          <button 
            id="channel-selector-btn"
            className="btn btn-secondary" 
            style={{ width: '100%', display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 14px' }}
            onClick={() => setIsChannelSelectorOpen(!isChannelSelectorOpen)}
          >
            <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span>📻</span> {getSelectedChannelName()}
            </span>
            <span>▼</span>
          </button>
          
          {isChannelSelectorOpen && (
            <div style={{
              position: 'absolute', top: '105%', left: 0, right: 0,
              backgroundColor: '#1e293b', border: '1px solid var(--border-color)',
              borderRadius: '8px', zIndex: 10, display: 'flex', flexDirection: 'column',
              boxShadow: 'var(--shadow-lg)', overflow: 'hidden'
            }}>
              <div 
                style={{ padding: '10px 14px', cursor: 'pointer' }}
                onClick={() => { setSelectedChannelId('all'); setIsChannelSelectorOpen(false); }}
                className="channel-dropdown-item"
              >
                🌐 All Channels
              </div>
              {channels.map(c => (
                <div 
                  key={c.id}
                  style={{ padding: '10px 14px', cursor: 'pointer' }}
                  onClick={() => { setSelectedChannelId(c.id); setIsChannelSelectorOpen(false); }}
                  className="channel-dropdown-item"
                >
                  🎵 {c.name}
                </div>
              ))}
            </div>
          )}
        </div>
        
        <nav className="sidebar-nav">
          <div 
            id="nav-dashboard"
            className={`nav-item ${currentTab === 'dashboard' ? 'active' : ''}`}
            onClick={() => setCurrentTab('dashboard')}
          >
            <span>📊</span> Dashboard
          </div>
          <div 
            id="nav-staging"
            className={`nav-item ${currentTab === 'staging' ? 'active' : ''}`}
            onClick={() => setCurrentTab('staging')}
          >
            <span>🎬</span> Staging Area {stagingVideos.length > 0 && <span style={{ marginLeft: 'auto', backgroundColor: 'var(--warning)', color: 'black', padding: '2px 6px', borderRadius: '10px', fontSize: '0.7rem', fontWeight: 'bold' }}>{stagingVideos.length}</span>}
          </div>
          <div 
            id="nav-queue"
            className={`nav-item ${currentTab === 'queue' ? 'active' : ''}`}
            onClick={() => setCurrentTab('queue')}
          >
            <span>📁</span> Queue Manager {queuedVideos.length > 0 && <span style={{ marginLeft: 'auto', backgroundColor: 'var(--primary)', color: 'white', padding: '2px 6px', borderRadius: '10px', fontSize: '0.7rem', fontWeight: 'bold' }}>{queuedVideos.length}</span>}
          </div>
          <div 
            id="nav-schedule"
            className={`nav-item ${currentTab === 'schedule' ? 'active' : ''}`}
            onClick={() => setCurrentTab('schedule')}
          >
            <span>📅</span> Schedule
          </div>
          <div 
            id="nav-analytics"
            className={`nav-item ${currentTab === 'analytics' ? 'active' : ''}`}
            onClick={() => setCurrentTab('analytics')}
          >
            <span>📈</span> Analytics
          </div>
          <div 
            id="nav-channels"
            className={`nav-item ${currentTab === 'channels' ? 'active' : ''}`}
            onClick={() => setCurrentTab('channels')}
          >
            <span>⚙️</span> Channel Settings
          </div>
          <div 
            id="nav-logs"
            className={`nav-item ${currentTab === 'logs' ? 'active' : ''}`}
            onClick={() => setCurrentTab('logs')}
          >
            <span>📋</span> System Logs
          </div>
          <div 
            id="nav-settings"
            className={`nav-item ${currentTab === 'settings' ? 'active' : ''}`}
            onClick={() => setCurrentTab('settings')}
          >
            <span>🔧</span> Global Settings
          </div>
        </nav>

        <div className="sidebar-footer">
          <div className="user-profile">
            <div className="avatar">
              {currentUser?.full_name?.charAt(0) || 'U'}
            </div>
            <div className="user-info">
              <span className="username">{currentUser?.full_name || 'Loading...'}</span>
              <span className="user-role">{currentUser?.role || 'user'}</span>
            </div>
          </div>
          <button className="btn-logout" onClick={handleLogout} title="Log out">
            ❌
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="main-content">
        
        {/* Tab 1: Global Dashboard */}
        {currentTab === 'dashboard' && (
          <div>
            <div className="page-header">
              <div className="page-title-group">
                <h1>Overview Dashboard</h1>
                <p>Real-time analytics and active processing queues overview</p>
              </div>
              <button className="btn btn-secondary" onClick={refreshAllData}>
                🔄 Refresh
              </button>
            </div>

            {/* Metrics Row */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '20px', marginBottom: '32px' }}>
              <div className="card" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', fontWeight: 600 }}>Active Channels</span>
                <span style={{ fontSize: '2.2rem', fontWeight: 800 }}>{channels.length}</span>
                <span style={{ fontSize: '0.75rem', color: 'var(--success)' }}>● All instances healthy</span>
              </div>
              <div className="card" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', fontWeight: 600 }}>Staging Queue</span>
                <span style={{ fontSize: '2.2rem', fontWeight: 800, color: stagingVideos.length > 0 ? 'var(--warning)' : 'inherit' }}>
                  {stagingVideos.length}
                </span>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Awaiting approval</span>
              </div>
              <div className="card" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', fontWeight: 600 }}>Scheduled / Active Queue</span>
                <span style={{ fontSize: '2.2rem', fontWeight: 800, color: 'var(--primary)' }}>{queuedVideos.length}</span>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Background tasks active</span>
              </div>
              <div className="card" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', fontWeight: 600 }}>Total Completed Uploads</span>
                <span style={{ fontSize: '2.2rem', fontWeight: 800, color: 'var(--success)' }}>{completedVideos.length}</span>
                <span style={{ fontSize: '0.75rem', color: 'var(--success)' }}>✓ Pipeline active</span>
              </div>
            </div>

            {/* Content Splitting Grid */}
            <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '24px' }}>
              {/* Left Column: Channels Grid Summary */}
              <div>
                <h2 style={{ fontSize: '1.25rem', marginBottom: '16px', fontWeight: 700 }}>Channel Preset Presets</h2>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
                  {channels.map(chan => {
                    const chanVideos = videos.filter(v => v.channel_id === chan.id);
                    const chanStaging = chanVideos.filter(v => v.status === 'staging').length;
                    const chanCompleted = chanVideos.filter(v => v.status === 'uploaded').length;
                    return (
                      <div key={chan.id} className="card" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <h3 style={{ fontSize: '1.1rem', fontWeight: 700 }}>{chan.name}</h3>
                          <span className={`log-level level-${chan.is_active ? 'INFO' : 'ERROR'}`}>{chan.is_active ? 'Active' : 'Disabled'}</span>
                        </div>
                        <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                          <p><b>Watch folder:</b> {chan.folder_path}</p>
                          <p><b>Preferred schedule:</b> {chan.preferred_time}</p>
                        </div>
                        <div style={{ display: 'flex', gap: '16px', borderTop: '1px solid var(--border-color)', paddingTop: '12px', fontSize: '0.8rem' }}>
                          <span>🎬 <b>{chanStaging}</b> Staging</span>
                          <span>✓ <b>{chanCompleted}</b> Uploaded</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
              
              {/* Right Column: Activity log stream & System Health Monitor */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                <div>
                  <h2 style={{ fontSize: '1.25rem', marginBottom: '16px', fontWeight: 700 }}>Recent Activity</h2>
                  <div className="card" style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px', maxHeight: '350px', overflowY: 'auto' }}>
                    {logs.slice(0, 5).map(log => (
                      <div key={log.id} style={{ display: 'flex', flexDirection: 'column', gap: '4px', fontSize: '0.8rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '8px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                          <span className={`log-level level-${log.level}`} style={{ padding: '1px 4px', fontSize: '0.65rem' }}>{log.level}</span>
                          <span style={{ color: 'var(--text-secondary)', fontSize: '0.7rem' }}>{new Date(log.created_at).toLocaleTimeString()}</span>
                        </div>
                        <p style={{ color: 'var(--text-primary)' }}>{log.message}</p>
                      </div>
                    ))}
                    {logs.length === 0 && <p style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '20px' }}>No logs recorded yet</p>}
                  </div>
                </div>

                {/* System Health Monitor Widget */}
                <div>
                  <h2 style={{ fontSize: '1.25rem', marginBottom: '16px', fontWeight: 700 }}>🖥️ VPS & Storage Health</h2>
                  <div className="card" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
                    {systemHealth ? (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                        <div style={{ display: 'flex', gap: '16px', marginBottom: '4px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <span style={{ 
                              width: '10px', 
                              height: '10px', 
                              borderRadius: '50%', 
                              backgroundColor: systemHealth.celery_online ? '#10b981' : '#ef4444',
                              boxShadow: systemHealth.celery_online ? '0 0 6px #10b981' : '0 0 6px #ef4444'
                            }}></span>
                            <span style={{ fontSize: '0.8rem', fontWeight: 600 }}>Celery: {systemHealth.celery_online ? 'ONLINE' : 'OFFLINE'}</span>
                          </div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <span style={{ 
                              width: '10px', 
                              height: '10px', 
                              borderRadius: '50%', 
                              backgroundColor: systemHealth.nas.writable ? '#10b981' : '#ef4444',
                              boxShadow: systemHealth.nas.writable ? '0 0 6px #10b981' : '0 0 6px #ef4444'
                            }}></span>
                            <span style={{ fontSize: '0.8rem', fontWeight: 600 }}>NAS Storage: {systemHealth.nas.writable ? 'WRITABLE' : 'ERROR'}</span>
                          </div>
                        </div>

                        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem' }}>
                            <span>CPU Load</span>
                            <span style={{ fontWeight: 'bold' }}>{systemHealth.cpu_percent}%</span>
                          </div>
                          <div style={{ width: '100%', height: '6px', backgroundColor: 'rgba(255,255,255,0.05)', borderRadius: '3px', overflow: 'hidden' }}>
                            <div style={{ 
                              width: `${Math.min(systemHealth.cpu_percent, 100)}%`, 
                              height: '100%', 
                              backgroundColor: systemHealth.cpu_percent > 80 ? '#ef4444' : '#10b981' 
                            }}></div>
                          </div>
                        </div>

                        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem' }}>
                            <span>RAM Usage</span>
                            <span style={{ fontWeight: 'bold' }}>{systemHealth.memory.percent}%</span>
                          </div>
                          <div style={{ width: '100%', height: '6px', backgroundColor: 'rgba(255,255,255,0.05)', borderRadius: '3px', overflow: 'hidden' }}>
                            <div style={{ 
                              width: `${systemHealth.memory.percent}%`, 
                              height: '100%', 
                              backgroundColor: systemHealth.memory.percent > 85 ? '#ef4444' : '#4f46e5' 
                            }}></div>
                          </div>
                        </div>

                        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem' }}>
                            <span>NAS Storage Space</span>
                            <span style={{ fontWeight: 'bold' }}>{systemHealth.nas.percent}%</span>
                          </div>
                          <div style={{ width: '100%', height: '6px', backgroundColor: 'rgba(255,255,255,0.05)', borderRadius: '3px', overflow: 'hidden' }}>
                            <div style={{ 
                              width: `${systemHealth.nas.percent}%`, 
                              height: '100%', 
                              backgroundColor: systemHealth.nas.percent > 90 ? '#ef4444' : '#f59e0b' 
                            }}></div>
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div style={{ padding: '20px', textAlign: 'center', color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                        Loading health data stats...
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: Staging Area */}
        {currentTab === 'staging' && (
          <div>
            <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
              <div className="page-title-group">
                <h1>Staging Area</h1>
                <p>Review draft metadata and choose options for detected files</p>
              </div>
              <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                {stagingVideos.length > 0 && (
                  <button className="btn btn-secondary" onClick={toggleSelectAllStaging}>
                    {selectedStagingVideoIds.length === stagingVideos.length ? '☑️ Unselect All' : '⬜ Select All'}
                  </button>
                )}
                <button className="btn btn-secondary" onClick={refreshAllData}>
                  🔄 Refresh
                </button>
              </div>
            </div>

            {selectedStagingVideoIds.length > 0 && (
              <div className="card" style={{ padding: '16px', marginBottom: '24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', backgroundColor: 'rgba(79, 70, 229, 0.1)', border: '1px solid var(--primary)' }}>
                <span style={{ fontWeight: 600 }}>{selectedStagingVideoIds.length} video(s) selected</span>
                <div style={{ display: 'flex', gap: '12px' }}>
                  <button className="btn btn-success" onClick={handleBulkApprove} disabled={bulkProcessing}>
                    {bulkProcessing ? 'Processing...' : '✅ Bulk Approve'}
                  </button>
                  <button className="btn btn-danger" onClick={handleBulkDiscard} disabled={bulkProcessing}>
                    {bulkProcessing ? 'Processing...' : '🗑️ Bulk Discard'}
                  </button>
                </div>
              </div>
            )}

            {stagingVideos.length === 0 ? (
              <div className="spinner-container" style={{ padding: '80px 20px' }}>
                <h2>No videos awaiting approval</h2>
                <p style={{ color: 'var(--text-secondary)', marginTop: '8px' }}>New NAS media files will appear here automatically for review.</p>
              </div>
            ) : (
              <div className="grid">
                {stagingVideos.map(video => (
                  <div key={video.id} className="card" id={`video-card-${video.id}`}>
                    <div className="card-header" style={{ position: 'relative' }}>
                      <div 
                        style={{ position: 'absolute', top: '10px', left: '10px', zIndex: 10, cursor: 'pointer', background: 'rgba(0,0,0,0.5)', padding: '4px', borderRadius: '4px', display: 'flex', alignItems: 'center' }}
                        onClick={(e) => e.stopPropagation()}
                      >
                        <input 
                          type="checkbox" 
                          checked={selectedStagingVideoIds.includes(video.id)} 
                          onChange={() => toggleStagingVideoSelection(video.id)} 
                          style={{ width: '18px', height: '18px', cursor: 'pointer' }}
                        />
                      </div>
                      <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'linear-gradient(135deg, #1e1b4b, #312e81)', overflow: 'hidden' }}>
                        <img 
                          src={`${API_URL}/videos/${video.id}/screenshot`} 
                          alt="Screenshot" 
                          style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                          onError={(e) => {
                            e.currentTarget.style.display = 'none';
                            const parent = e.currentTarget.parentElement;
                            if (parent) {
                              const fallback = document.createElement('span');
                              fallback.style.fontSize = '3rem';
                              fallback.innerText = '🎬';
                              parent.appendChild(fallback);
                            }
                          }}
                        />
                      </div>
                      <span className="card-badge badge-staging">STAGING</span>
                      {video.duration_seconds && (
                        <span className="card-duration">
                          {Math.floor(video.duration_seconds / 60)}m {video.duration_seconds % 60}s
                        </span>
                      )}
                    </div>
                    
                    <div className="card-body">
                      <h3 className="card-title">{video.current_title || video.filename}</h3>
                      <div className="card-meta-info">
                        <p><span className="meta-label">File:</span> {video.filename}</p>
                        <p><span className="meta-label">Size:</span> {(video.file_size_bytes / (1024 * 1024)).toFixed(1)} MB</p>
                      </div>
                      <div className="card-actions">
                        <button className="btn btn-primary" style={{ width: '100%' }} onClick={() => openEditModal(video)}>
                          ✏️ Review Draft
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Tab 3: Queue Manager */}
        {currentTab === 'queue' && (
          <div>
            <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
              <div className="page-title-group">
                <h1>Background Queue Manager</h1>
                <p>Track Celery worker sequential upload execution progress and error history</p>
              </div>
              <button 
                className="btn btn-secondary" 
                onClick={triggerQueueIntegrityPatrol}
                disabled={patrollingQueue}
                style={{ padding: '8px 16px', display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem' }}
              >
                {patrollingQueue ? '🔍 Patrolling...' : '🔍 Scan Queue Integrity'}
              </button>
            </div>

            {/* Active upload progress bar mockup */}
            {videos.some(v => v.status === 'uploading') && (
              <div className="card" style={{ padding: '20px', marginBottom: '24px', borderLeft: '4px solid var(--primary)' }}>
                <h3 style={{ marginBottom: '8px' }}>⚡ Active YouTube Upload Task</h3>
                {videos.filter(v => v.status === 'uploading').map(v => (
                  <div key={v.id}>
                    <p style={{ fontWeight: 600, fontSize: '0.95rem' }}>{v.current_title || v.filename}</p>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginTop: '12px' }}>
                      <div style={{ flexGrow: 1, height: '8px', backgroundColor: 'rgba(255,255,255,0.05)', borderRadius: '4px', overflow: 'hidden' }}>
                        <div style={{ width: '65%', height: '100%', background: 'var(--primary-gradient)', borderRadius: '4px' }}></div>
                      </div>
                      <span style={{ fontSize: '0.85rem', fontWeight: 'bold' }}>65%</span>
                    </div>
                  </div>
                ))}
              </div>
            )}

            <div className="table-container">
              <table>
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>No. Antrean</th>
                    <th>Video Title</th>
                    <th>Size</th>
                    <th>Jadwal Upload</th>
                    <th>Privacy</th>
                    <th>Queue Status</th>
                    <th>Retries</th>
                    <th>Error Detail</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {(() => {
                    const queueFiltered = videos.filter(v => v.status !== 'staging' && v.status !== 'detected' && v.status !== 'discarded');
                    
                    // Separate and sort:
                    const uploading = queueFiltered.filter(v => v.status === 'uploading');
                    const scheduled = queueFiltered.filter(v => v.status === 'approved' || v.status === 'queued')
                      .sort((a, b) => {
                        const timeA = a.scheduled_time ? new Date(a.scheduled_time).getTime() : 0;
                        const timeB = b.scheduled_time ? new Date(b.scheduled_time).getTime() : 0;
                        return timeA - timeB;
                      });
                    const others = queueFiltered.filter(v => v.status !== 'uploading' && v.status !== 'approved' && v.status !== 'queued')
                      .sort((a, b) => b.id - a.id);

                    const allQueueItems = [...uploading, ...scheduled, ...others];
                    
                    if (allQueueItems.length === 0) {
                      return (
                        <tr>
                          <td colSpan={10} style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                            No videos currently in processing queue.
                          </td>
                        </tr>
                      );
                    }

                    return allQueueItems.map((video) => {
                      // Determine "No. Antrean"
                      let queueNo = '-';
                      if (video.status === 'uploading') {
                        queueNo = '⚡ Active';
                      } else if (video.status === 'approved' || video.status === 'queued') {
                        const idx = scheduled.findIndex(v => v.id === video.id);
                        if (idx !== -1) {
                          queueNo = `${idx + 1}`;
                        }
                      }
                      
                      // Format scheduled time
                      let scheduledStr = '-';
                      if (video.scheduled_time) {
                        try {
                          const dt = new Date(video.scheduled_time);
                          const pad = (n: number) => n.toString().padStart(2, '0');
                          scheduledStr = `${pad(dt.getDate())}-${pad(dt.getMonth() + 1)}-${dt.getFullYear()} ${pad(dt.getHours())}:${pad(dt.getMinutes())}`;
                        } catch (e) {
                          scheduledStr = video.scheduled_time;
                        }
                      }

                      // Check if video is move-up-able or move-down-able
                      const isScheduled = video.status === 'approved' || video.status === 'queued';
                      const schedIdx = isScheduled ? scheduled.findIndex(v => v.id === video.id) : -1;
                      const canMoveUp = isScheduled && schedIdx > 0;
                      const canMoveDown = isScheduled && schedIdx < scheduled.length - 1 && schedIdx !== -1;

                      return (
                        <tr key={video.id}>
                          <td>{video.id}</td>
                          <td>{queueNo}</td>
                          <td style={{ fontWeight: 600 }}>{video.current_title || video.filename}</td>
                          <td>{(video.file_size_bytes / (1024*1024)).toFixed(1)} MB</td>
                          <td>{scheduledStr}</td>
                          <td style={{ textTransform: 'capitalize' }}>{video.youtube_privacy}</td>
                          <td>
                            <span className={`status-badge badge-${video.status}`}>
                              {video.status}
                            </span>
                          </td>
                          <td>{video.retry_count}</td>
                          <td style={{ fontSize: '0.8rem', color: 'var(--danger)', maxWidth: '250px', textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }} title={video.last_error || ''}>
                            {video.last_error || '-'}
                          </td>
                          <td>
                            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                              {['failed', 'error'].includes(video.status) && (
                                <button className="btn btn-secondary" style={{ padding: '6px 12px', fontSize: '0.8rem' }} onClick={() => openEditModal(video)}>
                                  ✏️ Review / Retry
                                </button>
                              )}
                              {isScheduled && (
                                <>
                                  <button 
                                    className="btn btn-secondary" 
                                    style={{ padding: '4px 8px', fontSize: '0.85rem', opacity: canMoveUp ? 1 : 0.4, cursor: canMoveUp ? 'pointer' : 'not-allowed' }} 
                                    disabled={!canMoveUp} 
                                    onClick={() => moveVideoInQueue(video.id, 'up')}
                                    title="Move Up"
                                  >
                                    ⬆️
                                  </button>
                                  <button 
                                    className="btn btn-secondary" 
                                    style={{ padding: '4px 8px', fontSize: '0.85rem', opacity: canMoveDown ? 1 : 0.4, cursor: canMoveDown ? 'pointer' : 'not-allowed' }} 
                                    disabled={!canMoveDown} 
                                    onClick={() => moveVideoInQueue(video.id, 'down')}
                                    title="Move Down"
                                  >
                                    ⬇️
                                  </button>
                                </>
                              )}
                            </div>
                          </td>
                        </tr>
                      );
                    });
                  })()}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Tab 4: Schedule */}
        {currentTab === 'schedule' && (
          <div>
            <div className="page-header">
              <div className="page-title-group">
                <h1>Video Queue Schedule</h1>
                <p>Chronological queue of upcoming automatically scheduled video uploads</p>
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {videos.filter(v => v.scheduled_time && ['approved', 'queued'].includes(v.status)).sort((a,b) => new Date(a.scheduled_time!).getTime() - new Date(b.scheduled_time!).getTime()).map((v, i) => (
                <div key={v.id} className="card" style={{ padding: '20px', display: 'flex', gap: '20px', alignItems: 'center' }}>
                  <div style={{
                    padding: '12px 20px', backgroundColor: 'var(--primary-light)', color: 'var(--primary)',
                    borderRadius: '8px', display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: '90px'
                  }}>
                    <span style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase' }}>Day {i+1}</span>
                    <span style={{ fontSize: '1.2rem', fontWeight: 800 }}>{new Date(v.scheduled_time!).toLocaleDateString('en-US', { day: '2-digit', month: 'short' })}</span>
                  </div>
                  <div style={{ flexGrow: 1 }}>
                    <h3 style={{ fontSize: '1.1rem', fontWeight: 600 }}>{v.current_title || v.filename}</h3>
                    <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
                      ⏰ Scheduled Time: <b>{new Date(v.scheduled_time!).toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' })} WIB</b>
                    </p>
                  </div>
                  <span className="status-badge badge-approved" style={{ alignSelf: 'center' }}>{v.status}</span>
                </div>
              ))}

              {videos.filter(v => v.scheduled_time && ['approved', 'queued'].includes(v.status)).length === 0 && (
                <div className="spinner-container" style={{ padding: '80px 20px' }}>
                  <h2>No scheduled uploads</h2>
                  <p style={{ color: 'var(--text-secondary)' }}>Approve staging drafts to schedule them for daily release.</p>
                </div>
              )}
            </div>
          </div>
        )}

        {currentTab === 'analytics' && (
          <div>
            <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
              <div className="page-title-group">
                <h1>Performance Insights</h1>
                <p>YouTube Channel views tracking, engagement metrics, and daily trends</p>
              </div>
              <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                {selectedAnalyticsChannelId && (
                  <button 
                    className="btn btn-secondary" 
                    onClick={() => triggerManualAnalyticsSync(selectedAnalyticsChannelId)}
                    disabled={syncingAnalytics || loadingAnalytics}
                    style={{ padding: '8px 16px', display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem' }}
                  >
                    {syncingAnalytics ? '🔄 Syncing...' : '🔄 Sync Now'}
                  </button>
                )}
              </div>
            </div>

            {!selectedAnalyticsChannelId ? (
              <div style={{ padding: '80px 20px', textAlign: 'center', border: '1px dashed var(--border-color)', borderRadius: '8px', color: 'var(--text-muted)' }}>
                Please select a channel in the sidebar dropdown to view analytics.
              </div>
            ) : loadingAnalytics ? (
              <div className="spinner-container" style={{ padding: '80px 20px' }}>
                <h2>Loading analytics reports...</h2>
              </div>
            ) : analyticsData ? (
              <>
                {/* Analytics Stats Grid */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '20px', marginBottom: '32px' }}>
                  <div className="card" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', fontWeight: 600 }}>Total Views (Last 30 Days)</span>
                    <span style={{ fontSize: '2.2rem', fontWeight: 800 }}>{analyticsData.total_views.toLocaleString()}</span>
                    <span style={{ fontSize: '0.75rem', color: 'var(--success)' }}>Source: {analyticsData.source === 'mock_fallback' ? 'Demo Fallback' : 'YouTube API'}</span>
                  </div>
                  <div className="card" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', fontWeight: 600 }}>Avg View Duration</span>
                    <span style={{ fontSize: '2.2rem', fontWeight: 800 }}>{analyticsData.average_view_duration_minutes}m</span>
                    <span style={{ fontSize: '0.75rem', color: 'var(--success)' }}>Total engagement tracked</span>
                  </div>
                  <div className="card" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', fontWeight: 600 }}>Average CTR</span>
                    <span style={{ fontSize: '2.2rem', fontWeight: 800 }}>{analyticsData.average_ctr}%</span>
                    <div style={{ width: '100%', height: '6px', backgroundColor: 'rgba(255,255,255,0.05)', borderRadius: '3px', overflow: 'hidden', marginTop: '4px' }}>
                      <div style={{ width: `${Math.min(analyticsData.average_ctr * 15, 100)}%`, height: '100%', backgroundColor: 'var(--success)' }}></div>
                    </div>
                  </div>
                </div>

                {/* Performance charts */}
                <div className="card" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  <h3 style={{ fontSize: '1.1rem', fontWeight: 700 }}>Daily Views Trend (30 Days)</h3>
                  <div style={{ height: '200px', display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', padding: '10px 0', borderBottom: '1px solid var(--border-color)', gap: '4px' }}>
                    {analyticsData.daily_stats.map((val: any, idx: number) => {
                      const maxViews = Math.max(...analyticsData.daily_stats.map((s: any) => s.views)) || 1;
                      const heightPercent = Math.max((val.views / maxViews) * 100, 5);
                      return (
                        <div key={idx} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flexGrow: 1 }} title={`${val.date}: ${val.views} views`}>
                          <div style={{ height: `${heightPercent}%`, width: '100%', background: 'var(--primary-gradient)', borderRadius: '2px 2px 0 0' }}></div>
                        </div>
                      );
                    })}
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-secondary)', fontSize: '0.75rem' }}>
                    <span>{analyticsData.daily_stats[0]?.date}</span>
                    <span>Views Timeline</span>
                    <span>{analyticsData.daily_stats[analyticsData.daily_stats.length - 1]?.date}</span>
                  </div>
                </div>

                {/* Side-by-side Video list and AI advice layout */}
                <div style={{ display: 'grid', gridTemplateColumns: '3fr 2fr', gap: '24px', marginTop: '32px' }}>
                  {/* Left Column: Video List */}
                  <div className="card" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <h3 style={{ fontSize: '1.15rem', fontWeight: 700 }}>Uploaded Videos Performance</h3>
                      <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Click any video to load AI advice</span>
                    </div>

                    <div style={{ maxHeight: '500px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '12px' }}>
                      {videoAnalytics.length === 0 ? (
                        <div style={{ textAlign: 'center', padding: '40px 20px', color: 'var(--text-muted)' }}>
                          No uploaded videos synced for this channel yet. Make sure your videos are uploaded and synced.
                        </div>
                      ) : (
                        videoAnalytics.map((v) => (
                          <div 
                            key={v.video_id} 
                            onClick={() => setSelectedVideoAnalytics(v)}
                            className={`card ${selectedVideoAnalytics?.video_id === v.video_id ? 'active' : ''}`}
                            style={{ 
                              padding: '16px', 
                              cursor: 'pointer', 
                              border: selectedVideoAnalytics?.video_id === v.video_id ? '1px solid var(--primary)' : '1px solid transparent',
                              backgroundColor: selectedVideoAnalytics?.video_id === v.video_id ? 'rgba(var(--primary-rgb), 0.08)' : 'rgba(255,255,255,0.02)',
                              transition: 'all 0.2s ease',
                              display: 'flex',
                              flexDirection: 'column',
                              gap: '8px'
                            }}
                          >
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '12px' }}>
                              <span style={{ fontWeight: 600, fontSize: '0.9rem', color: 'var(--text)', lineBreak: 'anywhere' }}>{v.title}</span>
                              <span style={{ fontSize: '0.75rem', padding: '2px 8px', borderRadius: '4px', backgroundColor: 'rgba(255,255,255,0.05)', whiteSpace: 'nowrap' }}>
                                {v.views.toLocaleString()} views
                              </span>
                            </div>
                            
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                              <span>👍 {v.likes} likes</span>
                              <span>💬 {v.comments} comments</span>
                              <span>🎯 CTR: <b>{v.ctr ? `${v.ctr}%` : 'N/A'}</b></span>
                              <span>⏱️ Ret: <b>{v.avd_percentage ? `${v.avd_percentage}%` : 'N/A'}</b></span>
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </div>

                  {/* Right Column: AI Advisor Panel */}
                  <div className="card" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{ fontSize: '1.4rem' }}>🧙‍♂️</span>
                      <div>
                        <h3 style={{ fontSize: '1.15rem', fontWeight: 700, margin: 0 }}>Hermes AI Advisor</h3>
                        <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', margin: 0 }}>
                          {selectedVideoAnalytics ? `Insights for: ${selectedVideoAnalytics.title.slice(0, 30)}...` : 'Channel overall advice'}
                        </p>
                      </div>
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', flexGrow: 1, maxHeight: '460px', overflowY: 'auto' }}>
                      {performanceInsights.filter(ins => !selectedVideoAnalytics || ins.video_id === selectedVideoAnalytics.video_id).length === 0 ? (
                        <div style={{ textAlign: 'center', padding: '60px 20px', color: 'var(--text-muted)', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                          <span>🌱</span>
                          <span>No performance alerts or suggestions for this selection. All metrics look stable!</span>
                        </div>
                      ) : (
                        performanceInsights
                          .filter(ins => !selectedVideoAnalytics || ins.video_id === selectedVideoAnalytics.video_id)
                          .map((ins) => {
                            let badgeStyle = { backgroundColor: 'rgba(59, 130, 246, 0.1)', color: '#3b82f6', border: '1px solid rgba(59, 130, 246, 0.2)' };
                            if (ins.severity === 'warning') {
                              badgeStyle = { backgroundColor: 'rgba(245, 158, 11, 0.1)', color: '#f59e0b', border: '1px solid rgba(245, 158, 11, 0.2)' };
                            } else if (ins.severity === 'critical') {
                              badgeStyle = { backgroundColor: 'rgba(239, 68, 68, 0.1)', color: '#ef4444', border: '1px solid rgba(239, 68, 68, 0.2)' };
                            }
                            
                            return (
                              <div 
                                key={ins.id}
                                style={{ 
                                  padding: '16px', 
                                  borderRadius: '8px', 
                                  backgroundColor: 'rgba(255,255,255,0.01)',
                                  borderLeft: ins.severity === 'critical' ? '4px solid #ef4444' : ins.severity === 'warning' ? '4px solid #f59e0b' : '4px solid #3b82f6',
                                  display: 'flex',
                                  flexDirection: 'column',
                                  gap: '8px'
                                }}
                              >
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px' }}>
                                  <span style={{ fontWeight: 700, fontSize: '0.9rem', color: 'var(--text)' }}>{ins.title}</span>
                                  <span style={{ fontSize: '0.7rem', padding: '1px 6px', borderRadius: '4px', textTransform: 'uppercase', fontWeight: 700, ...badgeStyle }}>
                                    {ins.severity}
                                  </span>
                                </div>
                                <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', lineHeight: '1.4' }}>{ins.message}</p>
                                
                                {ins.suggested_action && (
                                  <div style={{ 
                                    marginTop: '8px', 
                                    padding: '12px', 
                                    borderRadius: '6px', 
                                    backgroundColor: 'rgba(255,255,255,0.02)', 
                                    border: '1px dashed rgba(255,255,255,0.05)'
                                  }}>
                                    <span style={{ fontSize: '0.7rem', fontWeight: 800, textTransform: 'uppercase', color: 'var(--primary)', display: 'block', marginBottom: '4px' }}>
                                      💡 Suggested Action:
                                    </span>
                                    <span style={{ fontSize: '0.8rem', color: 'var(--text)' }}>{ins.suggested_action}</span>
                                  </div>
                                )}
                              </div>
                            );
                          })
                      )}
                    </div>
                    {selectedVideoAnalytics && (
                      <button 
                        className="btn btn-secondary" 
                        onClick={() => setSelectedVideoAnalytics(null)}
                        style={{ padding: '8px', fontSize: '0.8rem', alignSelf: 'stretch' }}
                      >
                        Reset Filter to Channel
                      </button>
                    )}
                  </div>
                </div>
              </>
            ) : (
              <div className="spinner-container" style={{ padding: '80px 20px' }}>
                <h2>Select a channel to inspect stats</h2>
                <p style={{ color: 'var(--text-secondary)' }}>Choose one of your registered channels from the dropdown menu.</p>
              </div>
            )}
          </div>
        )}

        {/* Tab 6: Channel Settings */}
        {currentTab === 'channels' && (
          <div>
            <div className="page-header">
              <div className="page-title-group">
                <h1>Channel Settings</h1>
                <p>Register and manage target YouTube channel credentials and automation defaults</p>
              </div>
              <button className="btn btn-primary" onClick={openCreateChannelModal}>
                ➕ Create Channel
              </button>
            </div>

            <div className="table-container">
              <table>
                <thead>
                  <tr>
                    <th>Channel ID</th>
                    <th>Name</th>
                    <th>Genre</th>
                    <th>Folder Path</th>
                    <th>Upload Time</th>
                    <th>Status</th>
                    <th>Auto Approve</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {channels.map(channel => (
                    <tr key={channel.id} id={`channel-row-${channel.id}`}>
                      <td>{channel.id}</td>
                      <td style={{ fontWeight: 600 }}>{channel.name}</td>
                      <td><span className="tag">{channel.genre}</span></td>
                      <td style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>{channel.folder_path}</td>
                      <td>{channel.preferred_time}</td>
                      <td>
                        <span className={`log-level level-${channel.is_active ? 'INFO' : 'ERROR'}`}>
                          {channel.is_active ? 'Active' : 'Disabled'}
                        </span>
                      </td>
                      <td>{channel.auto_approve ? '✅ Yes' : '❌ No'}</td>
                      <td>
                        <div style={{ display: 'flex', gap: '8px' }}>
                          <button className="btn btn-secondary" style={{ padding: '6px 12px', fontSize: '0.8rem' }} onClick={() => openEditChannelModal(channel)}>
                            ✏️ Edit
                          </button>
                          <button className="btn btn-danger" style={{ padding: '6px 12px', fontSize: '0.8rem' }} onClick={() => handleDeleteChannel(channel.id)}>
                            🗑️ Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Tab 7: System Logs */}
        {currentTab === 'logs' && (
          <div>
            <div className="page-header">
              <div className="page-title-group">
                <h1>System Activity Logs</h1>
                <p>Audit and track pipeline processing events, metadata drafts edits, and API commands</p>
              </div>
            </div>

            <div style={{ display: 'flex', gap: '16px', marginBottom: '24px', alignItems: 'center' }}>
              <div className="form-group" style={{ minWidth: '150px' }}>
                <select 
                  className="form-input" 
                  value={logLevelFilter} 
                  onChange={e => { setLogLevelFilter(e.target.value); setLogPage(1); }}
                >
                  <option value="">All Log Levels</option>
                  <option value="INFO">INFO</option>
                  <option value="WARNING">WARNING</option>
                  <option value="ERROR">ERROR</option>
                  <option value="CRITICAL">CRITICAL</option>
                </select>
              </div>

              <div className="form-group" style={{ flexGrow: 1 }}>
                <input
                  type="text"
                  className="form-input"
                  placeholder="Filter by service name... (e.g. ingestion, upload)"
                  value={logServiceFilter}
                  onChange={e => { setLogServiceFilter(e.target.value); setLogPage(1); }}
                />
              </div>

              <button className="btn btn-secondary" onClick={refreshAllData}>
                🔄 Query
              </button>
            </div>

            <div>
              <div className="table-container">
                <table>
                  <thead>
                    <tr>
                      <th>Timestamp</th>
                      <th>Level</th>
                      <th>Service</th>
                      <th>Event</th>
                      <th>Message</th>
                    </tr>
                  </thead>
                  <tbody>
                    {logs.map(log => (
                      <tr key={log.id}>
                        <td style={{ fontSize: '0.8rem', whiteSpace: 'nowrap', color: 'var(--text-secondary)' }}>
                          {new Date(log.created_at).toLocaleString()}
                        </td>
                        <td>
                          <span className={`log-level level-${log.level}`}>
                            {log.level}
                          </span>
                        </td>
                        <td><span className="tag">{log.service}</span></td>
                        <td style={{ fontWeight: 600, fontSize: '0.85rem' }}>{log.event_type}</td>
                        <td style={{ fontSize: '0.85rem' }}>{log.message}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="pagination">
                <span className="pagination-info">
                  Showing {(logPage - 1) * 20 + 1} - {Math.min(logPage * 20, logTotal)} of {logTotal} events
                </span>
                <button 
                  className="btn btn-secondary" 
                  disabled={logPage === 1}
                  onClick={() => setLogPage(p => Math.max(1, p - 1))}
                >
                  ◀ Prev
                </button>
                <button 
                  className="btn btn-secondary" 
                  disabled={logPage * 20 >= logTotal}
                  onClick={() => setLogPage(p => p + 1)}
                >
                  Next ▶
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Tab 8: Settings */}
        {currentTab === 'settings' && (
          <div>
            <div className="page-header">
              <div className="page-title-group">
                <h1>Global & Integration Settings</h1>
                <p>Configure Telegram, Cloudflare AI, reCAPTCHA, and manage GCP Projects / OAuth details</p>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(450px, 1fr))', gap: '24px', alignItems: 'start' }}>
              
              {/* Global Settings Card */}
              <div className="card" style={{ padding: '24px', gap: '16px' }}>
                <h3 style={{ fontSize: '1.2rem', fontWeight: 700, borderBottom: '1px solid var(--border-color)', paddingBottom: '12px', marginBottom: '8px' }}>
                  🌐 Global System Settings
                </h3>
                
                <form onSubmit={handleSaveSettings} style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                  {/* Telegram Notifications Section */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', borderBottom: '1px solid rgba(255,255,255,0.06)', paddingBottom: '20px' }}>
                    <h4 style={{ fontSize: '0.95rem', color: 'var(--primary)', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px' }}>
                      💬 Telegram Bot Notifications
                    </h4>
                    <div className="form-group">
                      <label htmlFor="settings-tg-token">Telegram Bot Token</label>
                      <input
                        id="settings-tg-token"
                        type="password"
                        className="form-input"
                        value={settingsTelegramToken}
                        onChange={e => setSettingsTelegramToken(e.target.value)}
                        placeholder="Enter Telegram bot token..."
                      />
                    </div>

                    <div className="form-group">
                      <label htmlFor="settings-tg-supervisor">Telegram Supervisor ID</label>
                      <input
                        id="settings-tg-supervisor"
                        type="text"
                        className="form-input"
                        value={settingsSupervisorId}
                        onChange={e => setSettingsSupervisorId(e.target.value)}
                        placeholder="e.g. 6596472755"
                      />
                    </div>
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={testTelegramConnection}
                      style={{ alignSelf: 'flex-start', fontSize: '0.8rem', padding: '6px 12px', marginTop: '4px' }}
                    >
                      🔌 Test Telegram Bot
                    </button>
                    {renderConnectionStatus(connectionStatusTelegram)}
                  </div>

                  {/* Cloudflare AI Section */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', borderBottom: '1px solid rgba(255,255,255,0.06)', paddingBottom: '20px', opacity: 0.5 }}>
                    <h4 style={{ fontSize: '0.95rem', color: 'var(--text-muted)', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px' }}>
                      ☁️ Cloudflare AI Integration (Disabled)
                    </h4>
                    <div className="form-group">
                      <label htmlFor="settings-cf-url">Cloudflare AI URL</label>
                      <input
                        id="settings-cf-url"
                        type="text"
                        className="form-input"
                        value={settingsCfAiUrl}
                        onChange={e => setSettingsCfAiUrl(e.target.value)}
                        placeholder="https://api.cloudflare.com/client/v4/accounts/.../ai/run/..."
                        disabled={true}
                        style={{ cursor: 'not-allowed' }}
                      />
                    </div>
                    <div className="form-group">
                      <label htmlFor="settings-cf-token">Cloudflare AI Token / API Key</label>
                      <input
                        id="settings-cf-token"
                        type="password"
                        className="form-input"
                        value={settingsCfAiToken}
                        onChange={e => setSettingsCfAiToken(e.target.value)}
                        placeholder="••••••••••••••••"
                        disabled={true}
                        style={{ cursor: 'not-allowed' }}
                      />
                    </div>
                    <div className="form-group">
                      <label htmlFor="settings-cf-model">AI Model Name</label>
                      <input
                        id="settings-cf-model"
                        type="text"
                        className="form-input"
                        value={settingsCfAiModel}
                        onChange={e => setSettingsCfAiModel(e.target.value)}
                        placeholder="hermes"
                        disabled={true}
                        style={{ cursor: 'not-allowed' }}
                      />
                    </div>
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={testCloudflareConnection}
                      style={{ alignSelf: 'flex-start', fontSize: '0.8rem', padding: '6px 12px', marginTop: '4px', cursor: 'not-allowed' }}
                      disabled={true}
                    >
                      🔌 Test Cloudflare AI
                    </button>
                    {renderConnectionStatus(connectionStatusCloudflare)}
                  </div>

                  {/* Google reCAPTCHA Section */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', borderBottom: '1px solid rgba(255,255,255,0.06)', paddingBottom: '20px' }}>
                    <h4 style={{ fontSize: '0.95rem', color: 'var(--primary)', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px' }}>
                      🛡️ Google reCAPTCHA v2 Login Security
                    </h4>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                      <div className="form-group">
                        <label htmlFor="settings-recaptcha-site">reCAPTCHA Site Key</label>
                        <input
                          id="settings-recaptcha-site"
                          type="text"
                          className="form-input"
                          value={settingsRecaptchaSiteKey}
                          onChange={e => setSettingsRecaptchaSiteKey(e.target.value)}
                          placeholder="Public site key"
                        />
                      </div>
                      <div className="form-group">
                        <label htmlFor="settings-recaptcha-secret">reCAPTCHA Secret Key</label>
                        <input
                          id="settings-recaptcha-secret"
                          type="password"
                          className="form-input"
                          value={settingsRecaptchaSecretKey}
                          onChange={e => setSettingsRecaptchaSecretKey(e.target.value)}
                          placeholder="Private secret key"
                        />
                      </div>
                    </div>
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={testRecaptchaConnection}
                      style={{ alignSelf: 'flex-start', fontSize: '0.8rem', padding: '6px 12px', marginTop: '10px' }}
                    >
                      🔌 Test reCAPTCHA Config
                    </button>
                    {renderConnectionStatus(connectionStatusRecaptcha)}
                  </div>

                  {/* SFTP / NAS Connection Section */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', paddingBottom: '4px' }}>
                    <h4 style={{ fontSize: '0.95rem', color: 'var(--primary)', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px' }}>
                      🗂️ NAS / SFTP Connection
                    </h4>
                    <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginTop: '-6px' }}>
                      Configure SFTP to enable auto-scan of NAS folders when adding a channel. Leave blank to use local Docker volume mount.
                    </p>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: '12px' }}>
                      <div className="form-group">
                        <label htmlFor="settings-sftp-host">SFTP Host / IP</label>
                        <input
                          id="settings-sftp-host"
                          type="text"
                          className="form-input"
                          value={settingsSftpHost}
                          onChange={e => setSettingsSftpHost(e.target.value)}
                          placeholder="e.g. 192.168.1.100"
                        />
                      </div>
                      <div className="form-group">
                        <label htmlFor="settings-sftp-port">Port</label>
                        <input
                          id="settings-sftp-port"
                          type="number"
                          className="form-input"
                          value={settingsSftpPort}
                          onChange={e => setSettingsSftpPort(e.target.value)}
                          placeholder="22"
                          style={{ width: '80px' }}
                        />
                      </div>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                      <div className="form-group">
                        <label htmlFor="settings-sftp-user">SFTP Username</label>
                        <input
                          id="settings-sftp-user"
                          type="text"
                          className="form-input"
                          value={settingsSftpUser}
                          onChange={e => setSettingsSftpUser(e.target.value)}
                          placeholder="e.g. admin"
                        />
                      </div>
                      <div className="form-group">
                        <label htmlFor="settings-sftp-pass">SFTP Password</label>
                        <input
                          id="settings-sftp-pass"
                          type="password"
                          className="form-input"
                          value={settingsSftpPassword}
                          onChange={e => setSettingsSftpPassword(e.target.value)}
                          placeholder="••••••••"
                        />
                      </div>
                    </div>
                    <div className="form-group">
                      <label htmlFor="settings-sftp-base">Base Path (watch folder root)</label>
                      <input
                        id="settings-sftp-base"
                        type="text"
                        className="form-input"
                        value={settingsSftpBasePath}
                        onChange={e => setSettingsSftpBasePath(e.target.value)}
                        placeholder="e.g. /volume1/youtube"
                      />
                    </div>
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={testSftpConnection}
                      style={{ alignSelf: 'flex-start', fontSize: '0.8rem', padding: '6px 12px', marginTop: '4px' }}
                    >
                      🔌 Test SFTP/NAS Connection
                    </button>
                    {renderConnectionStatus(connectionStatusSftp)}
                  </div>

                  <button type="submit" className="btn btn-primary" style={{ alignSelf: 'flex-start', marginTop: '12px' }}>
                    💾 Save System Settings
                  </button>
                </form>
              </div>



              {/* GCP Projects & OAuth Manager Card */}
              <div className="card" style={{ padding: '24px', gap: '16px' }}>
                <h3 style={{ fontSize: '1.2rem', fontWeight: 700, borderBottom: '1px solid var(--border-color)', paddingBottom: '12px', marginBottom: '8px' }}>
                  🔑 GCP Projects & OAuth Manager
                </h3>

                {/* Styled Quick Helper Guide & Console Links */}
                <div style={{
                  background: 'linear-gradient(135deg, rgba(99, 102, 241, 0.08) 0%, rgba(168, 85, 247, 0.08) 100%)',
                  border: '1px solid rgba(99, 102, 241, 0.2)',
                  borderRadius: 'var(--radius-md)',
                  padding: '16px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '12px',
                  fontSize: '0.85rem'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--primary)', fontWeight: 600 }}>
                    ℹ️ Quick Setup Guide & Google Cloud Console Links
                  </div>
                  <div style={{ color: 'var(--text-secondary)', lineHeight: '1.45' }}>
                    Setup YouTube API access and register your credentials in a few steps. Need help? Use the quick links below.
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', marginTop: '4px' }}>
                    <a href="https://console.cloud.google.com/" target="_blank" rel="noopener noreferrer" className="btn btn-secondary" style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', textDecoration: 'none', padding: '6px 12px', fontSize: '0.8rem' }}>
                      🌐 Google Cloud Console
                    </a>
                    <a href="https://console.cloud.google.com/apis/library/youtube.googleapis.com" target="_blank" rel="noopener noreferrer" className="btn btn-secondary" style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', textDecoration: 'none', padding: '6px 12px', fontSize: '0.8rem' }}>
                      🎬 Enable YouTube API
                    </a>
                    <a href="https://console.cloud.google.com/apis/credentials" target="_blank" rel="noopener noreferrer" className="btn btn-secondary" style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', textDecoration: 'none', padding: '6px 12px', fontSize: '0.8rem' }}>
                      🔑 GCP Credentials Screen
                    </a>
                    <a href="https://developers.google.com/oauthplayground/" target="_blank" rel="noopener noreferrer" className="btn btn-secondary" style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', textDecoration: 'none', padding: '6px 12px', fontSize: '0.8rem' }}>
                      ⚙️ OAuth 2.0 Playground
                    </a>
                  </div>
                  <details style={{ marginTop: '4px', cursor: 'pointer' }}>
                    <summary style={{ color: 'var(--primary)', fontWeight: 600, fontSize: '0.8rem', outline: 'none' }}>
                      📖 View Step-by-Step Setup Guide
                    </summary>
                    <div style={{ color: 'var(--text-secondary)', padding: '12px 4px 4px 4px', fontSize: '0.8rem', cursor: 'default', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      <div>
                        <strong>Step 1: Enable YouTube API</strong>
                        <p style={{ margin: '2px 0 0 0', color: 'var(--text-muted)' }}>Go to the Google Cloud Console link above, create or select a project, and enable the <strong>YouTube Data API v3</strong>.</p>
                      </div>
                      <div>
                        <strong>Step 2: Configure Consent Screen</strong>
                        <p style={{ margin: '2px 0 0 0', color: 'var(--text-muted)' }}>Set up your <a href="https://console.cloud.google.com/apis/credentials/consent" target="_blank" rel="noopener noreferrer" style={{ color: 'var(--primary)' }}>OAuth Consent Screen</a> as <strong>External</strong> and add your target YouTube Google account as a <strong>Test User</strong>.</p>
                      </div>
                      <div>
                        <strong>Step 3: Create OAuth Client ID</strong>
                        <p style={{ margin: '2px 0 0 0', color: 'var(--text-muted)' }}>Go to Credentials, click "Create Credentials" → "OAuth client ID" (Application type: <strong>Web application</strong>).</p>
                        <p style={{ margin: '2px 0 0 0', color: 'var(--text-muted)' }}>Add the following to <strong>Authorized redirect URIs</strong> in GCP Console:</p>
                        <ul style={{ margin: '4px 0 4px 20px', padding: 0, color: 'var(--text-muted)' }}>
                          <li>For One-Click Login (popup): <code>{getRedirectUri()}</code></li>
                          <li>For Playground (manual): <code>https://developers.google.com/oauthplayground</code></li>
                        </ul>
                        <p style={{ margin: '2px 0 0 0', color: 'var(--text-muted)' }}>Download the Client Secrets JSON file, open it, and paste the entire JSON string into the "Client Secrets JSON" field below.</p>
                      </div>
                      <div>
                        <strong>Step 4: Generate OAuth Refresh Token</strong>
                        <p style={{ margin: '2px 0 0 0', color: 'var(--text-muted)' }}>Go to OAuth 2.0 Playground, click the gear icon (top right):</p>
                        <ul style={{ margin: '4px 0 4px 20px', padding: 0, color: 'var(--text-muted)' }}>
                          <li>Check "Use your own OAuth credentials"</li>
                          <li>Enter your Client ID and Client Secret (from downloaded JSON)</li>
                          <li>Close settings</li>
                        </ul>
                        <p style={{ margin: '2px 0 0 0', color: 'var(--text-muted)' }}>In Step 1 of Playground, input scope: <code>https://www.googleapis.com/auth/youtube.upload</code> and click <strong>Authorize APIs</strong>.</p>
                        <p style={{ margin: '2px 0 0 0', color: 'var(--text-muted)' }}>Sign in to your target YouTube Google account, grant permissions, then in Step 2 click <strong>Exchange authorization code for tokens</strong>.</p>
                        <p style={{ margin: '2px 0 0 0', color: 'var(--text-muted)' }}>Copy the generated <code>refresh_token</code> and paste it in the "OAuth Refresh Token" field below.</p>
                      </div>
                    </div>
                  </details>
                </div>

                {selectedSettingsChannelId && (
                  <div style={{ padding: '8px 12px', borderRadius: '6px', background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border-color)', display: 'inline-flex', alignItems: 'center', gap: '8px', fontSize: '0.9rem', color: 'var(--text-secondary)', alignSelf: 'flex-start' }}>
                    <span>Target Channel Context:</span>
                    <strong style={{ color: 'var(--primary)' }}>
                      {channels.find(c => c.id === selectedSettingsChannelId)?.name || `ID: ${selectedSettingsChannelId}`}
                    </strong>
                  </div>
                )}

                {selectedSettingsChannelId ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                    
                    {/* Active GCP Projects List */}
                    <div>
                      <h4 style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '8px' }}>
                        Active GCP Projects for Channel
                      </h4>
                      {channelProjects.length > 0 ? (
                        <div className="table-container" style={{ margin: 0, border: '1px solid var(--border-color)', borderRadius: '8px' }}>
                          <table style={{ fontSize: '0.85rem' }}>
                            <thead>
                              <tr>
                                <th>Project Name</th>
                                <th>Project ID</th>
                                <th>Quota Limit</th>
                                <th>Actions</th>
                              </tr>
                            </thead>
                            <tbody>
                              {channelProjects.map(p => (
                                <tr key={p.id}>
                                  <td style={{ fontWeight: 600 }}>{p.project_name}</td>
                                  <td>{p.project_id}</td>
                                  <td>{p.quota_limit.toLocaleString()}</td>
                                  <td>
                                    <button 
                                      className="btn btn-danger" 
                                      style={{ padding: '4px 8px', fontSize: '0.75rem' }} 
                                      onClick={() => handleDeleteGcpProject(p.id)}
                                    >
                                      🗑️ Delete
                                    </button>
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      ) : (
                        <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>No GCP Projects configured for this channel yet.</p>
                      )}
                    </div>

                    {/* Add GCP Project Form */}
                    <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: '16px' }}>
                      <h4 style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '12px' }}>
                        ➕ Register New GCP Project
                      </h4>
                      <form onSubmit={handleAddGcpProject} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                          <div className="form-group">
                            <label htmlFor="gcp-name">Project Name</label>
                            <input
                              id="gcp-name"
                              type="text"
                              className="form-input"
                              value={gcpProjectName}
                              onChange={e => setGcpProjectName(e.target.value)}
                              placeholder="e.g. My YT Uploader"
                              required
                            />
                          </div>
                          <div className="form-group">
                            <label htmlFor="gcp-id">Project ID</label>
                            <input
                              id="gcp-id"
                              type="text"
                              className="form-input"
                              value={gcpProjectId}
                              onChange={e => setGcpProjectId(e.target.value)}
                              placeholder="e.g. yt-uploader-12345"
                              required
                            />
                          </div>
                        </div>

                        <div className="form-group">
                          <label htmlFor="gcp-json">Client Secrets JSON</label>
                          <textarea
                            id="gcp-json"
                            className="form-input"
                            style={{ minHeight: '100px', fontFamily: 'monospace', fontSize: '0.8rem' }}
                            value={gcpClientSecretJson}
                            onChange={e => setGcpClientSecretJson(e.target.value)}
                            placeholder='{"web":{"client_id":"...","client_secret":"..."}}'
                            required
                          />
                        </div>

                        <div className="form-group" style={{ width: '50%' }}>
                          <label htmlFor="gcp-quota">Daily Quota Limit</label>
                          <input
                            id="gcp-quota"
                            type="number"
                            className="form-input"
                            value={gcpQuotaLimit}
                            onChange={e => setGcpQuotaLimit(parseInt(e.target.value))}
                            required
                          />
                        </div>

                        <button type="submit" className="btn btn-primary" style={{ alignSelf: 'flex-start', marginTop: '4px' }}>
                          ➕ Add GCP Project
                        </button>
                      </form>
                    </div>

                    {/* Channel OAuth Credentials Status & Form */}
                    <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: '16px' }}>
                      <h4 style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '12px' }}>
                        🔑 Google OAuth Connection Status
                      </h4>

                      {/* Display Status Header */}
                      {loadingOauthStatus ? (
                        <div style={{ padding: '12px', background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border-color)', borderRadius: '8px', fontSize: '0.85rem' }}>
                          🔄 Checking connection status...
                        </div>
                      ) : oauthStatus?.connected ? (
                        <div style={{
                          padding: '16px',
                          background: 'rgba(52, 168, 83, 0.08)',
                          border: '1px solid var(--success)',
                          borderRadius: '8px',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: '12px',
                          marginBottom: '16px'
                        }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <span style={{ color: 'var(--success)', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.95rem' }}>
                              🟢 Connected to YouTube OAuth
                            </span>
                            <button
                              type="button"
                              className="btn btn-danger"
                              style={{ padding: '6px 12px', fontSize: '0.75rem', fontWeight: 600 }}
                              onClick={handleDisconnectOAuth}
                            >
                              🔌 Disconnect
                            </button>
                          </div>
                          <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: '1.5' }}>
                            <strong>Active GCP Project:</strong> <code style={{ background: 'rgba(255,255,255,0.05)', padding: '2px 6px', borderRadius: '4px' }}>{oauthStatus.gcp_project_id}</code> <br />
                            {oauthStatus.last_refreshed_at && (
                              <span>
                                <strong>Last Refreshed:</strong> {new Date(oauthStatus.last_refreshed_at).toLocaleString()} <br />
                              </span>
                            )}
                            {oauthStatus.last_error && (
                              <div style={{ color: 'var(--danger)', marginTop: '4px' }}>
                                <strong>Last Error:</strong> {oauthStatus.last_error}
                              </div>
                            )}
                          </div>
                        </div>
                      ) : (
                        <div style={{
                          padding: '16px',
                          background: 'rgba(234, 67, 53, 0.08)',
                          border: '1px solid var(--danger)',
                          borderRadius: '8px',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '8px',
                          color: 'var(--danger)',
                          fontWeight: 600,
                          fontSize: '0.95rem',
                          marginBottom: '16px'
                        }}>
                          🔴 Not Connected (Please complete authorization below)
                        </div>
                      )}

                      {/* Render Credentials Forms */}
                      {oauthStatus?.connected ? (
                        <details style={{
                          background: 'rgba(255, 255, 255, 0.01)',
                          border: '1px solid var(--border-color)',
                          borderRadius: '8px',
                          padding: '12px'
                        }}>
                          <summary style={{ cursor: 'pointer', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-muted)' }}>
                            Change Connection / Reconnect Options
                          </summary>
                          <div style={{ marginTop: '16px' }}>
                            <form onSubmit={handleSaveOAuthToken} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                              <div className="form-group">
                                <label htmlFor="oauth-gcp-project">Target GCP Project ID</label>
                                <select
                                  id="oauth-gcp-project"
                                  className="form-input"
                                  value={oauthGcpProjectId}
                                  onChange={e => setOauthGcpProjectId(e.target.value)}
                                  required
                                >
                                  <option value="">-- Select GCP Project --</option>
                                  {channelProjects.map(p => (
                                    <option key={p.id} value={p.project_id}>{p.project_name} ({p.project_id})</option>
                                  ))}
                                </select>
                              </div>

                              {/* Option A: One-Click Google Auth */}
                              <div style={{
                                padding: '16px',
                                background: 'rgba(255, 255, 255, 0.02)',
                                border: '1px solid var(--border-color)',
                                borderRadius: 'var(--radius-md)',
                                display: 'flex',
                                flexDirection: 'column',
                                gap: '10px'
                              }}>
                                <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                                  Option A: One-Click Google Authorization (Recommended)
                                </span>
                                <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', lineHeight: '1.4' }}>
                                  Click the button below to authorize this channel using Google's secure popup window.
                                </span>
                                <button
                                  type="button"
                                  className="btn btn-primary"
                                  disabled={!oauthGcpProjectId}
                                  onClick={handleGoogleAuthFlow}
                                  style={{
                                    background: oauthGcpProjectId 
                                      ? 'linear-gradient(135deg, #4285f4 0%, #34a853 100%)' 
                                      : 'var(--bg-card)',
                                    border: oauthGcpProjectId ? 'none' : '1px solid var(--border-color)',
                                    alignSelf: 'flex-start',
                                    fontWeight: 600,
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '8px',
                                    padding: '8px 16px',
                                    cursor: oauthGcpProjectId ? 'pointer' : 'not-allowed'
                                  }}
                                >
                                  <svg width="18" height="18" viewBox="0 0 24 24" fill="white">
                                    <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
                                    <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                                    <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z" fill="#FBBC05"/>
                                    <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z" fill="#EA4335"/>
                                  </svg>
                                  Authorize Channel with Google
                                </button>
                                {!oauthGcpProjectId && (
                                  <span style={{ fontSize: '0.75rem', color: 'var(--danger)' }}>
                                    * Please select a target GCP project above first.
                                  </span>
                                )}
                              </div>

                              {/* Option B: Manual token fallback */}
                              <div style={{
                                padding: '16px',
                                background: 'rgba(255, 255, 255, 0.02)',
                                border: '1px solid var(--border-color)',
                                borderRadius: 'var(--radius-md)',
                                display: 'flex',
                                flexDirection: 'column',
                                gap: '12px'
                              }}>
                                <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                                  Option B: Manual Refresh Token Entry (Alternative)
                                </span>
                                <div className="form-group" style={{ margin: 0 }}>
                                  <label htmlFor="oauth-refresh-token" style={{ marginBottom: '6px' }}>OAuth Refresh Token</label>
                                  <input
                                    id="oauth-refresh-token"
                                    type="password"
                                    className="form-input"
                                    value={oauthRefreshToken}
                                    onChange={e => setOauthRefreshToken(e.target.value)}
                                    placeholder="Enter Google OAuth refresh token manually..."
                                  />
                                </div>
                                <button 
                                  type="submit" 
                                  className="btn btn-primary" 
                                  disabled={!oauthRefreshToken}
                                  style={{ 
                                    alignSelf: 'flex-start', 
                                    opacity: oauthRefreshToken ? 1 : 0.6,
                                    cursor: oauthRefreshToken ? 'pointer' : 'not-allowed'
                                  }}
                                >
                                  💾 Save Channel Credentials
                                </button>
                              </div>
                            </form>
                          </div>
                        </details>
                      ) : (
                        <div style={{
                          background: 'rgba(255, 255, 255, 0.01)',
                          border: '1px solid var(--border-color)',
                          borderRadius: '8px',
                          padding: '16px'
                        }}>
                          <form onSubmit={handleSaveOAuthToken} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                            <div className="form-group">
                              <label htmlFor="oauth-gcp-project">Target GCP Project ID</label>
                              <select
                                id="oauth-gcp-project"
                                className="form-input"
                                value={oauthGcpProjectId}
                                onChange={e => setOauthGcpProjectId(e.target.value)}
                                required
                              >
                                <option value="">-- Select GCP Project --</option>
                                {channelProjects.map(p => (
                                  <option key={p.id} value={p.project_id}>{p.project_name} ({p.project_id})</option>
                                ))}
                              </select>
                            </div>

                            {/* Option A: One-Click Google Auth */}
                            <div style={{
                              padding: '16px',
                              background: 'rgba(255, 255, 255, 0.02)',
                              border: '1px solid var(--border-color)',
                              borderRadius: 'var(--radius-md)',
                              display: 'flex',
                              flexDirection: 'column',
                              gap: '10px'
                            }}>
                              <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                                Option A: One-Click Google Authorization (Recommended)
                              </span>
                              <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', lineHeight: '1.4' }}>
                                Click the button below to authorize this channel using Google's secure popup window.
                              </span>
                              <button
                                type="button"
                                className="btn btn-primary"
                                disabled={!oauthGcpProjectId}
                                onClick={handleGoogleAuthFlow}
                                style={{
                                  background: oauthGcpProjectId 
                                    ? 'linear-gradient(135deg, #4285f4 0%, #34a853 100%)' 
                                    : 'var(--bg-card)',
                                  border: oauthGcpProjectId ? 'none' : '1px solid var(--border-color)',
                                  alignSelf: 'flex-start',
                                  fontWeight: 600,
                                  display: 'flex',
                                  alignItems: 'center',
                                  gap: '8px',
                                  padding: '8px 16px',
                                  cursor: oauthGcpProjectId ? 'pointer' : 'not-allowed'
                                }}
                              >
                                <svg width="18" height="18" viewBox="0 0 24 24" fill="white">
                                  <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
                                  <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                                  <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z" fill="#FBBC05"/>
                                  <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z" fill="#EA4335"/>
                                </svg>
                                Authorize Channel with Google
                              </button>
                              {!oauthGcpProjectId && (
                                <span style={{ fontSize: '0.75rem', color: 'var(--danger)' }}>
                                  * Please select a target GCP project above first.
                                </span>
                              )}
                            </div>

                            {/* Option B: Manual token fallback */}
                            <div style={{
                              padding: '16px',
                              background: 'rgba(255, 255, 255, 0.02)',
                              border: '1px solid var(--border-color)',
                              borderRadius: 'var(--radius-md)',
                              display: 'flex',
                              flexDirection: 'column',
                              gap: '12px'
                            }}>
                              <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                                Option B: Manual Refresh Token Entry (Alternative)
                              </span>
                              <div className="form-group" style={{ margin: 0 }}>
                                <label htmlFor="oauth-refresh-token" style={{ marginBottom: '6px' }}>OAuth Refresh Token</label>
                                <input
                                  id="oauth-refresh-token"
                                  type="password"
                                  className="form-input"
                                  value={oauthRefreshToken}
                                  onChange={e => setOauthRefreshToken(e.target.value)}
                                  placeholder="Enter Google OAuth refresh token manually..."
                                />
                              </div>
                              <button 
                                type="submit" 
                                className="btn btn-primary" 
                                disabled={!oauthRefreshToken}
                                style={{ 
                                  alignSelf: 'flex-start', 
                                  opacity: oauthRefreshToken ? 1 : 0.6,
                                  cursor: oauthRefreshToken ? 'pointer' : 'not-allowed'
                                }}
                              >
                                💾 Save Channel Credentials
                              </button>
                            </div>
                          </form>
                        </div>
                      )}
                    </div>
                  </div>
                ) : (
                  <div style={{ padding: '40px 20px', textAlign: 'center', border: '1px dashed var(--border-color)', borderRadius: '8px', color: 'var(--text-muted)' }}>
                    Please select a channel in the sidebar dropdown to manage credentials and GCP projects.
                  </div>
                )}
              </div>

            </div>
          </div>
        )}
      </main>

      {/* Toast Notification alert */}
      {toast && (
        <div className={`toast toast-${toast.type}`}>
          <span>{toast.type === 'success' ? '✅' : '❌'}</span>
          <span>{toast.message}</span>
        </div>
      )}

      {/* Edit Video Drawer / Modal */}
      {isEditModalOpen && selectedVideo && (
        <div className="modal-overlay" id="edit-video-modal">
          <div className="modal-content">
            <div className="modal-header">
              <h2>Review Draft details — ID {selectedVideo.id}</h2>
              <button type="button" className="modal-close" onClick={() => setIsEditModalOpen(false)}>×</button>
            </div>

            <div className="modal-body">
              {/* Hermes AI Review & Prediction Note */}
              {selectedVideo.ai_review_note && (
                <div style={{
                  background: 'linear-gradient(135deg, rgba(79, 70, 229, 0.15), rgba(124, 58, 237, 0.15))',
                  border: '1px solid rgba(124, 58, 237, 0.3)',
                  borderRadius: '12px',
                  padding: '16px',
                  marginBottom: '20px',
                  boxShadow: '0 4px 20px rgba(124, 58, 237, 0.08)',
                  backdropFilter: 'blur(8px)',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px', color: '#c084fc', fontWeight: 'bold', fontSize: '0.95rem' }}>
                    <span>✨</span>
                    <span>Hermes AI Advisor Note & Prediction</span>
                  </div>
                  <p style={{ margin: 0, fontSize: '0.88rem', color: 'var(--text-secondary)', lineHeight: '1.5' }}>
                    {selectedVideo.ai_review_note}
                  </p>
                </div>
              )}

              {/* Screenshot Frame Display */}
              <div className="form-group" style={{ marginBottom: '16px' }}>
                <label style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span>Video Screenshot Frame</span>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    style={{ padding: '2px 6px', fontSize: '0.7rem' }}
                    onClick={() => setPreviewImageUrl(`${API_URL}/videos/${selectedVideo.id}/screenshot`)}
                  >
                    🔍 View Screenshot
                  </button>
                </label>
                <div style={{ width: '100%', height: '200px', background: 'rgba(0,0,0,0.2)', borderRadius: '8px', overflow: 'hidden', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
                  <img
                    src={`${API_URL}/videos/${selectedVideo.id}/screenshot`}
                    alt="Video Screenshot"
                    style={{ width: '100%', height: '100%', objectFit: 'contain', cursor: 'pointer' }}
                    onClick={() => setPreviewImageUrl(`${API_URL}/videos/${selectedVideo.id}/screenshot`)}
                    onError={(e) => {
                      e.currentTarget.style.display = 'none';
                      const parent = e.currentTarget.parentElement;
                      if (parent) {
                        const fallback = document.createElement('span');
                        fallback.style.fontSize = '3rem';
                        fallback.innerText = '🎬';
                        parent.appendChild(fallback);
                      }
                    }}
                  />
                </div>
              </div>

              {/* Thumbnail Draft Options */}
              <div className="form-group">
                <label>Select Thumbnail Option</label>
                <div style={{ padding: '20px', textAlign: 'center', background: 'rgba(0,0,0,0.1)', borderRadius: '8px', color: 'var(--text-muted)' }}>
                  Thumbnail generation is currently disabled.
                </div>
              </div>

              {/* Manual Presets & AI disabled controls */}
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginBottom: '16px' }}>
                <button
                  type="button"
                  className="btn"
                  onClick={handleApplyChannelPresets}
                  style={{
                    background: 'linear-gradient(135deg, #10b981, #059669)',
                    color: '#fff',
                    border: 'none',
                    fontWeight: 600,
                    padding: '8px 16px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    boxShadow: '0 4px 12px rgba(16, 185, 129, 0.25)',
                    transition: 'all 0.2s ease',
                  }}
                >
                  📋 Apply Channel Presets
                </button>
                <button
                  type="button"
                  className="btn"
                  disabled={true}
                  style={{
                    background: 'rgba(255, 255, 255, 0.05)',
                    color: 'var(--text-muted)',
                    border: '1px solid rgba(255, 255, 255, 0.08)',
                    fontWeight: 600,
                    padding: '8px 16px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    cursor: 'not-allowed',
                    transition: 'all 0.2s ease',
                  }}
                  title="AI generator is temporarily pending/disabled."
                >
                  ✨ AI Optimization Disabled
                </button>
              </div>

              {aiEnhancedData && (
                <div style={{
                  background: 'rgba(255, 255, 255, 0.03)',
                  border: '1px solid rgba(255, 255, 255, 0.08)',
                  borderRadius: '12px',
                  padding: '16px',
                  marginBottom: '20px',
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                    <h3 style={{ margin: 0, fontSize: '1rem', color: 'var(--text-primary)' }}>✨ Hermes Recommendations</h3>
                    <button
                      type="button"
                      className="btn btn-secondary"
                      style={{ padding: '2px 8px', fontSize: '0.75rem' }}
                      onClick={() => setAiEnhancedData(null)}
                    >
                      Dismiss
                    </button>
                  </div>

                  <div className="form-group" style={{ marginBottom: '12px' }}>
                    <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Choose an Optimized Title:</label>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '6px' }}>
                      {aiEnhancedData.titles.map((t, idx) => (
                        <button
                          key={idx}
                          type="button"
                          className="form-input"
                          style={{
                            textAlign: 'left',
                            background: 'rgba(255,255,255,0.02)',
                            cursor: 'pointer',
                            padding: '10px 12px',
                            border: '1px solid rgba(255,255,255,0.08)',
                            borderRadius: '6px',
                            fontSize: '0.85rem',
                          }}
                          onClick={() => {
                            setEditTitle(t);
                            triggerToast('Applied title option!');
                          }}
                        >
                          📌 {t}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="form-group" style={{ marginBottom: '12px' }}>
                    <label style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                      <span>Optimized Description:</span>
                      <button
                        type="button"
                        className="btn btn-secondary"
                        style={{ padding: '2px 6px', fontSize: '0.7rem' }}
                        onClick={() => {
                          setEditDesc(aiEnhancedData.description);
                          triggerToast('Applied optimized description!');
                        }}
                      >
                        Apply Description
                      </button>
                    </label>
                    <pre style={{
                      whiteSpace: 'pre-wrap',
                      background: 'rgba(0,0,0,0.2)',
                      padding: '10px',
                      borderRadius: '6px',
                      fontSize: '0.8rem',
                      maxHeight: '150px',
                      overflowY: 'auto',
                      marginTop: '6px',
                    }}>
                      {aiEnhancedData.description}
                    </pre>
                  </div>

                  <div className="form-group">
                    <label style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                      <span>Optimized Tags:</span>
                      <button
                        type="button"
                        className="btn btn-secondary"
                        style={{ padding: '2px 6px', fontSize: '0.7rem' }}
                        onClick={() => {
                          setEditTags(aiEnhancedData.tags.join(', '));
                          triggerToast('Applied optimized tags!');
                        }}
                      >
                        Apply Tags
                      </button>
                    </label>
                    <div style={{ marginTop: '6px', display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                      {aiEnhancedData.tags.map((tag, idx) => (
                        <span key={idx} style={{
                          background: 'rgba(255,255,255,0.05)',
                          border: '1px solid rgba(255,255,255,0.1)',
                          borderRadius: '4px',
                          padding: '3px 8px',
                          fontSize: '0.75rem',
                        }}>
                          #{tag}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {/* Metadata Fields */}
              <div className="form-group">
                <label htmlFor="edit-title">Title Draft</label>
                <input 
                  id="edit-title"
                  type="text" 
                  className="form-input" 
                  value={editTitle} 
                  onChange={e => setEditTitle(e.target.value)} 
                  maxLength={100}
                />
              </div>

              <div className="form-group">
                <label htmlFor="edit-desc">Description Draft</label>
                <textarea 
                  id="edit-desc"
                  className="form-textarea" 
                  value={editDesc} 
                  onChange={e => setEditDesc(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label htmlFor="edit-tags">Tags (Comma-separated)</label>
                <input 
                  id="edit-tags"
                  type="text" 
                  className="form-input" 
                  value={editTags} 
                  onChange={e => setEditTags(e.target.value)}
                  placeholder="lofi, study, chill"
                />
              </div>

              <hr style={{ border: 'none', borderTop: '1px solid var(--border-color)', margin: '16px 0' }} />
              <h3>YouTube Settings Overrides</h3>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                <div className="form-group">
                  <label htmlFor="edit-playlist-id">Playlist ID Override</label>
                  <input
                    id="edit-playlist-id"
                    type="text"
                    className="form-input"
                    value={editPlaylistId}
                    onChange={e => setEditPlaylistId(e.target.value)}
                    placeholder="e.g. PL..."
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="edit-category-id">Category Override</label>
                  <select
                    id="edit-category-id"
                    className="form-input"
                    value={editCategoryId}
                    onChange={e => setEditCategoryId(e.target.value)}
                  >
                    <option value="1">Film & Animation (1)</option>
                    <option value="2">Autos & Vehicles (2)</option>
                    <option value="10">Music (10)</option>
                    <option value="15">Pets & Animals (15)</option>
                    <option value="17">Sports (17)</option>
                    <option value="19">Travel & Events (19)</option>
                    <option value="20">Gaming (20)</option>
                    <option value="22">People & Blogs (22)</option>
                    <option value="23">Comedy (23)</option>
                    <option value="24">Entertainment (24)</option>
                    <option value="25">News & Politics (25)</option>
                    <option value="26">Howto & Style (26)</option>
                    <option value="27">Education (27)</option>
                    <option value="28">Science & Technology (28)</option>
                    <option value="29">Nonprofits & Activism (29)</option>
                  </select>
                </div>
              </div>

              <div className="form-group">
                <label htmlFor="edit-default-lang">Subtitle Language Override</label>
                <select
                  id="edit-default-lang"
                  className="form-input"
                  value={editDefaultLanguage}
                  onChange={e => setEditDefaultLanguage(e.target.value)}
                >
                  <option value="">-- No Language --</option>
                  <option value="en">English (en)</option>
                  <option value="id">Indonesian (id)</option>
                  <option value="es">Spanish (es)</option>
                  <option value="ja">Japanese (ja)</option>
                  <option value="fr">French (fr)</option>
                  <option value="pt">Portuguese (pt)</option>
                  <option value="hi">Hindi (hi)</option>
                  <option value="de">German (de)</option>
                  <option value="ko">Korean (ko)</option>
                  <option value="zh">Chinese (zh)</option>
                </select>
              </div>

              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '20px', alignItems: 'center', margin: '12px 0' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={editMadeForKids}
                    onChange={e => setEditMadeForKids(e.target.checked)}
                  />
                  Made for Kids
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={editAgeRestricted}
                    onChange={e => setEditAgeRestricted(e.target.checked)}
                  />
                  Age Restricted (18+)
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={editAiGenerated}
                    onChange={e => setEditAiGenerated(e.target.checked)}
                  />
                  Altered/AI-Generated Content
                </label>
              </div>

              {(editAgeRestricted || editAiGenerated) && (
                <div style={{
                  background: 'rgba(245, 158, 11, 0.05)',
                  border: '1px solid rgba(245, 158, 11, 0.2)',
                  borderRadius: '8px',
                  padding: '12px',
                  marginBottom: '16px',
                  fontSize: '0.8rem',
                  color: 'var(--warning)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '4px',
                }}>
                  {editAgeRestricted && (
                    <span>⚠️ <b>Age Restriction Note</b>: YouTube Data API v3 does not support setting "Age Restriction" programmatically. This will be stored for documentation but must be checked/verified manually on YouTube Studio.</span>
                  )}
                  {editAiGenerated && (
                    <span>⚠️ <b>Altered/AI Content Note</b>: YouTube Data API v3 does not support setting "Altered/AI Content" flag programmatically. Please toggle this setting manually in YouTube Studio.</span>
                  )}
                </div>
              )}


              <div style={{ display: 'flex', gap: '12px', marginTop: '12px' }}>
                {['failed', 'error'].includes(selectedVideo.status) ? (
                  <>
                    <button type="button" className="btn btn-primary" onClick={() => handleRetryVideo(selectedVideo.id)}>
                      🔁 Retry Upload
                    </button>
                    {selectedVideo.status === 'error' && (
                      <button type="button" className="btn btn-danger" style={{ marginLeft: 'auto' }} onClick={() => handleDiscardVideo(selectedVideo.id)}>
                        🗑️ Discard Video
                      </button>
                    )}
                  </>
                ) : (
                  <>
                    <button type="button" className="btn btn-secondary" onClick={handleSaveMetadata}>
                      💾 Save Draft Changes
                    </button>
                    <button type="button" className="btn btn-success" onClick={() => handleApproveVideo(selectedVideo.id)}>
                      ✅ Approve & Schedule Upload
                    </button>
                    <button type="button" className="btn btn-danger" style={{ marginLeft: 'auto' }} onClick={() => handleDiscardVideo(selectedVideo.id)}>
                      🗑️ Discard Video
                    </button>
                  </>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Create / Edit Channel Modal */}
      {isChannelModalOpen && (
        <div className="modal-overlay" id="channel-form-modal">
          <form className="modal-content" onSubmit={handleSaveChannel}>
            <div className="modal-header">
              <h2>{editingChannel ? 'Modify Channel configuration' : 'Register New Channel'}</h2>
              <button type="button" className="modal-close" onClick={() => setIsChannelModalOpen(false)}>×</button>
            </div>
            
            <div className="modal-body">
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                <div className="form-group">
                  <label htmlFor="chan-name">Channel Name</label>
                  <input
                    id="chan-name"
                    type="text"
                    className="form-input"
                    value={chanName}
                    onChange={e => setChanName(e.target.value)}
                    required
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="chan-genre">Genre</label>
                  <select
                    id="chan-genre"
                    className="form-input"
                    value={chanGenre}
                    onChange={e => setChanGenre(e.target.value)}
                    required
                  >
                    <option value="">-- Select YouTube Category --</option>
                    <option value="Film & Animation">Film & Animation</option>
                    <option value="Autos & Vehicles">Autos & Vehicles</option>
                    <option value="Music">Music</option>
                    <option value="Pets & Animals">Pets & Animals</option>
                    <option value="Sports">Sports</option>
                    <option value="Travel & Events">Travel & Events</option>
                    <option value="Gaming">Gaming</option>
                    <option value="People & Blogs">People & Blogs</option>
                    <option value="Comedy">Comedy</option>
                    <option value="Entertainment">Entertainment</option>
                    <option value="News & Politics">News & Politics</option>
                    <option value="Howto & Style">Howto & Style</option>
                    <option value="Education">Education</option>
                    <option value="Science & Technology">Science & Technology</option>
                    <option value="Nonprofits & Activism">Nonprofits & Activism</option>
                  </select>
                </div>
              </div>

              <div className="form-group">
                <label htmlFor="chan-folder">NAS Watch Folder Path</label>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                  <select
                    id="chan-folder"
                    className="form-input"
                    value={chanFolder}
                    onChange={e => setChanFolder(e.target.value)}
                    required
                    style={{ flex: 1 }}
                  >
                    <option value="">-- Select Folder on NAS --</option>
                    {watchFolders.map(folder => (
                      <option key={folder} value={folder}>{folder}</option>
                    ))}
                    {chanFolder && !watchFolders.includes(chanFolder) && (
                      <option value={chanFolder}>{chanFolder} (Custom/Legacy)</option>
                    )}
                  </select>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={fetchWatchFolders}
                    title="Refresh folder list"
                    style={{ padding: '8px 12px', flexShrink: 0, fontSize: '1rem' }}
                  >
                    🔄
                  </button>
                </div>
                {watchFolders.length === 0 && (
                  <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                    No folders found. Configure SFTP in Settings or ensure the NAS volume is mounted.
                  </p>
                )}
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                <div className="form-group">
                  <label>Preferred Daily Upload Time</label>
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                    <select
                      className="form-input"
                      style={{ flex: 1 }}
                      value={chanHour}
                      onChange={e => setChanHour(e.target.value)}
                    >
                      {Array.from({ length: 24 }).map((_, i) => {
                        const h = String(i).padStart(2, '0');
                        return <option key={h} value={h}>{h}</option>;
                      })}
                    </select>
                    <span>:</span>
                    <select
                      className="form-input"
                      style={{ flex: 1 }}
                      value={chanMinute}
                      onChange={e => setChanMinute(e.target.value)}
                    >
                      {Array.from({ length: 60 }).map((_, i) => {
                        const m = String(i).padStart(2, '0');
                        return <option key={m} value={m}>{m}</option>;
                      })}
                    </select>
                    <span>:</span>
                    <select
                      className="form-input"
                      style={{ flex: 1 }}
                      value={chanSecond}
                      onChange={e => setChanSecond(e.target.value)}
                    >
                      {Array.from({ length: 60 }).map((_, i) => {
                        const s = String(i).padStart(2, '0');
                        return <option key={s} value={s}>{s}</option>;
                      })}
                    </select>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: '20px', alignItems: 'center', marginTop: '28px' }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={chanActive}
                      onChange={e => setChanActive(e.target.checked)}
                    />
                    Active
                  </label>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={chanAutoApprove}
                      onChange={e => setChanAutoApprove(e.target.checked)}
                    />
                    Auto Approve
                  </label>
                </div>
              </div>

              <hr style={{ border: 'none', borderTop: '1px solid var(--border-color)', margin: '8px 0' }} />
              <h3>AI Metadata generation templates</h3>

              <div className="form-group">
                <label htmlFor="chan-title-temp">Preset Title Template</label>
                <input
                  id="chan-title-temp"
                  type="text"
                  className="form-input"
                  value={chanTitleTemp}
                  onChange={e => setChanTitleTemp(e.target.value)}
                  placeholder="e.g. {mood} lofi mix for {activity}"
                />
              </div>

              <div className="form-group">
                <label htmlFor="chan-desc-temp">Preset Description Template</label>
                <textarea
                  id="chan-desc-temp"
                  className="form-textarea"
                  value={chanDescTemp}
                  onChange={e => setChanDescTemp(e.target.value)}
                  placeholder="Default video summary, links, and hashtags presets..."
                />
              </div>

              <div className="form-group">
                <label htmlFor="chan-tags">Preset Tags (Comma-separated)</label>
                <input
                  id="chan-tags"
                  type="text"
                  className="form-input"
                  value={chanTags}
                  onChange={e => setChanTags(e.target.value)}
                  placeholder="lofi, lofigirl, relaxing"
                />
              </div>

              <hr style={{ border: 'none', borderTop: '1px solid var(--border-color)', margin: '8px 0' }} />
              <h3>YouTube Defaults & Channel Presets</h3>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                <div className="form-group">
                  <label htmlFor="chan-playlist-id">Default Playlist ID</label>
                  <input
                    id="chan-playlist-id"
                    type="text"
                    className="form-input"
                    value={chanPlaylistId}
                    onChange={e => setChanPlaylistId(e.target.value)}
                    placeholder="e.g. PL..."
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="chan-category-id">Default Category</label>
                  <select
                    id="chan-category-id"
                    className="form-input"
                    value={chanCategoryId}
                    onChange={e => setChanCategoryId(e.target.value)}
                  >
                    <option value="">-- Select Category --</option>
                    <option value="1">Film & Animation (1)</option>
                    <option value="2">Autos & Vehicles (2)</option>
                    <option value="10">Music (10)</option>
                    <option value="15">Pets & Animals (15)</option>
                    <option value="17">Sports (17)</option>
                    <option value="19">Travel & Events (19)</option>
                    <option value="20">Gaming (20)</option>
                    <option value="22">People & Blogs (22)</option>
                    <option value="23">Comedy (23)</option>
                    <option value="24">Entertainment (24)</option>
                    <option value="25">News & Politics (25)</option>
                    <option value="26">Howto & Style (26)</option>
                    <option value="27">Education (27)</option>
                    <option value="28">Science & Technology (28)</option>
                    <option value="29">Nonprofits & Activism (29)</option>
                  </select>
                </div>
              </div>

              <div className="form-group">
                <label htmlFor="chan-default-lang">Default Subtitle Language</label>
                <select
                  id="chan-default-lang"
                  className="form-input"
                  value={chanDefaultLanguage}
                  onChange={e => setChanDefaultLanguage(e.target.value)}
                >
                  <option value="">-- Select Language --</option>
                  <option value="en">English (en)</option>
                  <option value="id">Indonesian (id)</option>
                  <option value="es">Spanish (es)</option>
                  <option value="ja">Japanese (ja)</option>
                  <option value="fr">French (fr)</option>
                  <option value="pt">Portuguese (pt)</option>
                  <option value="hi">Hindi (hi)</option>
                  <option value="de">German (de)</option>
                  <option value="ko">Korean (ko)</option>
                  <option value="zh">Chinese (zh)</option>
                </select>
              </div>

              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '20px', alignItems: 'center', margin: '12px 0' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={chanMadeForKids}
                    onChange={e => setChanMadeForKids(e.target.checked)}
                  />
                  Made for Kids
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={chanAgeRestricted}
                    onChange={e => setChanAgeRestricted(e.target.checked)}
                  />
                  Age Restricted (18+)
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={chanAiGenerated}
                    onChange={e => setChanAiGenerated(e.target.checked)}
                  />
                  Altered/AI-Generated Content
                </label>
              </div>

              <hr style={{ border: 'none', borderTop: '1px solid var(--border-color)', margin: '8px 0' }} />
              <h3>AI Thumbnail presets</h3>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '16px' }}>
                <div className="form-group">
                  <label htmlFor="chan-thumb-style">Thumbnail Style Name</label>
                  <input
                    id="chan-thumb-style"
                    type="text"
                    className="form-input"
                    value={chanThumbStyle}
                    onChange={e => setChanThumbStyle(e.target.value)}
                    placeholder="e.g. fireplace_relax"
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="chan-thumb-prompt">AI Style Prompt</label>
                  <input
                    id="chan-thumb-prompt"
                    type="text"
                    className="form-input"
                    value={chanThumbPrompt}
                    onChange={e => setChanThumbPrompt(e.target.value)}
                    placeholder="Detailed visual artwork prompt context..."
                  />
                </div>
              </div>

              <div style={{ display: 'flex', gap: '12px', marginTop: '12px' }}>
                <button type="submit" className="btn btn-primary" style={{ flexGrow: 1 }}>
                  💾 Save Channel Settings
                </button>
                <button type="button" className="btn btn-secondary" onClick={() => setIsChannelModalOpen(false)}>
                  Cancel
                </button>
              </div>
            </div>
          </form>
        </div>
      )}

      {/* Lightbox / Image Preview Modal */}
      {previewImageUrl && (
        <div className="modal-overlay" style={{ zIndex: 1100 }} onClick={() => setPreviewImageUrl(null)}>
          <div className="modal-content" style={{ maxWidth: '800px', padding: '10px', background: 'transparent', border: 'none', boxShadow: 'none' }} onClick={e => e.stopPropagation()}>
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '10px' }}>
              <button 
                type="button" 
                className="modal-close" 
                style={{ fontSize: '2rem', color: '#fff', background: 'rgba(0,0,0,0.5)', width: '40px', height: '40px', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center' }} 
                onClick={() => setPreviewImageUrl(null)}
              >
                ×
              </button>
            </div>
            <img 
              src={previewImageUrl} 
              alt="Preview" 
              style={{ width: '100%', maxHeight: '80vh', objectFit: 'contain', borderRadius: '8px', boxShadow: '0 8px 32px rgba(0,0,0,0.5)' }} 
            />
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
