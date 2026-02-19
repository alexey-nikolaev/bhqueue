/**
 * LocationAcquisition - Modal component for getting accurate GPS position
 * 
 * Shows a spinner while acquiring GPS, displays current accuracy,
 * and waits until accuracy is good enough for queue tracking.
 */

import React, { useEffect, useState, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Modal,
  ActivityIndicator,
  TouchableOpacity,
  Linking,
  Platform,
} from 'react-native';
import * as Location from 'expo-location';
import { colors, spacing, borderRadius } from '../theme';

// Berghain coordinates (center of queue area)
const BERGHAIN_LAT = 52.5107;
const BERGHAIN_LNG = 13.4430;
const MAX_DISTANCE_METERS = 500; // Must be within 500m of Berghain

// =============================================================================
// TESTING: Set to true to skip Berghain distance validation
// =============================================================================
const SKIP_LOCATION_VALIDATION = true;
const MIN_SPINNER_TIME = 3000; // Show spinner for at least 3 seconds (for testing UX)

// Accuracy thresholds
const TARGET_ACCURACY = 15; // meters - ideal for landmark assignment
const ACCEPTABLE_ACCURACY = 30; // meters - minimum acceptable
const MAX_WAIT_TIME = 30000; // 30 seconds max

interface LocationResult {
  latitude: number;
  longitude: number;
  accuracy: number;
}

interface Props {
  visible: boolean;
  onLocationAcquired: (location: LocationResult) => void;
  onCancel: () => void;
  onError: (error: string) => void;
}

// Calculate distance between two points using Haversine formula
function getDistanceMeters(
  lat1: number,
  lon1: number,
  lat2: number,
  lon2: number
): number {
  const R = 6371000; // Earth radius in meters
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) *
      Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

export default function LocationAcquisition({
  visible,
  onLocationAcquired,
  onCancel,
  onError,
}: Props) {
  const [status, setStatus] = useState<'acquiring' | 'validating' | 'success' | 'error'>('acquiring');
  const [currentAccuracy, setCurrentAccuracy] = useState<number | null>(null);
  const [message, setMessage] = useState('Finding your location...');
  const [bestLocation, setBestLocation] = useState<LocationResult | null>(null);
  const watchRef = useRef<Location.LocationSubscription | null>(null);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);
  const startTimeRef = useRef<number>(0);

  useEffect(() => {
    console.log('LocationAcquisition: visible changed to', visible);
    if (visible) {
      console.log('LocationAcquisition: Starting acquisition...');
      startLocationAcquisition();
    } else {
      cleanup();
    }

    return () => cleanup();
  }, [visible]);

  const cleanup = () => {
    if (watchRef.current) {
      watchRef.current.remove();
      watchRef.current = null;
    }
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
  };

  // Open device settings for the app
  const openSettings = () => {
    if (Platform.OS === 'ios') {
      Linking.openURL('app-settings:');
    } else {
      Linking.openSettings();
    }
  };

  const startLocationAcquisition = async () => {
    setStatus('acquiring');
    setCurrentAccuracy(null);
    setBestLocation(null);
    setMessage('Finding your location...');
    startTimeRef.current = Date.now();

    try {
      // First check current permission status
      const { status: currentStatus } = await Location.getForegroundPermissionsAsync();
      
      if (currentStatus === 'denied') {
        // Permission was previously denied - need to go to Settings
        setStatus('error');
        setMessage('Location access is off.\nEnable it in Settings to join.');
        return;
      }
      
      // Request permission (will prompt if 'undetermined', or return current status)
      const { status: permStatus } = await Location.requestForegroundPermissionsAsync();
      if (permStatus !== 'granted') {
        setStatus('error');
        setMessage('Location permission is required to join the queue.');
        return;
      }

      // Start watching position with high accuracy
      watchRef.current = await Location.watchPositionAsync(
        {
          accuracy: Location.Accuracy.BestForNavigation,
          timeInterval: 1000, // Update every second
          distanceInterval: 0, // Update even if not moving
        },
        (location) => {
          const accuracy = location.coords.accuracy || 999;
          setCurrentAccuracy(Math.round(accuracy));

          const newLocation: LocationResult = {
            latitude: location.coords.latitude,
            longitude: location.coords.longitude,
            accuracy: accuracy,
          };

          // Keep track of best location so far
          if (!bestLocation || accuracy < bestLocation.accuracy) {
            setBestLocation(newLocation);
          }

          // Update message based on accuracy
          if (accuracy > 50) {
            setMessage('Waiting for GPS satellites...');
          } else if (accuracy > TARGET_ACCURACY) {
            setMessage('Improving accuracy...');
          } else {
            setMessage('Got accurate position!');
          }

          // Check if we've reached target accuracy
          // Also ensure minimum spinner time for better UX
          const elapsedTime = Date.now() - startTimeRef.current;
          if (accuracy <= TARGET_ACCURACY && elapsedTime >= MIN_SPINNER_TIME) {
            finishWithLocation(newLocation);
          } else if (accuracy <= TARGET_ACCURACY) {
            // Good accuracy but need to wait for minimum spinner time
            setMessage('Got accurate position! Finishing...');
            const remainingTime = MIN_SPINNER_TIME - elapsedTime;
            setTimeout(() => {
              finishWithLocation(newLocation);
            }, remainingTime);
          }
        }
      );

      // Set timeout - use best available location after MAX_WAIT_TIME
      timeoutRef.current = setTimeout(() => {
        const best = bestLocation;
        if (best && best.accuracy <= ACCEPTABLE_ACCURACY) {
          finishWithLocation(best);
        } else if (best) {
          // Location exists but not accurate enough
          setStatus('error');
          setMessage(`GPS accuracy is ${Math.round(best.accuracy)}m - too imprecise for queue tracking.`);
          onError('GPS accuracy insufficient. Please try again in an open area.');
        } else {
          setStatus('error');
          setMessage('Could not get GPS position');
          onError('Could not determine your location. Please check GPS settings.');
        }
      }, MAX_WAIT_TIME);

    } catch (error) {
      console.error('Location error:', error);
      setStatus('error');
      onError('Failed to access GPS');
    }
  };

  const finishWithLocation = (location: LocationResult) => {
    cleanup();
    setStatus('validating');
    setMessage('Checking if you\'re at Berghain...');

    // Validate distance to Berghain (skip in testing mode)
    const distance = getDistanceMeters(
      location.latitude,
      location.longitude,
      BERGHAIN_LAT,
      BERGHAIN_LNG
    );

    if (!SKIP_LOCATION_VALIDATION && distance > MAX_DISTANCE_METERS) {
      setStatus('error');
      setMessage(`You appear to be ${Math.round(distance)}m from Berghain.`);
      onError(`You need to be at Berghain to join the queue (detected ${Math.round(distance)}m away).`);
      return;
    }

    // Success! Store location and wait for user to confirm
    setStatus('success');
    if (SKIP_LOCATION_VALIDATION && distance > MAX_DISTANCE_METERS) {
      setMessage(`GPS accuracy: ±${Math.round(location.accuracy)}m\nDistance from Berghain: ${Math.round(distance)}m\n\n(Validation skipped for testing)`);
    } else {
      setMessage(`GPS accuracy: ±${Math.round(location.accuracy)}m\nYou're ${Math.round(distance)}m from Berghain.`);
    }
    
    // Store the location for when user taps Continue
    setBestLocation(location);
  };

  // Called when user taps Continue on success
  const handleContinue = () => {
    if (bestLocation) {
      onLocationAcquired(bestLocation);
    }
  };

  const getAccuracyColor = () => {
    if (!currentAccuracy) return colors.textMuted;
    if (currentAccuracy <= TARGET_ACCURACY) return colors.success;
    if (currentAccuracy <= ACCEPTABLE_ACCURACY) return colors.warning;
    return colors.error;
  };

  const getProgressPercentage = () => {
    if (!currentAccuracy) return 0;
    if (currentAccuracy <= TARGET_ACCURACY) return 100;
    // Map 100m -> 0%, 15m -> 100%
    const progress = Math.max(0, Math.min(100, ((100 - currentAccuracy) / (100 - TARGET_ACCURACY)) * 100));
    return Math.round(progress);
  };

  return (
    <Modal
      visible={visible}
      transparent
      animationType="fade"
      onRequestClose={onCancel}
    >
      <View style={styles.overlay}>
        <View style={styles.container}>
          {/* Header */}
          <Text style={styles.title}>
            {status === 'acquiring' && '📡 Getting GPS Position'}
            {status === 'validating' && '📍 Validating Location'}
            {status === 'success' && '✓ Location Confirmed'}
            {status === 'error' && '⚠️ Location Error'}
          </Text>

          {/* Spinner */}
          {(status === 'acquiring' || status === 'validating') && (
            <View style={styles.spinnerContainer}>
              <ActivityIndicator size="large" color={colors.accent} />
            </View>
          )}

          {/* Accuracy display */}
          {status === 'acquiring' && currentAccuracy && (
            <View style={styles.accuracyContainer}>
              <Text style={styles.accuracyLabel}>Current accuracy:</Text>
              <Text style={[styles.accuracyValue, { color: getAccuracyColor() }]}>
                ±{currentAccuracy}m
              </Text>
              <View style={styles.progressBar}>
                <View 
                  style={[
                    styles.progressFill, 
                    { 
                      width: `${getProgressPercentage()}%`,
                      backgroundColor: getAccuracyColor(),
                    }
                  ]} 
                />
              </View>
              <Text style={styles.targetText}>
                Target: ±{TARGET_ACCURACY}m for accurate queue position
              </Text>
            </View>
          )}

          {/* Status message */}
          <Text style={styles.message}>{message}</Text>

          {/* Buttons */}
          <View style={styles.buttonContainer}>
            {status === 'success' && (
              <TouchableOpacity
                style={styles.continueButton}
                onPress={handleContinue}
              >
                <Text style={styles.continueButtonText}>Continue</Text>
              </TouchableOpacity>
            )}
            
            {status === 'error' && message.includes('Settings') && (
              <TouchableOpacity
                style={styles.settingsButton}
                onPress={openSettings}
              >
                <Text style={styles.settingsButtonText}>Open Settings</Text>
              </TouchableOpacity>
            )}
            
            {status === 'error' && !message.includes('Settings') && (
              <TouchableOpacity
                style={styles.retryButton}
                onPress={startLocationAcquisition}
              >
                <Text style={styles.retryButtonText}>Try Again</Text>
              </TouchableOpacity>
            )}
            
            <TouchableOpacity
              style={styles.cancelButton}
              onPress={onCancel}
            >
              <Text style={styles.cancelButtonText}>Cancel</Text>
            </TouchableOpacity>
          </View>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.8)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: spacing.lg,
  },
  container: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.lg,
    padding: spacing.xl,
    width: '100%',
    maxWidth: 340,
    alignItems: 'center',
  },
  title: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.textPrimary,
    marginBottom: spacing.lg,
    textAlign: 'center',
  },
  spinnerContainer: {
    marginVertical: spacing.lg,
  },
  accuracyContainer: {
    width: '100%',
    alignItems: 'center',
    marginVertical: spacing.md,
  },
  accuracyLabel: {
    fontSize: 14,
    color: colors.textSecondary,
    marginBottom: spacing.xs,
  },
  accuracyValue: {
    fontSize: 36,
    fontWeight: '700',
    marginBottom: spacing.sm,
  },
  progressBar: {
    width: '100%',
    height: 8,
    backgroundColor: colors.border,
    borderRadius: 4,
    overflow: 'hidden',
    marginBottom: spacing.sm,
  },
  progressFill: {
    height: '100%',
    borderRadius: 4,
  },
  targetText: {
    fontSize: 12,
    color: colors.textMuted,
    textAlign: 'center',
  },
  message: {
    fontSize: 16,
    color: colors.textSecondary,
    textAlign: 'center',
    marginVertical: spacing.md,
    lineHeight: 22,
  },
  buttonContainer: {
    flexDirection: 'row',
    gap: spacing.md,
    marginTop: spacing.md,
  },
  continueButton: {
    backgroundColor: colors.accent,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.xl,
    borderRadius: borderRadius.md,
  },
  continueButtonText: {
    color: colors.buttonText,
    fontSize: 16,
    fontWeight: '600',
  },
  retryButton: {
    backgroundColor: colors.accent,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.lg,
    borderRadius: borderRadius.md,
  },
  retryButtonText: {
    color: colors.buttonText,
    fontSize: 16,
    fontWeight: '600',
  },
  settingsButton: {
    backgroundColor: colors.accent,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.lg,
    borderRadius: borderRadius.md,
  },
  settingsButtonText: {
    color: colors.buttonText,
    fontSize: 16,
    fontWeight: '600',
  },
  cancelButton: {
    backgroundColor: colors.border,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.lg,
    borderRadius: borderRadius.md,
  },
  cancelButtonText: {
    color: colors.textSecondary,
    fontSize: 16,
    fontWeight: '500',
  },
});
