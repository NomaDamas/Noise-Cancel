import 'dart:async';
import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter_card_swiper/flutter_card_swiper.dart';
import 'package:noise_cancel_app/models/post.dart';
import 'package:noise_cancel_app/screens/archive_screen.dart';
import 'package:noise_cancel_app/screens/settings_screen.dart';
import 'package:noise_cancel_app/services/api_service.dart';
import 'package:noise_cancel_app/services/second_brain_service.dart';
import 'package:noise_cancel_app/widgets/post_card.dart';

class SwipeScreen extends StatefulWidget {
  const SwipeScreen({
    super.key,
    this.apiService,
    this.secondBrainService,
    this.swiperController,
    this.settingsScreenBuilder,
    this.archiveScreenBuilder,
  });

  final ApiService? apiService;
  final SecondBrainService? secondBrainService;
  final CardSwiperController? swiperController;
  final WidgetBuilder? settingsScreenBuilder;
  final WidgetBuilder? archiveScreenBuilder;

  @override
  State<SwipeScreen> createState() => _SwipeScreenState();
}

class _SwipeScreenState extends State<SwipeScreen> {
  static const int _pageSize = 20;
  static const int _prefetchThreshold = 5;

  late final ApiService _apiService;
  late final SecondBrainService _secondBrainService;
  late final CardSwiperController _swiperController;
  late final WidgetBuilder _settingsScreenBuilder;
  late final WidgetBuilder _archiveScreenBuilder;
  late final bool _ownsController;

  final List<Post> _posts = <Post>[];
  int _offset = 0;
  int _archivedCount = 0;
  int? _currentIndex;
  bool _isLoading = false;
  bool _hasMore = true;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _apiService = widget.apiService ?? ApiService();
    _secondBrainService = widget.secondBrainService ?? SecondBrainService();
    _ownsController = widget.swiperController == null;
    _swiperController = widget.swiperController ?? CardSwiperController();
    _settingsScreenBuilder =
        widget.settingsScreenBuilder ?? (_) => const SettingsScreen();
    _archiveScreenBuilder =
        widget.archiveScreenBuilder ?? (_) => const ArchiveScreen();
    unawaited(_fetchNextBatch());
    unawaited(_refreshArchiveCount());
  }

  @override
  void dispose() {
    if (_ownsController) {
      unawaited(_swiperController.dispose());
    }
    super.dispose();
  }

  Future<void> _fetchNextBatch() async {
    if (_isLoading || !_hasMore) {
      return;
    }

    setState(() {
      _isLoading = true;
    });

    try {
      final batch = await _apiService.fetchPosts(
        limit: _pageSize,
        offset: _offset,
      );
      if (!mounted) {
        return;
      }

      setState(() {
        _posts.addAll(batch);
        _offset += batch.length;
        _hasMore = batch.isNotEmpty;
        if (_posts.isNotEmpty && _currentIndex == null) {
          _currentIndex = 0;
        }
        _errorMessage = null;
      });
    } catch (_) {
      if (!mounted) {
        return;
      }
      setState(() {
        _hasMore = false;
        _errorMessage = 'Could not load posts.';
      });
    } finally {
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
      }
    }
  }

  Future<void> _onRefresh() async {
    setState(() {
      _posts.clear();
      _offset = 0;
      _currentIndex = null;
      _hasMore = true;
      _errorMessage = null;
      _isLoading = false;
    });
    await _fetchNextBatch();
    await _refreshArchiveCount();
  }

  Future<bool> _onSwipe(
    int previousIndex,
    int? currentIndex,
    CardSwiperDirection direction,
  ) async {
    if (previousIndex < 0 || previousIndex >= _posts.length) {
      return false;
    }

    final post = _posts[previousIndex];

    try {
      if (direction == CardSwiperDirection.left) {
        final archivedPostData =
            await _apiService.archivePost(post.classificationId);
        unawaited(_secondBrainService.forward(archivedPostData));
      } else if (direction == CardSwiperDirection.right) {
        await _apiService.deletePost(post.classificationId);
      } else {
        return false;
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          _errorMessage = 'Action failed. Try again.';
        });
      }
      return false;
    }

    if (!mounted) {
      return true;
    }

    setState(() {
      _currentIndex = currentIndex;
      _errorMessage = null;
    });

    if (direction == CardSwiperDirection.left) {
      unawaited(_refreshArchiveCount());
    }

    final remainingCards = _remainingCards(currentIndex);
    if (remainingCards < _prefetchThreshold) {
      unawaited(_fetchNextBatch());
    }

    return true;
  }

  int _remainingCards(int? currentIndex) {
    if (currentIndex == null || _posts.isEmpty) {
      return 0;
    }
    return _posts.length - currentIndex;
  }

  void _setPostNoteAtIndex(int index, String? note) {
    if (index < 0 || index >= _posts.length) {
      return;
    }
    final current = _posts[index];
    _posts[index] = Post(
      id: current.id,
      classificationId: current.classificationId,
      platform: current.platform,
      authorName: current.authorName,
      authorUrl: current.authorUrl,
      postUrl: current.postUrl,
      postText: current.postText,
      summary: current.summary,
      category: current.category,
      confidence: current.confidence,
      reasoning: current.reasoning,
      classifiedAt: current.classifiedAt,
      swipeStatus: current.swipeStatus,
      note: note,
    );
  }

  Future<void> _openNoteEditor(int index) async {
    if (index < 0 || index >= _posts.length) {
      return;
    }

    final post = _posts[index];
    final controller = TextEditingController(text: post.note ?? '');

    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: const Color(0xFF1E1E1E),
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (sheetContext) {
        final bottomInset = MediaQuery.of(sheetContext).viewInsets.bottom;
        return Padding(
          padding: EdgeInsets.fromLTRB(16, 16, 16, bottomInset + 16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '메모 추가',
                style: Theme.of(sheetContext).textTheme.titleMedium,
              ),
              const SizedBox(height: 10),
              TextField(
                key: const Key('note-input-field'),
                controller: controller,
                maxLines: 4,
                minLines: 3,
                decoration: const InputDecoration(
                  hintText: '이 게시물에 남길 메모를 입력하세요',
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 12),
              SizedBox(
                width: double.infinity,
                child: FilledButton(
                  key: const Key('note-save-button'),
                  onPressed: () async {
                    final noteText = controller.text.trim();
                    if (noteText.isEmpty) {
                      if (!mounted) {
                        return;
                      }
                      setState(() {
                        _errorMessage = '메모를 입력해 주세요.';
                      });
                      return;
                    }

                    try {
                      final savedNote =
                          await _apiService.saveNote(post.classificationId, noteText);
                      if (!mounted) {
                        return;
                      }
                      setState(() {
                        _setPostNoteAtIndex(index, savedNote ?? noteText);
                        _errorMessage = null;
                      });
                      if (!sheetContext.mounted) {
                        return;
                      }
                      if (Navigator.of(sheetContext).canPop()) {
                        Navigator.of(sheetContext).pop();
                      }
                    } catch (_) {
                      if (!mounted) {
                        return;
                      }
                      setState(() {
                        _errorMessage = '메모를 저장하지 못했습니다.';
                      });
                    }
                  },
                  child: const Text('Save'),
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  void _openSettings() {
    Navigator.of(context).push(
      MaterialPageRoute<void>(builder: _settingsScreenBuilder),
    );
  }

  Future<void> _openArchive() async {
    await Navigator.of(context).push(
      MaterialPageRoute<void>(builder: _archiveScreenBuilder),
    );
    if (!mounted) {
      return;
    }
    await _refreshArchiveCount();
  }

  Future<void> _refreshArchiveCount() async {
    try {
      final page = await _apiService.fetchPostPage(
        limit: 1,
        offset: 0,
        swipeStatus: 'archived',
      );
      if (!mounted) {
        return;
      }
      setState(() {
        _archivedCount = page.total;
      });
    } catch (_) {
      if (!mounted) {
        return;
      }
      setState(() {
        _archivedCount = 0;
      });
    }
  }

  Widget _buildArchiveIcon() {
    final countLabel = _archivedCount > 99 ? '99+' : '$_archivedCount';
    return Stack(
      clipBehavior: Clip.none,
      children: [
        const Icon(Icons.archive_outlined),
        if (_archivedCount > 0)
          Positioned(
            right: -8,
            top: -8,
            child: Container(
              key: const Key('archive-count-badge'),
              padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
              decoration: BoxDecoration(
                color: Colors.redAccent,
                borderRadius: BorderRadius.circular(999),
              ),
              child: Text(
                countLabel,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 10,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
          ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final remainingCards = _remainingCards(_currentIndex);
    final showEmptyState = remainingCards == 0 && !_isLoading && !_hasMore;
    final showLoadingState = remainingCards == 0 && _isLoading;

    return Scaffold(
      appBar: AppBar(
        title: const Text('NoiseCancel'),
        leading: IconButton(
          key: const Key('open-archive-button'),
          onPressed: _openArchive,
          icon: _buildArchiveIcon(),
          tooltip: '저장고',
        ),
        actions: [
          IconButton(
            onPressed: _openSettings,
            icon: const Icon(Icons.settings),
            tooltip: 'Settings',
          ),
        ],
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          child: Column(
            children: [
              if (_errorMessage != null)
                Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: Text(
                    _errorMessage!,
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                          color: Colors.redAccent,
                        ),
                  ),
                ),
              Expanded(
                child: RefreshIndicator(
                  onRefresh: _onRefresh,
                  child: LayoutBuilder(
                    builder: (context, constraints) {
                      return SingleChildScrollView(
                        physics: const AlwaysScrollableScrollPhysics(),
                        child: SizedBox(
                          height: constraints.maxHeight,
                          width: constraints.maxWidth,
                          child: Builder(
                            builder: (context) {
                              if (showLoadingState) {
                                return const Center(
                                    child: CircularProgressIndicator());
                              }

                              if (showEmptyState) {
                                return const Center(
                                  child: Text(
                                    'All caught up!',
                                    style: TextStyle(
                                        fontSize: 18,
                                        fontWeight: FontWeight.w600),
                                  ),
                                );
                              }

                              if (_posts.isEmpty) {
                                return const SizedBox.shrink();
                              }

                              return CardSwiper(
                                controller: _swiperController,
                                cardsCount: _posts.length,
                                numberOfCardsDisplayed: min(3, _posts.length),
                                isLoop: false,
                                allowedSwipeDirection:
                                    const AllowedSwipeDirection.only(
                                  left: true,
                                  right: true,
                                ),
                                onSwipe: _onSwipe,
                                cardBuilder: (
                                  context,
                                  index,
                                  horizontalThresholdPercentage,
                                  verticalThresholdPercentage,
                                ) {
                                  return PostCard(
                                    post: _posts[index],
                                    horizontalOffsetPercentage:
                                        horizontalThresholdPercentage,
                                    onLongPress: () => _openNoteEditor(index),
                                  );
                                },
                              );
                            },
                          ),
                        ),
                      );
                    },
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
