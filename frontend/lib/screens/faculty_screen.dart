import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/models.dart';
import '../providers/providers.dart';

/// Faculty search screen with "Navigate to Office" button.
class FacultyScreen extends StatefulWidget {
  const FacultyScreen({super.key});

  @override
  State<FacultyScreen> createState() => _FacultyScreenState();
}

class _FacultyScreenState extends State<FacultyScreen> {
  final _controller = TextEditingController();

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<FacultyProvider>();

    return Scaffold(
      appBar: AppBar(
        title: const Text('Faculty Locator'),
      ),
      body: Column(
        children: [
          // ── Search bar ─────────────────────────────────────────────────
          Padding(
            padding: const EdgeInsets.all(16),
            child: SearchBar(
              controller: _controller,
              hintText: 'Search by faculty name…',
              leading: const Icon(Icons.search),
              trailing: [
                if (_controller.text.isNotEmpty)
                  IconButton(
                    icon: const Icon(Icons.clear),
                    onPressed: () {
                      _controller.clear();
                      context.read<FacultyProvider>().clear();
                    },
                  ),
              ],
              onChanged: (value) =>
                  context.read<FacultyProvider>().search(value),
            ),
          ),

          // ── Results ────────────────────────────────────────────────────
          Expanded(
            child: provider.isLoading
                ? const Center(child: CircularProgressIndicator())
                : provider.errorMessage != null
                    ? Center(child: Text(provider.errorMessage!))
                    : provider.results.isEmpty
                        ? Center(
                            child: Text(_controller.text.isEmpty
                                ? 'Search for a faculty member above.'
                                : 'No results found.'),
                          )
                        : ListView.builder(
                            itemCount: provider.results.length,
                            padding: const EdgeInsets.symmetric(horizontal: 16),
                            itemBuilder: (ctx, i) =>
                                _FacultyCard(member: provider.results[i]),
                          ),
          ),
        ],
      ),
      bottomNavigationBar: _buildBottomNav(context),
    );
  }

  BottomNavigationBar _buildBottomNav(BuildContext context) =>
      BottomNavigationBar(
        currentIndex: 3,
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
          }
        },
      );
}

class _FacultyCard extends StatelessWidget {
  const _FacultyCard({required this.member});
  final FacultyMember member;

  @override
  Widget build(BuildContext context) => Card(
        margin: const EdgeInsets.only(bottom: 12),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // ── Header ──────────────────────────────────────────────────
              Row(
                children: [
                  CircleAvatar(
                    child: Text(
                      member.name.isNotEmpty
                          ? member.name[0].toUpperCase()
                          : '?',
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(member.name,
                            style: const TextStyle(
                                fontWeight: FontWeight.bold, fontSize: 15)),
                        if (member.designation != null)
                          Text(member.designation!,
                              style: const TextStyle(color: Colors.grey)),
                        if (member.department != null)
                          Text(member.department!,
                              style: const TextStyle(color: Colors.grey)),
                      ],
                    ),
                  ),
                  Chip(
                    label: Text(member.isAvailable ? 'Available' : 'Busy'),
                    backgroundColor: member.isAvailable
                        ? Colors.green[50]
                        : Colors.red[50],
                    side: BorderSide(
                        color: member.isAvailable
                            ? Colors.green
                            : Colors.red),
                    labelStyle: TextStyle(
                        color: member.isAvailable
                            ? Colors.green
                            : Colors.red),
                  ),
                ],
              ),

              // ── Office info ──────────────────────────────────────────────
              if (member.office != null) ...[
                const Divider(height: 20),
                Row(
                  children: [
                    const Icon(Icons.room_outlined,
                        size: 16, color: Colors.grey),
                    const SizedBox(width: 6),
                    Expanded(
                      child: Text(
                        '${member.office!.name ?? 'Unknown office'}'
                        '${member.office!.wingName != null ? ' – ${member.office!.wingName}' : ''}',
                        style: const TextStyle(color: Colors.grey),
                      ),
                    ),
                    TextButton.icon(
                      onPressed: () {
                        if (member.office?.locationId != null) {
                          context
                              .read<NavigationProvider>()
                              .navigateTo(member.office!.locationId);
                          Navigator.of(context).pushNamed('/map');
                        }
                      },
                      icon: const Icon(Icons.directions_walk, size: 16),
                      label: const Text('Navigate'),
                    ),
                  ],
                ),
              ],
            ],
          ),
        ),
      );
}
