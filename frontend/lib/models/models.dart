/// Data models for the SCNRO Flutter application.

class Location {
  final int locationId;
  final String name;
  final String? category;
  final String? wingName;
  final int? floorLevel;
  final double? latitude;
  final double? longitude;

  const Location({
    required this.locationId,
    required this.name,
    this.category,
    this.wingName,
    this.floorLevel,
    this.latitude,
    this.longitude,
  });

  factory Location.fromJson(Map<String, dynamic> json) => Location(
        locationId: json['location_id'] as int,
        name: json['name'] as String,
        category: json['category'] as String?,
        wingName: json['wing_name'] as String?,
        floorLevel: json['floor_level'] as int?,
        latitude: (json['latitude'] as num?)?.toDouble(),
        longitude: (json['longitude'] as num?)?.toDouble(),
      );
}

class AvailableRoom {
  final int locationId;
  final String name;
  final String? category;
  final String? wingName;
  final int? floorLevel;
  final double? latitude;
  final double? longitude;
  final String? freeUntil;
  final int freeMinutes;
  final double distanceM;
  final double score;

  const AvailableRoom({
    required this.locationId,
    required this.name,
    this.category,
    this.wingName,
    this.floorLevel,
    this.latitude,
    this.longitude,
    this.freeUntil,
    required this.freeMinutes,
    required this.distanceM,
    required this.score,
  });

  factory AvailableRoom.fromJson(Map<String, dynamic> json) => AvailableRoom(
        locationId: json['location_id'] as int,
        name: json['name'] as String,
        category: json['category'] as String?,
        wingName: json['wing_name'] as String?,
        floorLevel: json['floor_level'] as int?,
        latitude: (json['latitude'] as num?)?.toDouble(),
        longitude: (json['longitude'] as num?)?.toDouble(),
        freeUntil: json['free_until'] as String?,
        freeMinutes: (json['free_minutes'] as num?)?.toInt() ?? 0,
        distanceM: (json['distance_m'] as num?)?.toDouble() ?? 0.0,
        score: (json['score'] as num?)?.toDouble() ?? 0.0,
      );
}

class LostFoundItem {
  final int? itemId;
  final int userId;
  final String itemName;
  final String? description;
  final String? imageUrl;
  final String status;
  final int? locationLastSeen;
  final String? createdAt;

  const LostFoundItem({
    this.itemId,
    required this.userId,
    required this.itemName,
    this.description,
    this.imageUrl,
    required this.status,
    this.locationLastSeen,
    this.createdAt,
  });

  factory LostFoundItem.fromJson(Map<String, dynamic> json) => LostFoundItem(
        itemId: json['item_id'] as int?,
        userId: json['user_id'] as int,
        itemName: json['item_name'] as String,
        description: json['description'] as String?,
        imageUrl: json['image_url'] as String?,
        status: json['status'] as String,
        locationLastSeen: json['location_last_seen'] as int?,
        createdAt: json['created_at'] as String?,
      );

  Map<String, dynamic> toJson() => {
        'user_id': userId,
        'item_name': itemName,
        if (description != null) 'description': description,
        if (imageUrl != null) 'image_url': imageUrl,
        'status': status,
        if (locationLastSeen != null) 'location_last_seen': locationLastSeen,
      };
}

class FacultyMember {
  final int facultyId;
  final String name;
  final String? designation;
  final String? department;
  final bool isAvailable;
  final Location? office;

  const FacultyMember({
    required this.facultyId,
    required this.name,
    this.designation,
    this.department,
    required this.isAvailable,
    this.office,
  });

  factory FacultyMember.fromJson(Map<String, dynamic> json) => FacultyMember(
        facultyId: json['faculty_id'] as int,
        name: json['name'] as String,
        designation: json['designation'] as String?,
        department: json['department'] as String?,
        isAvailable: json['is_available'] as bool? ?? false,
        office: json['office'] != null
            ? Location.fromJson(json['office'] as Map<String, dynamic>)
            : null,
      );
}

class NavigationPath {
  final Map<String, dynamic> from;
  final Map<String, dynamic> to;
  final List<int> pathNodes;
  final double totalDistanceM;
  final List<Map<String, double>> coordinates;

  const NavigationPath({
    required this.from,
    required this.to,
    required this.pathNodes,
    required this.totalDistanceM,
    required this.coordinates,
  });

  factory NavigationPath.fromJson(Map<String, dynamic> json) => NavigationPath(
        from: Map<String, dynamic>.from(json['from'] as Map),
        to: Map<String, dynamic>.from(json['to'] as Map),
        pathNodes: List<int>.from(json['path_nodes'] as List),
        totalDistanceM: (json['total_distance_m'] as num).toDouble(),
        coordinates: (json['coordinates'] as List)
            .map((c) => {
                  'lat': (c['lat'] as num).toDouble(),
                  'lng': (c['lng'] as num).toDouble(),
                })
            .toList(),
      );
}

// ── Attendance models ────────────────────────────────────────────────────────

class DailyAttendanceRecord {
  final int recordId;
  final int studentId;
  final int courseId;
  final String date;
  /// "present" | "absent" | "late"
  final String status;
  final int markedBy;
  final String? createdAt;

  const DailyAttendanceRecord({
    required this.recordId,
    required this.studentId,
    required this.courseId,
    required this.date,
    required this.status,
    required this.markedBy,
    this.createdAt,
  });

  factory DailyAttendanceRecord.fromJson(Map<String, dynamic> json) =>
      DailyAttendanceRecord(
        recordId: json['record_id'] as int,
        studentId: json['student_id'] as int,
        courseId: json['course_id'] as int,
        date: json['date'] as String,
        status: json['status'] as String,
        markedBy: json['marked_by'] as int,
        createdAt: json['created_at'] as String?,
      );
}

class AttendanceFineRecord {
  final int fineId;
  final int studentId;
  final String studentName;
  final String studentEmail;
  final int courseId;
  final String courseCode;
  final String courseName;
  final double? attendancePercentage;
  final double fineAmount;
  final String? reason;
  /// "pending" | "paid" | "waived"
  final String status;
  final String issuedAt;

  const AttendanceFineRecord({
    required this.fineId,
    required this.studentId,
    required this.studentName,
    required this.studentEmail,
    required this.courseId,
    required this.courseCode,
    required this.courseName,
    this.attendancePercentage,
    required this.fineAmount,
    this.reason,
    required this.status,
    required this.issuedAt,
  });

  factory AttendanceFineRecord.fromJson(Map<String, dynamic> json) =>
      AttendanceFineRecord(
        fineId: json['fine_id'] as int,
        studentId: json['student_id'] as int,
        studentName: json['student_name'] as String? ?? '',
        studentEmail: json['student_email'] as String? ?? '',
        courseId: json['course_id'] as int,
        courseCode: json['course_code'] as String? ?? '',
        courseName: json['course_name'] as String? ?? '',
        attendancePercentage:
            (json['attendance_percentage'] as num?)?.toDouble(),
        fineAmount: (json['fine_amount'] as num).toDouble(),
        reason: json['reason'] as String?,
        status: json['status'] as String,
        issuedAt: json['issued_at'] as String,
      );
}

class AttendanceStudentSummary {
  final int studentId;
  final String name;
  final String email;
  final int totalClasses;
  final int present;
  final int absent;
  final int late;
  final double percentage;
  /// true when attendance < 75 %
  final bool fineRequired;
  /// false when attendance < 70 %
  final bool examEligible;
  final Map<String, dynamic>? fine;

  const AttendanceStudentSummary({
    required this.studentId,
    required this.name,
    required this.email,
    required this.totalClasses,
    required this.present,
    required this.absent,
    required this.late,
    required this.percentage,
    required this.fineRequired,
    required this.examEligible,
    this.fine,
  });

  factory AttendanceStudentSummary.fromJson(Map<String, dynamic> json) =>
      AttendanceStudentSummary(
        studentId: json['student_id'] as int,
        name: json['name'] as String? ?? '',
        email: json['email'] as String? ?? '',
        totalClasses: (json['total_classes'] as num?)?.toInt() ?? 0,
        present: (json['present'] as num?)?.toInt() ?? 0,
        absent: (json['absent'] as num?)?.toInt() ?? 0,
        late: (json['late'] as num?)?.toInt() ?? 0,
        percentage: (json['percentage'] as num?)?.toDouble() ?? 0.0,
        fineRequired: json['fine_required'] as bool? ?? false,
        examEligible: json['exam_eligible'] as bool? ?? true,
        fine: json['fine'] as Map<String, dynamic>?,
      );
}
