import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:noise_cancel_app/models/post.dart';
import 'package:noise_cancel_app/screens/archive_screen.dart';
import 'package:noise_cancel_app/services/api_service.dart';
import 'package:noise_cancel_app/widgets/expanded_content.dart';
import 'package:noise_cancel_app/widgets/post_card.dart';

Post _buildPost(
  int index, {
  String platform = 'linkedin',
  String? postText,
}) {
  return Post(
    id: 'post-$index',
    classificationId: 'cls-$index',
    platform: platform,
    authorName: 'Author $index',
    authorUrl: 'https://example.com/authors/$index',
    postUrl: 'https://example.com/posts/$index',
    postText: postText ?? 'Archived post text $index',
    summary: 'Summary $index',
    category: 'Read',
    confidence: 0.95,
    reasoning: 'Relevant to interests',
    classifiedAt: '2026-02-25T10:00:00+00:00',
    swipeStatus: 'archived',
  );
}

class FakeArchiveApiService extends ApiService {
  FakeArchiveApiService({
    required this.onFetch,
  }) : super(baseUrl: 'http://localhost:8012');

  final PostPage Function({
    required int limit,
    required int offset,
    required String category,
    required String swipeStatus,
    String? platform,
    String? query,
  }) onFetch;

  final List<Map<String, Object?>> requests = <Map<String, Object?>>[];

  @override
  Future<PostPage> fetchPostPage({
    int limit = 20,
    int offset = 0,
    String category = 'Read',
    String swipeStatus = 'pending',
    String? platform,
    String? query,
  }) async {
    requests.add(<String, Object?>{
      'limit': limit,
      'offset': offset,
      'category': category,
      'swipeStatus': swipeStatus,
      'platform': platform,
      'query': query,
    });
    return onFetch(
      limit: limit,
      offset: offset,
      category: category,
      swipeStatus: swipeStatus,
      platform: platform,
      query: query,
    );
  }
}

Future<void> _pumpArchiveScreen(
  WidgetTester tester, {
  required FakeArchiveApiService apiService,
}) async {
  await tester.pumpWidget(
    MaterialApp(
      theme: ThemeData(useMaterial3: false),
      home: ArchiveScreen(apiService: apiService),
    ),
  );
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('renders 저장고 app bar, search field, chips, and compact list',
      (tester) async {
    final apiService = FakeArchiveApiService(
      onFetch: ({
        required limit,
        required offset,
        required category,
        required swipeStatus,
        String? platform,
        String? query,
      }) {
        return PostPage(
          posts: <Post>[_buildPost(0, platform: 'reddit')],
          total: 1,
          hasMore: false,
        );
      },
    );

    await _pumpArchiveScreen(tester, apiService: apiService);

    expect(find.text('저장고'), findsOneWidget);
    expect(find.byKey(const Key('archive-search-field')), findsOneWidget);
    expect(find.byKey(const Key('archive-filter-all')), findsOneWidget);
    expect(find.byKey(const Key('archive-filter-linkedin')), findsOneWidget);
    expect(find.byKey(const Key('archive-filter-x')), findsOneWidget);
    expect(find.byKey(const Key('archive-filter-threads')), findsOneWidget);
    expect(find.byKey(const Key('archive-filter-reddit')), findsOneWidget);
    expect(find.byKey(const Key('archive-filter-rss')), findsOneWidget);

    expect(find.byType(PostCard), findsNothing);
    expect(find.text('Author 0'), findsOneWidget);
    expect(find.textContaining('Archived post text 0'), findsOneWidget);
    expect(find.text('2026-02-25'), findsOneWidget);
    expect(
        find.byKey(const Key('archive-platform-badge-cls-0')), findsOneWidget);
    expect(apiService.requests.first['swipeStatus'], 'archived');
  });

  testWidgets('debounces search input by 300ms before triggering request',
      (tester) async {
    final apiService = FakeArchiveApiService(
      onFetch: ({
        required limit,
        required offset,
        required category,
        required swipeStatus,
        String? platform,
        String? query,
      }) {
        return PostPage(
          posts: <Post>[_buildPost(0, postText: query ?? 'seed')],
          total: 1,
          hasMore: false,
        );
      },
    );

    await _pumpArchiveScreen(tester, apiService: apiService);
    expect(apiService.requests, hasLength(1));

    await tester.enterText(
      find.byKey(const Key('archive-search-field')),
      'flutter',
    );
    await tester.pump(const Duration(milliseconds: 299));
    expect(apiService.requests, hasLength(1));

    await tester.pump(const Duration(milliseconds: 1));
    await tester.pumpAndSettle();
    expect(apiService.requests, hasLength(2));
    expect(apiService.requests.last['query'], 'flutter');
  });

  testWidgets('applies platform filter and expands item with ExpandedContent',
      (tester) async {
    final apiService = FakeArchiveApiService(
      onFetch: ({
        required limit,
        required offset,
        required category,
        required swipeStatus,
        String? platform,
        String? query,
      }) {
        return PostPage(
          posts: <Post>[_buildPost(0, platform: platform ?? 'linkedin')],
          total: 1,
          hasMore: false,
        );
      },
    );

    await _pumpArchiveScreen(tester, apiService: apiService);

    await tester.tap(find.byKey(const Key('archive-filter-reddit')));
    await tester.pumpAndSettle();
    expect(apiService.requests.last['platform'], 'reddit');

    await tester.tap(find.byKey(const Key('archive-item-cls-0')));
    await tester.pumpAndSettle();
    expect(find.byType(ExpandedContent), findsOneWidget);
  });

  testWidgets('loads next page on scroll when more archived items exist',
      (tester) async {
    final apiService = FakeArchiveApiService(
      onFetch: ({
        required limit,
        required offset,
        required category,
        required swipeStatus,
        String? platform,
        String? query,
      }) {
        if (offset == 0) {
          return PostPage(
            posts: List<Post>.generate(20, _buildPost),
            total: 21,
            hasMore: true,
          );
        }
        return PostPage(
          posts: <Post>[_buildPost(20)],
          total: 21,
          hasMore: false,
        );
      },
    );

    await _pumpArchiveScreen(tester, apiService: apiService);
    expect(
      apiService.requests.map((request) => request['offset']),
      contains(0),
    );

    await tester.fling(
      find.byKey(const Key('archive-post-list')),
      const Offset(0, -1500),
      2000,
    );
    await tester.pumpAndSettle();

    expect(
      apiService.requests.map((request) => request['offset']),
      contains(20),
    );
  });
}
