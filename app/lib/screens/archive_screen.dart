import 'dart:async';

import 'package:flutter/material.dart';

import '../models/post.dart';
import '../services/api_service.dart';
import '../widgets/expanded_content.dart';

class _PlatformFilter {
  const _PlatformFilter({
    required this.label,
    required this.value,
  });

  final String label;
  final String? value;
}

class _PlatformBadgeStyle {
  const _PlatformBadgeStyle({
    required this.label,
    required this.icon,
    required this.backgroundColor,
  });

  final String label;
  final IconData icon;
  final Color backgroundColor;
}

class ArchiveScreen extends StatefulWidget {
  const ArchiveScreen({
    super.key,
    this.apiService,
  });

  final ApiService? apiService;

  @override
  State<ArchiveScreen> createState() => _ArchiveScreenState();
}

class _ArchiveScreenState extends State<ArchiveScreen> {
  static const int _pageSize = 20;
  static const Duration _debounceDuration = Duration(milliseconds: 300);
  static const List<_PlatformFilter> _platformFilters = <_PlatformFilter>[
    _PlatformFilter(label: 'All', value: null),
    _PlatformFilter(label: 'LinkedIn', value: 'linkedin'),
    _PlatformFilter(label: 'X', value: 'x'),
    _PlatformFilter(label: 'Threads', value: 'threads'),
    _PlatformFilter(label: 'Reddit', value: 'reddit'),
    _PlatformFilter(label: 'RSS', value: 'rss'),
  ];

  late final ApiService _apiService;
  final TextEditingController _searchController = TextEditingController();
  final ScrollController _scrollController = ScrollController();

  final List<Post> _posts = <Post>[];
  Timer? _searchDebounce;
  int _offset = 0;
  bool _isLoadingInitial = false;
  bool _isLoadingMore = false;
  bool _hasMore = true;
  String? _errorMessage;
  String? _selectedPlatform;
  String _query = '';
  String? _expandedClassificationId;

  @override
  void initState() {
    super.initState();
    _apiService = widget.apiService ?? ApiService();
    _scrollController.addListener(_onScroll);
    unawaited(_reloadPosts());
  }

  @override
  void dispose() {
    _searchDebounce?.cancel();
    _searchController.dispose();
    _scrollController
      ..removeListener(_onScroll)
      ..dispose();
    super.dispose();
  }

  static _PlatformBadgeStyle _platformBadgeStyle(String rawPlatform) {
    switch (rawPlatform.trim().toLowerCase()) {
      case 'linkedin':
        return const _PlatformBadgeStyle(
          label: 'LinkedIn',
          icon: Icons.business,
          backgroundColor: Color(0xFF0A66C2),
        );
      case 'x':
        return const _PlatformBadgeStyle(
          label: 'X',
          icon: Icons.close,
          backgroundColor: Color(0xFF000000),
        );
      case 'threads':
        return const _PlatformBadgeStyle(
          label: 'Threads',
          icon: Icons.alternate_email,
          backgroundColor: Color(0xFF000000),
        );
      case 'reddit':
        return const _PlatformBadgeStyle(
          label: 'Reddit',
          icon: Icons.forum,
          backgroundColor: Color(0xFFFF4500),
        );
      case 'rss':
        return const _PlatformBadgeStyle(
          label: 'RSS',
          icon: Icons.rss_feed,
          backgroundColor: Color(0xFFF26522),
        );
      default:
        return const _PlatformBadgeStyle(
          label: 'Unknown',
          icon: Icons.public,
          backgroundColor: Color(0xFF757575),
        );
    }
  }

  void _onScroll() {
    if (!_scrollController.hasClients ||
        _isLoadingInitial ||
        _isLoadingMore ||
        !_hasMore) {
      return;
    }

    final position = _scrollController.position;
    if (position.pixels < position.maxScrollExtent - 200) {
      return;
    }

    unawaited(_fetchPage(isPagination: true));
  }

  Future<void> _reloadPosts() async {
    setState(() {
      _posts.clear();
      _offset = 0;
      _hasMore = true;
      _errorMessage = null;
      _expandedClassificationId = null;
    });
    await _fetchPage();
  }

  Future<void> _fetchPage({bool isPagination = false}) async {
    if ((isPagination && (_isLoadingInitial || _isLoadingMore || !_hasMore)) ||
        (!isPagination && _isLoadingInitial)) {
      return;
    }

    setState(() {
      if (isPagination) {
        _isLoadingMore = true;
      } else {
        _isLoadingInitial = true;
      }
    });

    try {
      final page = await _apiService.fetchPostPage(
        limit: _pageSize,
        offset: _offset,
        swipeStatus: 'archived',
        platform: _selectedPlatform,
        query: _query.isEmpty ? null : _query,
      );
      if (!mounted) {
        return;
      }

      setState(() {
        _posts.addAll(page.posts);
        _offset += page.posts.length;
        _hasMore = page.hasMore && page.posts.isNotEmpty;
        _errorMessage = null;
      });
    } catch (_) {
      if (!mounted) {
        return;
      }
      setState(() {
        _errorMessage = '저장고를 불러오지 못했습니다.';
        _hasMore = false;
      });
    } finally {
      if (mounted) {
        setState(() {
          _isLoadingInitial = false;
          _isLoadingMore = false;
        });
      }
    }
  }

  void _onSearchChanged(String value) {
    _searchDebounce?.cancel();
    _searchDebounce = Timer(_debounceDuration, () {
      final normalized = value.trim();
      if (normalized == _query) {
        return;
      }
      _query = normalized;
      unawaited(_reloadPosts());
    });
  }

  void _onSearchSubmitted(String value) {
    _searchDebounce?.cancel();
    final normalized = value.trim();
    if (normalized == _query) {
      return;
    }
    _query = normalized;
    unawaited(_reloadPosts());
  }

  void _onPlatformSelected(String? platform) {
    if (_selectedPlatform == platform) {
      return;
    }
    setState(() {
      _selectedPlatform = platform;
    });
    unawaited(_reloadPosts());
  }

  void _toggleExpanded(String classificationId) {
    setState(() {
      _expandedClassificationId = _expandedClassificationId == classificationId
          ? null
          : classificationId;
    });
  }

  String _formatDate(String raw) {
    final parsed = DateTime.tryParse(raw);
    if (parsed == null) {
      return raw;
    }
    final local = parsed.toLocal();
    final month = local.month.toString().padLeft(2, '0');
    final day = local.day.toString().padLeft(2, '0');
    return '${local.year}-$month-$day';
  }

  Widget _buildPlatformChips() {
    return SizedBox(
      height: 40,
      child: ListView.separated(
        key: const Key('archive-chip-list'),
        scrollDirection: Axis.horizontal,
        itemCount: _platformFilters.length,
        separatorBuilder: (context, index) => const SizedBox(width: 8),
        itemBuilder: (context, index) {
          final filter = _platformFilters[index];
          final key = filter.value == null
              ? const Key('archive-filter-all')
              : Key('archive-filter-${filter.value}');
          return ChoiceChip(
            key: key,
            label: Text(filter.label),
            selected: _selectedPlatform == filter.value,
            onSelected: (_) => _onPlatformSelected(filter.value),
          );
        },
      ),
    );
  }

  Widget _buildPostItem(BuildContext context, Post post) {
    final badge = _platformBadgeStyle(post.platform);
    final isExpanded = _expandedClassificationId == post.classificationId;

    return InkWell(
      key: Key('archive-item-${post.classificationId}'),
      onTap: () => _toggleExpanded(post.classificationId),
      borderRadius: BorderRadius.circular(12),
      child: Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: const Color(0xFF1E1E1E),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: Colors.white12),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  key: Key('archive-platform-badge-${post.classificationId}'),
                  padding:
                      const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: badge.backgroundColor,
                    borderRadius: BorderRadius.circular(999),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(
                        badge.icon,
                        size: 12,
                        color: Colors.white,
                      ),
                      const SizedBox(width: 4),
                      Text(
                        badge.label,
                        style: Theme.of(context).textTheme.labelSmall?.copyWith(
                              color: Colors.white,
                              fontWeight: FontWeight.w700,
                            ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    post.authorName,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: Theme.of(context).textTheme.titleSmall?.copyWith(
                          fontWeight: FontWeight.w700,
                        ),
                  ),
                ),
                const SizedBox(width: 8),
                Text(
                  _formatDate(post.classifiedAt),
                  style: Theme.of(context).textTheme.labelSmall?.copyWith(
                        color: Colors.white70,
                      ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              post.postText,
              maxLines: isExpanded ? null : 2,
              overflow:
                  isExpanded ? TextOverflow.visible : TextOverflow.ellipsis,
              style: Theme.of(context).textTheme.bodySmall,
            ),
            if (isExpanded) ...[
              const SizedBox(height: 10),
              const Divider(height: 1, color: Colors.white12),
              const SizedBox(height: 10),
              SizedBox(
                height: 320,
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(12),
                  child: ExpandedContent(post: post),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildBody() {
    if (_isLoadingInitial && _posts.isEmpty) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_errorMessage != null && _posts.isEmpty) {
      return Center(child: Text(_errorMessage!));
    }

    if (_posts.isEmpty) {
      return const Center(child: Text('저장된 게시물이 없습니다.'));
    }

    return RefreshIndicator(
      onRefresh: _reloadPosts,
      child: ListView.separated(
        key: const Key('archive-post-list'),
        controller: _scrollController,
        padding: const EdgeInsets.only(bottom: 20),
        itemCount: _posts.length + (_isLoadingMore ? 1 : 0),
        separatorBuilder: (context, index) => const SizedBox(height: 8),
        itemBuilder: (context, index) {
          if (index >= _posts.length) {
            return const Padding(
              padding: EdgeInsets.symmetric(vertical: 12),
              child: Center(child: CircularProgressIndicator()),
            );
          }
          return _buildPostItem(context, _posts[index]);
        },
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('저장고'),
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(12, 10, 12, 0),
          child: Column(
            children: [
              TextField(
                key: const Key('archive-search-field'),
                controller: _searchController,
                textInputAction: TextInputAction.search,
                onChanged: _onSearchChanged,
                onSubmitted: _onSearchSubmitted,
                decoration: const InputDecoration(
                  hintText: '키워드로 검색',
                  prefixIcon: Icon(Icons.search),
                  border: OutlineInputBorder(),
                  isDense: true,
                ),
              ),
              const SizedBox(height: 10),
              _buildPlatformChips(),
              const SizedBox(height: 10),
              Expanded(child: _buildBody()),
            ],
          ),
        ),
      ),
    );
  }
}
