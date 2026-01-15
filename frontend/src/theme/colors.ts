/**
 * Color palette for KlubFlow
 * 
 * Inspired by Berlin nightlife aesthetic:
 * - Dark, moody backgrounds
 * - Concrete grays
 * - Cyan blue accents
 */

export const colors = {
  // Base colors
  background: '#0A0A0A',
  surface: '#141414',
  surfaceLight: '#1E1E1E',
  
  // Brand colors
  brandGray: '#8A8A8A',
  brandCyan: '#00FFFF',
  
  // Text
  textPrimary: '#FFFFFF',
  textSecondary: '#A0A0A0',
  textMuted: '#666666',
  
  // Accent - cyan blue
  accent: '#00FFFF',
  accentLight: '#66FFFF',
  accentDark: '#00CCCC',
  
  // Status colors
  success: '#4CAF50',
  warning: '#FFC107',
  error: '#F44336',
  info: '#2196F3',
  
  // Queue status colors
  queueShort: '#4CAF50',    // < 1 hour - green
  queueMedium: '#FFC107',   // 1-2 hours - yellow
  queueLong: '#FF6B35',     // 2-3 hours - orange
  queueVeryLong: '#F44336', // > 3 hours - red
  
  // Club status
  clubOpen: '#4CAF50',
  clubClosed: '#666666',
  
  // Borders
  border: '#2A2A2A',
  borderLight: '#3A3A3A',
  
  // Overlay
  overlay: 'rgba(0, 0, 0, 0.7)',
};

export const getQueueColor = (waitMinutes: number): string => {
  if (waitMinutes < 60) return colors.queueShort;
  if (waitMinutes < 120) return colors.queueMedium;
  if (waitMinutes < 180) return colors.queueLong;
  return colors.queueVeryLong;
};
