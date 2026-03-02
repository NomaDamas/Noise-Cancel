import 'package:noise_cancel_app/models/post.dart';
import 'package:share_plus/share_plus.dart';

String buildShareText(Post post) {
  final postUrl = post.postUrl ?? '';
  final buffer = StringBuffer(
    '${post.authorName} (${post.platform})\n\n${post.postText}\n\n$postUrl',
  );

  final noteText = post.note?.trim();
  if (noteText != null && noteText.isNotEmpty) {
    buffer.write('\n\n💭 My note: $noteText');
  }
  return buffer.toString();
}

abstract class ShareService {
  Future<void> sharePost(Post post);
}

class NativeShareService implements ShareService {
  const NativeShareService();

  @override
  Future<void> sharePost(Post post) {
    return SharePlus.instance.share(
      ShareParams(text: buildShareText(post)),
    );
  }
}
