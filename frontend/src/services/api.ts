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
