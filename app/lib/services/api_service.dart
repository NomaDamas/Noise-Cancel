import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;

import '../models/post.dart';

class ApiServiceException implements Exception {
  const ApiServiceException(
    this.message, {
    this.statusCode,
  });

  final String message;
  final int? statusCode;

  @override
  String toString() {
    if (statusCode == null) {
      return 'ApiServiceException: $message';
    }
    return 'ApiServiceException(statusCode: $statusCode, message: $message)';
  }
}

class ApiService {
  ApiService({
    String? baseUrl,
    FlutterSecureStorage? storage,
    http.Client? client,
  }) : _configuredBaseUrl = _normalizeBaseUrl(baseUrl),
       _storage = storage ?? const FlutterSecureStorage(),
       _client = client ?? http.Client();

  static const String serverUrlStorageKey = 'server_url';
  static const String _defaultBaseUrl = 'http://localhost:8012';

  final String? _configuredBaseUrl;
  final FlutterSecureStorage _storage;
  final http.Client _client;

  Future<List<Post>> fetchPosts({
    int limit = 20,
    int offset = 0,
  }) async {
    final uri = await _buildUri(
      '/api/posts',
      queryParameters: <String, String>{
        'limit': '$limit',
        'offset': '$offset',
      },
    );
    final response = await _request(() => _client.get(uri), action: 'fetch posts');
    final payload = _decodeJsonMap(response.body, action: 'fetch posts');

    final posts = payload['posts'];
    if (posts is! List<dynamic>) {
      throw const ApiServiceException('Invalid posts response payload');
    }

    try {
      return posts
          .map((item) => Post.fromJson(_coerceMap(item, action: 'fetch posts')))
          .toList(growable: false);
    } on FormatException catch (error) {
      throw ApiServiceException('Invalid post payload: ${error.message}');
    } on ApiServiceException {
      rethrow;
    } catch (error) {
      throw ApiServiceException('Failed to parse posts: $error');
    }
  }

  Future<Map<String, dynamic>> archivePost(String classificationId) async {
    final uri = await _buildUri('/api/posts/${Uri.encodeComponent(classificationId)}/archive');
    final response = await _request(() => _client.post(uri), action: 'archive post');
    return _decodeJsonMap(response.body, action: 'archive post');
  }

  Future<void> deletePost(String classificationId) async {
    final uri = await _buildUri('/api/posts/${Uri.encodeComponent(classificationId)}/delete');
    await _request(() => _client.post(uri), action: 'delete post');
  }

  Future<String> _resolveBaseUrl() async {
    if (_configuredBaseUrl != null) {
      return _configuredBaseUrl;
    }

    try {
      final storedUrl = await _storage.read(key: serverUrlStorageKey);
      return _normalizeBaseUrl(storedUrl) ?? _defaultBaseUrl;
    } catch (error) {
      throw ApiServiceException('Failed to read server URL from secure storage: $error');
    }
  }

  Future<Uri> _buildUri(
    String path, {
    Map<String, String>? queryParameters,
  }) async {
    final baseUrl = await _resolveBaseUrl();
    return Uri.parse('$baseUrl$path').replace(queryParameters: queryParameters);
  }

  Future<http.Response> _request(
    Future<http.Response> Function() request, {
    required String action,
  }) async {
    try {
      final response = await request();
      if (response.statusCode < 200 || response.statusCode >= 300) {
        throw ApiServiceException(
          'Request failed while trying to $action',
          statusCode: response.statusCode,
        );
      }
      return response;
    } on ApiServiceException {
      rethrow;
    } on http.ClientException catch (error) {
      throw ApiServiceException('Network error while trying to $action: ${error.message}');
    } catch (error) {
      throw ApiServiceException('Unexpected error while trying to $action: $error');
    }
  }

  Map<String, dynamic> _decodeJsonMap(
    String body, {
    required String action,
  }) {
    try {
      final payload = jsonDecode(body);
      return _coerceMap(payload, action: action);
    } on FormatException catch (error) {
      throw ApiServiceException('Invalid JSON while trying to $action: ${error.message}');
    } on ApiServiceException {
      rethrow;
    } catch (error) {
      throw ApiServiceException('Failed to decode response while trying to $action: $error');
    }
  }

  Map<String, dynamic> _coerceMap(
    Object? value, {
    required String action,
  }) {
    if (value is Map<String, dynamic>) {
      return value;
    }
    if (value is Map) {
      return value.map((key, dynamic item) => MapEntry('$key', item));
    }
    throw ApiServiceException('Invalid response format while trying to $action');
  }

  static String? _normalizeBaseUrl(String? value) {
    if (value == null) {
      return null;
    }
    final trimmed = value.trim();
    if (trimmed.isEmpty) {
      return null;
    }
    return trimmed.endsWith('/') ? trimmed.substring(0, trimmed.length - 1) : trimmed;
  }
}
