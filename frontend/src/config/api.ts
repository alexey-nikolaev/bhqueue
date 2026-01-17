/**
 * API configuration
 */

import { Platform } from 'react-native';

// =============================================================================
// DEVELOPMENT MODE - Set to 'local' for simulators, 'tunnel' for physical devices
// =============================================================================
const DEV_MODE: 'local' | 'tunnel' = 'tunnel';

// ngrok tunnel URL - UPDATE THIS when you start ngrok
const NGROK_URL = 'https://unswabbed-unrespectfully-sherell.ngrok-free.dev';

const getBaseUrl = () => {
  if (!__DEV__) {
    return 'https://klubflow-api.herokuapp.com';
  }
  
  // Development mode
  if (DEV_MODE === 'tunnel') {
    return NGROK_URL;
  }
  
  // Local development
  if (Platform.OS === 'web') {
    return 'http://localhost:8000';
  }
  
  // iOS Simulator
  if (Platform.OS === 'ios') {
    return 'http://127.0.0.1:8000';
  }
  
  // Android Emulator uses special IP
  if (Platform.OS === 'android') {
    return 'http://10.0.2.2:8000';
  }
  
  return 'http://127.0.0.1:8000';
};

export const API_BASE_URL = getBaseUrl();

export const API_ENDPOINTS = {
  // Auth
  register: '/api/auth/register',
  login: '/api/auth/login',
  me: '/api/auth/me',
  logout: '/api/auth/logout',
  
  // Clubs
  clubs: '/api/clubs',
  clubStatus: (slug: string) => `/api/clubs/${slug}/status`,
  clubQueues: (slug: string) => `/api/clubs/${slug}/queues`,
  clubMarkers: (slug: string) => `/api/clubs/${slug}/markers`,
  
  // Legacy (for backwards compatibility)
  berghainStatus: '/api/clubs/berghain/status',
  
  // Queue - User session
  queueJoin: '/api/queue/join',
  queueSession: '/api/queue/session',
  queuePosition: '/api/queue/position',
  queueCheckpoint: '/api/queue/checkpoint',
  queueResult: '/api/queue/result',
  queueLeave: '/api/queue/leave',
  queueStatus: '/api/queue/status',
};
