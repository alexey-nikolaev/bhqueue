/**
 * Home Screen - Main dashboard showing queue status
 */

import React, { useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  RefreshControl,
  ScrollView,
  ActivityIndicator,
  SafeAreaView,
} from 'react-native';
import { useNavigation } from '@react-navigation/native';
import { colors, typography, spacing, borderRadius, getQueueColor } from '../theme';
import { useQueueStore } from '../store/queueStore';
import { useAuthStore } from '../store/authStore';

export default function HomeScreen() {
  const navigation = useNavigation();
  const { clubStatus, isLoading, error, lastUpdated, fetchStatus } = useQueueStore();
  const { user, isAuthenticated } = useAuthStore();

  const handleBack = () => {
    navigation.getParent()?.goBack();
  };

  useEffect(() => {
    fetchStatus();
    // Refresh every 2 minutes
    const interval = setInterval(fetchStatus, 120000);
    return () => clearInterval(interval);
  }, []);

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

      {/* Queue Estimate Card (placeholder for now) */}
      {clubStatus?.is_open && (
        <View style={styles.queueCard}>
          <Text style={styles.queueLabel}>Estimated Wait</Text>
          <View style={styles.queueTimeContainer}>
            <Text style={[styles.queueTime, { color: getQueueColor(90) }]}>--</Text>
            <Text style={styles.queueUnit}>min</Text>
          </View>
          <Text style={styles.queueConfidence}>No data yet</Text>
          <Text style={styles.queueHint}>
            Be the first to report the queue!
          </Text>
        </View>
      )}

      {/* Action Button */}
      {clubStatus?.is_open && (
        <TouchableOpacity style={styles.actionButton}>
          <Text style={styles.actionButtonText}>I'm in the queue</Text>
        </TouchableOpacity>
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
  actionButtonText: {
    ...typography.button,
    color: colors.textPrimary,
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
