/**
 * API service for communicating with the backend
 */

import axios, { AxiosError, AxiosInstance } from 'axios';
import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';
import { API_BASE_URL, API_ENDPOINTS } from '../config/api';

// Token storage key
const TOKEN_KEY = 'auth_token';

// Create axios instance
const api: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 10000,
});

// Add auth token to requests
api.interceptors.request.use(async (config) => {
  const token = await getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Token management - use localStorage on web, SecureStore on native
export async function getToken(): Promise<string | null> {
  try {
    if (Platform.OS === 'web') {
      return localStorage.getItem(TOKEN_KEY);
    }
    return await SecureStore.getItemAsync(TOKEN_KEY);
  } catch {
    return null;
  }
}

export async function setToken(token: string): Promise<void> {
  if (Platform.OS === 'web') {
    localStorage.setItem(TOKEN_KEY, token);
  } else {
    await SecureStore.setItemAsync(TOKEN_KEY, token);
  }
}

export async function removeToken(): Promise<void> {
  if (Platform.OS === 'web') {
    localStorage.removeItem(TOKEN_KEY);
  } else {
    await SecureStore.deleteItemAsync(TOKEN_KEY);
  }
}

// Types
export interface User {
  id: string;
  email: string;
  display_name: string | null;
  provider: string;
  is_verified: boolean;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface ClubStatus {
  is_open: boolean;
  event_name: string | null;
  phase: 'closed' | 'queue_open' | 'party_running';
  queue_opens_at?: string;
  starts_at?: string;
  ends_at?: string;
  next_event?: {
    name: string;
    queue_opens_at: string;
    starts_at: string;
    ends_at: string;
  };
}

export interface SpatialMarker {
  id: string;
  queue_id: string | null;
  name: string;
  aliases: string[] | null;
  latitude: number;
  longitude: number;
  distance_from_door_meters: number;
  typical_wait_minutes: number | null;
  display_order: number;
}

export interface QueueType {
  id: string;
  queue_type: string;
  name: string;
  description: string | null;
  display_order: number;
}

export interface QueueSession {
  id: string;
  queue_type: string;
  joined_at: string;
  result: string | null;
  result_at: string | null;
  wait_duration_minutes: number | null;
  position_count: number;
  last_marker: string | null;
}

export interface QueueStatusResponse {
  estimated_wait_minutes: number | null;
  confidence: 'low' | 'medium' | 'high';
  data_points: number;
  last_update: string | null;
  spatial_marker: string | null;
  queue_length: string | null;
  sources: Record<string, number>;
}

export interface ApiError {
  detail: string;
}

// Auth API
export async function register(
  email: string,
  password: string,
  displayName?: string
): Promise<AuthResponse> {
  console.log('Registering user:', email, 'to', API_BASE_URL);
  try {
    const response = await api.post<AuthResponse>(API_ENDPOINTS.register, {
      email,
      password,
      display_name: displayName,
    });
    console.log('Registration successful:', response.data);
    await setToken(response.data.access_token);
    return response.data;
  } catch (error) {
    console.error('Registration failed:', error);
    throw error;
  }
}

export async function login(email: string, password: string): Promise<AuthResponse> {
  console.log('Logging in user:', email, 'to', API_BASE_URL);
  try {
    const response = await api.post<AuthResponse>(API_ENDPOINTS.login, {
      email,
      password,
    });
    console.log('Login successful:', response.data);
    await setToken(response.data.access_token);
    return response.data;
  } catch (error) {
    console.error('Login failed:', error);
    throw error;
  }
}

export async function logout(): Promise<void> {
  try {
    await api.post(API_ENDPOINTS.logout);
  } finally {
    await removeToken();
  }
}

export async function getCurrentUser(): Promise<User> {
  const response = await api.get<User>(API_ENDPOINTS.me);
  return response.data;
}

// Club API
export async function getBerghainStatus(): Promise<ClubStatus> {
  const response = await api.get<ClubStatus>(API_ENDPOINTS.berghainStatus);
  return response.data;
}

export async function getClubMarkers(slug: string = 'berghain'): Promise<SpatialMarker[]> {
  const response = await api.get<SpatialMarker[]>(API_ENDPOINTS.clubMarkers(slug));
  return response.data;
}

export async function getClubQueues(slug: string = 'berghain'): Promise<QueueType[]> {
  const response = await api.get<QueueType[]>(API_ENDPOINTS.clubQueues(slug));
  return response.data;
}

// Queue API - User Session
export async function joinQueue(
  clubSlug: string = 'berghain',
  queueType: string = 'main',
  latitude?: number,
  longitude?: number
): Promise<QueueSession> {
  const response = await api.post<QueueSession>(API_ENDPOINTS.queueJoin, {
    club_slug: clubSlug,
    queue_type: queueType,
    latitude,
    longitude,
  });
  return response.data;
}

export async function getQueueSession(): Promise<QueueSession | null> {
  try {
    const response = await api.get<QueueSession | null>(API_ENDPOINTS.queueSession);
    return response.data;
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 404) {
      return null;
    }
    throw error;
  }
}

export async function submitPosition(
  latitude: number,
  longitude: number,
  accuracyMeters?: number
): Promise<void> {
  await api.post(API_ENDPOINTS.queuePosition, {
    latitude,
    longitude,
    accuracy_meters: accuracyMeters,
    recorded_at: new Date().toISOString(),
  });
}

export async function submitCheckpoint(markerId: string): Promise<{
  success: boolean;
  message: string;
  estimated_wait_minutes: number | null;
}> {
  const response = await api.post(API_ENDPOINTS.queueCheckpoint, {
    marker_id: markerId,
  });
  return response.data;
}

export async function submitResult(result: 'admitted' | 'rejected'): Promise<QueueSession> {
  const response = await api.post<QueueSession>(API_ENDPOINTS.queueResult, {
    result,
  });
  return response.data;
}

export async function leaveQueue(): Promise<void> {
  await api.post(API_ENDPOINTS.queueLeave);
}

export async function getQueueStatus(clubSlug: string = 'berghain'): Promise<QueueStatusResponse> {
  const response = await api.get<QueueStatusResponse>(API_ENDPOINTS.queueStatus, {
    params: { club_slug: clubSlug },
  });
  return response.data;
}

// Error handling helper
export function getErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<ApiError>;
    if (axiosError.response?.data?.detail) {
      return axiosError.response.data.detail;
    }
    if (axiosError.message) {
      return axiosError.message;
    }
  }
  return 'An unexpected error occurred';
}

export default api;
