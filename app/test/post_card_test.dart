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

Future<void> _pumpPostCard(
  WidgetTester tester,
  Post post, {
  int horizontalOffsetPercentage = 0,
}) async {
  await tester.pumpWidget(
    MaterialApp(
      theme: ThemeData(useMaterial3: false),
      home: Scaffold(
        body: Center(
          child: PostCard(
            post: post,
            horizontalOffsetPercentage: horizontalOffsetPercentage,
          ),
        ),
      ),
    ),
  );
}

TextSpan _findExpandedBodySpan(WidgetTester tester, String postText) {
  final richTextFinder = find.byWidgetPredicate((widget) {
    if (widget is! RichText) {
      return false;
    }

    final span = widget.text;
    return span is TextSpan && span.toPlainText() == postText;
  });

  expect(richTextFinder, findsOneWidget);
  final richText = tester.widget<RichText>(richTextFinder);
  return richText.text as TextSpan;
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
    expect(find.text('LinkedIn에서 보기'), findsOneWidget);
  });

  testWidgets('opens ExpandedContent bottom sheet with full post text', (
    WidgetTester tester,
  ) async {
    const postText = 'This is the full post body text';
    await _pumpPostCard(tester, _buildPost());

    await tester.tap(find.text('더보기'));
    await tester.pumpAndSettle();

    expect(find.byType(ExpandedContent), findsOneWidget);
    expect(_findExpandedBodySpan(tester, postText).toPlainText(), postText);
  });

  testWidgets('hides LinkedIn button when postUrl is null',
      (WidgetTester tester) async {
    await _pumpPostCard(tester, _buildPost(postUrl: null));

    expect(find.text('더보기'), findsOneWidget);
    expect(find.text('LinkedIn에서 보기'), findsNothing);
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
      (padding) => padding.padding == const EdgeInsets.all(20),
    );
    expect(hasReadablePadding, isTrue);
  });

  testWidgets('shows green border when dragged left', (
    WidgetTester tester,
  ) async {
    await _pumpPostCard(tester, _buildPost(), horizontalOffsetPercentage: -50);

    final card = tester.widget<Card>(find.byType(Card));
    final shape = card.shape as RoundedRectangleBorder;
    expect(shape.side.color, const Color(0xFF4CAF50).withValues(alpha: 0.5));
    expect(shape.side.width, 2);
  });

  testWidgets('shows red border when dragged right', (
    WidgetTester tester,
  ) async {
    await _pumpPostCard(tester, _buildPost(), horizontalOffsetPercentage: 50);

    final card = tester.widget<Card>(find.byType(Card));
    final shape = card.shape as RoundedRectangleBorder;
    expect(shape.side.color, const Color(0xFFEF5350).withValues(alpha: 0.5));
    expect(shape.side.width, 2);
  });

  testWidgets('shows no border when offset is zero', (
    WidgetTester tester,
  ) async {
    await _pumpPostCard(tester, _buildPost(), horizontalOffsetPercentage: 0);

    final card = tester.widget<Card>(find.byType(Card));
    final shape = card.shape as RoundedRectangleBorder;
    expect(shape.side, BorderSide.none);
  });

  testWidgets('buttons are vertically stacked with outlined style', (
    WidgetTester tester,
  ) async {
    await _pumpPostCard(tester, _buildPost());

    expect(find.text('더보기'), findsOneWidget);
    expect(find.text('LinkedIn에서 보기'), findsOneWidget);
    expect(find.byType(OutlinedButton), findsNWidgets(2));
  });
}
