import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createStackNavigator } from '@react-navigation/stack';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { ChatScreen } from './src/screens/ChatScreen';
import { SessionsScreen } from './src/screens/SessionsScreen';

const Stack = createStackNavigator();

const screenOptions = {
  headerStyle: { backgroundColor: '#1a1040' },
  headerTintColor: '#e2d9f3',
  headerTitleStyle: { fontWeight: '700', letterSpacing: 0.5 },
  cardStyle: { backgroundColor: '#0f0c29' },
};

export default function App() {
  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <NavigationContainer>
        <Stack.Navigator screenOptions={screenOptions}>
          <Stack.Screen
            name="Chat"
            component={ChatScreen}
            options={{ title: '⚡ ZEUS' }}
          />
          <Stack.Screen
            name="Sessions"
            component={SessionsScreen}
            options={{ title: 'Sessions & Settings' }}
          />
        </Stack.Navigator>
      </NavigationContainer>
    </GestureHandlerRootView>
  );
}
