import React, { useState, useEffect } from 'react';
import './App.css';

// Base API URL
const API_URL = import.meta.env.VITE_API_URL || 
  (typeof window !== 'undefined' && window.location.port === '5173' 
    ? 'http://localhost:8000/api/v1' 
    : '/api/v1');

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

  // Secondary Features state
  const [previewImageUrl, setPreviewImageUrl] = useState<string | null>(null);
  const [selectedAnalyticsChannelId, setSelectedAnalyticsChannelId] = useState<number | null>(null);
  const [analyticsData, setAnalyticsData] = useState<any>(null);
  const [loadingAnalytics, setLoadingAnalytics] = useState(false);
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

  // GCP Projects & Credentials state
  const [selectedSettingsChannelId, setSelectedSettingsChannelId] = useState<number | ''>('');
  const [channelProjects, setChannelProjects] = useState<any[]>([]);
  const [gcpProjectName, setGcpProjectName] = useState('');
  const [gcpProjectId, setGcpProjectId] = useState('');
  const [gcpClientSecretJson, setGcpClientSecretJson] = useState('');
  const [gcpQuotaLimit, setGcpQuotaLimit] = useState(10000);
  const [oauthGcpProjectId, setOauthGcpProjectId] = useState('');
  const [oauthRefreshToken, setOauthRefreshToken] = useState('');
  
  // UI Toast and loading indicators
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);
  const [loading, setLoading] = useState(false);

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
          if (iframe.contentDocument?.readyState === 'complete') {
            setRecaptchaReady(true);
          } else {
            iframe.addEventListener('load', () => setRecaptchaReady(true), { once: true });
          }
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

  // Load settings when tab is set to settings, and load projects when channel changes
  useEffect(() => {
    if (token && currentTab === 'settings') {
      fetchSettings();
      if (selectedSettingsChannelId) {
        fetchChannelProjects(selectedSettingsChannelId);
      } else {
        setChannelProjects([]);
      }
    }
  }, [token, currentTab, selectedSettingsChannelId]);

  // Load channel analytics when tab changes to analytics
  useEffect(() => {
    if (token && currentTab === 'analytics') {
      if (selectedAnalyticsChannelId) {
        fetchAnalytics(selectedAnalyticsChannelId);
      } else if (channels.length > 0) {
        setSelectedAnalyticsChannelId(channels[0].id);
        fetchAnalytics(channels[0].id);
      }
    }
  }, [token, currentTab, selectedAnalyticsChannelId, channels]);

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
      } else {
        const data = await res.json();
        triggerToast(data.detail || 'Failed to save OAuth token.', 'error');
      }
    } catch (e) {
      triggerToast('Network error saving OAuth token.', 'error');
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
    setLoadingAnalytics(true);
    try {
      const res = await fetch(`${API_URL}/channels/${channelId}/analytics`, {
        headers: getHeaders(),
      });
      if (res.ok) {
        const data = await res.json();
        setAnalyticsData(data);
      } else {
        triggerToast('Failed to fetch channel analytics.', 'error');
      }
    } catch (e) {
      triggerToast('Error fetching analytics.', 'error');
    } finally {
      setLoadingAnalytics(false);
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
      </div>
    );
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
            <div className="page-header">
              <div className="page-title-group">
                <h1>Background Queue Manager</h1>
                <p>Track Celery worker sequential upload execution progress and error history</p>
              </div>
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
                    <th>Video Title</th>
                    <th>Size</th>
                    <th>Privacy</th>
                    <th>Queue Status</th>
                    <th>Retries</th>
                    <th>Error Detail</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {videos.filter(v => v.status !== 'staging' && v.status !== 'detected' && v.status !== 'discarded').map(video => (
                    <tr key={video.id}>
                      <td>{video.id}</td>
                      <td style={{ fontWeight: 600 }}>{video.current_title || video.filename}</td>
                      <td>{(video.file_size_bytes / (1024*1024)).toFixed(1)} MB</td>
                      <td style={{ textTransform: 'capitalize' }}>{video.youtube_privacy}</td>
                      <td>
                        <span className={`card-badge badge-${video.status}`}>
                          {video.status}
                        </span>
                      </td>
                      <td>{video.retry_count}</td>
                      <td style={{ fontSize: '0.8rem', color: 'var(--danger)', maxWidth: '250px', textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }} title={video.last_error || ''}>
                        {video.last_error || '-'}
                      </td>
                      <td>
                        {['failed', 'error'].includes(video.status) && (
                          <button className="btn btn-secondary" style={{ padding: '6px 12px', fontSize: '0.8rem' }} onClick={() => openEditModal(video)}>
                            ✏️ Review / Retry
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                  {videos.filter(v => v.status !== 'staging' && v.status !== 'detected' && v.status !== 'discarded').length === 0 && (
                    <tr>
                      <td colSpan={8} style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                        No videos currently in processing queue.
                      </td>
                    </tr>
                  )}
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
                  <span className="card-badge badge-approved" style={{ alignSelf: 'center' }}>{v.status}</span>
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

        {/* Tab 5: Analytics */}
        {currentTab === 'analytics' && (
          <div>
            <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
              <div className="page-title-group">
                <h1>Performance Insights</h1>
                <p>YouTube Channel views tracking, engagement metrics, and daily trends</p>
              </div>
              <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                <label style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', fontWeight: 600 }}>Select Channel:</label>
                <select 
                  className="form-input" 
                  style={{ width: '200px', marginTop: 0 }} 
                  value={selectedAnalyticsChannelId || ''} 
                  onChange={e => {
                    const val = e.target.value ? Number(e.target.value) : null;
                    setSelectedAnalyticsChannelId(val);
                    if (val) fetchAnalytics(val);
                  }}
                >
                  <option value="">-- Choose Channel --</option>
                  {channels.map(c => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
              </div>
            </div>

            {loadingAnalytics ? (
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
                  </div>

                  {/* Cloudflare AI Section */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', borderBottom: '1px solid rgba(255,255,255,0.06)', paddingBottom: '20px' }}>
                    <h4 style={{ fontSize: '0.95rem', color: 'var(--primary)', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px' }}>
                      ☁️ Cloudflare AI Integration
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
                      />
                    </div>
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

                <div className="form-group" style={{ marginBottom: '16px' }}>
                  <label htmlFor="settings-channel-select">Select Target Channel</label>
                  <select
                    id="settings-channel-select"
                    className="form-input"
                    value={selectedSettingsChannelId}
                    onChange={e => setSelectedSettingsChannelId(e.target.value ? parseInt(e.target.value) : '')}
                  >
                    <option value="">-- Choose a Channel --</option>
                    {channels.map(c => (
                      <option key={c.id} value={c.id}>{c.name}</option>
                    ))}
                  </select>
                </div>

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

                    {/* Channel OAuth Credentials Form */}
                    <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: '16px' }}>
                      <h4 style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '12px' }}>
                        🔑 Register Channel OAuth Refresh Token
                      </h4>
                      <form onSubmit={handleSaveOAuthToken} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
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

                        <div className="form-group">
                          <label htmlFor="oauth-refresh-token">OAuth Refresh Token</label>
                          <input
                            id="oauth-refresh-token"
                            type="password"
                            className="form-input"
                            value={oauthRefreshToken}
                            onChange={e => setOauthRefreshToken(e.target.value)}
                            placeholder="Enter Google OAuth refresh token..."
                            required
                          />
                        </div>

                        <button type="submit" className="btn btn-primary" style={{ alignSelf: 'flex-start', marginTop: '4px' }}>
                          💾 Save Channel Credentials
                        </button>
                      </form>
                    </div>

                  </div>
                ) : (
                  <div style={{ padding: '40px 20px', textAlign: 'center', border: '1px dashed var(--border-color)', borderRadius: '8px', color: 'var(--text-muted)' }}>
                    Select a channel above to configure its GCP Projects and OAuth credentials.
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
                {thumbnailDrafts.length === 0 ? (
                  <div style={{ padding: '20px', textAlign: 'center', background: 'rgba(0,0,0,0.1)', borderRadius: '8px' }}>
                    Generating / loading thumbnail styles...
                  </div>
                ) : (
                  <div className="thumbnail-select-grid">
                    {thumbnailDrafts.map(thumb => (
                      <div 
                        key={thumb.id}
                        className={`thumbnail-option ${thumb.is_selected ? 'selected' : ''}`}
                        onClick={() => handleSelectThumbnail(thumb.id)}
                        style={{ height: '200px' }}
                      >
                        <div style={{ width: '100%', height: '140px', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'linear-gradient(135deg, #312e81, #4f46e5)', position: 'relative', overflow: 'hidden' }}>
                          <img 
                            src={`${API_URL}/videos/thumbnails/${thumb.id}/image`} 
                            alt={thumb.style_name} 
                            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                            onError={(e) => {
                              e.currentTarget.style.display = 'none';
                              const parent = e.currentTarget.parentElement;
                              if (parent) {
                                const fallback = document.createElement('span');
                                fallback.style.fontSize = '2.5rem';
                                fallback.innerText = '🖼️';
                                parent.appendChild(fallback);
                              }
                            }}
                          />
                        </div>
                        <div className="thumbnail-label" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 12px' }}>
                          <span>{thumb.style_name}</span>
                          <button 
                            type="button"
                            className="btn btn-secondary" 
                            style={{ padding: '2px 6px', fontSize: '0.7rem' }}
                            onClick={(e) => {
                              e.stopPropagation();
                              setPreviewImageUrl(`${API_URL}/videos/thumbnails/${thumb.id}/image`);
                            }}
                          >
                            🔍 Preview
                          </button>
                        </div>
                        {thumb.is_selected && <div className="thumbnail-check">✓</div>}
                      </div>
                    ))}
                  </div>
                )}
              </div>

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
