import 'package:flutter/material.dart';

class PlatformBadgeStyle {
  const PlatformBadgeStyle({
    required this.label,
    required this.icon,
    required this.backgroundColor,
  });

  final String label;
  final IconData icon;
  final Color backgroundColor;
}

String platformDisplayName(String rawPlatform) {
  switch (rawPlatform.trim().toLowerCase()) {
    case 'linkedin':
      return 'LinkedIn';
    case 'x':
      return 'X';
    case 'threads':
      return 'Threads';
    case 'reddit':
      return 'Reddit';
    case 'rss':
      return 'RSS';
    default:
      return rawPlatform;
  }
}

PlatformBadgeStyle platformBadgeStyle(String rawPlatform) {
  switch (rawPlatform.trim().toLowerCase()) {
    case 'linkedin':
      return const PlatformBadgeStyle(
        label: 'LinkedIn',
        icon: Icons.business,
        backgroundColor: Color(0xFF0A66C2),
      );
    case 'x':
      return const PlatformBadgeStyle(
        label: 'X',
        icon: Icons.tag,
        backgroundColor: Color(0xFF000000),
      );
    case 'threads':
      return const PlatformBadgeStyle(
        label: 'Threads',
        icon: Icons.alternate_email,
        backgroundColor: Color(0xFF000000),
      );
    case 'reddit':
      return const PlatformBadgeStyle(
        label: 'Reddit',
        icon: Icons.forum,
        backgroundColor: Color(0xFFFF4500),
      );
    case 'rss':
      return const PlatformBadgeStyle(
        label: 'RSS',
        icon: Icons.rss_feed,
        backgroundColor: Color(0xFFFF8C00),
      );
    default:
      return PlatformBadgeStyle(
        label: rawPlatform,
        icon: Icons.language,
        backgroundColor: const Color(0xFF757575),
      );
  }
}
