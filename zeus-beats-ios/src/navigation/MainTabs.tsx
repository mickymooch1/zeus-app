import React from 'react';
import { Text } from 'react-native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { CreateSongScreen } from '../screens/CreateSongScreen';
import { LibraryScreen }    from '../screens/LibraryScreen';
import { COLORS }           from '../constants/theme';

const Tab = createBottomTabNavigator();

function TabIcon({ icon, color, size }: { icon: string; color: string; size: number }) {
  return <Text style={{ fontSize: size * 0.85, color }}>{icon}</Text>;
}

export function MainTabs() {
  return (
    <Tab.Navigator
      screenOptions={{
        headerStyle:           { backgroundColor: '#1a1040' },
        headerTintColor:       COLORS.textPrimary,
        headerTitleStyle:      { fontWeight: '700', letterSpacing: 0.5 },
        tabBarStyle: {
          backgroundColor: COLORS.tabBg,
          borderTopColor:  'rgba(255,255,255,0.08)',
          paddingBottom:   4,
          height:          58,
        },
        tabBarActiveTintColor:   COLORS.tabActive,
        tabBarInactiveTintColor: COLORS.tabInactive,
      }}
    >
      <Tab.Screen
        name="CreateSong"
        component={CreateSongScreen}
        options={{
          title:        '⚡ Create',
          tabBarLabel:  'Create',
          tabBarIcon:   ({ color, size }) => <TabIcon icon="⚡" color={color} size={size} />,
        }}
      />
      <Tab.Screen
        name="Library"
        component={LibraryScreen}
        options={{
          title:        'Library',
          tabBarLabel:  'Library',
          tabBarIcon:   ({ color, size }) => <TabIcon icon="🎵" color={color} size={size} />,
        }}
      />
    </Tab.Navigator>
  );
}
