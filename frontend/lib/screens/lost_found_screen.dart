import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/models.dart';
import '../providers/providers.dart';

/// Community lost-and-found board screen.
class LostFoundScreen extends StatefulWidget {
  const LostFoundScreen({super.key});

  @override
  State<LostFoundScreen> createState() => _LostFoundScreenState();
}

class _LostFoundScreenState extends State<LostFoundScreen>
    with SingleTickerProviderStateMixin {
  late final TabController _tabs;

  @override
  void initState() {
    super.initState();
    _tabs = TabController(length: 3, vsync: this);
    _tabs.addListener(_onTabChanged);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<LostFoundProvider>().loadItems();
    });
  }

  void _onTabChanged() {
    if (_tabs.indexIsChanging) return;
    final filters = [null, 'Lost', 'Found'];
    context.read<LostFoundProvider>().loadItems(status: filters[_tabs.index]);
  }

  @override
  void dispose() {
    _tabs.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<LostFoundProvider>();

    return Scaffold(
      appBar: AppBar(
        title: const Text('Lost & Found'),
        bottom: TabBar(
          controller: _tabs,
          tabs: const [
            Tab(text: 'All'),
            Tab(text: 'Lost'),
            Tab(text: 'Found'),
          ],
        ),
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => _showReportDialog(context),
        icon: const Icon(Icons.add),
        label: const Text('Report Item'),
      ),
      body: provider.isLoading
          ? const Center(child: CircularProgressIndicator())
          : provider.errorMessage != null
              ? Center(child: Text(provider.errorMessage!))
              : provider.items.isEmpty
                  ? const Center(child: Text('No items reported yet.'))
                  : ListView.builder(
                      itemCount: provider.items.length,
                      padding: const EdgeInsets.all(12),
                      itemBuilder: (ctx, i) =>
                          _ItemCard(item: provider.items[i]),
                    ),
      bottomNavigationBar: _buildBottomNav(context),
    );
  }

  Future<void> _showReportDialog(BuildContext context) async {
    final formKey = GlobalKey<FormState>();
    String itemName = '';
    String description = '';
    String status = 'Lost';

    await showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      builder: (ctx) => Padding(
        padding: EdgeInsets.only(
          bottom: MediaQuery.of(ctx).viewInsets.bottom,
          left: 16,
          right: 16,
          top: 24,
        ),
        child: Form(
          key: formKey,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text('Report a Lost / Found Item',
                  style: TextStyle(
                      fontSize: 16, fontWeight: FontWeight.bold)),
              const SizedBox(height: 12),
              TextFormField(
                decoration:
                    const InputDecoration(labelText: 'Item name *'),
                validator: (v) =>
                    (v == null || v.isEmpty) ? 'Required' : null,
                onSaved: (v) => itemName = v ?? '',
              ),
              const SizedBox(height: 8),
              TextFormField(
                decoration:
                    const InputDecoration(labelText: 'Description'),
                onSaved: (v) => description = v ?? '',
              ),
              const SizedBox(height: 8),
              DropdownButtonFormField<String>(
                value: status,
                decoration:
                    const InputDecoration(labelText: 'Status *'),
                items: ['Lost', 'Found']
                    .map((s) => DropdownMenuItem(value: s, child: Text(s)))
                    .toList(),
                onChanged: (v) => status = v ?? 'Lost',
              ),
              const SizedBox(height: 16),
              ElevatedButton(
                onPressed: () async {
                  if (!formKey.currentState!.validate()) return;
                  formKey.currentState!.save();
                  Navigator.pop(ctx);
                  final item = LostFoundItem(
                    // TODO: replace with authenticated user ID once auth is implemented
                    userId: 1,
                    itemName: itemName,
                    description: description.isEmpty ? null : description,
                    status: status,
                  );
                  final success = await context
                      .read<LostFoundProvider>()
                      .reportItem(item);
                  if (context.mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(
                          content: Text(success
                              ? 'Item reported successfully!'
                              : 'Failed to report item.')),
                    );
                  }
                },
                child: const Text('Submit'),
              ),
              const SizedBox(height: 16),
            ],
          ),
        ),
      ),
    );
  }

  BottomNavigationBar _buildBottomNav(BuildContext context) =>
      BottomNavigationBar(
        currentIndex: 2,
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
            case 3:
              Navigator.of(context).pushReplacementNamed('/faculty');
              break;
          }
        },
      );
}

class _ItemCard extends StatelessWidget {
  const _ItemCard({required this.item});
  final LostFoundItem item;

  static const _statusColors = {
    'Lost': Colors.red,
    'Found': Colors.green,
    'Claimed': Colors.grey,
  };

  @override
  Widget build(BuildContext context) {
    final color =
        _statusColors[item.status] ?? Colors.blueGrey;

    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: color.withOpacity(0.15),
          child: Icon(Icons.inventory_2_outlined, color: color),
        ),
        title: Text(item.itemName,
            style: const TextStyle(fontWeight: FontWeight.w600)),
        subtitle: item.description != null ? Text(item.description!) : null,
        trailing: Chip(
          label: Text(item.status),
          backgroundColor: color.withOpacity(0.15),
          side: BorderSide(color: color),
          labelStyle: TextStyle(color: color),
        ),
      ),
    );
  }
}
