import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:noise_cancel_app/models/post.dart';
import 'package:url_launcher/url_launcher.dart';

class ExpandedContent extends StatefulWidget {
  const ExpandedContent({
    super.key,
    required this.post,
  });

  final Post post;

  @override
  State<ExpandedContent> createState() => _ExpandedContentState();
}

class _ExpandedContentState extends State<ExpandedContent> {
  static final RegExp _urlPattern = RegExp(
    r'https?:\/\/[^\s]+',
    caseSensitive: false,
  );

  final List<TapGestureRecognizer> _urlRecognizers = <TapGestureRecognizer>[];

  @override
  void dispose() {
    _disposeUrlRecognizers();
    super.dispose();
  }

  void _disposeUrlRecognizers() {
    for (final recognizer in _urlRecognizers) {
      recognizer.dispose();
    }
    _urlRecognizers.clear();
  }

  Future<void> _openAuthorProfile() async {
    final uri = Uri.tryParse(widget.post.authorUrl);
    if (uri == null) {
      return;
    }

    await launchUrl(uri, mode: LaunchMode.externalApplication);
  }

  Future<void> _openPostUrl(String url) async {
    final uri = Uri.tryParse(url);
    if (uri == null) {
      return;
    }

    await launchUrl(uri, mode: LaunchMode.externalApplication);
  }

  List<TextSpan> _buildPostTextSpans({
    required String postText,
    required TextStyle bodyStyle,
    required TextStyle linkStyle,
  }) {
    _disposeUrlRecognizers();

    final spans = <TextSpan>[];
    var start = 0;

    for (final match in _urlPattern.allMatches(postText)) {
      if (match.start > start) {
        spans.add(
          TextSpan(
            text: postText.substring(start, match.start),
            style: bodyStyle,
          ),
        );
      }

      final url = match.group(0)!;
      final recognizer = TapGestureRecognizer()
        ..onTap = () {
          _openPostUrl(url);
        };
      _urlRecognizers.add(recognizer);

      spans.add(
        TextSpan(
          text: url,
          style: linkStyle,
          recognizer: recognizer,
        ),
      );
      start = match.end;
    }

    if (start < postText.length) {
      spans.add(
        TextSpan(
          text: postText.substring(start),
          style: bodyStyle,
        ),
      );
    }

    if (spans.isEmpty) {
      spans.add(TextSpan(text: postText, style: bodyStyle));
    }

    return spans;
  }

  String _confidenceLabel() {
    final percentage = (widget.post.confidence * 100).round();
    return '${widget.post.category} $percentage%';
  }

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    final bodyStyle = textTheme.bodyMedium?.copyWith(height: 1.4) ??
        const TextStyle(height: 1.4);
    final linkStyle = bodyStyle.copyWith(
      color: Colors.blue.shade300,
      decoration: TextDecoration.underline,
    );

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
                        widget.post.authorName,
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
                child: RichText(
                  text: TextSpan(
                    style: bodyStyle,
                    children: _buildPostTextSpans(
                      postText: widget.post.postText,
                      bodyStyle: bodyStyle,
                      linkStyle: linkStyle,
                    ),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
