import 'package:flutter/material.dart';
import 'package:flutter/gestures.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:noise_cancel_app/models/post.dart';
import 'package:noise_cancel_app/widgets/expanded_content.dart';

Post _buildPost({
  double confidence = 0.95,
  String postText = 'This is the full post body text',
}) {
  return Post(
    id: 'post-1',
    classificationId: 'cls-1',
    platform: 'linkedin',
    authorName: 'Jane Doe',
    authorUrl: 'https://linkedin.com/in/jane',
    postUrl: 'https://linkedin.com/posts/post-1',
    postText: postText,
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

TextSpan _findBodyTextSpan(WidgetTester tester, String postText) {
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
  testWidgets('shows author info with LinkedIn profile action',
      (WidgetTester tester) async {
    await _pumpExpandedContent(tester, _buildPost());

    expect(find.text('Jane Doe'), findsOneWidget);
    expect(find.text('LinkedIn'), findsOneWidget);
  });

  testWidgets('shows full post text inside scrollable area',
      (WidgetTester tester) async {
    const postText = 'This is the full post body text';
    await _pumpExpandedContent(tester, _buildPost(postText: postText));

    expect(find.byType(SingleChildScrollView), findsOneWidget);
    expect(_findBodyTextSpan(tester, postText).toPlainText(), postText);
  });

  testWidgets(
      'renders URL segments as clickable spans and keeps plain text untouched',
      (WidgetTester tester) async {
    const firstUrl = 'https://example.com/path/to/article?foo=bar#summary';
    const secondUrl = 'http://docs.example.org/start?ref=feed#top';
    const postText = 'Before $firstUrl between $secondUrl after';

    await _pumpExpandedContent(
      tester,
      _buildPost(postText: postText),
    );

    final bodySpan = _findBodyTextSpan(tester, postText);
    final spans = bodySpan.children!.whereType<TextSpan>().toList();

    expect(spans.length, 5);
    expect(spans[0].text, 'Before ');
    expect(spans[0].recognizer, isNull);
    expect(spans[1].text, firstUrl);
    expect(spans[1].recognizer, isA<TapGestureRecognizer>());
    expect(spans[1].style?.decoration, TextDecoration.underline);
    expect(spans[2].text, ' between ');
    expect(spans[2].recognizer, isNull);
    expect(spans[3].text, secondUrl);
    expect(spans[3].recognizer, isA<TapGestureRecognizer>());
    expect(spans[3].style?.decoration, TextDecoration.underline);
    expect(spans[4].text, ' after');
    expect(spans[4].recognizer, isNull);
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
