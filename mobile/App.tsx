import React, { useState } from 'react';
import { Text } from 'react-native';
import { NavigationContainer } from '@react-navigation/native';
import { createStackNavigator } from '@react-navigation/stack';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { LoginScreen } from './src/screens/LoginScreen';
import { ChatScreen } from './src/screens/ChatScreen';
import { SessionsScreen } from './src/screens/SessionsScreen';
import { SettingsScreen } from './src/screens/SettingsScreen';
import { SplashScreen } from './src/screens/SplashScreen';

const Stack = createStackNavigator();
const Tab = createBottomTabNavigator();

const headerStyle = {
  headerStyle: { backgroundColor: '#1a1040' },
  headerTintColor: '#e2d9f3',
  headerTitleStyle: { fontWeight: '700' as const, letterSpacing: 0.5 },
  cardStyle: { backgroundColor: '#0f0c29' },
};

function TabIcon({ icon, color, size }: { icon: string; color: string; size: number }) {
  return <Text style={{ fontSize: size * 0.85, color }}>{icon}</Text>;
}

function MainTabs() {
  return (
    <Tab.Navigator
      screenOptions={{
        headerStyle: { backgroundColor: '#1a1040' },
        headerTintColor: '#e2d9f3',
        headerTitleStyle: { fontWeight: '700', letterSpacing: 0.5 },
        tabBarStyle: {
          backgroundColor: '#120d2e',
          borderTopColor: 'rgba(255,255,255,0.08)',
          paddingBottom: 4,
          height: 58,
        },
        tabBarActiveTintColor: '#a78bfa',
        tabBarInactiveTintColor: '#3a3a5a',
      }}
    >
      <Tab.Screen
        name="Chat"
        component={ChatScreen}
        options={{
          title: '⚡ Zeus',
          tabBarLabel: 'Chat',
          tabBarIcon: ({ color, size }) => <TabIcon icon="⚡" color={color} size={size} />,
        }}
      />
      <Tab.Screen
        name="History"
        component={SessionsScreen}
        options={{
          title: 'History',
          tabBarLabel: 'History',
          tabBarIcon: ({ color, size }) => <TabIcon icon="📋" color={color} size={size} />,
        }}
      />
      <Tab.Screen
        name="Settings"
        component={SettingsScreen}
        options={{
          title: 'Settings',
          tabBarLabel: 'Settings',
          tabBarIcon: ({ color, size }) => <TabIcon icon="⚙️" color={color} size={size} />,
        }}
      />
    </Tab.Navigator>
  );
}

export default function App() {
  const [splashDone, setSplashDone] = useState(false);

  if (!splashDone) {
    return (
      <GestureHandlerRootView style={{ flex: 1 }}>
        <SplashScreen onDone={() => setSplashDone(true)} />
      </GestureHandlerRootView>
    );
  }

  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <NavigationContainer>
        <Stack.Navigator screenOptions={headerStyle} initialRouteName="Login">
          <Stack.Screen
            name="Login"
            component={LoginScreen}
            options={{ headerShown: false }}
          />
          <Stack.Screen
            name="Main"
            component={MainTabs}
            options={{ headerShown: false }}
          />
        </Stack.Navigator>
      </NavigationContainer>
    </GestureHandlerRootView>
  );
}
