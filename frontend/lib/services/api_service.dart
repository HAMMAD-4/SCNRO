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

  // ── Attendance ───────────────────────────────────────────────────────────

  /// Mark daily attendance for a batch of students in [courseId] on [date]
  /// (format YYYY-MM-DD).  [entries] is a list of
  /// `{'student_id': int, 'status': 'present'|'absent'|'late'}` maps.
  Future<Map<String, dynamic>> markAttendance({
    required String token,
    required int courseId,
    required String date,
    required List<Map<String, dynamic>> entries,
  }) async {
    final uri = Uri.parse('$baseUrl/api/v1/attendance/mark');
    final response = await _client.post(
      uri,
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer $token',
      },
      body: jsonEncode({
        'course_id': courseId,
        'date': date,
        'entries': entries,
      }),
    );
    _assertOk(response, expectedStatus: 201);
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  /// Fetch raw daily attendance records for a course.
  Future<List<DailyAttendanceRecord>> getAttendanceRecords({
    required String token,
    required int courseId,
    String? date,
    int? studentId,
  }) async {
    final params = <String, String>{};
    if (date != null) params['date'] = date;
    if (studentId != null) params['student_id'] = '$studentId';
    final uri = Uri.parse('$baseUrl/api/v1/attendance/$courseId/records')
        .replace(queryParameters: params.isNotEmpty ? params : null);
    final response = await _client.get(
      uri,
      headers: {'Authorization': 'Bearer $token'},
    );
    _assertOk(response);
    final data = jsonDecode(response.body) as Map<String, dynamic>;
    return (data['records'] as List)
        .map((r) => DailyAttendanceRecord.fromJson(r as Map<String, dynamic>))
        .toList();
  }

  /// Get attendance percentage summary (with fine/exam-eligibility flags).
  Future<Map<String, dynamic>> getAttendanceSummary({
    required String token,
    required int courseId,
  }) async {
    final uri = Uri.parse('$baseUrl/api/v1/attendance/$courseId/summary');
    final response = await _client.get(
      uri,
      headers: {'Authorization': 'Bearer $token'},
    );
    _assertOk(response);
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  /// Check exam eligibility for a course.
  Future<Map<String, dynamic>> getExamEligibility({
    required String token,
    required int courseId,
  }) async {
    final uri =
        Uri.parse('$baseUrl/api/v1/attendance/exam-eligibility/$courseId');
    final response = await _client.get(
      uri,
      headers: {'Authorization': 'Bearer $token'},
    );
    _assertOk(response);
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  /// List attendance fines visible to the current user.
  Future<List<AttendanceFineRecord>> getAttendanceFines({
    required String token,
    int? courseId,
  }) async {
    final params = courseId != null
        ? <String, String>{'course_id': '$courseId'}
        : <String, String>{};
    final uri = Uri.parse('$baseUrl/api/v1/attendance/fines')
        .replace(queryParameters: params.isNotEmpty ? params : null);
    final response = await _client.get(
      uri,
      headers: {'Authorization': 'Bearer $token'},
    );
    _assertOk(response);
    final data = jsonDecode(response.body) as Map<String, dynamic>;
    return (data['fines'] as List)
        .map((f) => AttendanceFineRecord.fromJson(f as Map<String, dynamic>))
        .toList();
  }

  /// Mark a fine as paid (admin only).
  Future<void> markFinePaid({
    required String token,
    required int fineId,
  }) async {
    final uri = Uri.parse('$baseUrl/api/v1/attendance/fines/$fineId/pay');
    final response = await _client.put(
      uri,
      headers: {'Authorization': 'Bearer $token'},
    );
    _assertOk(response);
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
