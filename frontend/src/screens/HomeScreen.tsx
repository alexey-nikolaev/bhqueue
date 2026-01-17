/**
 * Home Screen - Main dashboard showing queue status
 */

import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  RefreshControl,
  ScrollView,
  ActivityIndicator,
  SafeAreaView,
  Alert,
} from 'react-native';
import { useNavigation } from '@react-navigation/native';
import * as Location from 'expo-location';
import { colors, typography, spacing, borderRadius, getQueueColor, getFlowStatus } from '../theme';
import { useQueueStore } from '../store/queueStore';
import { useAuthStore } from '../store/authStore';

export default function HomeScreen() {
  const navigation = useNavigation<any>();
  const { 
    clubStatus, 
    queueStatus,
    session,
    isLoading, 
    isJoining,
    error, 
    lastUpdated, 
    fetchStatus,
    fetchSession,
    joinQueue,
  } = useQueueStore();
  const { user, isAuthenticated } = useAuthStore();
  const [locationStatus, setLocationStatus] = useState<string>('checking');

  const handleBack = () => {
    navigation.getParent()?.goBack();
  };

  // Check for existing session on mount
  useEffect(() => {
    fetchStatus();
    fetchSession();
    
    // Check location permission
    (async () => {
      const { status } = await Location.getForegroundPermissionsAsync();
      setLocationStatus(status);
    })();
    
    // Refresh every 2 minutes
    const interval = setInterval(fetchStatus, 120000);
    return () => clearInterval(interval);
  }, []);

  // Handle join queue button press
  const handleJoinQueue = async () => {
    // Request location permission if not granted
    if (locationStatus !== 'granted') {
      const { status } = await Location.requestForegroundPermissionsAsync();
      setLocationStatus(status);
      
      if (status !== 'granted') {
        Alert.alert(
          'Location Required',
          'GPS helps track your queue position. You can still join without it.',
          [
            { text: 'Cancel', style: 'cancel' },
            { 
              text: 'Join Anyway', 
              onPress: () => doJoinQueue() 
            },
          ]
        );
        return;
      }
    }
    
    await doJoinQueue();
  };

  const doJoinQueue = async () => {
    let latitude: number | undefined;
    let longitude: number | undefined;
    
    try {
      const location = await Location.getCurrentPositionAsync({
        accuracy: Location.Accuracy.Balanced,
      });
      latitude = location.coords.latitude;
      longitude = location.coords.longitude;
    } catch (e) {
      console.log('Could not get location:', e);
    }
    
    const success = await joinQueue('main', latitude, longitude);
    if (success) {
      navigation.navigate('Queue');
    }
  };

  // Navigate to queue screen if already in queue
  const handleContinueQueue = () => {
    navigation.navigate('Queue');
  };

  const formatTime = (isoString: string) => {
    const date = new Date(isoString);
    return date.toLocaleTimeString('de-DE', { 
      hour: '2-digit', 
      minute: '2-digit',
      timeZone: 'Europe/Berlin'
    });
  };

  const formatDate = (isoString: string) => {
    const date = new Date(isoString);
    return date.toLocaleDateString('de-DE', { 
      weekday: 'short',
      day: 'numeric',
      month: 'short',
      timeZone: 'Europe/Berlin'
    });
  };

  if (isLoading && !clubStatus) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color={colors.accent} />
        <Text style={styles.loadingText}>Loading...</Text>
      </View>
    );
  }

  return (
    <SafeAreaView style={styles.safeArea}>
      {/* Back button */}
      <TouchableOpacity style={styles.backButton} onPress={handleBack}>
        <Text style={styles.backButtonText}>← Back</Text>
      </TouchableOpacity>

      <ScrollView 
        style={styles.container}
        contentContainerStyle={styles.content}
        refreshControl={
          <RefreshControl
            refreshing={isLoading}
            onRefresh={fetchStatus}
            tintColor={colors.accent}
          />
        }
      >
        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.clubName}>Berghain</Text>
          <Text style={styles.subtitle}>Queue Status</Text>
        </View>

      {/* Status Card */}
      <View style={styles.statusCard}>
        {clubStatus?.is_open ? (
          <>
            <View style={styles.statusBadge}>
              <View style={[styles.statusDot, { backgroundColor: colors.clubOpen }]} />
              <Text style={styles.statusText}>Open</Text>
            </View>
            <Text style={styles.eventName}>{clubStatus.event_name}</Text>
            <Text style={styles.phaseText}>
              {clubStatus.phase === 'queue_open' ? 'Queue is forming' : 'Party in progress'}
            </Text>
          </>
        ) : (
          <>
            <View style={styles.statusBadge}>
              <View style={[styles.statusDot, { backgroundColor: colors.clubClosed }]} />
              <Text style={styles.statusText}>Closed</Text>
            </View>
            {clubStatus?.next_event && (
              <View style={styles.nextEventContainer}>
                <Text style={styles.nextEventLabel}>Next Event</Text>
                <Text style={styles.nextEventName}>{clubStatus.next_event.name}</Text>
                <Text style={styles.nextEventTime}>
                  {formatDate(clubStatus.next_event.queue_opens_at)} • Queue opens {formatTime(clubStatus.next_event.queue_opens_at)}
                </Text>
              </View>
            )}
          </>
        )}
      </View>

      {/* Queue Estimate Card */}
      {clubStatus?.is_open && (
        <View style={styles.queueCard}>
          <Text style={styles.queueLabel}>Estimated Wait</Text>
          <View style={styles.queueTimeContainer}>
            {queueStatus?.estimated_wait_minutes ? (
              <>
                <Text style={[styles.queueTime, { color: getQueueColor(queueStatus.estimated_wait_minutes) }]}>
                  {queueStatus.estimated_wait_minutes}
                </Text>
                <Text style={styles.queueUnit}>min</Text>
              </>
            ) : (
              <>
                <Text style={[styles.queueTime, { color: colors.textMuted }]}>--</Text>
                <Text style={styles.queueUnit}>min</Text>
              </>
            )}
          </View>
          {queueStatus?.confidence && queueStatus.estimated_wait_minutes ? (
            <Text style={styles.queueConfidence}>
              {queueStatus.confidence} confidence • {queueStatus.data_points} reports
            </Text>
          ) : (
            <Text style={styles.queueConfidence}>No data yet</Text>
          )}
          {queueStatus?.spatial_marker && (
            <Text style={styles.queueHint}>
              Queue extends to: {queueStatus.spatial_marker}
            </Text>
          )}
          {!queueStatus?.estimated_wait_minutes && (
            <Text style={styles.queueHint}>
              Be the first to report the queue!
            </Text>
          )}
        </View>
      )}

      {/* Action Button */}
      {clubStatus?.is_open && (
        session ? (
          // Already in queue - show continue button
          <TouchableOpacity 
            style={styles.actionButton}
            onPress={handleContinueQueue}
          >
            <Text style={styles.actionButtonText}>Continue session →</Text>
          </TouchableOpacity>
        ) : (
          // Not in queue - show join button
          <TouchableOpacity 
            style={[styles.actionButton, isJoining && styles.actionButtonDisabled]}
            onPress={handleJoinQueue}
            disabled={isJoining}
          >
            {isJoining ? (
              <ActivityIndicator color={colors.buttonText} />
            ) : (
              <Text style={styles.actionButtonText}>I'm in the queue</Text>
            )}
          </TouchableOpacity>
        )
      )}

      {/* Last Updated */}
      {lastUpdated && (
        <Text style={styles.lastUpdated}>
          Last updated: {lastUpdated.toLocaleTimeString('de-DE', { 
            hour: '2-digit', 
            minute: '2-digit' 
          })}
        </Text>
      )}

      {/* Error */}
      {error && (
        <View style={styles.errorContainer}>
          <Text style={styles.errorText}>{error}</Text>
        </View>
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
  backButton: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
  },
  backButtonText: {
    ...typography.body,
    color: colors.accent,
  },
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    padding: spacing.lg,
    paddingTop: spacing.md,
  },
  loadingContainer: {
    flex: 1,
    backgroundColor: colors.background,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    ...typography.body,
    color: colors.textSecondary,
    marginTop: spacing.md,
  },
  header: {
    marginBottom: spacing.xl,
    alignItems: 'center',
  },
  clubName: {
    ...typography.h2,
    color: colors.textPrimary,
    letterSpacing: 4,
  },
  subtitle: {
    ...typography.bodySmall,
    color: colors.textSecondary,
    marginTop: spacing.xs,
  },
  statusCard: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
    marginBottom: spacing.lg,
  },
  statusBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  statusDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    marginRight: spacing.sm,
  },
  statusText: {
    ...typography.label,
    color: colors.textPrimary,
  },
  eventName: {
    ...typography.h2,
    color: colors.textPrimary,
    marginTop: spacing.sm,
  },
  phaseText: {
    ...typography.body,
    color: colors.textSecondary,
    marginTop: spacing.xs,
  },
  nextEventContainer: {
    marginTop: spacing.md,
  },
  nextEventLabel: {
    ...typography.label,
    color: colors.textMuted,
  },
  nextEventName: {
    ...typography.h3,
    color: colors.textPrimary,
    marginTop: spacing.xs,
  },
  nextEventTime: {
    ...typography.body,
    color: colors.textSecondary,
    marginTop: spacing.xs,
  },
  queueCard: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
    alignItems: 'center',
    marginBottom: spacing.lg,
  },
  queueLabel: {
    ...typography.label,
    color: colors.textMuted,
  },
  queueTimeContainer: {
    flexDirection: 'row',
    alignItems: 'baseline',
    marginTop: spacing.sm,
  },
  queueTime: {
    ...typography.number,
    color: colors.accent,
  },
  queueUnit: {
    ...typography.h2,
    color: colors.textSecondary,
    marginLeft: spacing.xs,
  },
  queueConfidence: {
    ...typography.bodySmall,
    color: colors.textMuted,
    marginTop: spacing.sm,
  },
  queueHint: {
    ...typography.bodySmall,
    color: colors.textSecondary,
    marginTop: spacing.md,
    textAlign: 'center',
  },
  actionButton: {
    backgroundColor: colors.accent,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
    alignItems: 'center',
    marginBottom: spacing.lg,
  },
  actionButtonDisabled: {
    opacity: 0.6,
  },
  actionButtonText: {
    ...typography.button,
    color: colors.buttonText,
  },
  lastUpdated: {
    ...typography.bodySmall,
    color: colors.textMuted,
    textAlign: 'center',
  },
  errorContainer: {
    backgroundColor: colors.error,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    marginTop: spacing.md,
  },
  errorText: {
    ...typography.bodySmall,
    color: colors.textPrimary,
    textAlign: 'center',
  },
});
