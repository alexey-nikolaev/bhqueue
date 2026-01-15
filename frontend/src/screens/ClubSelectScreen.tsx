/**
 * Club Selection Screen
 * Shows KlubFlow branding and allows users to select a club
 */

import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  SafeAreaView,
} from 'react-native';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { colors, typography, spacing, borderRadius } from '../theme';
import { useAuthStore } from '../store/authStore';

type Props = {
  navigation: NativeStackNavigationProp<any>;
};

// Club data - will come from API later
const CLUBS = [
  {
    id: 'berghain',
    name: 'Berghain',
    location: 'Friedrichshain',
    description: 'Techno temple',
    isActive: true,
  },
  {
    id: 'tresor',
    name: 'Tresor',
    location: 'Mitte',
    description: 'Underground institution',
    isActive: false,
  },
  {
    id: 'about-blank',
    name: '://about blank',
    location: 'Friedrichshain',
    description: 'Garden paradise',
    isActive: false,
  },
  {
    id: 'sisyphos',
    name: 'Sisyphos',
    location: 'Lichtenberg',
    description: 'Weekend marathon',
    isActive: false,
  },
];

export default function ClubSelectScreen({ navigation }: Props) {
  const { logout } = useAuthStore();

  const handleClubSelect = (clubId: string) => {
    if (clubId === 'berghain') {
      navigation.navigate('ClubDetail', { clubId });
    }
  };

  const handleBack = async () => {
    await logout();
  };

  return (
    <SafeAreaView style={styles.container}>
      {/* Back button */}
      <TouchableOpacity style={styles.backButton} onPress={handleBack}>
        <Text style={styles.backButtonText}>← Sign out</Text>
      </TouchableOpacity>

      <ScrollView contentContainerStyle={styles.content}>
        {/* Logo & Branding */}
        <View style={styles.header}>
          <Text style={styles.appName}>KlubFlow</Text>
          <Text style={styles.tagline}>Keep the night moving</Text>
        </View>

        {/* Club Selection */}
        <View style={styles.clubsSection}>
          <Text style={styles.sectionTitle}>Select a club</Text>
          
          {CLUBS.map((club) => (
            <TouchableOpacity
              key={club.id}
              style={[
                styles.clubCard,
                !club.isActive && styles.clubCardDisabled,
              ]}
              onPress={() => handleClubSelect(club.id)}
              disabled={!club.isActive}
            >
              <View style={styles.clubInfo}>
                <Text style={[
                  styles.clubName,
                  !club.isActive && styles.clubNameDisabled,
                ]}>
                  {club.name}
                </Text>
                <Text style={styles.clubLocation}>{club.location}</Text>
                <Text style={styles.clubDescription}>{club.description}</Text>
              </View>
              <View style={styles.clubStatus}>
                {club.isActive ? (
                  <View style={styles.activeBadge}>
                    <Text style={styles.activeBadgeText}>Live</Text>
                  </View>
                ) : (
                  <Text style={styles.comingSoonText}>Coming soon</Text>
                )}
              </View>
            </TouchableOpacity>
          ))}
        </View>

        {/* Footer */}
        <View style={styles.footer}>
          <Text style={styles.footerText}>
            More clubs coming soon
          </Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
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
  content: {
    padding: spacing.lg,
    paddingTop: spacing.md,
  },
  header: {
    alignItems: 'center',
    marginBottom: spacing.xxl,
  },
  appName: {
    fontSize: 36,
    fontWeight: '700',
    color: colors.textPrimary,
    letterSpacing: 1,
  },
  tagline: {
    ...typography.body,
    color: colors.accent,
    fontStyle: 'italic',
    marginTop: spacing.xs,
  },
  clubsSection: {
    marginBottom: spacing.xl,
  },
  sectionTitle: {
    ...typography.label,
    color: colors.textMuted,
    marginBottom: spacing.lg,
  },
  clubCard: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
    marginBottom: spacing.md,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: colors.border,
  },
  clubCardDisabled: {
    opacity: 0.5,
  },
  clubInfo: {
    flex: 1,
  },
  clubName: {
    ...typography.h3,
    color: colors.textPrimary,
  },
  clubNameDisabled: {
    color: colors.textMuted,
  },
  clubLocation: {
    ...typography.bodySmall,
    color: colors.textSecondary,
    marginTop: 2,
  },
  clubDescription: {
    ...typography.bodySmall,
    color: colors.textMuted,
    marginTop: spacing.xs,
    fontStyle: 'italic',
  },
  clubStatus: {
    marginLeft: spacing.md,
  },
  activeBadge: {
    backgroundColor: colors.accent,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: borderRadius.sm,
  },
  activeBadgeText: {
    ...typography.label,
    color: colors.background,
    fontWeight: '700',
  },
  comingSoonText: {
    ...typography.bodySmall,
    color: colors.textMuted,
  },
  footer: {
    alignItems: 'center',
    paddingVertical: spacing.lg,
  },
  footerText: {
    ...typography.bodySmall,
    color: colors.textMuted,
  },
});
