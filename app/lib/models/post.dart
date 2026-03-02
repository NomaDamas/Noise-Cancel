class Post {
  const Post({
    required this.id,
    required this.classificationId,
    required this.platform,
    required this.authorName,
    required this.authorUrl,
    required this.postUrl,
    required this.postText,
    required this.summary,
    required this.category,
    required this.confidence,
    required this.reasoning,
    required this.classifiedAt,
    required this.swipeStatus,
  });

  final String id;
  final String classificationId;
  final String platform;
  final String authorName;
  final String authorUrl;
  final String? postUrl;
  final String postText;
  final String summary;
  final String category;
  final double confidence;
  final String reasoning;
  final String classifiedAt;
  final String swipeStatus;

  factory Post.fromJson(Map<String, dynamic> json) {
    final confidenceValue = json['confidence'];
    if (confidenceValue is! num) {
      throw const FormatException('Missing or invalid "confidence" field');
    }

    return Post(
      id: _readString(json, 'id'),
      classificationId: _readString(json, 'classificationId',
          fallbackKey: 'classification_id'),
      platform: _readString(json, 'platform'),
      authorName: _readString(json, 'authorName', fallbackKey: 'author_name'),
      authorUrl: _readString(json, 'authorUrl', fallbackKey: 'author_url'),
      postUrl: _readOptionalString(json, 'postUrl', fallbackKey: 'post_url'),
      postText: _readString(json, 'postText', fallbackKey: 'post_text'),
      summary: _readString(json, 'summary'),
      category: _readString(json, 'category'),
      confidence: confidenceValue.toDouble(),
      reasoning: _readString(json, 'reasoning'),
      classifiedAt:
          _readString(json, 'classifiedAt', fallbackKey: 'classified_at'),
      swipeStatus:
          _readString(json, 'swipeStatus', fallbackKey: 'swipe_status'),
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
