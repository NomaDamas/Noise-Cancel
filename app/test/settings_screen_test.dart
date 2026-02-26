import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:noise_cancel_app/screens/settings_screen.dart';
import 'package:noise_cancel_app/services/api_service.dart';
import 'package:noise_cancel_app/services/second_brain_service.dart';

Future<void> _pumpSettingsScreen(WidgetTester tester) async {
  await tester.pumpWidget(
    MaterialApp(
      theme: ThemeData(
        brightness: Brightness.dark,
        scaffoldBackgroundColor: const Color(0xFF121212),
        cardColor: const Color(0xFF1E1E1E),
        useMaterial3: false,
      ),
      home: const SettingsScreen(),
    ),
  );
  await tester.pumpAndSettle();
}

void main() {
  setUp(() {
    FlutterSecureStorage.setMockInitialValues(<String, String>{});
  });

  testWidgets('loads existing values from secure storage on open',
      (tester) async {
    FlutterSecureStorage.setMockInitialValues(<String, String>{
      ApiService.serverUrlStorageKey: 'http://localhost:9000',
      SecondBrainService.enabledStorageKey: 'true',
      SecondBrainService.urlStorageKey: 'https://my-brain.example.com',
      SecondBrainService.apiKeyStorageKey: 'my-secret-key',
    });

    await _pumpSettingsScreen(tester);

    expect(find.text('Server URL'), findsOneWidget);
    expect(find.text('SecondBrain'), findsOneWidget);
    expect(find.text('http://localhost:9000'), findsOneWidget);
    expect(find.text('https://my-brain.example.com'), findsOneWidget);

    // API key is obscured, so verify the field exists by key
    expect(
      find.byKey(SettingsScreen.secondBrainApiKeyFieldKey),
      findsOneWidget,
    );

    final toggle = tester.widget<SwitchListTile>(
      find.byKey(SettingsScreen.secondBrainEnabledToggleKey),
    );
    expect(toggle.value, isTrue);
  });

  testWidgets('save persists server and SecondBrain settings to secure storage',
      (tester) async {
    await _pumpSettingsScreen(tester);

    await tester.enterText(
      find.byKey(SettingsScreen.serverUrlFieldKey),
      'http://configured:8012/',
    );
    await tester.tap(find.byKey(SettingsScreen.secondBrainEnabledToggleKey));
    await tester.pump();
    await tester.enterText(
      find.byKey(SettingsScreen.secondBrainUrlFieldKey),
      'https://brain.example.com',
    );
    await tester.enterText(
      find.byKey(SettingsScreen.secondBrainApiKeyFieldKey),
      'my-secret-key',
    );

    await tester.tap(find.byKey(SettingsScreen.saveButtonKey));
    await tester.pumpAndSettle();

    const storage = FlutterSecureStorage();
    expect(
      await storage.read(key: ApiService.serverUrlStorageKey),
      'http://configured:8012/',
    );
    expect(
      await storage.read(key: SecondBrainService.enabledStorageKey),
      'true',
    );
    expect(
      await storage.read(key: SecondBrainService.urlStorageKey),
      'https://brain.example.com',
    );
    expect(
      await storage.read(key: SecondBrainService.apiKeyStorageKey),
      'my-secret-key',
    );
  });

  testWidgets('uses dark styling consistent with the app', (tester) async {
    await _pumpSettingsScreen(tester);

    final scaffold = tester.widget<Scaffold>(find.byType(Scaffold));
    expect(scaffold.backgroundColor, const Color(0xFF121212));

    final cards = tester.widgetList<Card>(find.byType(Card));
    expect(cards, isNotEmpty);
    final allDarkCards =
        cards.every((card) => card.color == const Color(0xFF1E1E1E));
    expect(allDarkCards, isTrue);
  });
}
