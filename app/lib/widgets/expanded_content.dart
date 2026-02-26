import 'package:flutter/material.dart';
import 'package:noise_cancel_app/models/post.dart';
import 'package:url_launcher/url_launcher.dart';

class ExpandedContent extends StatelessWidget {
  const ExpandedContent({
    super.key,
    required this.post,
  });

  final Post post;

  Future<void> _openAuthorProfile() async {
    final uri = Uri.tryParse(post.authorUrl);
    if (uri == null) {
      return;
    }

    await launchUrl(uri, mode: LaunchMode.externalApplication);
  }

  String _confidenceLabel() {
    final percentage = (post.confidence * 100).round();
    return '${post.category} $percentage%';
  }

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;

    return SafeArea(
      top: false,
      child: Container(
        decoration: const BoxDecoration(
          color: Color(0xFF1E1E1E),
          borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
        ),
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        post.authorName,
                        style: textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Chip(
                        visualDensity: VisualDensity.compact,
                        side: BorderSide.none,
                        backgroundColor: Colors.blue.withValues(alpha: 0.2),
                        label: Text(
                          _confidenceLabel(),
                          style: textTheme.labelSmall?.copyWith(
                            color: Colors.blue.shade100,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
                TextButton.icon(
                  onPressed: _openAuthorProfile,
                  icon: const Icon(Icons.open_in_new, size: 16),
                  label: const Text('LinkedIn'),
                ),
              ],
            ),
            const SizedBox(height: 12),
            const Divider(color: Colors.white24, height: 1),
            const SizedBox(height: 12),
            Expanded(
              child: SingleChildScrollView(
                child: Text(
                  post.postText,
                  style: textTheme.bodyMedium?.copyWith(height: 1.4),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
