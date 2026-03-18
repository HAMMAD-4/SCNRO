import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'providers/providers.dart';
import 'screens/dashboard_screen.dart';
import 'screens/map_screen.dart';
import 'screens/lost_found_screen.dart';
import 'screens/faculty_screen.dart';
import 'services/api_service.dart';

void main() {
  runApp(const ScnroApp());
}

class ScnroApp extends StatelessWidget {
  const ScnroApp({super.key});

  static const _apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://10.0.2.2:8000', // Android emulator → localhost
  );

  @override
  Widget build(BuildContext context) {
    final api = ApiService(baseUrl: _apiBaseUrl);

    return MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => NavigationProvider(api)),
        ChangeNotifierProvider(create: (_) => ResourcesProvider(api)),
        ChangeNotifierProvider(create: (_) => LostFoundProvider(api)),
        ChangeNotifierProvider(create: (_) => FacultyProvider(api)),
      ],
      child: MaterialApp(
        title: 'SCNRO – Smart Campus',
        debugShowCheckedModeBanner: false,
        theme: ThemeData(
          colorScheme: ColorScheme.fromSeed(
            seedColor: const Color(0xFF1565C0),
          ),
          useMaterial3: true,
        ),
        initialRoute: '/',
        routes: {
          '/': (_) => const DashboardScreen(),
          '/map': (_) => const MapScreen(),
          '/lost-found': (_) => const LostFoundScreen(),
          '/faculty': (_) => const FacultyScreen(),
        },
      ),
    );
  }
}
