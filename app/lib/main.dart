import 'package:flutter/widgets.dart';

import 'app.dart';

export 'app.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const NoiseCancelAppRoot());
}
