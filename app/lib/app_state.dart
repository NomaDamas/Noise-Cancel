import 'package:flutter/foundation.dart';

class AppState extends ChangeNotifier {
  bool loading = false;

  void setLoading(bool value) {
    if (loading == value) {
      return;
    }
    loading = value;
    notifyListeners();
  }
}
