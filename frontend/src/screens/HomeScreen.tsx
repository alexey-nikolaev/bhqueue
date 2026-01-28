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
import { colors, typography, spacing, borderRadius } from '../theme';
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

  // Handle join queue button press - show queue type selection
  const handleJoinQueue = () => {
    Alert.alert(
      'Select Queue Type',
      'Which queue are you joining?',
      [
        {
          text: 'Main Queue',
          onPress: () => checkLocationAndJoin('main'),
        },
        {
          text: 'Guestlist',
          onPress: () => checkLocationAndJoin('guest_list'),
        },
        {
          text: 'Re-entry',
          onPress: () => checkLocationAndJoin('reentry'),
        },
        { text: 'Cancel', style: 'cancel' },
      ]
    );
  };

  // Check location permission and join queue
  const checkLocationAndJoin = async (queueType: 'main' | 'guest_list' | 'reentry') => {
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
              onPress: () => doJoinQueue(queueType) 
            },
          ]
        );
        return;
      }
    }
    
    await doJoinQueue(queueType);
  };

  const doJoinQueue = async (queueType: 'main' | 'guest_list' | 'reentry') => {
    // Fetch markers first so we can pre-select after join
    await useQueueStore.getState().fetchMarkers();
    
    let latitude: number | undefined;
    let longitude: number | undefined;
    
    // ==========================================================================
    // TESTING: Use coordinates near a landmark for testing
    // Set TESTING_MODE to false for production
    // ==========================================================================
    const TESTING_MODE = true;
    
    if (TESTING_MODE) {
      if (queueType === 'main') {
        // Coordinates near Metro sign (main queue): lat=52.5085, lng=13.4395
        latitude = 52.5086;
        longitude = 13.4396;
      } else {
        // Coordinates near ATM (GL/reentry landmark): lat=52.5112, lng=13.4442
        latitude = 52.5113;
        longitude = 13.4443;
      }
    } else {
      try {
        const location = await Location.getCurrentPositionAsync({
          accuracy: Location.Accuracy.Balanced,
        });
        latitude = location.coords.latitude;
        longitude = location.coords.longitude;
      } catch (e) {
        console.log('Could not get location:', e);
      }
    }
    
    const success = await joinQueue(queueType, latitude, longitude);
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
        <View style={styles.waitCard}>
          <Text style={styles.waitLabel}>Estimated wait</Text>
          {queueStatus?.estimated_wait_minutes ? (
            <Text style={styles.waitValue}>~{queueStatus.estimated_wait_minutes} min</Text>
          ) : (
            <Text style={[styles.waitValue, { color: colors.textMuted }]}>No data yet</Text>
          )}
          {queueStatus?.spatial_marker && (
            <Text style={styles.waitHint}>
              Queue at: {queueStatus.spatial_marker}
            </Text>
          )}
        </View>
      )}

      {/* Action Button */}
      {clubStatus?.is_open && (
        <TouchableOpacity 
          style={[styles.actionButton, isJoining && styles.actionButtonDisabled]}
          onPress={session ? handleContinueQueue : handleJoinQueue}
          disabled={isJoining}
        >
          {isJoining ? (
            <ActivityIndicator color={colors.buttonText} />
          ) : (
            <Text style={styles.actionButtonText}>I'm in the queue</Text>
          )}
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
    color: colors.accent,
    marginTop: spacing.xs,
  },
  waitHint: {
    ...typography.bodySmall,
    color: colors.textSecondary,
    marginTop: spacing.md,
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
