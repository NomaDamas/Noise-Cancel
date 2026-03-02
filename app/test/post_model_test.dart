import 'package:flutter_test/flutter_test.dart';
import 'package:noise_cancel_app/models/post.dart';

void main() {
  test('Post.fromJson maps snake_case API fields to model fields', () {
    final payload = <String, dynamic>{
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
    };

    final post = Post.fromJson(payload);

    expect(post.id, 'post-1');
    expect(post.classificationId, 'cls-1');
    expect(post.platform, 'linkedin');
    expect(post.authorName, 'Jane Doe');
    expect(post.authorUrl, 'https://linkedin.com/in/jane');
    expect(post.postUrl, 'https://linkedin.com/posts/post-1');
    expect(post.postText, 'A useful post');
    expect(post.summary, 'A short summary');
    expect(post.category, 'Read');
    expect(post.confidence, 0.95);
    expect(post.reasoning, 'Matches user interests');
    expect(post.classifiedAt, '2026-02-25T10:00:00+00:00');
    expect(post.swipeStatus, 'pending');
  });

  test('Post.fromJson accepts camelCase keys used in app code', () {
    final payload = <String, dynamic>{
      'id': 'post-2',
      'classificationId': 'cls-2',
      'platform': 'x',
      'authorName': 'John Doe',
      'authorUrl': 'https://linkedin.com/in/john',
      'postUrl': 'https://linkedin.com/posts/post-2',
      'postText': 'Another useful post',
      'summary': 'Another short summary',
      'category': 'Read',
      'confidence': 0.9,
      'reasoning': 'Strong relevance',
      'classifiedAt': '2026-02-25T11:00:00+00:00',
      'swipeStatus': 'archived',
    };

    final post = Post.fromJson(payload);

    expect(post.classificationId, 'cls-2');
    expect(post.platform, 'x');
    expect(post.authorName, 'John Doe');
    expect(post.swipeStatus, 'archived');
  });

  test('Post.fromJson accepts null post_url values', () {
    final payload = <String, dynamic>{
      'id': 'post-3',
      'classification_id': 'cls-3',
      'platform': 'rss',
      'author_name': 'No Link',
      'author_url': 'https://linkedin.com/in/no-link',
      'post_url': null,
      'post_text': 'Post without URL',
      'summary': 'Summary without URL',
      'category': 'Read',
      'confidence': 0.8,
      'reasoning': 'Still relevant',
      'classified_at': '2026-02-25T12:00:00+00:00',
      'swipe_status': 'pending',
    };

    final post = Post.fromJson(payload);

    expect(post.postUrl, isNull);
  });

  test('Post.fromJson throws when platform field is missing', () {
    final payload = <String, dynamic>{
      'id': 'post-4',
      'classification_id': 'cls-4',
      'author_name': 'Missing Platform',
      'author_url': 'https://example.com/author',
      'post_url': 'https://example.com/posts/post-4',
      'post_text': 'Missing platform field',
      'summary': 'Summary',
      'category': 'Read',
      'confidence': 0.7,
      'reasoning': 'Reasoning',
      'classified_at': '2026-02-25T12:00:00+00:00',
      'swipe_status': 'pending',
    };

    expect(() => Post.fromJson(payload), throwsFormatException);
  });
}
