import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'package:provider/provider.dart';

import '../providers/providers.dart';

/// 2.5D interactive campus map showing the current navigation path.
class MapScreen extends StatelessWidget {
  const MapScreen({super.key});

  // PUCIT campus centre coordinates
  static const _campusCenter = LatLng(31.4826, 74.3036);

  @override
  Widget build(BuildContext context) {
    final navProvider = context.watch<NavigationProvider>();

    // Build polyline from navigation path coordinates
    final polylinePoints = navProvider.currentPath?.coordinates
            .map((c) => LatLng(c['lat']!, c['lng']!))
            .toList() ??
        [];

    final destinationLatLng = navProvider.currentPath != null
        ? LatLng(
            double.tryParse(
                    navProvider.currentPath!.to['latitude']?.toString() ??
                        '') ??
                _campusCenter.latitude,
            double.tryParse(
                    navProvider.currentPath!.to['longitude']?.toString() ??
                        '') ??
                _campusCenter.longitude,
          )
        : null;

    return Scaffold(
      appBar: AppBar(
        title: Text(
          navProvider.currentPath != null
              ? 'Route to ${navProvider.currentPath!.to['name']}'
              : 'Campus Map',
        ),
        actions: [
          if (navProvider.currentPath != null)
            IconButton(
              icon: const Icon(Icons.close),
              onPressed: () => context.read<NavigationProvider>().clearPath(),
            ),
        ],
      ),
      body: Stack(
        children: [
          // ── Base map layer ──────────────────────────────────────────────
          FlutterMap(
            options: MapOptions(
              initialCenter: _campusCenter,
              initialZoom: 18.0,
              maxZoom: 22.0,
              minZoom: 14.0,
            ),
            children: [
              TileLayer(
                urlTemplate:
                    'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                userAgentPackageName: 'com.scnro.app',
              ),

              // Navigation polyline
              if (polylinePoints.isNotEmpty)
                PolylineLayer(
                  polylines: [
                    Polyline(
                      points: polylinePoints,
                      color: Colors.blueAccent,
                      strokeWidth: 4.0,
                    ),
                  ],
                ),

              // Destination marker
              if (destinationLatLng != null)
                MarkerLayer(
                  markers: [
                    Marker(
                      point: destinationLatLng,
                      width: 40,
                      height: 40,
                      child: const Icon(Icons.location_pin,
                          color: Colors.red, size: 40),
                    ),
                  ],
                ),

              // "You Are Here" marker (campus centre as placeholder)
              MarkerLayer(
                markers: [
                  Marker(
                    point: _campusCenter,
                    width: 40,
                    height: 40,
                    child: const Icon(Icons.my_location,
                        color: Colors.blueAccent, size: 32),
                  ),
                ],
              ),
            ],
          ),

          // ── Sliding info panel ──────────────────────────────────────────
          if (navProvider.currentPath != null)
            Positioned(
              left: 0,
              right: 0,
              bottom: 0,
              child: _PathInfoPanel(path: navProvider.currentPath!),
            ),

          if (navProvider.isLoading)
            const Positioned.fill(
              child: ColoredBox(
                color: Color(0x80000000),
                child: Center(child: CircularProgressIndicator()),
              ),
            ),
        ],
      ),
      bottomNavigationBar: _buildBottomNav(context),
    );
  }

  BottomNavigationBar _buildBottomNav(BuildContext context) =>
      BottomNavigationBar(
        currentIndex: 1,
        type: BottomNavigationBarType.fixed,
        items: const [
          BottomNavigationBarItem(
              icon: Icon(Icons.home_outlined), label: 'Home'),
          BottomNavigationBarItem(icon: Icon(Icons.map_outlined), label: 'Map'),
          BottomNavigationBarItem(
              icon: Icon(Icons.find_in_page_outlined), label: 'Lost & Found'),
          BottomNavigationBarItem(
              icon: Icon(Icons.person_search_outlined), label: 'Faculty'),
        ],
        onTap: (index) {
          switch (index) {
            case 0:
              Navigator.of(context).pushReplacementNamed('/');
              break;
            case 2:
              Navigator.of(context).pushReplacementNamed('/lost-found');
              break;
            case 3:
              Navigator.of(context).pushReplacementNamed('/faculty');
              break;
          }
        },
      );
}

class _PathInfoPanel extends StatelessWidget {
  const _PathInfoPanel({required this.path});
  final dynamic path;

  @override
  Widget build(BuildContext context) => Container(
        decoration: BoxDecoration(
          color: Theme.of(context).colorScheme.surface,
          borderRadius: const BorderRadius.vertical(top: Radius.circular(16)),
          boxShadow: const [BoxShadow(blurRadius: 8, color: Colors.black26)],
        ),
        padding: const EdgeInsets.all(16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Route to ${path.to['name']}',
              style: const TextStyle(
                  fontSize: 16, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 4),
            Text(
              'Distance: ${path.totalDistanceM.toStringAsFixed(1)} m',
              style: const TextStyle(color: Colors.grey),
            ),
            Text(
              'Via ${path.pathNodes.length} waypoints',
              style: const TextStyle(color: Colors.grey),
            ),
          ],
        ),
      );
}
