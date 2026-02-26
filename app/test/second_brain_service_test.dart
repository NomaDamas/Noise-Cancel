import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:noise_cancel_app/services/second_brain_service.dart';

void main() {
  setUp(() {
    FlutterSecureStorage.setMockInitialValues(<String, String>{});
  });

  test('forward posts to /ingest with x-api-key header and correct payload', () async {
    FlutterSecureStorage.setMockInitialValues(<String, String>{
      SecondBrainService.enabledStorageKey: 'true',
      SecondBrainService.urlStorageKey: 'https://brain.example.com',
      SecondBrainService.apiKeyStorageKey: 'test-key-123',
    });

    Uri? requestedUri;
    String? requestBody;
    Map<String, String>? requestHeaders;
    final client = MockClient((request) async {
      requestedUri = request.url;
      requestBody = request.body;
      requestHeaders = request.headers;
      return http.Response('ok', 200);
    });

    final service = SecondBrainService(client: client);
    await service.forward(<String, dynamic>{
      'author_name': 'Jane Doe',
      'summary': 'Useful insight',
      'post_url': 'https://linkedin.com/posts/abc',
      'post_text': 'Full post text here',
      'category': 'Read',
    });

    expect(requestedUri, isNotNull);
    expect(requestedUri.toString(), 'https://brain.example.com/ingest');
    expect(requestHeaders!['x-api-key'], 'test-key-123');
    expect(requestHeaders!['content-type'], 'application/json; charset=utf-8');

    final payload = jsonDecode(requestBody!) as Map<String, dynamic>;
    expect(payload['type'], 'memo');
    expect(payload['content'], contains('Jane Doe'));
    expect(payload['content'], contains('Useful insight'));
    expect(payload['content'], contains('Full post text here'));
    expect(payload['content'], contains('https://linkedin.com/posts/abc'));
    expect(payload['tags'], <String>['linkedin', 'read']);
    expect(payload['file_name'], isNull);
  });

  test('forward normalizes trailing slash in URL', () async {
    FlutterSecureStorage.setMockInitialValues(<String, String>{
      SecondBrainService.enabledStorageKey: 'true',
      SecondBrainService.urlStorageKey: 'https://brain.example.com/',
      SecondBrainService.apiKeyStorageKey: 'test-key-123',
    });

    Uri? requestedUri;
    final client = MockClient((request) async {
      requestedUri = request.url;
      return http.Response('ok', 200);
    });

    final service = SecondBrainService(client: client);
    await service.forward(<String, dynamic>{
      'author_name': 'Jane Doe',
      'summary': 'Useful insight',
      'post_url': 'https://linkedin.com/posts/abc',
      'post_text': 'Full post text here',
      'category': 'Read',
    });

    expect(requestedUri.toString(), 'https://brain.example.com/ingest');
  });

  test('forward does not post when disabled', () async {
    FlutterSecureStorage.setMockInitialValues(<String, String>{
      SecondBrainService.enabledStorageKey: 'false',
      SecondBrainService.urlStorageKey: 'https://brain.example.com',
      SecondBrainService.apiKeyStorageKey: 'test-key-123',
    });

    var callCount = 0;
    final client = MockClient((_) async {
      callCount += 1;
      return http.Response('ok', 200);
    });

    final service = SecondBrainService(client: client);
    await service.forward(<String, dynamic>{
      'author_name': 'Jane Doe',
      'summary': 'Useful insight',
      'post_url': 'https://linkedin.com/posts/abc',
      'post_text': 'Full post text here',
      'category': 'Read',
    });

    expect(callCount, 0);
  });

  test('forward does not post when API key is missing', () async {
    FlutterSecureStorage.setMockInitialValues(<String, String>{
      SecondBrainService.enabledStorageKey: 'true',
      SecondBrainService.urlStorageKey: 'https://brain.example.com',
    });

    var callCount = 0;
    final client = MockClient((_) async {
      callCount += 1;
      return http.Response('ok', 200);
    });

    final service = SecondBrainService(client: client);
    await service.forward(<String, dynamic>{
      'author_name': 'Jane Doe',
      'summary': 'Useful insight',
      'post_url': 'https://linkedin.com/posts/abc',
      'post_text': 'Full post text here',
      'category': 'Read',
    });

    expect(callCount, 0);
  });

  test('forward catches and swallows forwarding errors', () async {
    FlutterSecureStorage.setMockInitialValues(<String, String>{
      SecondBrainService.enabledStorageKey: 'true',
      SecondBrainService.urlStorageKey: 'https://brain.example.com',
      SecondBrainService.apiKeyStorageKey: 'test-key-123',
    });

    final client = MockClient((_) async {
      throw http.ClientException('network down');
    });

    final service = SecondBrainService(client: client);

    await expectLater(
      service.forward(<String, dynamic>{
        'author_name': 'Jane Doe',
        'summary': 'Useful insight',
        'post_url': 'https://linkedin.com/posts/abc',
        'post_text': 'Full post text here',
        'category': 'Read',
      }),
      completes,
    );
  });
}
