import 'package:flutter/foundation.dart';

import '../models/models.dart';
import '../services/api_service.dart';

// ── Navigation Provider ────────────────────────────────────────────────────

class NavigationProvider extends ChangeNotifier {
  NavigationProvider(this._api);

  final ApiService _api;
  NavigationPath? currentPath;
  bool isLoading = false;
  String? errorMessage;

  Future<void> navigateTo(int destinationId, {int fromId = 1}) async {
    isLoading = true;
    errorMessage = null;
    notifyListeners();

    try {
      currentPath =
          await _api.navigate(toId: destinationId, fromId: fromId);
    } on ApiException catch (e) {
      errorMessage = 'Navigation failed: ${e.message}';
    } catch (e) {
      errorMessage = 'Unexpected error: $e';
    } finally {
      isLoading = false;
      notifyListeners();
    }
  }

  void clearPath() {
    currentPath = null;
    errorMessage = null;
    notifyListeners();
  }
}

// ── Resources Provider ─────────────────────────────────────────────────────

class ResourcesProvider extends ChangeNotifier {
  ResourcesProvider(this._api);

  final ApiService _api;
  List<AvailableRoom> availableRooms = [];
  bool isLoading = false;
  String? errorMessage;

  Future<void> loadAvailableRooms({
    double userLat = 31.4826,
    double userLng = 74.3036,
  }) async {
    isLoading = true;
    errorMessage = null;
    notifyListeners();

    try {
      availableRooms = await _api.getAvailableRooms(
        userLat: userLat,
        userLng: userLng,
      );
    } on ApiException catch (e) {
      errorMessage = 'Could not load rooms: ${e.message}';
    } catch (e) {
      errorMessage = 'Unexpected error: $e';
    } finally {
      isLoading = false;
      notifyListeners();
    }
  }
}

// ── Lost & Found Provider ──────────────────────────────────────────────────

class LostFoundProvider extends ChangeNotifier {
  LostFoundProvider(this._api);

  final ApiService _api;
  List<LostFoundItem> items = [];
  bool isLoading = false;
  String? errorMessage;
  String? activeFilter;

  Future<void> loadItems({String? status}) async {
    isLoading = true;
    errorMessage = null;
    activeFilter = status;
    notifyListeners();

    try {
      items = await _api.getLostFoundItems(status: status);
    } on ApiException catch (e) {
      errorMessage = 'Could not load items: ${e.message}';
    } catch (e) {
      errorMessage = 'Unexpected error: $e';
    } finally {
      isLoading = false;
      notifyListeners();
    }
  }

  Future<bool> reportItem(LostFoundItem item) async {
    try {
      final created = await _api.reportItem(item);
      items.insert(0, created);
      notifyListeners();
      return true;
    } on ApiException catch (e) {
      errorMessage = 'Report failed: ${e.message}';
      notifyListeners();
      return false;
    } catch (e) {
      errorMessage = 'Unexpected error: $e';
      notifyListeners();
      return false;
    }
  }
}

// ── Faculty Provider ───────────────────────────────────────────────────────

class FacultyProvider extends ChangeNotifier {
  FacultyProvider(this._api);

  final ApiService _api;
  List<FacultyMember> results = [];
  bool isLoading = false;
  String? errorMessage;

  Future<void> search(String query) async {
    if (query.trim().isEmpty) {
      results = [];
      notifyListeners();
      return;
    }

    isLoading = true;
    errorMessage = null;
    notifyListeners();

    try {
      results = await _api.searchFaculty(query.trim());
    } on ApiException catch (e) {
      errorMessage = 'Search failed: ${e.message}';
    } catch (e) {
      errorMessage = 'Unexpected error: $e';
    } finally {
      isLoading = false;
      notifyListeners();
    }
  }

  void clear() {
    results = [];
    errorMessage = null;
    notifyListeners();
  }
}
