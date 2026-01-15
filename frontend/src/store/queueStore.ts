/**
 * Queue state management using Zustand
 */

import { create } from 'zustand';
import { ClubStatus, getBerghainStatus } from '../services/api';

interface QueueState {
  clubStatus: ClubStatus | null;
  isLoading: boolean;
  error: string | null;
  lastUpdated: Date | null;
  
  // User's queue session
  isInQueue: boolean;
  joinedAt: Date | null;
  
  // Actions
  fetchStatus: () => Promise<void>;
  joinQueue: () => void;
  leaveQueue: () => void;
}

export const useQueueStore = create<QueueState>((set, get) => ({
  clubStatus: null,
  isLoading: false,
  error: null,
  lastUpdated: null,
  isInQueue: false,
  joinedAt: null,

  fetchStatus: async () => {
    set({ isLoading: true, error: null });
    try {
      const status = await getBerghainStatus();
      set({ 
        clubStatus: status, 
        isLoading: false, 
        lastUpdated: new Date() 
      });
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Failed to fetch status';
      set({ error: message, isLoading: false });
    }
  },

  joinQueue: () => {
    set({ isInQueue: true, joinedAt: new Date() });
    // TODO: Call API to register queue join
  },

  leaveQueue: () => {
    set({ isInQueue: false, joinedAt: null });
    // TODO: Call API to register queue leave
  },
}));
