import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;

class WebhookService {
  WebhookService({
    FlutterSecureStorage? storage,
    http.Client? client,
  }) : _storage = storage ?? const FlutterSecureStorage(),
       _client = client ?? http.Client();

  static const String webhookUrlStorageKey = 'webhook_url';
  static const String webhookEnabledStorageKey = 'webhook_enabled';
  static const String webhookTemplateStorageKey = 'webhook_template';
  static const String defaultWebhookTemplate =
      '{"author": "{{author_name}}", "summary": "{{summary}}", "url": "{{post_url}}", "category": "{{category}}"}';
  static final RegExp _placeholderPattern = RegExp(r'{{\s*([a-zA-Z0-9_]+)\s*}}');

  final FlutterSecureStorage _storage;
  final http.Client _client;

  Future<bool> isEnabled() async {
    try {
      final rawValue = await _storage.read(key: webhookEnabledStorageKey);
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

      final webhookUrl = (await _storage.read(key: webhookUrlStorageKey))?.trim();
      if (webhookUrl == null || webhookUrl.isEmpty) {
        return;
      }

      final uri = Uri.tryParse(webhookUrl);
      if (uri == null) {
        return;
      }

      final payload = await _buildPayload(postData);

      await _client.post(
        uri,
        headers: const <String, String>{
          'Content-Type': 'application/json',
        },
        body: jsonEncode(payload),
      );
    } catch (error) {
      debugPrint('Webhook forwarding failed: $error');
    }
  }

  Future<Object?> _buildPayload(Map<String, dynamic> postData) async {
    final configuredTemplate = await _storage.read(key: webhookTemplateStorageKey);
    final template = configuredTemplate?.trim();
    final templateJson =
        (template == null || template.isEmpty) ? defaultWebhookTemplate : template;

    try {
      final parsedTemplate = jsonDecode(templateJson);
      return _applyTemplate(parsedTemplate, postData);
    } on FormatException catch (error) {
      debugPrint('Invalid webhook template, falling back to default template: ${error.message}');
      final fallbackTemplate = jsonDecode(defaultWebhookTemplate);
      return _applyTemplate(fallbackTemplate, postData);
    }
  }

  Object? _applyTemplate(Object? value, Map<String, dynamic> postData) {
    if (value is String) {
      return value.replaceAllMapped(_placeholderPattern, (match) {
        final key = match.group(1);
        if (key == null) {
          return '';
        }
        final replacement = postData[key];
        return replacement?.toString() ?? '';
      });
    }

    if (value is List<dynamic>) {
      return value
          .map((item) => _applyTemplate(item, postData))
          .toList(growable: false);
    }

    if (value is Map) {
      return value.map(
        (key, item) => MapEntry('$key', _applyTemplate(item, postData)),
      );
    }

    return value;
  }
}
