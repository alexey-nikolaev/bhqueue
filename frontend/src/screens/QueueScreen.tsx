/**
 * Queue Screen - Active queue session UI
 * 
 * Shows:
 * - Estimated wait time based on selected landmark
 * - Checkpoint buttons (landmarks)
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
  RefreshControl,
  SafeAreaView,
} from 'react-native';
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
    isSubmitting,
    error,
    fetchMarkers,
    submitCheckpoint,
    submitResult,
    leaveQueue,
    clearError,
  } = useQueueStore();

  const [isRefreshing, setIsRefreshing] = useState(false);

  // Fetch markers on mount
  useEffect(() => {
    fetchMarkers();
  }, []);

  // Handle refresh
  const onRefresh = useCallback(async () => {
    setIsRefreshing(true);
    await fetchMarkers();
    setIsRefreshing(false);
  }, []);

  // Handle checkpoint press
  const handleCheckpoint = async (marker: SpatialMarker) => {
    await submitCheckpoint(marker);
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

  // Get markers for the current session's queue type
  // Main queue has its own landmarks; GL and Re-entry share the same landmarks
  // Hidden markers are in DB for parsing but not shown in UI
  const glMarkerNames = ['Barriers', 'Love sculpture', 'Garten door', 'ATM', 'Park'];
  const hiddenMarkers = ['Hellweg'];  // For parsing only, not displayed
  const queueMarkers = session?.queue_type === 'main' 
    ? markers.filter(m => !glMarkerNames.includes(m.name) && !hiddenMarkers.includes(m.name))
    : markers.filter(m => glMarkerNames.includes(m.name));

  if (!session) {
    return (
      <SafeAreaView style={styles.safeArea}>
        <View style={styles.container}>
          <Text style={styles.noSessionText}>No active queue session</Text>
          <TouchableOpacity 
            style={styles.backButton}
            onPress={() => navigation.goBack()}
          >
            <Text style={styles.backButtonText}>Go Back</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safeArea}>
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
        <View style={styles.queueTypeBadge}>
          <Text style={styles.queueTypeText}>
            {session.queue_type === 'guest_list' ? 'Guestlist' : 
             session.queue_type === 'reentry' ? 'Re-entry' : 'Main Queue'}
          </Text>
        </View>
      </View>

      {/* Result Section - At the door? */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>At the door?</Text>
        <View style={styles.resultButtonsRow}>
          <TouchableOpacity
            style={[styles.resultButtonSmall, styles.admittedButton]}
            onPress={() => handleResult('admitted')}
          >
            <Text style={styles.resultButtonText}>I got in! 🎉</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.resultButtonSmall, styles.rejectedButton]}
            onPress={() => handleResult('rejected')}
          >
            <Text style={styles.rejectedButtonText}>Rejected 😔</Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* Estimated Wait Card */}
      {currentMarker?.typical_wait_minutes != null && currentMarker.typical_wait_minutes > 0 && (
        <View style={styles.waitCard}>
          <Text style={styles.waitLabel}>Estimated wait</Text>
          <Text style={styles.waitValue}>~{currentMarker.typical_wait_minutes} min</Text>
        </View>
      )}

      {/* Checkpoint Section */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Where are you?</Text>
        
        <View style={styles.checkpointGrid}>
          {queueMarkers.map((marker, index) => (
            <TouchableOpacity
              key={marker.id}
              style={[
                styles.checkpointButton,
                currentMarker?.id === marker.id && styles.checkpointActive,
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
            </TouchableOpacity>
          ))}
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

      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: colors.background,
  },
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    padding: spacing.lg,
    paddingTop: spacing.md,
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
  queueTypeBadge: {
    backgroundColor: colors.secondary,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: borderRadius.full,
    marginTop: spacing.sm,
  },
  queueTypeText: {
    ...typography.bodySmall,
    color: colors.buttonText,
    fontWeight: '600',
  },
  waitCard: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
    alignItems: 'center',
    marginBottom: spacing.lg,
  },
  waitLabel: {
    ...typography.label,
    color: colors.textMuted,
  },
  waitValue: {
    ...typography.h1,
    color: colors.secondary,
    marginTop: spacing.xs,
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
    backgroundColor: colors.surface,
    borderColor: colors.secondary,
    borderWidth: 2,
  },
  checkpointText: {
    ...typography.body,
    color: colors.textPrimary,
  },
  checkpointTextActive: {
    color: colors.secondary,
    fontWeight: '600',
  },
  resultButtonsRow: {
    flexDirection: 'row',
    gap: spacing.md,
  },
  resultButtonSmall: {
    flex: 1,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    alignItems: 'center',
    justifyContent: 'center',
  },
  admittedButton: {
    backgroundColor: colors.accent,
  },
  rejectedButton: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  resultButtonText: {
    ...typography.button,
    color: colors.buttonText,
    fontSize: 16,
  },
  rejectedButtonText: {
    ...typography.button,
    color: colors.textPrimary,
    fontSize: 16,
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
