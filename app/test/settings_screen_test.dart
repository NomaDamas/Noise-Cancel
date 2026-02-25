import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:noise_cancel_app/screens/settings_screen.dart';
import 'package:noise_cancel_app/services/api_service.dart';
import 'package:noise_cancel_app/services/webhook_service.dart';

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
      WebhookService.webhookEnabledStorageKey: 'true',
      WebhookService.webhookUrlStorageKey: 'https://hooks.example.com/path',
      WebhookService.webhookTemplateStorageKey:
          '{"author":"{{author_name}}","summary":"{{summary}}"}',
    });

    await _pumpSettingsScreen(tester);

    expect(find.text('Server URL'), findsOneWidget);
    expect(find.text('Webhook Configuration'), findsOneWidget);
    expect(find.text('http://localhost:9000'), findsOneWidget);
    expect(find.text('https://hooks.example.com/path'), findsOneWidget);
    expect(
      find.text('{"author":"{{author_name}}","summary":"{{summary}}"}'),
      findsOneWidget,
    );

    final webhookToggle = tester.widget<SwitchListTile>(
      find.byKey(SettingsScreen.webhookEnabledToggleKey),
    );
    expect(webhookToggle.value, isTrue);
  });

  testWidgets('save persists server and webhook settings to secure storage',
      (tester) async {
    await _pumpSettingsScreen(tester);

    await tester.enterText(
      find.byKey(SettingsScreen.serverUrlFieldKey),
      'http://configured:8000/',
    );
    await tester.tap(find.byKey(SettingsScreen.webhookEnabledToggleKey));
    await tester.pump();
    await tester.enterText(
      find.byKey(SettingsScreen.webhookUrlFieldKey),
      'https://hooks.example.com/custom',
    );
    await tester.enterText(
      find.byKey(SettingsScreen.webhookTemplateFieldKey),
      '{"headline":"{{summary}}"}',
    );

    await tester.tap(find.byKey(SettingsScreen.saveButtonKey));
    await tester.pumpAndSettle();

    const storage = FlutterSecureStorage();
    expect(
      await storage.read(key: ApiService.serverUrlStorageKey),
      'http://configured:8000/',
    );
    expect(
      await storage.read(key: WebhookService.webhookEnabledStorageKey),
      'true',
    );
    expect(
      await storage.read(key: WebhookService.webhookUrlStorageKey),
      'https://hooks.example.com/custom',
    );
    expect(
      await storage.read(key: WebhookService.webhookTemplateStorageKey),
      '{"headline":"{{summary}}"}',
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
