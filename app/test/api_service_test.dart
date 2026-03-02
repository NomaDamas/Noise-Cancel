import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:noise_cancel_app/services/api_service.dart';

void main() {
  setUp(() {
    FlutterSecureStorage.setMockInitialValues(<String, String>{});
  });

  test('fetchPosts reads server URL from secure storage and parses posts',
      () async {
    FlutterSecureStorage.setMockInitialValues(<String, String>{
      'server_url': 'http://localhost:9000/',
    });

    Uri? requestedUri;
    final client = MockClient((request) async {
      requestedUri = request.url;
      return http.Response(
        jsonEncode(<String, dynamic>{
          'posts': [
            <String, dynamic>{
              'id': 'post-1',
              'classification_id': 'cls-1',
              'platform': 'linkedin',
              'author_name': 'Jane Doe',
              'author_url': 'https://linkedin.com/in/jane',
              'post_url': 'https://linkedin.com/posts/post-1',
              'post_text': 'A useful post',
              'summary': 'A short summary',
              'category': 'Read',
              'confidence': 0.95,
              'reasoning': 'Matches user interests',
              'classified_at': '2026-02-25T10:00:00+00:00',
              'swipe_status': 'pending',
            },
          ],
          'total': 1,
          'has_more': false,
        }),
        200,
      );
    });

    final service = ApiService(client: client);
    final posts = await service.fetchPosts(limit: 5, offset: 10);

    expect(requestedUri, isNotNull);
    expect(requestedUri.toString(),
        'http://localhost:9000/api/posts?limit=5&offset=10');
    expect(posts, hasLength(1));
    expect(posts.first.classificationId, 'cls-1');
  });

  test('fetchPosts uses provided baseUrl when configured', () async {
    FlutterSecureStorage.setMockInitialValues(<String, String>{
      'server_url': 'http://from-storage:9999',
    });

    Uri? requestedUri;
    final client = MockClient((request) async {
      requestedUri = request.url;
      return http.Response(
        jsonEncode(<String, dynamic>{
          'posts': <Map<String, dynamic>>[],
          'total': 0,
          'has_more': false,
        }),
        200,
      );
    });

    final service =
        ApiService(baseUrl: 'http://configured:8012', client: client);
    await service.fetchPosts();

    expect(requestedUri, isNotNull);
    expect(requestedUri.toString(),
        'http://configured:8012/api/posts?limit=20&offset=0');
  });

  test('archivePost returns the full post data payload', () async {
    Uri? requestedUri;
    final client = MockClient((request) async {
      requestedUri = request.url;
      return http.Response(
        jsonEncode(<String, dynamic>{
          'status': 'archived',
          'classification_id': 'cls-1',
          'author_name': 'Jane Doe',
          'summary': 'A short summary',
          'post_url': 'https://linkedin.com/posts/post-1',
          'post_text': 'A useful post',
          'category': 'Read',
        }),
        200,
      );
    });

    final service =
        ApiService(baseUrl: 'http://localhost:8012', client: client);
    final payload = await service.archivePost('cls-1');

    expect(requestedUri, isNotNull);
    expect(requestedUri.toString(),
        'http://localhost:8012/api/posts/cls-1/archive');
    expect(payload['author_name'], 'Jane Doe');
    expect(payload['category'], 'Read');
  });

  test('deletePost calls delete endpoint and completes on success', () async {
    Uri? requestedUri;
    final client = MockClient((request) async {
      requestedUri = request.url;
      return http.Response(
        jsonEncode(<String, dynamic>{
          'status': 'deleted',
          'classification_id': 'cls-1',
        }),
        200,
      );
    });

    final service =
        ApiService(baseUrl: 'http://localhost:8012', client: client);
    await service.deletePost('cls-1');

    expect(requestedUri, isNotNull);
    expect(requestedUri.toString(),
        'http://localhost:8012/api/posts/cls-1/delete');
  });

  test('fetchPosts throws ApiServiceException on non-200 response', () async {
    final client = MockClient((_) async => http.Response('server error', 500));
    final service =
        ApiService(baseUrl: 'http://localhost:8012', client: client);

    await expectLater(
      service.fetchPosts(),
      throwsA(isA<ApiServiceException>()),
    );
  });

  test('archivePost throws ApiServiceException on http errors', () async {
    final client = MockClient((_) async => http.Response('not found', 404));
    final service =
        ApiService(baseUrl: 'http://localhost:8012', client: client);

    await expectLater(
      service.archivePost('missing'),
      throwsA(isA<ApiServiceException>()),
    );
  });

  test('deletePost throws ApiServiceException on network exceptions', () async {
    final client =
        MockClient((_) async => throw http.ClientException('network error'));
    final service =
        ApiService(baseUrl: 'http://localhost:8012', client: client);

    await expectLater(
      service.deletePost('cls-1'),
      throwsA(isA<ApiServiceException>()),
    );
  });

  test('includes X-API-Key header in requests when configured', () async {
    FlutterSecureStorage.setMockInitialValues(<String, String>{
      ApiService.serverUrlStorageKey: 'http://localhost:8012',
      ApiService.apiKeyStorageKey: 'test-api-key',
    });

    final observedHeaders = <Map<String, String>>[];
    final client = MockClient((request) async {
      observedHeaders.add(Map<String, String>.from(request.headers));

      if (request.url.path.endsWith('/archive')) {
        return http.Response(
          jsonEncode(<String, dynamic>{
            'status': 'archived',
          }),
          200,
        );
      }
      if (request.url.path.endsWith('/delete')) {
        return http.Response(
          jsonEncode(<String, dynamic>{
            'status': 'deleted',
          }),
          200,
        );
      }
      return http.Response(
        jsonEncode(<String, dynamic>{
          'posts': <Map<String, dynamic>>[],
          'total': 0,
          'has_more': false,
        }),
        200,
      );
    });

    final service = ApiService(client: client);
    await service.fetchPosts();
    await service.archivePost('cls-1');
    await service.deletePost('cls-1');

    expect(observedHeaders, hasLength(3));
    for (final headers in observedHeaders) {
      expect(
        headers['X-API-Key'] ?? headers['x-api-key'],
        'test-api-key',
      );
    }
  });
}
