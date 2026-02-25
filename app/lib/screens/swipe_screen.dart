import 'dart:async';
import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter_card_swiper/flutter_card_swiper.dart';
import 'package:noise_cancel_app/models/post.dart';
import 'package:noise_cancel_app/screens/settings_screen.dart';
import 'package:noise_cancel_app/services/api_service.dart';
import 'package:noise_cancel_app/services/webhook_service.dart';
import 'package:noise_cancel_app/widgets/post_card.dart';

class SwipeScreen extends StatefulWidget {
  const SwipeScreen({
    super.key,
    this.apiService,
    this.webhookService,
    this.swiperController,
    this.settingsScreenBuilder,
  });

  final ApiService? apiService;
  final WebhookService? webhookService;
  final CardSwiperController? swiperController;
  final WidgetBuilder? settingsScreenBuilder;

  @override
  State<SwipeScreen> createState() => _SwipeScreenState();
}

class _SwipeScreenState extends State<SwipeScreen> {
  static const int _pageSize = 20;
  static const int _prefetchThreshold = 5;

  late final ApiService _apiService;
  late final WebhookService _webhookService;
  late final CardSwiperController _swiperController;
  late final WidgetBuilder _settingsScreenBuilder;
  late final bool _ownsController;

  final List<Post> _posts = <Post>[];
  int _offset = 0;
  int? _currentIndex;
  bool _isLoading = false;
  bool _hasMore = true;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _apiService = widget.apiService ?? ApiService();
    _webhookService = widget.webhookService ?? WebhookService();
    _ownsController = widget.swiperController == null;
    _swiperController = widget.swiperController ?? CardSwiperController();
    _settingsScreenBuilder = widget.settingsScreenBuilder ?? (_) => const SettingsScreen();
    unawaited(_fetchNextBatch());
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
        final archivedPostData = await _apiService.archivePost(post.classificationId);
        final enabled = await _webhookService.isEnabled();
        if (enabled) {
          unawaited(_webhookService.forward(archivedPostData));
        }
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

  void _openSettings() {
    Navigator.of(context).push(
      MaterialPageRoute<void>(builder: _settingsScreenBuilder),
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
                child: Builder(
                  builder: (context) {
                    if (showLoadingState) {
                      return const Center(child: CircularProgressIndicator());
                    }

                    if (showEmptyState) {
                      return const Center(
                        child: Text(
                          'All caught up!',
                          style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
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
                      allowedSwipeDirection: const AllowedSwipeDirection.only(
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
                        return PostCard(post: _posts[index]);
                      },
                    );
                  },
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
