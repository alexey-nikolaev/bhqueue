/**
 * Typography styles for KlubFlow
 */

import { TextStyle } from 'react-native';

export const typography = {
  // Headers
  h1: {
    fontSize: 32,
    fontWeight: '700',
    letterSpacing: -0.5,
  } as TextStyle,
  
  h2: {
    fontSize: 24,
    fontWeight: '600',
    letterSpacing: -0.3,
  } as TextStyle,
  
  h3: {
    fontSize: 20,
    fontWeight: '600',
  } as TextStyle,
  
  // Body
  body: {
    fontSize: 16,
    fontWeight: '400',
    lineHeight: 24,
  } as TextStyle,
  
  bodySmall: {
    fontSize: 14,
    fontWeight: '400',
    lineHeight: 20,
  } as TextStyle,
  
  // Labels
  label: {
    fontSize: 12,
    fontWeight: '500',
    letterSpacing: 0.5,
  } as TextStyle,
  
  // Numbers (for queue times)
  number: {
    fontSize: 48,
    fontWeight: '700',
    letterSpacing: -1,
  } as TextStyle,
  
  numberSmall: {
    fontSize: 32,
    fontWeight: '600',
  } as TextStyle,
  
  // Button
  button: {
    fontSize: 16,
    fontWeight: '600',
    letterSpacing: 0.5,
  } as TextStyle,
};
