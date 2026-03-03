class Post {
  const Post({
    required this.id,
    required this.classificationId,
    required this.platform,
    required this.authorName,
    this.authorUrl,
    required this.postUrl,
    required this.postText,
    required this.summary,
    required this.category,
    required this.confidence,
    required this.reasoning,
    required this.classifiedAt,
    required this.swipeStatus,
    this.note,
  });

  final String id;
  final String classificationId;
  final String platform;
  final String authorName;
  final String? authorUrl;
  final String? postUrl;
  final String postText;
  final String summary;
  final String category;
  final double confidence;
  final String reasoning;
  final String classifiedAt;
  final String swipeStatus;
  final String? note;

  factory Post.fromJson(Map<String, dynamic> json) {
    final confidenceValue = json['confidence'];

    return Post(
      id: _readString(json, 'id'),
      classificationId: _readStringOrDefault(json, 'classificationId',
          fallbackKey: 'classification_id', defaultValue: ''),
      platform: _readStringOrDefault(json, 'platform', defaultValue: 'unknown'),
      authorName: _readStringOrDefault(json, 'authorName',
          fallbackKey: 'author_name', defaultValue: 'Unknown'),
      authorUrl: _readOptionalString(json, 'authorUrl', fallbackKey: 'author_url'),
      postUrl: _readOptionalString(json, 'postUrl', fallbackKey: 'post_url'),
      postText: _readStringOrDefault(json, 'postText',
          fallbackKey: 'post_text', defaultValue: ''),
      summary: _readStringOrDefault(json, 'summary', defaultValue: ''),
      category: _readStringOrDefault(json, 'category', defaultValue: 'Unknown'),
      confidence: (confidenceValue is num) ? confidenceValue.toDouble() : 0.0,
      reasoning: _readStringOrDefault(json, 'reasoning', defaultValue: ''),
      classifiedAt: _readStringOrDefault(json, 'classifiedAt',
          fallbackKey: 'classified_at', defaultValue: ''),
      swipeStatus: _readStringOrDefault(json, 'swipeStatus',
          fallbackKey: 'swipe_status', defaultValue: 'pending'),
      note: _readOptionalString(json, 'note'),
    );
  }

  static String _readString(
    Map<String, dynamic> json,
    String key, {
    String? fallbackKey,
  }) {
    final value = json[key] ?? (fallbackKey != null ? json[fallbackKey] : null);
    if (value is String) {
      return value;
    }
    throw FormatException('Missing or invalid "$key" field');
  }

  static String _readStringOrDefault(
    Map<String, dynamic> json,
    String key, {
    String? fallbackKey,
    required String defaultValue,
  }) {
    final value = json[key] ?? (fallbackKey != null ? json[fallbackKey] : null);
    if (value is String) {
      return value;
    }
    return defaultValue;
  }

  static String? _readOptionalString(
    Map<String, dynamic> json,
    String key, {
    String? fallbackKey,
  }) {
    final value = json[key] ?? (fallbackKey != null ? json[fallbackKey] : null);
    if (value == null) {
      return null;
    }
    if (value is String) {
      return value;
    }
    throw FormatException('Missing or invalid "$key" field');
  }
}
