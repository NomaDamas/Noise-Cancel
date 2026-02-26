import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:noise_cancel_app/main.dart';

void main() {
  testWidgets('boots dark themed app from main.dart', (WidgetTester tester) async {
    await tester.pumpWidget(
      const NoiseCancelAppRoot(
        home: Scaffold(body: Text('Theme host')),
      ),
    );

    expect(find.text('Theme host'), findsOneWidget);

    final MaterialApp app = tester.widget<MaterialApp>(find.byType(MaterialApp));
    final ThemeData theme = app.theme!;
    expect(theme.brightness, Brightness.dark);
    expect(theme.scaffoldBackgroundColor, const Color(0xFF121212));
    expect(theme.cardColor, const Color(0xFF1E1E1E));
    expect(theme.colorScheme.primary, isNot(const Color(0xFF121212)));
  });
}
