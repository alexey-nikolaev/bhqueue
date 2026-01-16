/**
 * Color palette for KlubFlow
 * 
 * Dark, industrial Berlin nightlife aesthetic
 * Neon green accent matching the app icon
 */

export const colors = {
  // Core Brand Palette (matching icon)
  deepNight: '#12121A',      // Primary background (from icon)
  neonGreen: '#00E676',      // Main accent - neon green from icon ring
  klubOrange: '#FF8C00',     // Secondary accent - orange from icon K
  cardSlate: '#1E1E28',      // Card/surface background (from icon)
  pureWhite: '#FFFFFF',      // Primary headers, high-importance text
  mutedGrey: '#8E8E93',      // Secondary text, inactive tab icons
  
  // Aliases for easier usage
  background: '#12121A',     // Dark charcoal-blue (from icon)
  surface: '#1E1E28',        // Slightly lighter (from icon)
  surfaceLight: '#2A2A36',
  
  // Brand colors
  accent: '#00E676',         // Neon Green (main accent)
  accentLight: '#69F0AE',
  accentDark: '#00C853',
  
  // Secondary accent (orange)
  secondary: '#FF8C00',      // Klub Orange
  secondaryLight: '#FFA940',
  secondaryDark: '#CC7000',
  
  // Text
  textPrimary: '#FFFFFF',
  textSecondary: '#8E8E93',
  textMuted: '#636366',
  
  // Flow Status Indicators (for Flow Circles)
  flowFluid: '#00E676',      // Neon Green - walk-ins, very short wait
  flowSteady: '#FFD600',     // Vivid Yellow - 15-30 min wait
  flowStalled: '#FF5722',    // Safety Orange - 60+ min, high rejection
  
  // Status colors (general)
  success: '#00E676',        // Neon Green
  warning: '#FFD600',        // Vivid Yellow
  error: '#FF5722',          // Safety Orange
  info: '#2196F3',
  
  // Queue status colors (mapped to flow status)
  queueShort: '#00E676',     // Neon Green - < 15 min
  queueMedium: '#FFD600',    // Vivid Yellow - 15-30 min
  queueLong: '#FF8C00',      // Klub Orange - 30-60 min
  queueVeryLong: '#FF5722',  // Safety Orange - 60+ min
  
  // Club status
  clubOpen: '#00E676',       // Neon Green
  clubClosed: '#636366',
  
  // Borders
  border: '#2A2A36',
  borderLight: '#3A3A46',
  
  // Overlay
  overlay: 'rgba(0, 0, 0, 0.7)',
  
  // For button text on colored backgrounds
  buttonText: '#000000',     // Black text on neon green for max legibility
};

// Helper to get queue color based on wait time
export const getQueueColor = (waitMinutes: number): string => {
  if (waitMinutes < 15) return colors.queueShort;      // Fluid
  if (waitMinutes < 30) return colors.queueMedium;     // Steady
  if (waitMinutes < 60) return colors.queueLong;       // Building
  return colors.queueVeryLong;                          // Stalled
};

// Helper to get flow status label
export const getFlowStatus = (waitMinutes: number): { label: string; color: string } => {
  if (waitMinutes < 15) return { label: 'Fluid', color: colors.flowFluid };
  if (waitMinutes < 30) return { label: 'Steady', color: colors.flowSteady };
  if (waitMinutes < 60) return { label: 'Building', color: colors.klubOrange };
  return { label: 'Stalled', color: colors.flowStalled };
};
