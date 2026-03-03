import 'package:flutter/material.dart';
import 'package:flutter_card_swiper/flutter_card_swiper.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:noise_cancel_app/models/post.dart';
import 'package:noise_cancel_app/screens/swipe_screen.dart';
import 'package:noise_cancel_app/services/api_service.dart';
import 'package:noise_cancel_app/services/second_brain_service.dart';
import 'package:noise_cancel_app/widgets/post_card.dart';

Post _buildPost(
  int index, {
  String? note,
}) {
  return Post(
    id: 'post-$index',
    classificationId: 'cls-$index',
    platform: 'linkedin',
    authorName: 'Author $index',
    authorUrl: 'https://linkedin.com/in/author-$index',
    postUrl: 'https://linkedin.com/posts/post-$index',
    postText: 'Full post text $index',
    summary: 'Summary $index',
    category: 'Read',
    confidence: 0.9,
    reasoning: 'Relevant',
    classifiedAt: '2026-02-25T10:00:00+00:00',
    swipeStatus: 'pending',
    note: note,
  );
}

class FakeApiService extends ApiService {
  FakeApiService({
    required this.responsesByOffset,
    required this.events,
    Map<String, dynamic>? archiveResponse,
    this.archivedCount = 0,
  })  : _archiveResponse = archiveResponse ??
            <String, dynamic>{
              'classification_id': 'cls-0',
              'author_name': 'Author 0',
              'summary': 'Summary 0',
              'post_url': 'https://linkedin.com/posts/post-0',
              'post_text': 'Full post text 0',
              'category': 'Read',
            },
        super(baseUrl: 'http://localhost:8012');

  final Map<int, List<Post>> responsesByOffset;
  final List<String> events;
  final Map<String, dynamic> _archiveResponse;
  final int archivedCount;
  final List<int> requestedOffsets = <int>[];
  final List<String> archivedIds = <String>[];
  final List<String> deletedIds = <String>[];
  final List<Map<String, String>> noteSaves = <Map<String, String>>[];
  final List<Map<String, Object?>> pageRequests = <Map<String, Object?>>[];

  @override
  Future<List<Post>> fetchPosts({
    int limit = 20,
    int offset = 0,
    String category = 'Read',
    String swipeStatus = 'pending',
    String? platform,
    String? query,
  }) async {
    requestedOffsets.add(offset);
    return List<Post>.of(responsesByOffset[offset] ?? <Post>[]);
  }

  @override
  Future<Map<String, dynamic>> archivePost(String classificationId) async {
    events.add('archive');
    archivedIds.add(classificationId);
    return Map<String, dynamic>.of(_archiveResponse);
  }

  @override
  Future<void> deletePost(String classificationId) async {
    events.add('delete');
    deletedIds.add(classificationId);
  }

  @override
  Future<String?> saveNote(String classificationId, String noteText) async {
    events.add('save-note');
    noteSaves.add(<String, String>{
      'classificationId': classificationId,
      'note': noteText,
    });
    return noteText;
  }

  @override
  Future<PostPage> fetchPostPage({
    int limit = 20,
    int offset = 0,
    String category = 'Read',
    String swipeStatus = 'pending',
    String? platform,
    String? query,
  }) async {
    pageRequests.add(<String, Object?>{
      'limit': limit,
      'offset': offset,
      'category': category,
      'swipeStatus': swipeStatus,
      'platform': platform,
      'query': query,
    });
    return PostPage(
      posts: <Post>[],
      total: archivedCount,
      hasMore: false,
    );
  }
}

class FakeSecondBrainService extends SecondBrainService {
  FakeSecondBrainService({
    required this.enabled,
    required this.events,
  });

  final bool enabled;
  final List<String> events;
  final List<Map<String, dynamic>> forwardedPayloads = <Map<String, dynamic>>[];

  @override
  Future<bool> isEnabled() async => enabled;

  @override
  Future<void> forward(Map<String, dynamic> postData) async {
    events.add('forward');
    forwardedPayloads.add(Map<String, dynamic>.of(postData));
  }
}

Future<void> _pumpScreen(
  WidgetTester tester, {
  required FakeApiService apiService,
  required FakeSecondBrainService secondBrainService,
  CardSwiperController? controller,
  WidgetBuilder? settingsScreenBuilder,
  WidgetBuilder? archiveScreenBuilder,
}) async {
  await tester.pumpWidget(
    MaterialApp(
      theme: ThemeData(useMaterial3: false),
      home: SwipeScreen(
        apiService: apiService,
        secondBrainService: secondBrainService,
        swiperController: controller,
        settingsScreenBuilder: settingsScreenBuilder,
        archiveScreenBuilder: archiveScreenBuilder,
      ),
    ),
  );
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('defines SwipeScreen stateful UI with CardSwiper and PostCard',
      (tester) async {
    final events = <String>[];
    final apiService = FakeApiService(
      responsesByOffset: <int, List<Post>>{
        0: <Post>[_buildPost(0), _buildPost(1)],
      },
      events: events,
    );
    final secondBrainService =
        FakeSecondBrainService(enabled: true, events: events);

    await _pumpScreen(
      tester,
      apiService: apiService,
      secondBrainService: secondBrainService,
    );

    expect(find.byType(SwipeScreen), findsOneWidget);
    expect(find.byType(CardSwiper), findsOneWidget);
    expect(find.byType(PostCard), findsWidgets);
  });

  testWidgets('swipe left archives and forwards when SecondBrain is enabled',
      (tester) async {
    final controller = CardSwiperController();
    final events = <String>[];
    final archivePayload = <String, dynamic>{
      'classification_id': 'cls-0',
      'author_name': 'Author 0',
      'summary': 'Summary 0',
      'post_url': 'https://linkedin.com/posts/post-0',
      'post_text': 'Full post text 0',
      'category': 'Read',
    };
    final apiService = FakeApiService(
      responsesByOffset: <int, List<Post>>{
        0: <Post>[_buildPost(0)],
      },
      events: events,
      archiveResponse: archivePayload,
    );
    final secondBrainService =
        FakeSecondBrainService(enabled: true, events: events);

    await _pumpScreen(
      tester,
      apiService: apiService,
      secondBrainService: secondBrainService,
      controller: controller,
    );

    controller.swipe(CardSwiperDirection.left);
    await tester.pumpAndSettle();

    expect(apiService.archivedIds, <String>['cls-0']);
    expect(secondBrainService.forwardedPayloads,
        <Map<String, dynamic>>[archivePayload]);
    expect(events, <String>['archive', 'forward']);
  });

  testWidgets('swipe right deletes the post', (tester) async {
    final controller = CardSwiperController();
    final events = <String>[];
    final apiService = FakeApiService(
      responsesByOffset: <int, List<Post>>{
        0: <Post>[_buildPost(0)],
      },
      events: events,
    );
    final secondBrainService =
        FakeSecondBrainService(enabled: false, events: events);

    await _pumpScreen(
      tester,
      apiService: apiService,
      secondBrainService: secondBrainService,
      controller: controller,
    );

    controller.swipe(CardSwiperDirection.right);
    await tester.pumpAndSettle();

    expect(apiService.deletedIds, <String>['cls-0']);
    expect(secondBrainService.forwardedPayloads, isEmpty);
    expect(events, <String>['delete']);
  });

  testWidgets('prefetches next batch when fewer than five cards remain',
      (tester) async {
    final controller = CardSwiperController();
    final events = <String>[];
    final initialBatch = List<Post>.generate(6, _buildPost);
    final nextBatch = List<Post>.generate(2, (index) => _buildPost(index + 6));
    final apiService = FakeApiService(
      responsesByOffset: <int, List<Post>>{
        0: initialBatch,
        6: nextBatch,
      },
      events: events,
    );
    final secondBrainService =
        FakeSecondBrainService(enabled: false, events: events);

    await _pumpScreen(
      tester,
      apiService: apiService,
      secondBrainService: secondBrainService,
      controller: controller,
    );

    expect(apiService.requestedOffsets, <int>[0]);

    controller.swipe(CardSwiperDirection.right);
    await tester.pumpAndSettle();
    expect(apiService.requestedOffsets, <int>[0]);

    controller.swipe(CardSwiperDirection.right);
    await tester.pumpAndSettle();
    expect(apiService.requestedOffsets, <int>[0, 6]);
  });

  testWidgets('shows all-caught-up empty state when no posts are available',
      (tester) async {
    final events = <String>[];
    final apiService = FakeApiService(
      responsesByOffset: <int, List<Post>>{
        0: <Post>[],
      },
      events: events,
    );
    final secondBrainService =
        FakeSecondBrainService(enabled: false, events: events);

    await _pumpScreen(
      tester,
      apiService: apiService,
      secondBrainService: secondBrainService,
    );

    expect(find.text('All caught up!'), findsOneWidget);
  });

  testWidgets(
      'app bar shows title, archive button with count, and settings navigation',
      (tester) async {
    final events = <String>[];
    final apiService = FakeApiService(
      responsesByOffset: <int, List<Post>>{
        0: <Post>[_buildPost(0)],
      },
      events: events,
      archivedCount: 7,
    );
    final secondBrainService =
        FakeSecondBrainService(enabled: false, events: events);

    await _pumpScreen(
      tester,
      apiService: apiService,
      secondBrainService: secondBrainService,
      settingsScreenBuilder: (_) => const Scaffold(
        body: Center(child: Text('Mock Settings Screen')),
      ),
      archiveScreenBuilder: (_) => const Scaffold(
        body: Center(child: Text('Mock Archive Screen')),
      ),
    );

    expect(find.text('NoiseCancel'), findsOneWidget);
    expect(find.byKey(const Key('open-archive-button')), findsOneWidget);
    expect(find.byIcon(Icons.archive_outlined), findsOneWidget);
    expect(find.text('7'), findsOneWidget);
    expect(find.byIcon(Icons.settings), findsOneWidget);

    await tester.tap(find.byKey(const Key('open-archive-button')));
    await tester.pumpAndSettle();
    expect(find.text('Mock Archive Screen'), findsOneWidget);

    Navigator.of(tester.element(find.text('Mock Archive Screen'))).pop();
    await tester.pumpAndSettle();

    await tester.tap(find.byIcon(Icons.settings));
    await tester.pumpAndSettle();

    expect(find.text('Mock Settings Screen'), findsOneWidget);
  });

  testWidgets('pull-to-refresh resets posts and fetches from offset 0',
      (tester) async {
    final events = <String>[];
    final apiService = FakeApiService(
      responsesByOffset: <int, List<Post>>{
        0: <Post>[_buildPost(0), _buildPost(1)],
      },
      events: events,
    );
    final secondBrainService =
        FakeSecondBrainService(enabled: false, events: events);

    await _pumpScreen(
      tester,
      apiService: apiService,
      secondBrainService: secondBrainService,
    );

    expect(apiService.requestedOffsets, <int>[0]);
    expect(find.byType(PostCard), findsWidgets);

    // Pull to refresh via fling down on the scrollable area.
    await tester.fling(
      find.byType(SingleChildScrollView),
      const Offset(0, 300),
      1000,
    );
    await tester.pumpAndSettle();

    expect(apiService.requestedOffsets, <int>[0, 0]);
  });

  testWidgets('pull-to-refresh works in empty "All caught up!" state',
      (tester) async {
    final events = <String>[];
    final apiService = FakeApiService(
      responsesByOffset: <int, List<Post>>{
        0: <Post>[],
      },
      events: events,
    );
    final secondBrainService =
        FakeSecondBrainService(enabled: false, events: events);

    await _pumpScreen(
      tester,
      apiService: apiService,
      secondBrainService: secondBrainService,
    );

    expect(find.text('All caught up!'), findsOneWidget);

    // Update the fake to return posts on the next fetch.
    apiService.responsesByOffset[0] = <Post>[_buildPost(0)];

    await tester.fling(
      find.byType(SingleChildScrollView),
      const Offset(0, 300),
      1000,
    );
    await tester.pumpAndSettle();

    expect(find.byType(PostCard), findsWidgets);
    expect(find.text('All caught up!'), findsNothing);
  });

  testWidgets('long-press opens note sheet and saves note to server', (tester) async {
    final events = <String>[];
    final apiService = FakeApiService(
      responsesByOffset: <int, List<Post>>{
        0: <Post>[_buildPost(0)],
      },
      events: events,
    );
    final secondBrainService =
        FakeSecondBrainService(enabled: false, events: events);

    await _pumpScreen(
      tester,
      apiService: apiService,
      secondBrainService: secondBrainService,
    );

    await tester.longPress(find.byType(PostCard).first);
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('note-input-field')), findsOneWidget);
    expect(find.byKey(const Key('note-save-button')), findsOneWidget);

    await tester.enterText(
      find.byKey(const Key('note-input-field')),
      'Investigate this in Friday review',
    );
    await tester.tap(find.byKey(const Key('note-save-button')));
    await tester.pumpAndSettle();

    expect(
      apiService.noteSaves,
      <Map<String, String>>[
        <String, String>{
          'classificationId': 'cls-0',
          'note': 'Investigate this in Friday review',
        }
      ],
    );
    expect(find.text('📝'), findsOneWidget);
  });
}
