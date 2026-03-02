import 'package:flutter_test/flutter_test.dart';
import 'package:noise_cancel_app/models/post.dart';
import 'package:noise_cancel_app/services/share_service.dart';

Post _buildPost({
  String? note,
}) {
  return Post(
    id: 'post-1',
    classificationId: 'cls-1',
    platform: 'linkedin',
    authorName: 'Jane Doe',
    authorUrl: 'https://linkedin.com/in/jane',
    postUrl: 'https://linkedin.com/posts/post-1',
    postText: 'This is the full post body text',
    summary: 'Short AI summary',
    category: 'Read',
    confidence: 0.95,
    reasoning: 'Relevant to interests',
    classifiedAt: '2026-02-25T10:00:00+00:00',
    swipeStatus: 'pending',
    note: note,
  );
}

void main() {
  test('buildShareText formats author platform text and url', () {
    final text = buildShareText(_buildPost());

    expect(
      text,
      'Jane Doe (linkedin)\n\nThis is the full post body text\n\n'
      'https://linkedin.com/posts/post-1',
    );
  });

  test('buildShareText appends note when note exists', () {
    final text = buildShareText(
      _buildPost(note: 'Remember this for the next sprint'),
    );

    expect(
      text,
      'Jane Doe (linkedin)\n\nThis is the full post body text\n\n'
      'https://linkedin.com/posts/post-1\n\n'
      '💭 My note: Remember this for the next sprint',
    );
  });

  test('buildShareText does not append blank note', () {
    final text = buildShareText(_buildPost(note: '   '));

    expect(
      text,
      'Jane Doe (linkedin)\n\nThis is the full post body text\n\n'
      'https://linkedin.com/posts/post-1',
    );
  });
}
