import 'package:flutter/material.dart';
import 'package:noise_cancel_app/models/post.dart';
import 'package:noise_cancel_app/widgets/expanded_content.dart';
import 'package:url_launcher/url_launcher.dart';

class PostCard extends StatelessWidget {
  const PostCard({
    super.key,
    required this.post,
    this.horizontalOffsetPercentage = 0,
  });

  final Post post;
  final int horizontalOffsetPercentage;

  static const _saveColor = Color(0xFF4CAF50);
  static const _dropColor = Color(0xFFEF5350);

  void _showExpandedContent(BuildContext context) {
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: const Color(0xFF1E1E1E),
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (_) => SizedBox(
        height: MediaQuery.of(context).size.height * 0.85,
        child: ExpandedContent(post: post),
      ),
    );
  }

  Future<void> _openPostUrl() async {
    final url = post.postUrl;
    if (url == null || url.isEmpty) {
      return;
    }

    final uri = Uri.tryParse(url);
    if (uri == null) {
      return;
    }

    await launchUrl(uri, mode: LaunchMode.externalApplication);
  }

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    final opacity = (horizontalOffsetPercentage.abs() / 100).clamp(0.0, 1.0);

    final overlayColor = horizontalOffsetPercentage < 0 ? _saveColor : _dropColor;
    return Card(
      color: const Color(0xFF1E1E1E),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: opacity > 0
            ? BorderSide(
                color: overlayColor.withOpacity(opacity),
                width: 2,
              )
            : BorderSide.none,
      ),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              post.authorName,
              style: textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.bold,
              ),
            ),
            const Divider(color: Colors.white12),
            Text(
              post.summary,
              style: textTheme.bodyLarge?.copyWith(height: 1.5),
            ),
            const SizedBox(height: 16),
            SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                onPressed: () => _showExpandedContent(context),
                icon: const Icon(Icons.expand_more),
                label: const Text('더보기'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: Colors.white70,
                  side: const BorderSide(color: Colors.white24),
                  shape: const StadiumBorder(),
                ),
              ),
            ),
            if (post.postUrl != null) ...[
              const SizedBox(height: 8),
              SizedBox(
                width: double.infinity,
                child: OutlinedButton.icon(
                  onPressed: _openPostUrl,
                  icon: const Icon(Icons.open_in_new),
                  label: const Text('LinkedIn에서 보기'),
                  style: OutlinedButton.styleFrom(
                    foregroundColor: Colors.white70,
                    side: const BorderSide(color: Colors.white24),
                    shape: const StadiumBorder(),
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
