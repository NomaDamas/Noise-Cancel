import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:noise_cancel_app/models/post.dart';
import 'package:noise_cancel_app/widgets/expanded_content.dart';
import 'package:noise_cancel_app/widgets/post_card.dart';

Post _buildPost({String? postUrl = 'https://linkedin.com/posts/post-1'}) {
  return Post(
    id: 'post-1',
    classificationId: 'cls-1',
    authorName: 'Jane Doe',
    authorUrl: 'https://linkedin.com/in/jane',
    postUrl: postUrl,
    postText: 'This is the full post body text',
    summary: 'Short AI summary',
    category: 'Read',
    confidence: 0.95,
    reasoning: 'Relevant to interests',
    classifiedAt: '2026-02-25T10:00:00+00:00',
    swipeStatus: 'pending',
  );
}

Future<void> _pumpPostCard(WidgetTester tester, Post post) async {
  await tester.pumpWidget(
    MaterialApp(
      theme: ThemeData(useMaterial3: false),
      home: Scaffold(
        body: Center(
          child: PostCard(post: post),
        ),
      ),
    ),
  );
}

void main() {
  testWidgets('renders author summary and both action buttons when link exists',
      (
    WidgetTester tester,
  ) async {
    await _pumpPostCard(tester, _buildPost());

    expect(find.text('Jane Doe'), findsOneWidget);
    expect(find.text('Short AI summary'), findsOneWidget);
    expect(find.text('더보기'), findsOneWidget);
    expect(find.text('Link'), findsOneWidget);
  });

  testWidgets('opens ExpandedContent bottom sheet with full post text', (
    WidgetTester tester,
  ) async {
    await _pumpPostCard(tester, _buildPost());

    await tester.tap(find.text('더보기'));
    await tester.pumpAndSettle();

    expect(find.byType(ExpandedContent), findsOneWidget);
    expect(find.text('This is the full post body text'), findsOneWidget);
  });

  testWidgets('hides Link button when postUrl is null',
      (WidgetTester tester) async {
    await _pumpPostCard(tester, _buildPost(postUrl: null));

    expect(find.text('더보기'), findsOneWidget);
    expect(find.text('Link'), findsNothing);
  });

  testWidgets('uses dark card color rounded corners and readable padding', (
    WidgetTester tester,
  ) async {
    await _pumpPostCard(tester, _buildPost());

    final card = tester.widget<Card>(find.byType(Card));
    expect(card.color, const Color(0xFF1E1E1E));

    final shape = card.shape as RoundedRectangleBorder;
    expect(shape.borderRadius, BorderRadius.circular(16));

    final paddings = tester.widgetList<Padding>(
      find.descendant(
        of: find.byType(PostCard),
        matching: find.byType(Padding),
      ),
    );

    final hasReadablePadding = paddings.any(
      (padding) => padding.padding == const EdgeInsets.all(16),
    );
    expect(hasReadablePadding, isTrue);
  });
}
