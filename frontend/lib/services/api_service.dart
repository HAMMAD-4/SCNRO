import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/models.dart';

/// HTTP client that communicates with the SCNRO FastAPI backend.
class ApiService {
  ApiService({required this.baseUrl, http.Client? client})
      : _client = client ?? http.Client();

  final String baseUrl;
  final http.Client _client;

  // ── Navigation ──────────────────────────────────────────────────────────

  /// Returns the shortest path from [fromId] to [toId].
  Future<NavigationPath> navigate({required int toId, int fromId = 1}) async {
    final uri = Uri.parse('$baseUrl/api/v1/navigate')
        .replace(queryParameters: {'to': '$toId', 'from': '$fromId'});
    final response = await _client.get(uri);
    _assertOk(response);
    return NavigationPath.fromJson(
        jsonDecode(response.body) as Map<String, dynamic>);
  }

  // ── Resources ───────────────────────────────────────────────────────────

  /// Returns rooms that are currently vacant, ranked by proximity.
  Future<List<AvailableRoom>> getAvailableRooms({
    double userLat = 31.4826,
    double userLng = 74.3036,
  }) async {
    final uri = Uri.parse('$baseUrl/api/v1/resources/available').replace(
      queryParameters: {
        'user_lat': '$userLat',
        'user_lng': '$userLng',
      },
    );
    final response = await _client.get(uri);
    _assertOk(response);
    final data = jsonDecode(response.body) as Map<String, dynamic>;
    final rooms = data['available_rooms'] as List;
    return rooms
        .map((r) => AvailableRoom.fromJson(r as Map<String, dynamic>))
        .toList();
  }

  // ── Lost & Found ────────────────────────────────────────────────────────

  /// Returns all lost & found items, optionally filtered by [status].
  Future<List<LostFoundItem>> getLostFoundItems({String? status}) async {
    final params = status != null ? {'status': status} : <String, String>{};
    final uri = Uri.parse('$baseUrl/api/v1/items')
        .replace(queryParameters: params.isNotEmpty ? params : null);
    final response = await _client.get(uri);
    _assertOk(response);
    final data = jsonDecode(response.body) as Map<String, dynamic>;
    return (data['items'] as List)
        .map((i) => LostFoundItem.fromJson(i as Map<String, dynamic>))
        .toList();
  }

  /// Reports a lost or found item.
  Future<LostFoundItem> reportItem(LostFoundItem item) async {
    final uri = Uri.parse('$baseUrl/api/v1/items/report');
    final response = await _client.post(
      uri,
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(item.toJson()),
    );
    _assertOk(response, expectedStatus: 201);
    return LostFoundItem.fromJson(
        jsonDecode(response.body) as Map<String, dynamic>);
  }

  // ── Faculty ─────────────────────────────────────────────────────────────

  /// Searches faculty members by partial name match.
  Future<List<FacultyMember>> searchFaculty(String name) async {
    final uri = Uri.parse('$baseUrl/api/v1/faculty/search')
        .replace(queryParameters: {'name': name});
    final response = await _client.get(uri);
    _assertOk(response);
    final data = jsonDecode(response.body) as Map<String, dynamic>;
    return (data['faculty'] as List)
        .map((f) => FacultyMember.fromJson(f as Map<String, dynamic>))
        .toList();
  }

  // ── Helpers ─────────────────────────────────────────────────────────────

  void _assertOk(http.Response response, {int expectedStatus = 200}) {
    if (response.statusCode != expectedStatus) {
      throw ApiException(
        statusCode: response.statusCode,
        message: response.body,
      );
    }
  }
}

class ApiException implements Exception {
  const ApiException({required this.statusCode, required this.message});
  final int statusCode;
  final String message;

  @override
  String toString() => 'ApiException($statusCode): $message';
}
