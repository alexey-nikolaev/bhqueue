/**
 * Queue Screen - Active queue session UI
 * 
 * Shows:
 * - Current position in queue (last checkpoint)
 * - Estimated wait time
 * - Checkpoint buttons (markers)
 * - Result buttons (admitted/rejected)
 * - Leave queue option
 */

import React, { useEffect, useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  Alert,
  ActivityIndicator,
  RefreshControl,
} from 'react-native';
import * as Location from 'expo-location';
import { useNavigation } from '@react-navigation/native';
import { colors, typography, spacing, borderRadius } from '../theme';
import { useQueueStore } from '../store/queueStore';
import { SpatialMarker } from '../services/api';

export default function QueueScreen() {
  const navigation = useNavigation();
  const {
    session,
    markers,
    currentMarker,
    queueStatus,
    isSubmitting,
    error,
    fetchMarkers,
    fetchStatus,
    submitCheckpoint,
    submitPosition,
    submitResult,
    leaveQueue,
    clearError,
  } = useQueueStore();

  const [locationPermission, setLocationPermission] = useState<boolean>(false);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Request location permission
  useEffect(() => {
    (async () => {
      const { status } = await Location.requestForegroundPermissionsAsync();
      setLocationPermission(status === 'granted');
    })();
  }, []);

  // Fetch markers and status on mount
  useEffect(() => {
    fetchMarkers();
    fetchStatus();
  }, []);

  // Periodic position updates (silent - GPS is optional)
  useEffect(() => {
    if (!locationPermission || !session) return;

    const updatePosition = async () => {
      try {
        const location = await Location.getCurrentPositionAsync({
          accuracy: Location.Accuracy.Balanced,
        });
        // Silent submission - don't show errors for GPS
        submitPosition(
          location.coords.latitude,
          location.coords.longitude,
          location.coords.accuracy ?? undefined
        ).catch(() => {}); // Ignore errors silently
      } catch (e) {
        // GPS not available - that's okay
      }
    };

    // Initial position
    updatePosition();
    
    // Update every 2 minutes
    const interval = setInterval(updatePosition, 120000);

    return () => clearInterval(interval);
  }, [locationPermission, session]);

  // Handle refresh
  const onRefresh = useCallback(async () => {
    setIsRefreshing(true);
    await Promise.all([fetchMarkers(), fetchStatus()]);
    setIsRefreshing(false);
  }, []);

  // Handle checkpoint press
  const handleCheckpoint = async (marker: SpatialMarker) => {
    const { waitMinutes } = await submitCheckpoint(marker);
    if (waitMinutes !== null) {
      Alert.alert(
        'Checkpoint Recorded',
        `You're at ${marker.name}. Estimated wait: ~${waitMinutes} minutes.`,
        [{ text: 'OK' }]
      );
    }
  };

  // Handle result press
  const handleResult = (result: 'admitted' | 'rejected') => {
    const title = result === 'admitted' ? 'You got in!' : 'Rejected';
    const message = result === 'admitted' 
      ? 'Congratulations! Have a great time!'
      : 'Sorry to hear that. Better luck next time!';
    
    Alert.alert(
      title,
      message,
      [
        {
          text: 'Confirm',
          onPress: async () => {
            await submitResult(result);
            navigation.goBack();
          },
        },
        { text: 'Cancel', style: 'cancel' },
      ]
    );
  };

  // Handle leave queue
  const handleLeave = () => {
    Alert.alert(
      'Leave Queue?',
      'Are you sure you want to leave the queue?',
      [
        {
          text: 'Yes, Leave',
          style: 'destructive',
          onPress: async () => {
            await leaveQueue();
            navigation.goBack();
          },
        },
        { text: 'Cancel', style: 'cancel' },
      ]
    );
  };

  // Calculate time in queue
  const getTimeInQueue = () => {
    if (!session?.joined_at) return null;
    const joined = new Date(session.joined_at);
    const now = new Date();
    const minutes = Math.floor((now.getTime() - joined.getTime()) / 60000);
    if (minutes < 60) return `${minutes} min`;
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return `${hours}h ${mins}m`;
  };

  // Get markers for the current session's queue type
  // For MVP, we filter based on marker names (main queue markers don't include GL landmarks)
  const glMarkerNames = ['Barriers', 'Love sculpture', 'Garten door', 'ATM', 'Park'];
  const mainQueueMarkers = session?.queue_type === 'main' 
    ? markers.filter(m => !glMarkerNames.includes(m.name))
    : markers.filter(m => glMarkerNames.includes(m.name));

  if (!session) {
    return (
      <View style={styles.container}>
        <Text style={styles.noSessionText}>No active queue session</Text>
        <TouchableOpacity 
          style={styles.backButton}
          onPress={() => navigation.goBack()}
        >
          <Text style={styles.backButtonText}>Go Back</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <ScrollView 
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl
          refreshing={isRefreshing}
          onRefresh={onRefresh}
          tintColor={colors.accent}
        />
      }
    >
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.title}>In Queue</Text>
        <Text style={styles.timeInQueue}>{getTimeInQueue()}</Text>
      </View>

      {/* Current Position Card */}
      <View style={styles.positionCard}>
        <Text style={styles.positionLabel}>Your Position</Text>
        <Text style={styles.positionValue}>
          {currentMarker?.name || 'Not set yet'}
        </Text>
        {currentMarker?.typical_wait_minutes != null && currentMarker.typical_wait_minutes > 0 && (
          <Text style={styles.estimatedWait}>
            ~{currentMarker.typical_wait_minutes} min estimated
          </Text>
        )}
      </View>

      {/* Queue Status */}
      {queueStatus && queueStatus.estimated_wait_minutes != null && queueStatus.estimated_wait_minutes > 0 && (
        <View style={styles.statusCard}>
          <Text style={styles.statusLabel}>Community Estimate</Text>
          <View style={styles.statusRow}>
            <Text style={styles.statusValue}>
              ~{queueStatus.estimated_wait_minutes} min
            </Text>
            <Text style={styles.confidenceBadge}>
              {queueStatus.confidence} confidence
            </Text>
          </View>
          {queueStatus.spatial_marker && (
            <Text style={styles.statusMarker}>
              Queue to: {queueStatus.spatial_marker}
            </Text>
          )}
        </View>
      )}

      {/* Checkpoint Section */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Where are you?</Text>
        <Text style={styles.sectionSubtitle}>
          Tap when you reach a landmark
        </Text>
        
        <View style={styles.checkpointGrid}>
          {mainQueueMarkers.map((marker, index) => (
            <TouchableOpacity
              key={marker.id}
              style={[
                styles.checkpointButton,
                currentMarker?.id === marker.id && styles.checkpointActive,
                // Make odd items (right column) have no right margin
                index % 2 === 1 && { marginRight: 0 },
              ]}
              onPress={() => handleCheckpoint(marker)}
              disabled={isSubmitting}
            >
              <Text style={[
                styles.checkpointText,
                currentMarker?.id === marker.id && styles.checkpointTextActive,
              ]}>
                {marker.name}
              </Text>
              {marker.typical_wait_minutes !== null && marker.typical_wait_minutes !== undefined && (
                <Text style={[
                  styles.checkpointWait,
                  currentMarker?.id === marker.id && styles.checkpointWaitActive,
                ]}>
                  ~{marker.typical_wait_minutes}m
                </Text>
              )}
            </TouchableOpacity>
          ))}
        </View>
      </View>

      {/* Result Section */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>At the door?</Text>
        
        <View style={styles.resultButtons}>
          <TouchableOpacity
            style={[styles.resultButton, styles.admittedButton]}
            onPress={() => handleResult('admitted')}
            disabled={isSubmitting}
          >
            {isSubmitting ? (
              <ActivityIndicator color={colors.buttonText} />
            ) : (
              <Text style={styles.resultButtonText}>I got in! 🎉</Text>
            )}
          </TouchableOpacity>
          
          <TouchableOpacity
            style={[styles.resultButton, styles.rejectedButton]}
            onPress={() => handleResult('rejected')}
            disabled={isSubmitting}
          >
            <Text style={styles.rejectedButtonText}>Rejected 😔</Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* Leave Queue */}
      <TouchableOpacity
        style={styles.leaveButton}
        onPress={handleLeave}
        disabled={isSubmitting}
      >
        <Text style={styles.leaveButtonText}>Leave Queue</Text>
      </TouchableOpacity>

      {/* Error Display */}
      {error && (
        <TouchableOpacity style={styles.errorBanner} onPress={clearError}>
          <Text style={styles.errorText}>{error}</Text>
          <Text style={styles.errorDismiss}>Tap to dismiss</Text>
        </TouchableOpacity>
      )}

      {/* GPS Status */}
      <View style={styles.gpsStatus}>
        <View style={[
          styles.gpsDot,
          { backgroundColor: locationPermission ? colors.success : colors.error }
        ]} />
        <Text style={styles.gpsText}>
          {locationPermission ? 'GPS tracking active' : 'GPS not available'}
        </Text>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    padding: spacing.lg,
    paddingBottom: spacing.xl * 2,
  },
  header: {
    alignItems: 'center',
    marginBottom: spacing.xl,
  },
  title: {
    ...typography.h1,
    color: colors.textPrimary,
  },
  timeInQueue: {
    ...typography.h3,
    color: colors.accent,
    marginTop: spacing.xs,
  },
  positionCard: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
    alignItems: 'center',
    marginBottom: spacing.lg,
    borderWidth: 2,
    borderColor: colors.accent,
  },
  positionLabel: {
    ...typography.label,
    color: colors.textMuted,
  },
  positionValue: {
    ...typography.h2,
    color: colors.textPrimary,
    marginTop: spacing.sm,
  },
  estimatedWait: {
    ...typography.body,
    color: colors.accent,
    marginTop: spacing.xs,
  },
  statusCard: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
    marginBottom: spacing.lg,
  },
  statusLabel: {
    ...typography.label,
    color: colors.textMuted,
  },
  statusRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: spacing.sm,
  },
  statusValue: {
    ...typography.h3,
    color: colors.textPrimary,
  },
  confidenceBadge: {
    ...typography.bodySmall,
    color: colors.textSecondary,
    backgroundColor: colors.surfaceLight,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderRadius: borderRadius.sm,
  },
  statusMarker: {
    ...typography.body,
    color: colors.textSecondary,
    marginTop: spacing.sm,
  },
  section: {
    marginBottom: spacing.xl,
  },
  sectionTitle: {
    ...typography.h3,
    color: colors.textPrimary,
    marginBottom: spacing.xs,
  },
  sectionSubtitle: {
    ...typography.bodySmall,
    color: colors.textMuted,
    marginBottom: spacing.md,
  },
  checkpointGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
  },
  checkpointButton: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
    width: '48%',
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  checkpointActive: {
    backgroundColor: colors.accent,
    borderColor: colors.accent,
  },
  checkpointText: {
    ...typography.body,
    color: colors.textPrimary,
  },
  checkpointTextActive: {
    color: colors.buttonText,
    fontWeight: '600',
  },
  checkpointWait: {
    ...typography.bodySmall,
    color: colors.textMuted,
    marginTop: spacing.xs,
  },
  checkpointWaitActive: {
    color: colors.buttonText,
    opacity: 0.8,
  },
  resultButtons: {
    gap: spacing.md,
  },
  resultButton: {
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
    alignItems: 'center',
  },
  admittedButton: {
    backgroundColor: colors.success,
  },
  rejectedButton: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.error,
  },
  resultButtonText: {
    ...typography.button,
    color: colors.buttonText,
    fontSize: 18,
  },
  rejectedButtonText: {
    ...typography.button,
    color: colors.error,
    fontSize: 18,
  },
  leaveButton: {
    alignItems: 'center',
    padding: spacing.md,
  },
  leaveButtonText: {
    ...typography.body,
    color: colors.textMuted,
    textDecorationLine: 'underline',
  },
  errorBanner: {
    backgroundColor: colors.error,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    marginTop: spacing.lg,
    alignItems: 'center',
  },
  errorText: {
    ...typography.body,
    color: colors.textPrimary,
  },
  errorDismiss: {
    ...typography.bodySmall,
    color: colors.textPrimary,
    opacity: 0.7,
    marginTop: spacing.xs,
  },
  gpsStatus: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: spacing.lg,
  },
  gpsDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: spacing.sm,
  },
  gpsText: {
    ...typography.bodySmall,
    color: colors.textMuted,
  },
  noSessionText: {
    ...typography.body,
    color: colors.textSecondary,
    textAlign: 'center',
    marginTop: spacing.xl * 2,
  },
  backButton: {
    alignItems: 'center',
    marginTop: spacing.lg,
  },
  backButtonText: {
    ...typography.body,
    color: colors.accent,
  },
});
