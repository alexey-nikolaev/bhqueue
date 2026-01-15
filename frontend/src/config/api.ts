/**
 * API configuration
 */

import { Platform } from 'react-native';

// Use localhost for development
// Will be replaced with production URL later
// ngrok tunnel URL for development (update when ngrok restarts)
const NGROK_URL = 'https://unswabbed-unrespectfully-sherell.ngrok-free.dev';

const getBaseUrl = () => {
  if (!__DEV__) {
    return 'https://bhqueue-api.herokuapp.com';
  }
  
  // In development
  if (Platform.OS === 'web') {
    return 'http://localhost:8000';
  }
  
  // For physical devices and simulators, use ngrok tunnel
  return NGROK_URL;
};

export const API_BASE_URL = getBaseUrl();

export const API_ENDPOINTS = {
  // Auth
  register: '/api/auth/register',
  login: '/api/auth/login',
  me: '/api/auth/me',
  logout: '/api/auth/logout',
  
  // Clubs
  berghainStatus: '/api/clubs/berghain/status',
  
  // Queue (to be implemented)
  queueJoin: '/api/queue/join',
  queueCheckin: '/api/queue/checkin',
  queueResult: '/api/queue/result',
  queueStatus: '/api/queue/status',
};
