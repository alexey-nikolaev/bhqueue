/**
 * Queue state management using Zustand
 * 
 * Handles:
 * - Club status and queue estimates
 * - User's queue session (join, position, checkpoints, result)
 * - Spatial markers for checkpoint UI
 */

import { create } from 'zustand';
import {
  ClubStatus,
  QueueSession,
  QueueStatusResponse,
  SpatialMarker,
  getBerghainStatus,
  getClubMarkers,
  getQueueSession,
  getQueueStatus,
  joinQueue as apiJoinQueue,
  submitPosition as apiSubmitPosition,
  submitCheckpoint as apiSubmitCheckpoint,
  submitResult as apiSubmitResult,
  leaveQueue as apiLeaveQueue,
} from '../services/api';

interface QueueState {
  // Club status
  clubStatus: ClubStatus | null;
  queueStatus: QueueStatusResponse | null;
  markers: SpatialMarker[];
  
  // Loading states
  isLoading: boolean;
  isJoining: boolean;
  isSubmitting: boolean;
  
  // Error handling
  error: string | null;
  lastUpdated: Date | null;
  
  // User's queue session
  session: QueueSession | null;
  currentMarker: SpatialMarker | null;  // Last confirmed marker
  
  // Actions
  fetchStatus: () => Promise<void>;
  fetchMarkers: () => Promise<void>;
  fetchSession: () => Promise<void>;
  
  joinQueue: (queueType?: string, latitude?: number, longitude?: number) => Promise<boolean>;
  submitPosition: (latitude: number, longitude: number, accuracy?: number) => Promise<void>;
  submitCheckpoint: (marker: SpatialMarker) => Promise<{ waitMinutes: number | null }>;
  submitResult: (result: 'admitted' | 'rejected') => Promise<void>;
  leaveQueue: () => Promise<void>;
  
  clearError: () => void;
}

export const useQueueStore = create<QueueState>((set, get) => ({
  // Initial state
  clubStatus: null,
  queueStatus: null,
  markers: [],
  isLoading: false,
  isJoining: false,
  isSubmitting: false,
  error: null,
  lastUpdated: null,
  session: null,
  currentMarker: null,

  // Fetch club and queue status
  fetchStatus: async () => {
    set({ isLoading: true, error: null });
    try {
      const [clubStatus, queueStatus] = await Promise.all([
        getBerghainStatus(),
        getQueueStatus(),
      ]);
      set({ 
        clubStatus,
        queueStatus,
        isLoading: false, 
        lastUpdated: new Date(),
      });
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Failed to fetch status';
      set({ error: message, isLoading: false });
    }
  },

  // Fetch spatial markers
  fetchMarkers: async () => {
    try {
      const markers = await getClubMarkers('berghain');
      // Sort by display_order
      markers.sort((a, b) => a.display_order - b.display_order);
      set({ markers });
    } catch (error: any) {
      console.error('Failed to fetch markers:', error);
    }
  },

  // Fetch user's current session
  fetchSession: async () => {
    try {
      const session = await getQueueSession();
      // Clear error when session is fetched successfully
      set({ session, error: null });
    } catch (error: any) {
      console.error('Failed to fetch session:', error);
    }
  },

  // Join the queue
  joinQueue: async (queueType = 'main', latitude?: number, longitude?: number) => {
    set({ isJoining: true, error: null });
    try {
      const session = await apiJoinQueue('berghain', queueType, latitude, longitude);
      
      // Pre-select the nearest marker if returned
      let currentMarker = null;
      if (session.nearest_marker_id) {
        const { markers } = get();
        currentMarker = markers.find(m => m.id === session.nearest_marker_id) || null;
      }
      
      set({ session, currentMarker, isJoining: false });
      return true;
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Failed to join queue';
      set({ error: message, isJoining: false });
      return false;
    }
  },

  // Submit GPS position
  submitPosition: async (latitude: number, longitude: number, accuracy?: number) => {
    const { session } = get();
    // Don't submit if no session or session already has a result
    if (!session || session.result) return;
    
    try {
      await apiSubmitPosition(latitude, longitude, accuracy);
    } catch (error: any) {
      console.error('Failed to submit position:', error);
    }
  },

  // Submit checkpoint (user confirms passing a marker)
  submitCheckpoint: async (marker: SpatialMarker) => {
    const { session } = get();
    // Don't submit if no session or session already has a result
    if (!session || session.result) return { waitMinutes: null };
    
    set({ isSubmitting: true });
    try {
      const result = await apiSubmitCheckpoint(marker.id);
      set({ 
        currentMarker: marker,
        isSubmitting: false,
      });
      return { waitMinutes: result.estimated_wait_minutes };
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Failed to submit checkpoint';
      set({ error: message, isSubmitting: false });
      return { waitMinutes: null };
    }
  },

  // Submit queue result (admitted or rejected)
  submitResult: async (result: 'admitted' | 'rejected') => {
    set({ isSubmitting: true, error: null });
    try {
      await apiSubmitResult(result);
      // Clear session - it's now complete, stops GPS updates
      set({ 
        session: null,
        isSubmitting: false,
        currentMarker: null,
      });
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Failed to submit result';
      set({ error: message, isSubmitting: false });
    }
  },

  // Leave the queue
  leaveQueue: async () => {
    set({ isSubmitting: true, error: null });
    try {
      await apiLeaveQueue();
      set({ 
        session: null,
        currentMarker: null,
        isSubmitting: false,
      });
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Failed to leave queue';
      set({ error: message, isSubmitting: false });
    }
  },

  clearError: () => set({ error: null }),
}));
