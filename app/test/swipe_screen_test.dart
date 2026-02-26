import 'package:flutter/material.dart';
import 'package:flutter_card_swiper/flutter_card_swiper.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:noise_cancel_app/models/post.dart';
import 'package:noise_cancel_app/screens/swipe_screen.dart';
import 'package:noise_cancel_app/services/api_service.dart';
import 'package:noise_cancel_app/services/webhook_service.dart';
import 'package:noise_cancel_app/widgets/post_card.dart';

Post _buildPost(int index) {
  return Post(
    id: 'post-$index',
    classificationId: 'cls-$index',
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
  );
}

class FakeApiService extends ApiService {
  FakeApiService({
    required this.responsesByOffset,
    required this.events,
    Map<String, dynamic>? archiveResponse,
  }) : _archiveResponse =
           archiveResponse ??
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
  final List<int> requestedOffsets = <int>[];
  final List<String> archivedIds = <String>[];
  final List<String> deletedIds = <String>[];

  @override
  Future<List<Post>> fetchPosts({
    int limit = 20,
    int offset = 0,
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
}

class FakeWebhookService extends WebhookService {
  FakeWebhookService({
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
  required FakeWebhookService webhookService,
  CardSwiperController? controller,
  WidgetBuilder? settingsScreenBuilder,
}) async {
  await tester.pumpWidget(
    MaterialApp(
      theme: ThemeData(useMaterial3: false),
      home: SwipeScreen(
        apiService: apiService,
        webhookService: webhookService,
        swiperController: controller,
        settingsScreenBuilder: settingsScreenBuilder,
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
    final webhookService = FakeWebhookService(enabled: true, events: events);

    await _pumpScreen(
      tester,
      apiService: apiService,
      webhookService: webhookService,
    );

    expect(find.byType(SwipeScreen), findsOneWidget);
    expect(find.byType(CardSwiper), findsOneWidget);
    expect(find.byType(PostCard), findsWidgets);
  });

  testWidgets('swipe left archives and forwards when webhook is enabled',
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
    final webhookService = FakeWebhookService(enabled: true, events: events);

    await _pumpScreen(
      tester,
      apiService: apiService,
      webhookService: webhookService,
      controller: controller,
    );

    controller.swipe(CardSwiperDirection.left);
    await tester.pumpAndSettle();

    expect(apiService.archivedIds, <String>['cls-0']);
    expect(webhookService.forwardedPayloads, <Map<String, dynamic>>[archivePayload]);
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
    final webhookService = FakeWebhookService(enabled: false, events: events);

    await _pumpScreen(
      tester,
      apiService: apiService,
      webhookService: webhookService,
      controller: controller,
    );

    controller.swipe(CardSwiperDirection.right);
    await tester.pumpAndSettle();

    expect(apiService.deletedIds, <String>['cls-0']);
    expect(webhookService.forwardedPayloads, isEmpty);
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
    final webhookService = FakeWebhookService(enabled: false, events: events);

    await _pumpScreen(
      tester,
      apiService: apiService,
      webhookService: webhookService,
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
    final webhookService = FakeWebhookService(enabled: false, events: events);

    await _pumpScreen(
      tester,
      apiService: apiService,
      webhookService: webhookService,
    );

    expect(find.text('All caught up!'), findsOneWidget);
  });

  testWidgets('app bar shows title and settings icon navigates to settings screen',
      (tester) async {
    final events = <String>[];
    final apiService = FakeApiService(
      responsesByOffset: <int, List<Post>>{
        0: <Post>[_buildPost(0)],
      },
      events: events,
    );
    final webhookService = FakeWebhookService(enabled: false, events: events);

    await _pumpScreen(
      tester,
      apiService: apiService,
      webhookService: webhookService,
      settingsScreenBuilder: (_) => const Scaffold(
        body: Center(child: Text('Mock Settings Screen')),
      ),
    );

    expect(find.text('NoiseCancel'), findsOneWidget);
    expect(find.byIcon(Icons.settings), findsOneWidget);

    await tester.tap(find.byIcon(Icons.settings));
    await tester.pumpAndSettle();

    expect(find.text('Mock Settings Screen'), findsOneWidget);
  });
}
