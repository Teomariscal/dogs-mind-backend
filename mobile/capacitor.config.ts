import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'net.thedogsmind.app',
  appName: 'The Dogs Mind',
  webDir: '../frontend',
  ios: {
    contentInset: 'always',
    backgroundColor: '#ffffff',
    scrollEnabled: true,
    limitsNavigationsToAppBoundDomains: true,
  },
  server: {
    iosScheme: 'https',
  },
};

export default config;
