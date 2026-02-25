import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:noise_cancel_app/services/webhook_service.dart';

void main() {
  setUp(() {
    FlutterSecureStorage.setMockInitialValues(<String, String>{});
  });

  test('forward uses default template when webhook_template is not configured', () async {
    FlutterSecureStorage.setMockInitialValues(<String, String>{
      WebhookService.webhookEnabledStorageKey: 'true',
      WebhookService.webhookUrlStorageKey: 'https://hooks.example.com/default',
    });

    Uri? requestedUri;
    String? requestBody;
    final client = MockClient((request) async {
      requestedUri = request.url;
      requestBody = request.body;
      return http.Response('ok', 200);
    });

    final service = WebhookService(client: client);
    await service.forward(<String, dynamic>{
      'author_name': 'Jane Doe',
      'summary': 'Useful insight',
      'post_url': 'https://linkedin.com/posts/abc',
      'category': 'Read',
      'post_text': 'Long text that should not be sent by default',
    });

    expect(requestedUri, isNotNull);
    expect(requestedUri.toString(), 'https://hooks.example.com/default');
    expect(
      jsonDecode(requestBody!) as Map<String, dynamic>,
      <String, dynamic>{
        'author': 'Jane Doe',
        'summary': 'Useful insight',
        'url': 'https://linkedin.com/posts/abc',
        'category': 'Read',
      },
    );
  });

  test('forward substitutes placeholders from custom webhook template', () async {
    FlutterSecureStorage.setMockInitialValues(<String, String>{
      WebhookService.webhookEnabledStorageKey: 'true',
      WebhookService.webhookUrlStorageKey: 'https://hooks.example.com/custom',
      WebhookService.webhookTemplateStorageKey: jsonEncode(<String, dynamic>{
        'headline': 'From {{author_name}}',
        'url': '{{post_url}}',
        'topic': '{{category}}',
        'confidence': '{{confidence}}',
        'missing': '{{not_present}}',
      }),
    });

    String? requestBody;
    final client = MockClient((request) async {
      requestBody = request.body;
      return http.Response('ok', 200);
    });

    final service = WebhookService(client: client);
    await service.forward(<String, dynamic>{
      'author_name': 'Jane Doe',
      'post_url': 'https://linkedin.com/posts/abc',
      'category': 'Read',
      'confidence': 0.95,
    });

    expect(
      jsonDecode(requestBody!) as Map<String, dynamic>,
      <String, dynamic>{
        'headline': 'From Jane Doe',
        'url': 'https://linkedin.com/posts/abc',
        'topic': 'Read',
        'confidence': '0.95',
        'missing': '',
      },
    );
  });

  test('forward returns without posting when webhook is disabled', () async {
    FlutterSecureStorage.setMockInitialValues(<String, String>{
      WebhookService.webhookEnabledStorageKey: 'false',
      WebhookService.webhookUrlStorageKey: 'https://hooks.example.com/disabled',
    });

    var callCount = 0;
    final client = MockClient((_) async {
      callCount += 1;
      return http.Response('ok', 200);
    });

    final service = WebhookService(client: client);
    await service.forward(<String, dynamic>{
      'author_name': 'Jane Doe',
      'summary': 'Useful insight',
      'post_url': 'https://linkedin.com/posts/abc',
      'category': 'Read',
    });

    expect(callCount, 0);
  });

  test('forward catches and swallows forwarding errors', () async {
    FlutterSecureStorage.setMockInitialValues(<String, String>{
      WebhookService.webhookEnabledStorageKey: 'true',
      WebhookService.webhookUrlStorageKey: 'https://hooks.example.com/error',
    });

    final client = MockClient((_) async {
      throw http.ClientException('network down');
    });

    final service = WebhookService(client: client);

    await expectLater(
      service.forward(<String, dynamic>{
        'author_name': 'Jane Doe',
        'summary': 'Useful insight',
        'post_url': 'https://linkedin.com/posts/abc',
        'category': 'Read',
      }),
      completes,
    );
  });
}
