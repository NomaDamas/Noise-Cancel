import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:noise_cancel_app/models/post.dart';
import 'package:noise_cancel_app/widgets/expanded_content.dart';

Post _buildPost({double confidence = 0.95}) {
  return Post(
    id: 'post-1',
    classificationId: 'cls-1',
    authorName: 'Jane Doe',
    authorUrl: 'https://linkedin.com/in/jane',
    postUrl: 'https://linkedin.com/posts/post-1',
    postText: 'This is the full post body text',
    summary: 'Short AI summary',
    category: 'Read',
    confidence: confidence,
    reasoning: 'Relevant to interests',
    classifiedAt: '2026-02-25T10:00:00+00:00',
    swipeStatus: 'pending',
  );
}

Future<void> _pumpExpandedContent(WidgetTester tester, Post post) async {
  await tester.pumpWidget(
    MaterialApp(
      theme: ThemeData.dark(),
      home: Scaffold(
        body: ExpandedContent(post: post),
      ),
    ),
  );
}

void main() {
  testWidgets('shows author info with LinkedIn profile action',
      (WidgetTester tester) async {
    await _pumpExpandedContent(tester, _buildPost());

    expect(find.text('Jane Doe'), findsOneWidget);
    expect(find.text('LinkedIn'), findsOneWidget);
  });

  testWidgets('shows full post text inside scrollable area',
      (WidgetTester tester) async {
    await _pumpExpandedContent(tester, _buildPost());

    expect(find.byType(SingleChildScrollView), findsOneWidget);
    expect(find.text('This is the full post body text'), findsOneWidget);
  });

  testWidgets('shows category and confidence badge text',
      (WidgetTester tester) async {
    await _pumpExpandedContent(tester, _buildPost(confidence: 0.95));

    expect(find.byType(Chip), findsOneWidget);
    expect(find.text('Read 95%'), findsOneWidget);
  });

  testWidgets('uses dark card-style surface color',
      (WidgetTester tester) async {
    await _pumpExpandedContent(tester, _buildPost());

    final containers = tester.widgetList<Container>(find.byType(Container));
    final hasDarkContainer = containers.any((container) {
      return container.decoration is BoxDecoration &&
          (container.decoration! as BoxDecoration).color ==
              const Color(0xFF1E1E1E);
    });

    expect(hasDarkContainer, isTrue);
  });
}
