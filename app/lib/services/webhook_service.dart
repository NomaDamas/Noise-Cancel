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

      await _client.post(
        uri,
        headers: const <String, String>{
          'Content-Type': 'application/json',
        },
        body: jsonEncode(postData),
      );
    } catch (error) {
      debugPrint('Webhook forwarding failed: $error');
    }
  }
}
