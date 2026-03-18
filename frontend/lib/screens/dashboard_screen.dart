import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../providers/providers.dart';
import '../models/models.dart';

/// Dashboard: quick-access cards for the next class and nearest free lab.
class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<ResourcesProvider>().loadAvailableRooms();
    });
  }

  @override
  Widget build(BuildContext context) {
    final resourcesProvider = context.watch<ResourcesProvider>();

    return Scaffold(
      appBar: AppBar(
        title: const Text('SCNRO – Smart Campus'),
        centerTitle: true,
      ),
      body: RefreshIndicator(
        onRefresh: () =>
            context.read<ResourcesProvider>().loadAvailableRooms(),
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            // ── Section header ────────────────────────────────────────────
            const Text(
              'Live Campus Updates',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 12),

            if (resourcesProvider.isLoading)
              const Center(child: CircularProgressIndicator())
            else if (resourcesProvider.errorMessage != null)
              _ErrorCard(message: resourcesProvider.errorMessage!)
            else if (resourcesProvider.availableRooms.isEmpty)
              const Center(child: Text('No vacant rooms found right now.'))
            else ...[
              const _SectionLabel(label: 'Nearest Free Labs & Classrooms'),
              ...resourcesProvider.availableRooms
                  .take(5)
                  .map((room) => _RoomCard(room: room)),
            ],
          ],
        ),
      ),
      bottomNavigationBar: _BottomNav(currentIndex: 0),
    );
  }
}

// ── Widgets ────────────────────────────────────────────────────────────────

class _SectionLabel extends StatelessWidget {
  const _SectionLabel({required this.label});
  final String label;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: Text(label,
            style: const TextStyle(fontSize: 14, color: Colors.grey)),
      );
}

class _RoomCard extends StatelessWidget {
  const _RoomCard({required this.room});
  final AvailableRoom room;

  @override
  Widget build(BuildContext context) {
    final freeText = room.freeUntil != null
        ? 'Free until ${room.freeUntil} (${room.freeMinutes} min)'
        : 'No upcoming classes';

    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: ListTile(
        leading: const Icon(Icons.meeting_room_outlined, color: Colors.green),
        title: Text(room.name,
            style: const TextStyle(fontWeight: FontWeight.w600)),
        subtitle: Text(
            '${room.wingName ?? ''} · Floor ${room.floorLevel ?? '-'}\n$freeText'),
        trailing: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text('${room.distanceM.toStringAsFixed(0)} m',
                style: const TextStyle(
                    fontWeight: FontWeight.bold, color: Colors.blueAccent)),
          ],
        ),
        onTap: () {
          context
              .read<NavigationProvider>()
              .navigateTo(room.locationId);
          Navigator.of(context).pushNamed('/map');
        },
      ),
    );
  }
}

class _ErrorCard extends StatelessWidget {
  const _ErrorCard({required this.message});
  final String message;

  @override
  Widget build(BuildContext context) => Card(
        color: Colors.red[50],
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Text(message, style: const TextStyle(color: Colors.red)),
        ),
      );
}

class _BottomNav extends StatelessWidget {
  const _BottomNav({required this.currentIndex});
  final int currentIndex;

  @override
  Widget build(BuildContext context) => BottomNavigationBar(
        currentIndex: currentIndex,
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
            case 1:
              Navigator.of(context).pushReplacementNamed('/map');
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
