import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;

class SecondBrainService {
  SecondBrainService({
    FlutterSecureStorage? storage,
    http.Client? client,
  }) : _storage = storage ?? const FlutterSecureStorage(),
       _client = client ?? http.Client();

  static const String urlStorageKey = 'second_brain_url';
  static const String enabledStorageKey = 'second_brain_enabled';
  static const String apiKeyStorageKey = 'second_brain_api_key';

  final FlutterSecureStorage _storage;
  final http.Client _client;

  Future<bool> isEnabled() async {
    try {
      final rawValue = await _storage.read(key: enabledStorageKey);
      return rawValue == 'true';
    } catch (_) {
      return false;
    }
  }

  Future<void> forward(Map<String, dynamic> postData) async {
    try {
      final enabled = await isEnabled();
      if (!enabled) {
        return;
      }

      var baseUrl = (await _storage.read(key: urlStorageKey))?.trim();
      if (baseUrl == null || baseUrl.isEmpty) {
        return;
      }

      final apiKey = (await _storage.read(key: apiKeyStorageKey))?.trim();
      if (apiKey == null || apiKey.isEmpty) {
        return;
      }

      if (baseUrl.endsWith('/')) {
        baseUrl = baseUrl.substring(0, baseUrl.length - 1);
      }

      final uri = Uri.tryParse('$baseUrl/ingest');
      if (uri == null) {
        return;
      }

      final payload = _buildPayload(postData);

      await _client.post(
        uri,
        headers: <String, String>{
          'Content-Type': 'application/json; charset=utf-8',
          'x-api-key': apiKey,
        },
        body: jsonEncode(payload),
      );
    } catch (error) {
      debugPrint('SecondBrain forwarding failed: $error');
    }
  }

  Map<String, Object?> _buildPayload(Map<String, dynamic> postData) {
    final authorName = postData['author_name']?.toString() ?? '';
    final summary = postData['summary']?.toString() ?? '';
    final postText = postData['post_text']?.toString() ?? '';
    final postUrl = postData['post_url']?.toString() ?? '';
    final category = postData['category']?.toString() ?? '';

    return <String, Object?>{
      'type': 'memo',
      'content': '# $authorName\n\n$summary\n\n---\n\n$postText\n\n[원본 링크]($postUrl)',
      'tags': <String>['linkedin', category.toLowerCase()],
      'file_name': null,
    };
  }
}
